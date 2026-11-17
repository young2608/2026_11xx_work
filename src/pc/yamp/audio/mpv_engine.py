# -*- coding: utf-8 -*-
"""
libmpv 재생 엔진 (D1) — config.txt `audio_backend = mpv`
  10밴드 EQ (lavfi equalizer), 음정 (rubberband), 갭리스, 속도
  필요: mpv-2.dll (MSYS2: pacman -S mingw-w64-ucrt-x86_64-mpv → build.sh exe 가 함께 복사)
  dll 을 못 찾으면 create_engine() 이 Qt 엔진으로 되돌아감 (로그 경고)
  스펙트럼: libmpv 는 오디오 버퍼를 넘겨주지 않음 → mpv 엔진에서는 스펙트럼 꺼짐

AudioEngine(Qt) 와 같은 시그널·메서드 → controller / UI 는 엔진 종류를 몰라도 됨.
libmpv 이벤트는 별도 스레드에서 받아 Qt 시그널로 전달 (메인 스레드로 자동 큐잉).
"""
import ctypes
import ctypes.util
import locale
import logging
import os
import sys
import threading

from PyQt6.QtCore import QObject, pyqtSignal

log = logging.getLogger("yamp.mpv")

EQ_FREQS = (31, 62, 125, 250, 500, 1000, 2000, 4000, 8000, 16000)

# libmpv 상수
FMT_STRING, FMT_FLAG, FMT_INT64, FMT_DOUBLE = 1, 3, 4, 5
EV_SHUTDOWN, EV_START_FILE, EV_END_FILE, EV_FILE_LOADED, EV_PROPERTY_CHANGE = 1, 6, 7, 8, 22
END_EOF, END_ERROR = 0, 4


def parse_eq_bands(text) -> list[float]:
    """'0,1.5,-3,...' → 10개 dB (−12..12). 모자라면 0, 잘못된 값은 0"""
    out = []
    for part in str(text or "").split(","):
        try:
            out.append(max(-12.0, min(12.0, float(part.strip()))))
        except ValueError:
            out.append(0.0)
    return (out + [0.0] * 10)[:10]


def build_af(eq_enabled: bool, bands, pitch_st: int = 0) -> str:
    """mpv af 문자열 (테스트 대상). 효과가 없으면 빈 문자열"""
    parts = []
    if eq_enabled:
        eq = [f"equalizer=f={f}:t=o:w=1:g={g:g}" for f, g in zip(EQ_FREQS, bands) if abs(g) >= 0.05]
        if eq:
            parts.append("lavfi=[" + ",".join(eq) + "]")
    if pitch_st:
        parts.append(f"rubberband=pitch-scale={2 ** (pitch_st / 12):.6f}")
    return ",".join(parts)


EQ_PRESETS = {
    "평탄": [0] * 10,
    "베이스 강조": [6, 5, 4, 2, 0, 0, 0, 0, 0, 0],
    "고음 강조": [0, 0, 0, 0, 0, 1, 2, 4, 5, 6],
    "보컬": [-2, -2, -1, 1, 3, 4, 3, 1, 0, -1],
    "록": [5, 3, 1, -1, -2, -1, 1, 3, 4, 5],
    "클래식": [4, 3, 2, 1, 0, 0, 0, 1, 2, 3],
    "재즈": [3, 2, 1, 2, -1, -1, 0, 1, 2, 3],
    "댄스": [6, 5, 2, 0, 0, -1, -2, -2, 0, 0],
}


class _Event(ctypes.Structure):
    _fields_ = [("event_id", ctypes.c_int), ("error", ctypes.c_int),
                ("reply_userdata", ctypes.c_uint64), ("data", ctypes.c_void_p)]


class _EventProperty(ctypes.Structure):
    _fields_ = [("name", ctypes.c_char_p), ("format", ctypes.c_int), ("data", ctypes.c_void_p)]


class _EventEndFile(ctypes.Structure):
    _fields_ = [("reason", ctypes.c_int), ("error", ctypes.c_int)]


def _candidates():
    here = os.path.dirname(sys.executable if getattr(sys, "frozen", False) else os.path.abspath(__file__))
    names = ["mpv-2.dll", "libmpv-2.dll", "mpv-1.dll"] if sys.platform == "win32" else \
        ["libmpv.so.2", "libmpv.so.1", "libmpv.so", "libmpv.2.dylib", "libmpv.dylib"]
    paths = []
    for base in (here, os.path.join(here, "_internal"), getattr(sys, "_MEIPASS", "")):
        if base:
            paths += [os.path.join(base, n) for n in names]
    found = ctypes.util.find_library("mpv")
    if found:
        paths.append(found)
    return paths + names


def load_libmpv():
    for p in _candidates():
        try:
            lib = ctypes.CDLL(p)
            lib.mpv_create.restype = ctypes.c_void_p
            lib.mpv_wait_event.restype = ctypes.POINTER(_Event)
            lib.mpv_wait_event.argtypes = [ctypes.c_void_p, ctypes.c_double]
            for fn in ("mpv_initialize", "mpv_terminate_destroy", "mpv_wakeup"):
                getattr(lib, fn).argtypes = [ctypes.c_void_p]
            lib.mpv_set_option_string.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p]
            lib.mpv_set_property_string.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p]
            lib.mpv_command.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_char_p)]
            lib.mpv_observe_property.argtypes = [ctypes.c_void_p, ctypes.c_uint64, ctypes.c_char_p, ctypes.c_int]
            lib.mpv_get_property.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int, ctypes.c_void_p]
            log.info("libmpv: %s", p)
            return lib
        except (OSError, AttributeError):
            continue
    return None


class MpvEngine(QObject):
    positionChanged = pyqtSignal(int)
    durationChanged = pyqtSignal(int)
    stateChanged = pyqtSignal(str)
    ended = pyqtSignal()
    error = pyqtSignal(str)
    bufferReady = pyqtSignal(object)       # 사용 안 함 (호환)
    _evt = pyqtSignal(int, object)         # 이벤트 스레드 → 메인 스레드

    name = "mpv"
    supports_eq = True
    supports_pitch = True
    supports_spectrum = False
    supports_skip_silence = True
    _skip_silence = False

    def __init__(self, lib, parent=None):
        super().__init__(parent)
        self.lib = lib
        try:
            locale.setlocale(locale.LC_NUMERIC, "C")       # libmpv 요구사항
        except locale.Error:
            pass
        self.h = lib.mpv_create()
        if not self.h:
            raise RuntimeError("mpv_create 실패")
        for k, v in (("vo", "null"), ("video", "no"), ("audio-display", "no"), ("idle", "yes"),
                     ("gapless-audio", "weak"), ("input-default-bindings", "no"), ("terminal", "no"),
                     ("prefetch-playlist", "yes"), ("volume-max", "100")):
            lib.mpv_set_option_string(self.h, k.encode(), v.encode())
        if lib.mpv_initialize(self.h) < 0:
            raise RuntimeError("mpv_initialize 실패")
        for i, (name, fmt) in enumerate((("time-pos", FMT_DOUBLE), ("duration", FMT_DOUBLE), ("pause", FMT_FLAG))):
            lib.mpv_observe_property(self.h, i + 1, name.encode(), fmt)
        self._pos = 0
        self._dur = 0
        self._paused = True
        self._loaded = False
        self._volume = 70
        self._muted = False
        self._gain = 1.0
        self._fade = 1.0
        self._eq = (False, [0.0] * 10)
        self._pitch = 0
        self._pending_seek = -1
        self._autoplay = True
        self._evt.connect(self._on_evt)
        self._alive = True
        self._thread = threading.Thread(target=self._loop, name="mpv-events", daemon=True)
        self._thread.start()
        self._apply_volume()

    # ---------------------------------------------------------- 이벤트 스레드
    def _loop(self):
        while self._alive:
            ev = self.lib.mpv_wait_event(self.h, 0.5).contents
            eid = ev.event_id
            if eid == 0:
                continue
            if eid == EV_SHUTDOWN:
                break
            if eid == EV_PROPERTY_CHANGE and ev.data:
                p = ctypes.cast(ev.data, ctypes.POINTER(_EventProperty)).contents
                name = (p.name or b"").decode()
                val = None
                if p.data and p.format == FMT_DOUBLE:
                    val = ctypes.cast(p.data, ctypes.POINTER(ctypes.c_double)).contents.value
                elif p.data and p.format == FMT_FLAG:
                    val = bool(ctypes.cast(p.data, ctypes.POINTER(ctypes.c_int)).contents.value)
                if name == "time-pos":
                    # vr0.1.0.008: time-pos 는 오디오 블록마다(초당 수십 번) 옴 → Qt 시그널로 넘기지 않고
                    # 값만 저장 (int 대입은 원자적). 컨트롤러가 50ms 마다 position() 으로 읽음.
                    # (전에는 매번 스레드 간 큐 이벤트 → UI 스레드가 쓸데없이 깨어남)
                    if val is not None:
                        self._pos = int(val * 1000)
                    continue
                self._evt.emit(eid, (name, val))
            elif eid == EV_END_FILE and ev.data:
                e = ctypes.cast(ev.data, ctypes.POINTER(_EventEndFile)).contents
                self._evt.emit(eid, (e.reason, e.error))
            elif eid in (EV_FILE_LOADED, EV_START_FILE):
                self._evt.emit(eid, None)

    def _on_evt(self, eid, data):
        if eid == EV_PROPERTY_CHANGE:
            name, val = data
            if name == "duration":
                self._dur = int((val or 0) * 1000)
                self.durationChanged.emit(self._dur)
            elif name == "pause" and val is not None:
                self._paused = val
                if self._loaded:
                    self.stateChanged.emit("paused" if val else "playing")
        elif eid == EV_FILE_LOADED:
            self._loaded = True
            if self._pending_seek > 0:
                self.seek(self._pending_seek)
                self._pending_seek = -1
            self.stateChanged.emit("paused" if self._paused else "playing")
        elif eid == EV_END_FILE:
            reason, err = data
            self._loaded = False
            if reason == END_EOF:
                self.stateChanged.emit("stopped")
                self.ended.emit()
            elif reason == END_ERROR:
                self.error.emit(f"재생할 수 없는 파일 (mpv {err})")

    # ---------------------------------------------------------- 명령
    def _cmd(self, *args):
        arr = (ctypes.c_char_p * (len(args) + 1))(*[str(a).encode("utf-8") for a in args], None)
        return self.lib.mpv_command(self.h, arr)

    def _set(self, name, value):
        return self.lib.mpv_set_property_string(self.h, name.encode(), str(value).encode("utf-8"))

    def load(self, path: str, autoplay: bool = True, start_ms: int = 0):
        self._pending_seek = start_ms if start_ms > 0 else -1
        self._loaded = False
        self._set("pause", "no" if autoplay else "yes")
        self._cmd("loadfile", path, "replace")

    def play(self):
        self._set("pause", "no")

    def pause(self):
        self._set("pause", "yes")

    def toggle(self):
        self._set("pause", "no" if self._paused else "yes")

    def stop(self):
        self._cmd("stop")
        self._loaded = False
        self._pos = 0
        self.stateChanged.emit("stopped")

    def seek(self, ms: int):
        self._cmd("seek", f"{max(0, int(ms)) / 1000:.3f}", "absolute")

    def position(self) -> int:
        return self._pos

    def duration(self) -> int:
        return self._dur

    def is_playing(self) -> bool:
        return self._loaded and not self._paused

    def volume(self) -> int:
        return self._volume

    def set_volume(self, v: int):
        self._volume = max(0, min(100, int(v)))
        self._apply_volume()

    def set_muted(self, m: bool):
        self._muted = bool(m)
        self._apply_volume()

    def effective_volume(self) -> float:
        if self._muted:
            return 0.0
        return max(0.0, min(1.0, (self._volume / 100.0) ** 3 * self._gain * self._fade))

    def _apply_volume(self):
        self._set("volume", f"{self.effective_volume() * 100:.2f}")

    def set_gain(self, factor: float):
        self._gain = max(0.0, float(factor))
        self._apply_volume()

    def set_fade(self, f: float):
        f = max(0.0, min(1.0, float(f)))
        if abs(f - self._fade) > 0.001:
            self._fade = f
            self._apply_volume()

    def set_rate(self, rate: float):
        self._set("speed", f"{max(0.25, min(4.0, float(rate))):.3f}")

    def set_pitch(self, semitones: int):
        self._pitch = int(semitones)
        self._apply_af()

    def set_eq(self, enabled: bool, bands):
        self._eq = (bool(enabled), list(bands))
        self._sound = None
        self._apply_af()

    def set_spectrum(self, on: bool):
        pass                      # mpv 백엔드는 PCM 버퍼를 내보내지 않음

    def set_sound(self, settings):
        """vr0.1.0.006 사운드 탭 전체 (EQ·프리앰프·톤·밸런스·컴프레서·리미터) — domain/dsp.mpv_af"""
        self._sound = settings
        self._apply_af()

    def set_skip_silence(self, on: bool):
        """무음 건너뛰기 (vr0.1.0.010)"""
        self._skip_silence = bool(on)
        self._apply_af()

    def _apply_af(self):
        from ..domain.dsp import SILENCE_AF, mpv_af
        if getattr(self, "_sound", None) is not None:
            af = mpv_af(self._sound, self._pitch, self._skip_silence)
        else:
            af = build_af(self._eq[0], self._eq[1], self._pitch)
            if self._skip_silence:
                af = SILENCE_AF + ("," + af if af else "")
        if self._set("af", af) < 0:
            log.warning("mpv af 적용 실패: %s", af)

    def shutdown(self):
        if not self._alive:
            return
        self._alive = False
        try:
            self._cmd("quit")
            self.lib.mpv_wakeup(self.h)
            self._thread.join(1.0)
            self.lib.mpv_terminate_destroy(self.h)
        except Exception:  # noqa
            pass


def create_engine(backend: str, parent=None):
    """config audio_backend → 엔진. mpv 실패 시 Qt 로 (반환: (engine, 메시지))"""
    from .engine import AudioEngine
    if backend == "mpv":
        lib = load_libmpv()
        if lib is None:
            log.warning("libmpv(mpv-2.dll) 를 찾을 수 없어 Qt 엔진 사용")
            return AudioEngine(parent), "mpv-2.dll 없음 → Qt 엔진으로 실행 (EQ·음정 사용 불가)"
        try:
            return MpvEngine(lib, parent), ""
        except Exception as e:
            log.warning("mpv 초기화 실패: %s → Qt 엔진", e)
            return AudioEngine(parent), f"mpv 초기화 실패 → Qt 엔진 ({e})"
    return AudioEngine(parent), ""
