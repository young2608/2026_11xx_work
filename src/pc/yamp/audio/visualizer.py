"""스펙트럼 분석: QAudioBuffer → numpy FFT → 로그 간격 24밴드 (0~1), 최대 30fps.
v026 (f51): 밴드 계산 = domain/vis_math.bands_from_mags (Android 와 같은 규칙 — 낮은 밴드 보간 · RMS · +3 dB/옥타브)"""
import functools
import time

import numpy as np
from PyQt6.QtCore import QObject, pyqtSignal

from ..domain.vis_math import VIS_BANDS, bands_from_mags, to_db  # noqa: F401  (v019 R10: 한 벌로 — 이전 import 호환)

N_BANDS = VIS_BANDS
FFT_N = 1024


def band_edges(sr: int, n_fft: int = FFT_N, n_bands: int = N_BANDS):
    f = np.geomspace(40, min(16000, sr / 2 - 1), n_bands + 1)
    idx = np.clip((f / (sr / n_fft)).astype(int), 1, n_fft // 2)
    for i in range(1, len(idx)):       # 각 밴드 최소 1 bin
        if idx[i] <= idx[i - 1]:
            idx[i] = idx[i - 1] + 1
    return np.clip(idx, 1, n_fft // 2)


_WINDOW = np.hanning(FFT_N)


@functools.lru_cache(maxsize=16)
def _band_plan(sr: int, n_bands: int) -> tuple:
    """v018 (f33 P8): 표본율별 밴드 (시작, 끝) bin 을 한 번만 계산 (전에는 프레임마다 geomspace)"""
    e = band_edges(sr, FFT_N, n_bands).tolist()
    return tuple((e[i], max(e[i + 1], e[i] + 1)) for i in range(n_bands))


def compute_bands(mono: np.ndarray, sr: int, n_bands: int = N_BANDS) -> list[float]:
    """mono: float -1..1. 반환: 0..1 밴드 레벨 (Qt 비의존 — 테스트 대상).
    v018: 창 함수 · 밴드 경계 캐시, dB 변환 · 범위 자르기를 numpy 한 번에 (값은 전과 같음)"""
    if mono.size < 64:
        return [0.0] * n_bands
    x = mono[-FFT_N:]
    if x.size < FFT_N:
        x = np.pad(x, (FFT_N - x.size, 0))
    spec = np.abs(np.fft.rfft(x * _WINDOW)) / (FFT_N / 4)           # 꽉 찬 사인 ≈ 1.0 (0 dB)
    return bands_from_mags(spec.tolist(), float(sr) / FFT_N, int(n_bands), 60.0, 1.0)   # v026: -60dB..0dB → 0..1


_SAMPLE_BYTES = {"Int16": 2, "Int32": 4, "Float": 4, "UInt8": 1}


def buffer_to_mono(buf, max_frames: int | None = None) -> tuple[np.ndarray, int] | None:
    """QAudioBuffer → (모노 float32, 표본율). max_frames (v022 N6): 끝 프레임 N 개만 변환 (스펙트럼은 마지막 1024개만 필요 —
    긴 버퍼 전체를 복사 · 변환하지 않음). None = 전체 (곡 파형)"""
    fmt = buf.format()
    n = buf.byteCount()
    if n <= 0:
        return None
    from PyQt6.QtMultimedia import QAudioFormat     # f38: 여기서만 — 계산 함수(compute_bands 등)는 QtMultimedia 없이도 import
    sf = fmt.sampleFormat()
    F = QAudioFormat.SampleFormat
    ch = max(1, fmt.channelCount())
    names = {F.Int16: "Int16", F.Int32: "Int32", F.Float: "Float", F.UInt8: "UInt8"}
    if sf not in names:
        return None
    frame = _SAMPLE_BYTES[names[sf]] * ch
    start = 0
    if max_frames and n > max_frames * frame:
        start = (n // frame - max_frames) * frame          # 프레임 경계에서 자름
    ptr = buf.constData()
    try:
        ptr.setsize(n)
        raw = memoryview(ptr)[start:].tobytes() if start else bytes(ptr)
    except Exception:
        raw = ptr.asstring(n)[start:]
    if sf == F.Int16:
        a = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    elif sf == F.Int32:
        a = np.frombuffer(raw, dtype=np.int32).astype(np.float32) / 2147483648.0
    elif sf == F.Float:
        a = np.frombuffer(raw, dtype=np.float32)
    else:
        a = (np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128) / 128.0
    if ch > 1:
        a = a[: a.size // ch * ch].reshape(-1, ch).mean(axis=1)
    return a, fmt.sampleRate() or 44100


WAVE_N = 256


def frame_stats(mono: np.ndarray, n: int = WAVE_N) -> tuple[list[float], float, float]:
    """소리 시각화 (vr0.1.0.014): (파동 n점 -1..1, RMS 0..1, 피크 0..1) — 마지막 FFT_N 표본 기준. Qt 비의존 — 테스트 대상"""
    if mono.size == 0:
        return [0.0] * n, 0.0, 0.0
    x = mono[-FFT_N:]
    rms = float(np.sqrt(np.mean(np.square(x, dtype=np.float64))))
    peak = float(np.max(np.abs(x)))
    idx = np.linspace(0, x.size - 1, n).astype(int)
    return np.clip(x[idx], -1, 1).astype(float).tolist(), min(1.0, rms), min(1.0, peak)   # v018: tolist


class SpectrumAnalyzer(QObject):
    levels = pyqtSignal(list)
    frame = pyqtSignal(object)          # (wave list, rms, peak) — 시각화 블럭 (v014)

    def __init__(self, parent=None, fps: int = 30):
        super().__init__(parent)
        self.min_dt = 1.0 / fps
        self._last = 0.0
        self._acc = np.zeros(0, dtype=np.float32)
        self.enabled = True

    def feed(self, buf):
        if not self.enabled:
            return
        r = buffer_to_mono(buf, FFT_N)                 # v022 (N6): 끝 1024 프레임만
        if r is None:
            return
        a, sr = r
        if a.size >= FFT_N:                     # v018: 긴 버퍼는 끝 FFT_N 표본만 (이어 붙일 필요 없음)
            self._acc = a[-FFT_N:]
        else:
            self._acc = np.concatenate([self._acc, a])[-FFT_N:]
        now = time.monotonic()
        if now - self._last < self.min_dt:
            return
        self._last = now
        self.levels.emit(compute_bands(self._acc, sr))
        self.frame.emit(frame_stats(self._acc))
