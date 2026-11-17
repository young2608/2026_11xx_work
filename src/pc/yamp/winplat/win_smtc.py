"""Windows 시스템 미디어 전송 컨트롤 (SMTC) — 볼륨 팝업 / 잠금 화면 / 작업 표시줄 미디어 위젯 (vr0.1.0.009)

*** best-effort ***
  MSYS2 mingw Python 에는 MSVC 용 winrt-* 휠이 설치되지 않는 경우가 대부분 → 그때는 available=False, 모든 메서드 no-op.
  pyWinRT 패키지가 있으면 사용:
    winrt-runtime  winrt-Windows.Media  winrt-Windows.Media.Playback
    winrt-Windows.Foundation  winrt-Windows.Storage.Streams   (앨범아트용, 없으면 아트만 생략)
  winrt 경로는 이 저장소 CI(Linux) 에서 시험 불가 — 모든 호출을 try 로 감싸고 실패 시 기능을 끔.

구조
  MediaPlayer 하나 생성 → CommandManager 끔 (자동 처리 X) → SystemMediaTransportControls 직접 제어
  버튼 이벤트는 WinRT 스레드에서 옴 → 내부 시그널(QueuedConnection) 로 Qt 스레드에 넘긴 뒤 command(str) 발생
    "toggle"(재생/일시정지) "next" "prev" "stop"
"""
import logging
import os
import sys
import tempfile
import time

from PyQt6.QtCore import QObject, Qt, pyqtSignal

log = logging.getLogger("yamp.win")
_logged_missing = False


def _load_winrt():
    """(media 모듈, playback 모듈) 또는 None"""
    if sys.platform != "win32":
        return None
    try:
        import winrt.windows.media as media               # noqa: F401
        import winrt.windows.media.playback as playback
        return media, playback
    except Exception:                                      # noqa: BLE001 — ImportError 외 DLL 오류 등도 포함
        return None


class Smtc(QObject):
    command = pyqtSignal(str)
    _raw = pyqtSignal(str)                                 # WinRT 스레드 → Qt 스레드 전달용

    def __init__(self, parent=None):
        super().__init__(parent)
        global _logged_missing
        self.available = False
        self._smtc = None
        self._player = None
        self._token = None
        self._media = None
        self._tl_last = 0.0
        self._tl_dur = -1
        self._cover_path = None
        self._raw.connect(self.command.emit, Qt.ConnectionType.QueuedConnection)
        mods = _load_winrt()
        if mods is None:
            if not _logged_missing:
                _logged_missing = True
                log.info("SMTC 미사용 (winrt 패키지 없음)")
            return
        try:
            self._media, playback = mods
            m = self._media
            self._player = playback.MediaPlayer()
            self._player.command_manager.is_enabled = False
            s = self._player.system_media_transport_controls
            s.is_enabled = True
            s.is_play_enabled = True
            s.is_pause_enabled = True
            s.is_next_enabled = True
            s.is_previous_enabled = True
            s.is_stop_enabled = True
            s.playback_status = m.MediaPlaybackStatus.STOPPED
            B = m.SystemMediaTransportControlsButton
            self._map = {int(B.PLAY): "toggle", int(B.PAUSE): "toggle", int(B.NEXT): "next",
                         int(B.PREVIOUS): "prev", int(B.STOP): "stop"}
            self._token = s.add_button_pressed(self._on_button)
            self._smtc = s
            self.available = True
        except Exception as e:                             # noqa: BLE001
            log.warning("SMTC 초기화 실패 — 사용 안 함: %s", e)
            self._disable()

    # ------------------------------------------------------------ 내부
    def _on_button(self, sender, args):
        # WinRT 스레드에서 호출됨 — 여기서는 시그널만
        try:
            act = self._map.get(int(args.button))
            if act:
                self._raw.emit(act)
        except Exception:                                  # noqa: BLE001
            pass

    def _disable(self):
        self.available = False
        try:
            if self._smtc is not None and self._token is not None:
                self._smtc.remove_button_pressed(self._token)
        except Exception:                                  # noqa: BLE001
            pass
        try:
            if self._player is not None:
                self._player.close()
        except Exception:                                  # noqa: BLE001
            pass
        self._smtc = self._player = self._token = None

    def _guard(self, what: str, fn):
        if not self.available:
            return
        try:
            fn()
        except Exception as e:                             # noqa: BLE001
            log.warning("SMTC %s 실패 — 사용 중지: %s", what, e)
            self._disable()

    def _cover_ref(self, cover_bytes):
        """앨범아트 → 임시 파일 → RandomAccessStreamReference (실패하면 None, 아트만 생략)"""
        if not cover_bytes:
            return None
        try:
            from winrt.windows.foundation import Uri
            from winrt.windows.storage.streams import RandomAccessStreamReference
            if self._cover_path is None:
                self._cover_path = os.path.join(tempfile.gettempdir(), "yamp_smtc_cover_%d.img" % os.getpid())
            with open(self._cover_path, "wb") as f:
                f.write(cover_bytes)
            uri = Uri("file:///" + self._cover_path.replace("\\", "/"))
            return RandomAccessStreamReference.create_from_uri(uri)
        except Exception as e:                             # noqa: BLE001
            log.debug("SMTC 앨범아트 생략: %s", e)
            return None

    # ------------------------------------------------------------ 공개 API
    def set_metadata(self, title: str, artist: str, album: str, cover_bytes=None):
        def run():
            du = self._smtc.display_updater
            du.clear_all()
            du.type = self._media.MediaPlaybackType.MUSIC
            mp = du.music_properties
            mp.title = title or ""
            mp.artist = artist or ""
            mp.album_title = album or ""
            ref = self._cover_ref(cover_bytes)
            if ref is not None:
                du.thumbnail = ref
            du.update()
            self._tl_dur = -1                              # 곡이 바뀌면 다음 타임라인은 바로 반영
        self._guard("메타데이터", run)

    def set_state(self, state: str):
        def run():
            S = self._media.MediaPlaybackStatus
            self._smtc.playback_status = {"playing": S.PLAYING, "paused": S.PAUSED}.get(state, S.STOPPED)
        self._guard("상태", run)

    def set_timeline(self, pos_ms: int, dur_ms: int):
        if not self.available:
            return
        now = time.monotonic()
        dur = max(0, int(dur_ms or 0))
        if dur == self._tl_dur and now - self._tl_last < 1.0:   # 1초에 한 번 (길이가 바뀌면 즉시)
            return
        self._tl_last, self._tl_dur = now, dur

        def run():
            from datetime import timedelta
            tl = self._media.SystemMediaTransportControlsTimelineProperties()
            pos = max(0, min(int(pos_ms or 0), dur)) if dur else 0
            tl.start_time = timedelta(0)
            tl.min_seek_time = timedelta(0)
            tl.end_time = timedelta(milliseconds=dur)
            tl.max_seek_time = timedelta(milliseconds=dur)
            tl.position = timedelta(milliseconds=pos)
            self._smtc.update_timeline_properties(tl)
        self._guard("타임라인", run)

    def close(self):
        self._disable()
        if self._cover_path:
            try:
                os.remove(self._cover_path)
            except OSError:
                pass
            self._cover_path = None
