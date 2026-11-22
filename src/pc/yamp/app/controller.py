"""Controller: 플레이리스트 · 엔진 · 가사 · 설정 · 라이브러리를 묶는 중심. UI 는 시그널만 구독.

기능별 코드는 믹스인 모듈로 나눔 (vr0.1.0.007 모듈화):
  ctl_playback  재생 목록 · 재생 · 위치 · 엔진 이벤트 · 세션
  ctl_lyrics    가사 싱크 · 다시 찾기 · .lrc 저장
  ctl_queue     대기열 · 믹스/라디오 · 좋아요 · 별점
  ctl_effects   ReplayGain · 페이드 · A-B · 속도/음정 · 사운드 · 슬립 타이머
  ctl_library   재생 기록 · 추천 홈 · 스캔 · 태그 편집 · 폴더 재생
  jobs          백그라운드 작업 (태그 · 일반)
"""
import logging

from PyQt6.QtCore import QObject, QThreadPool, QTimer, pyqtSignal

from ..audio.mpv_engine import create_engine
from ..audio.visualizer import SpectrumAnalyzer
from ..data.playlist import Playlist, Track
from ..data.tags import TagInfo
from ..data.library import Library
from ..data.recorder import PlayRecorder
from ..lyrics.service import LyricsService
from .jobs import JobEmitter, TagEmitter
from .ctl_playback import PlaybackMixin
from .ctl_lyrics import LyricsMixin
from .ctl_queue import QueueMixin
from .ctl_effects import EffectsMixin
from .ctl_library import LibraryMixin

log = logging.getLogger("yamp.ctrl")

TICK_MS = 50                 # 재생 중 위치 폴링
AUTOSAVE_MS = 5 * 60 * 1000  # 설정·세션 자동 저장 주기
MAINT_MS = 24 * 3600 * 1000  # v020 (f40 L1): 실행 중 정리 주기 (하루)


class Controller(PlaybackMixin, LyricsMixin, QueueMixin, EffectsMixin, LibraryMixin, QObject):
    trackChanged = pyqtSignal(object, object)     # Track, TagInfo
    lyricsChanged = pyqtSignal(object)            # Lyrics | None
    lyricsStatus = pyqtSignal(str)
    positionChanged = pyqtSignal(int, int)        # pos_ms, dur_ms
    lyricPosition = pyqtSignal(int)               # 싱크 보정 적용된 위치
    stateChanged = pyqtSignal(str)
    playlistChanged = pyqtSignal()                # 목록 내용이 바뀜 (모델 다시 만듦)
    currentChanged = pyqtSignal()                 # 현재 곡만 바뀜 (행 색만 다시 그림)
    tagsUpdated = pyqtSignal()
    modesChanged = pyqtSignal()
    levels = pyqtSignal(list)
    visFrame = pyqtSignal(object)                 # v014: (파동, RMS, 피크) — 소리 시각화 블럭
    message = pyqtSignal(str)
    queueChanged = pyqtSignal()
    likedChanged = pyqtSignal(bool)
    abChanged = pyqtSignal(object)                # (a, b) 또는 None
    sleepChanged = pyqtSignal(str)                # 표시 문구 ("" = 꺼짐)
    homeReady = pyqtSignal(object)                # [(id, 제목, [keys])]
    libraryChanged = pyqtSignal()
    soundChanged = pyqtSignal()

    def __init__(self, cfg, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self.pl = Playlist()
        self.engine, msg = create_engine(str(cfg["audio_backend"]), self)
        self.backend_message = msg
        self.library = Library(cfg.data_dir / "library.db")
        self.recorder = PlayRecorder()
        self.queue: list[Track] = []              # 다음에 재생할 곡 (B5)
        self.ab = None                            # (a_ms, b_ms) 구간 반복 (A5)
        self._ab_a = None
        self._sleep_end = 0.0                     # monotonic, 0 = 꺼짐
        self._sleep_track = False                 # "곡 끝날 때"
        self._ended_flag = False
        self._cue_end_fired = False
        self.spectrum = SpectrumAnalyzer(self)
        self.lyrics = LyricsService(cfg, cfg.data_dir / "lyrics", self)
        self.tag_info = TagInfo()
        self.cur_lyrics = None
        self._errors = 0
        self._tag_gen = [0]
        self._tag_em = TagEmitter()
        self._tag_em.progress.connect(self.tagsUpdated)
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(1)

        e = self.engine
        e.set_muted(bool(cfg["muted"]))
        e.set_volume(int(cfg["volume"]))
        e.stateChanged.connect(self._on_state)
        e.ended.connect(self._on_ended)
        e.error.connect(self._on_error)
        e.durationChanged.connect(lambda d: self.positionChanged.emit(e.position(), d))
        if getattr(e, "supports_spectrum", True):
            e.bufferReady.connect(self.spectrum.feed)
        e.set_rate(float(cfg["speed"] or 1.0))
        e.set_pitch(int(cfg["pitch_st"] or 0))
        self.sound = self._load_sound()
        e.set_sound(self.sound)
        e.set_skip_silence(bool(cfg["skip_silence"]))
        self._jem = JobEmitter()
        self._jobs = QThreadPool(self)
        self._jobs.setMaxThreadCount(1)
        # v032 (f60 P7): 라이브러리 폴더 스캔은 따로 (첫 스캔 = 새 곡마다 태그 읽기 → 수천 곡이면 수 분.
        #   전에는 같은 작업 줄(_jobs)이라 그동안 추천 홈 · 하루 정리 · 스마트 목록 작업이 스캔이 끝날 때까지 기다렸음)
        self._scan_jobs = QThreadPool(self)
        self._scan_jobs.setMaxThreadCount(1)
        self._home_cb = None
        self._jem.done.connect(self._on_job_done)
        self.spectrum.levels.connect(self.levels)
        self.spectrum.frame.connect(self.visFrame)
        self.lyrics.found.connect(self._on_lyrics)
        self.lyrics.searching.connect(self.lyricsStatus)
        # 가사·LCD 를 부드럽게: 재생 중 50ms 폴링 (창이 숨겨지면 화면 갱신 시그널만 줄임 — set_ui_active)
        self._tick = QTimer(self, interval=TICK_MS, timeout=self._on_tick)
        self.ui_active = True
        self._ui_skip = 0
        self._closed = False                      # shutdown() 뒤 True
        # 장시간 운용: 설정·세션 주기 저장 (비정상 종료 대비)
        self._autosave = QTimer(self, interval=AUTOSAVE_MS, timeout=self.autosave)
        self._autosave.start()
        self._maint = QTimer(self, interval=MAINT_MS, timeout=self.maintenance)   # 첫 정리는 MainWindow 가 시작 8초 뒤
        self._maint.start()

    # ------------------------------------------------ 장시간 운용 (vr0.1.0.007)
    def set_ui_active(self, on: bool):
        """창이 최소화·트레이로 숨겨지면 False: 위치 시그널을 줄이고 스펙트럼 계산을 멈춤 (소리 처리는 그대로)"""
        on = bool(on)
        if on == self.ui_active:
            return
        self.ui_active = on
        self.sync_spectrum()
        self._ui_skip = 0
        if on:
            self._on_tick(force=True)
        log.debug("ui active=%s", on)

    def sync_spectrum(self):
        """스펙트럼 계산·버퍼 출력은 '켜짐 + 창 보임' 일 때만"""
        on = self.ui_active and bool(self.cfg["spectrum"])
        self.spectrum.enabled = on
        self.engine.set_spectrum(on)

    def autosave(self):
        """세션(재생 목록·위치)·설정 저장. 실패해도 재생에 영향 없음"""
        try:
            self.save_session()
            self.cfg.save()
        except OSError as e:
            log.warning("autosave: %s", e)

    def shutdown(self):
        if self._closed:                          # v020 (f40): 두 번 불려도 안전 (DB 를 두 번 닫으면 예외 → closeEvent 안이면 앱 abort)
            return
        self._closed = True
        self._tag_gen[0] += 1
        self._resume_remember()
        self._finish_record(False)
        self.lyrics.cancel()
        self._tick.stop()
        self._autosave.stop()
        self._maint.stop()
        self.engine.stop()
        self._pool.waitForDone(2000)
        self._jobs.waitForDone(2000)
        self._scan_jobs.waitForDone(3000)         # v032 (f60 P7): 스캔은 _closed 를 보고 곡 사이에서 멈춤 → DB 닫기 전에 끝남
        self.lyrics.wait(1000)
        try:
            self.engine.shutdown()
        except Exception:  # noqa
            pass
        self.library.close()
