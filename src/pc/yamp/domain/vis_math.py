# -*- coding: utf-8 -*-
"""소리 시각화 계산 (vr0.1.0.019 R10 — ui/vis_block.py · audio/visualizer.py 에서 모음, Qt 비의존 · 테스트 대상)
Android domain/VisMath.kt 와 같은 역할: dB 변환(바닥 -60 dB) · 차트 높이 · 파일 파형 구간 · 파동 자동 키움(AGC)
(전에는 to_db 가 vis_block.py 와 visualizer.py 에 두 벌 있었음)"""
import functools
import math


DB_FLOOR = -60.0


DB_GRID = (-6, -12, -24, -48)


def to_db(v: float, floor: float = DB_FLOOR) -> float:
    return floor if v <= 10 ** (floor / 20) else max(floor, 20.0 * math.log10(v))


def db_y(db: float, top: float, h: float, floor: float = DB_FLOOR) -> float:
    """dB → 화면 y (0 dB = 위, floor = 아래)"""
    return top + h * (min(0.0, db) / floor)


def peaks_window(peaks: list[float], pos_ms: int, dur_ms: int, n: int, span_s: float = 6.0) -> list[float]:
    """파일 파형(0..1)에서 지금 위치 ±span/2 구간을 n점으로 (mpv 대신 그림). 범위 밖은 0"""
    if not peaks or dur_ms <= 0 or n <= 0:
        return [0.0] * max(0, n)
    per_ms = len(peaks) / dur_ms
    start = pos_ms - span_s * 500
    out = []
    for i in range(n):
        t = start + span_s * 1000 * i / max(1, n - 1)
        k = int(t * per_ms)
        out.append(float(peaks[k]) if 0 <= k < len(peaks) else 0.0)
    return out


AGC_MAX = 8.0          # v017: 파동 자동 키움 최대 배율
AGC_FILL = 0.85        # 블럭 높이의 이만큼까지
AGC_QUIET = 0.005      # 이보다 조용하면 키우지 않음 (잡음 확대 방지)


def agc_step(gain: float, peak: float) -> float:
    """파동 자동 키움 한 단계 (v017 규칙, v019 에서 그리기 코드와 분리): 커질 땐 35 % 씩 빠르게 줄이고, 작아질 땐 8 % 씩 천천히 키움"""
    if peak <= AGC_QUIET:
        return gain
    want = min(AGC_MAX, AGC_FILL / peak)
    return gain + (want - gain) * (0.35 if want < gain else 0.08)


# ================================================================ v026 (f51): 비주얼라이저 재구성 — PC · Android 같은 규칙
#   (Android domain/VisMath.kt 의 bandsFromMags · BandSmoother 와 같은 계산 — testdata/vis_cases.txt 로 둘 다 확인)
#   1) 밴드: 24개, 50 Hz ~ 16 kHz 로그 간격. bin 보다 좁은 낮은 밴드는 가운데 주파수에서 bin 사이 직선 보간
#      (전: 낮은 밴드 3~4개가 같은 bin 1개를 읽어 '똑같은 높이'로 붙어 보였음) · 넓은 밴드 = bin 들의 RMS (전: 최댓값 → 들쭉날쭉)
#      + 높은 소리 보정 +3 dB/옥타브 (1 kHz 기준) — 음악은 높을수록 에너지가 작아 오른쪽이 늘 낮게 보이는 것을 고르게
#   2) 움직임: 이웃 밴드 살짝 섞기(0.2 · 0.6 · 0.2) → 오를 때 τ 50 ms · 내릴 때 τ 350 ms 지수 곡선 (프레임 간격 dt 기준 — fps 와 무관)
#      꼭대기 표시 = 0.5초 머문 뒤 중력 가속으로 떨어짐 (Winamp · foobar2000 · Poweramp 방식)

VIS_BANDS = 24
VIS_F_LO = 50.0
VIS_F_HI = 16000.0
VIS_TILT_DB_OCT = 3.0
VIS_ATTACK_S = 0.05
VIS_RELEASE_S = 0.35
VIS_PEAK_HOLD_S = 0.5
VIS_PEAK_GRAVITY = 2.5          # 높이(0..1) / 초²
VIS_SPATIAL = (0.2, 0.6, 0.2)
VIS_STALE_S = 0.25              # 새 레벨이 이만큼 안 오면(멈춤 · 엔진 바뀜) 목표를 0 으로 → 막대가 내려앉음


def band_freqs(n: int = VIS_BANDS, lo: float = VIS_F_LO, hi: float = VIS_F_HI) -> list[tuple[float, float, float]]:
    """밴드 (시작, 끝, 가운데) Hz — 가운데 = 기하 평균"""
    out = []
    for b in range(n):
        f0 = lo * (hi / lo) ** (b / n)
        f1 = lo * (hi / lo) ** ((b + 1) / n)
        out.append((f0, f1, math.sqrt(f0 * f1)))
    return out


@functools.lru_cache(maxsize=32)
def _band_plan(m: int, bin_hz: float, n: int) -> tuple:
    """v032 (f60 P3): 밴드별 계산 방법을 (FFT 크기 · bin 간격 · 밴드 수) 마다 한 번만 정함 — 전에는 프레임마다
    band_freqs(거듭제곱 48번 · 제곱근 24번) 와 보간 위치 · bin 범위를 다시 계산. 값 · 계산 순서는 그대로 (결과 비트까지 같음)
    반환: 밴드마다 (0, k, k+1, fr, tilt) = 좁은 밴드 보간 / (1, k0, k1, 0, tilt) = 넓은 밴드 RMS"""
    out = []
    for f0, f1, fc in band_freqs(n):
        tilt = VIS_TILT_DB_OCT * math.log2(fc / 1000.0)
        if f1 - f0 < 2 * bin_hz:
            x = min(m - 1.0, max(1.0, fc / bin_hz))
            k = int(x)
            out.append((0, k, min(m - 1, k + 1), x - k, tilt))
        else:
            k0 = max(1, int(f0 / bin_hz))
            k1 = min(m, max(k0 + 1, int(f1 / bin_hz)))
            out.append((1, k0, k1, 0.0, tilt))
    return tuple(out)


def bands_from_mags(mags, bin_hz: float, n: int = VIS_BANDS, range_db: float = 60.0, ref: float = 1.0) -> list[float]:
    """FFT 크기 배열(mags[k] = k × bin_hz Hz) → n 밴드 0..1. 순수 계산 (PC numpy 배열 · 리스트 모두)
    좁은 밴드(bin 2개 폭 미만) = 가운데 주파수 보간 · 넓은 밴드 = bin 들의 RMS · +3 dB/옥타브 (Android VisMath.bandsFromMags 와 같음)"""
    m = len(mags)
    out = []
    if m < 2 or bin_hz <= 0:
        return [0.0] * n
    for wide, k0, k1, fr, tilt in _band_plan(m, float(bin_hz), int(n)):
        if not wide:                                   # 좁은 밴드: 가운데 주파수 보간
            a = float(mags[k0])
            b = float(mags[k1])
            v = a + (b - a) * fr
        else:                                          # 넓은 밴드: RMS
            s = 0.0
            for k in range(k0, k1):
                s += float(mags[k]) ** 2
            v = math.sqrt(s / (k1 - k0)) if k1 > k0 else 0.0         # 나이퀴스트 넘는 밴드 = 0
        db = 20.0 * math.log10(max(v, 1e-9) / ref) + tilt
        out.append(min(1.0, max(0.0, (db + range_db) / range_db)))
    return out


class BandSmoother:
    """막대 · 웨이브 움직임 (프레임마다 step). v = 보이는 높이, peaks = 꼭대기 표시 — 메모리 재사용"""

    def __init__(self, n: int = VIS_BANDS):
        self.n = n
        self.v = [0.0] * n
        self.peaks = [0.0] * n
        self._hold = [0.0] * n
        self._fall = [0.0] * n
        self.target = [0.0] * n

    def set_target(self, lv):
        lv = list(lv)[: self.n]
        self.target = lv + [0.0] * (self.n - len(lv))
        self._age = 0.0

    def step(self, dt: float):
        n = self.n
        dt = min(0.25, max(0.0, float(dt)))
        self._age = getattr(self, "_age", 0.0) + dt
        if self._age > VIS_STALE_S:
            self.target = [0.0] * n
        a0, a1, a2 = VIS_SPATIAL
        t = self.target
        sm = [a0 * t[max(0, i - 1)] + a1 * t[i] + a2 * t[min(n - 1, i + 1)] for i in range(n)]
        ka = 1.0 - math.exp(-dt / VIS_ATTACK_S)
        kr = 1.0 - math.exp(-dt / VIS_RELEASE_S)
        for i in range(n):
            cur, want = self.v[i], sm[i]
            cur += (want - cur) * (ka if want > cur else kr)
            self.v[i] = cur
            if cur >= self.peaks[i]:
                self.peaks[i] = cur
                self._hold[i] = VIS_PEAK_HOLD_S
                self._fall[i] = 0.0
            elif self._hold[i] > 0:
                self._hold[i] = max(0.0, self._hold[i] - dt)
            else:
                self._fall[i] += VIS_PEAK_GRAVITY * dt
                self.peaks[i] = max(cur, self.peaks[i] - self._fall[i] * dt)
        return self.v, self.peaks

    def idle(self, eps: float = 0.003) -> bool:
        """모두 내려앉고 새 값도 0 → 프레임 멈춰도 됨"""
        return max(self.v + self.peaks + self.target, default=0.0) <= eps

    def reset(self):
        self.__init__(self.n)


def smooth_curve(vals, x0: float, x1: float) -> list[tuple[float, float, float, float, float, float]]:
    """웨이브 모드: 점들을 부드러운 곡선(Catmull-Rom → 3차 베지어)으로. 양 끝은 0 으로 모아 둥근 모양.
    반환: [(c1x, c1y, c2x, c2y, x, y) …] — 첫 점 (x0, 0) 에서 시작, y = 0..1 높이"""
    pts = [0.0] + [float(v) for v in vals] + [0.0]
    n = len(pts)
    xs = [x0 + (x1 - x0) * i / (n - 1) for i in range(n)]
    out = []
    for i in range(n - 1):
        p0 = (xs[max(0, i - 1)], pts[max(0, i - 1)])
        p1 = (xs[i], pts[i])
        p2 = (xs[i + 1], pts[i + 1])
        p3 = (xs[min(n - 1, i + 2)], pts[min(n - 1, i + 2)])
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        out.append((c1[0], max(0.0, c1[1]), c2[0], max(0.0, c2[1]), p2[0], p2[1]))
    return out


# ================================================================ v027 (f53): 다른 앱 표현 방식 반영 — PC · Android 같은 규칙
#   모드: bars(스펙트럼) · wave(웨이브) · radial(원형, foobar2000 Radial · audioMotion radial · Avee) ·
#         gram(스펙트로그램, foobar2000 Spectrogram) · chart(레벨)
#   막대 모양(스펙트럼 버튼을 한 번 더 누르면 바뀜): round(둥근, 기본) · led(LED 칸, Winamp · foobar LED Bars · audioMotion LEDS) ·
#         mirror(가운데 = 낮은 소리 대칭, audioMotion mirror) · reflex(바닥 반사, audioMotion Reflex)

VIS_MODES = ("bars", "wave", "radial", "gram", "chart")
BAR_STYLES = ("round", "led", "mirror", "reflex")
GRAM_COLS = 150                 # 스펙트로그램 기록 칸 (30fps × 5초)
LED_CELL = 5.0                  # LED 칸 높이(px, 10pt 기준) · 칸 사이 2px


def parse_mode(m) -> str:
    return m if m in VIS_MODES else "chart"


def next_bar_style(cur) -> str:
    """스펙트럼 버튼을 다시 누를 때: round → led → mirror → reflex → round (모르는 값 = round 다음)"""
    i = BAR_STYLES.index(cur) if cur in BAR_STYLES else -1
    return BAR_STYLES[(i + 1) % len(BAR_STYLES)]


def mirror_order(n: int) -> list[int]:
    """미러 막대 배치 (왼쪽 → 오른쪽 2n칸의 밴드 번호): 높은 … 낮은 | 낮은 … 높은 (가운데 = 베이스)"""
    return list(range(n - 1, -1, -1)) + list(range(n))


def led_cells(v: float, h: float, cell: float = LED_CELL, gap: float = 2.0) -> int:
    """LED 막대: 높이 h 안 칸 수 중 v(0..1) 만큼 켜진 칸 (반올림, 최소 0)"""
    total = max(1, int((h + gap) // (cell + gap)))
    return max(0, min(total, int(math.floor(v * total + 0.5))))       # 반올림 (Android 와 같게 .5 → 올림)


def heat_rgb(v: float, stops) -> tuple[int, int, int]:
    """스펙트로그램 색: v(0..1) 를 색 4개(테마 graph_bg → spectrum_lo → spectrum_hi → peak, '#rrggbb')에 고르게 보간"""
    v = min(1.0, max(0.0, float(v)))
    cs = [(int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16)) for c in stops]
    seg = len(cs) - 1
    x = v * seg
    i = min(seg - 1, int(x))
    f = x - i
    a, b = cs[i], cs[i + 1]
    return tuple(int(math.floor(a[k] + (b[k] - a[k]) * f + 0.5)) for k in range(3))


class GramHistory:
    """스펙트로그램 기록: 최근 cols 프레임 × n 밴드 (링 버퍼 — 오래된 것부터 0..size-1)"""

    def __init__(self, n: int = VIS_BANDS, cols: int = GRAM_COLS):
        self.n, self.cols = n, cols
        self._buf = [[0.0] * n for _ in range(cols)]
        self._head = 0
        self.size = 0

    def push(self, lv):
        row = self._buf[self._head]
        for i in range(self.n):
            row[i] = float(lv[i]) if i < len(lv) else 0.0
        self._head = (self._head + 1) % self.cols
        self.size = min(self.cols, self.size + 1)

    def col(self, i: int) -> list[float]:
        """i = 0 (가장 오래됨) … size-1 (최근)"""
        return self._buf[(self._head - self.size + i) % self.cols]

    def clear(self):
        self._head = 0
        self.size = 0
