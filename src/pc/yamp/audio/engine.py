"""재생 엔진: QMediaPlayer + QAudioOutput (Qt FFmpeg 백엔드).

나중에 libmpv 백엔드(EQ)로 바꿀 수 있도록 UI/컨트롤러는 이 클래스의 시그널·메서드만 사용.
"""
import logging

from PyQt6.QtCore import QObject, QUrl, pyqtSignal
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer

try:
    from PyQt6.QtMultimedia import QAudioBufferOutput   # Qt 6.8+
except ImportError:  # pragma: no cover
    QAudioBufferOutput = None

log = logging.getLogger("yamp.engine")


class AudioEngine(QObject):
    positionChanged = pyqtSignal(int)     # ms
    durationChanged = pyqtSignal(int)     # ms
    stateChanged = pyqtSignal(str)        # playing | paused | stopped
    ended = pyqtSignal()
    error = pyqtSignal(str)
    bufferReady = pyqtSignal(object)      # QAudioBuffer (스펙트럼용)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.player = QMediaPlayer(self)
        self.out = QAudioOutput(self)
        self.player.setAudioOutput(self.out)
        self.buf_out = None
        self._buf_on = True
        if QAudioBufferOutput is not None:
            try:
                self.buf_out = QAudioBufferOutput(self)
                self.player.setAudioBufferOutput(self.buf_out)
                self.buf_out.audioBufferReceived.connect(self._on_buffer)
            except Exception as e:  # pragma: no cover
                log.info("buffer output unavailable: %s", e)
                self.buf_out = None
        self.player.positionChanged.connect(lambda p: self.positionChanged.emit(int(p)))
        self.player.durationChanged.connect(lambda d: self.durationChanged.emit(int(d)))
        self.player.playbackStateChanged.connect(self._on_state)
        self.player.mediaStatusChanged.connect(self._on_status)
        self.player.errorOccurred.connect(self._on_error)
        self._volume = 70
        self._muted = False
        self._pending_seek = -1
        self._gain = 1.0          # ReplayGain 배율
        self._fade = 1.0          # 전환 페이드 · 슬립 타이머 배율

    name = "qt"
    supports_eq = False
    supports_pitch = False
    supports_spectrum = True
    supports_skip_silence = False

    # ---- 명령 ----
    def load(self, path: str, autoplay: bool = True, start_ms: int = 0):
        self._pending_seek = start_ms if start_ms > 0 else -1
        self.player.setSource(QUrl.fromLocalFile(path))
        if autoplay:
            self.player.play()

    def play(self):
        self.player.play()

    def pause(self):
        self.player.pause()

    def toggle(self):
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def stop(self):
        self.player.stop()

    def seek(self, ms: int):
        self.player.setPosition(max(0, int(ms)))

    def position(self) -> int:
        return int(self.player.position())

    def duration(self) -> int:
        return int(self.player.duration())

    def is_playing(self) -> bool:
        return self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState

    def set_volume(self, v: int):
        self._volume = max(0, min(100, int(v)))
        self._apply_volume()

    def effective_volume(self) -> float:
        """지각 볼륨(3제곱) × ReplayGain × 페이드, 0..1"""
        if self._muted:
            return 0.0
        return max(0.0, min(1.0, (self._volume / 100.0) ** 3 * self._gain * self._fade))

    def _apply_volume(self):
        self.out.setVolume(self.effective_volume())

    def set_gain(self, factor: float):
        self._gain = max(0.0, float(factor))
        self._apply_volume()

    def set_fade(self, f: float):
        f = max(0.0, min(1.0, float(f)))
        if abs(f - self._fade) > 0.001:
            self._fade = f
            self._apply_volume()

    def set_rate(self, rate: float):
        """재생 속도 (Qt 는 음정도 같이 바뀔 수 있음 — 백엔드에 따라 다름)"""
        self.player.setPlaybackRate(max(0.25, min(4.0, float(rate))))

    def set_pitch(self, semitones: int):
        pass                      # Qt 백엔드 미지원 (mpv 백엔드 사용)

    def set_eq(self, enabled: bool, bands):
        pass                      # Qt 백엔드 미지원 (mpv 백엔드 사용)

    def set_spectrum(self, on: bool):
        """스펙트럼이 필요 없을 때(꺼짐·창 숨김) 버퍼 시그널을 끊음 — vr0.1.0.008
        이어져 있으면 재생 내내 오디오 블록마다 QAudioBuffer 를 파이썬으로 넘김 (변환·할당·시그널).
        (setAudioBufferOutput(None) 으로 떼면 PyQt 소유권 문제로 종료 시 메모리 오류 → 시그널만 끊음)"""
        if self.buf_out is None:
            return
        on = bool(on)
        if on == self._buf_on:
            return
        self._buf_on = on
        if on:
            self.buf_out.audioBufferReceived.connect(self._on_buffer)
        else:
            self.buf_out.audioBufferReceived.disconnect(self._on_buffer)

    def _on_buffer(self, b):
        self.bufferReady.emit(b)       # 시그널→시그널 직접 연결은 타입 불일치로 실패

    def set_skip_silence(self, on: bool):
        pass                      # Qt 백엔드 미지원 (vr0.1.0.010 무음 건너뛰기는 mpv 백엔드)

    def set_sound(self, settings):
        pass                      # Qt 백엔드: 효과 미지원 (사운드 탭에 안내 표시) — mpv 백엔드 사용

    def shutdown(self):
        self.player.stop()

    def set_muted(self, m: bool):
        self._muted = bool(m)
        self.set_volume(self._volume)

    def volume(self) -> int:
        return self._volume

    # ---- 내부 ----
    def _on_state(self, st):
        S = QMediaPlayer.PlaybackState
        self.stateChanged.emit({S.PlayingState: "playing", S.PausedState: "paused"}.get(st, "stopped"))

    def _on_status(self, st):
        M = QMediaPlayer.MediaStatus
        if st in (M.LoadedMedia, M.BufferedMedia) and self._pending_seek > 0:
            self.player.setPosition(self._pending_seek)
            self._pending_seek = -1
        elif st == M.EndOfMedia:
            self.ended.emit()
        elif st == M.InvalidMedia:
            self.error.emit("재생할 수 없는 파일")

    def _on_error(self, err, msg=""):
        if err != QMediaPlayer.Error.NoError:
            log.warning("player error %s %s", err, msg)
            self.error.emit(msg or str(err))
