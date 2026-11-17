# -*- coding: utf-8 -*-
"""
사운드 처리 계산 (순수 파이썬 — Qt 비의존). Android domain/Dsp.kt 와 **같은 식**.
공용 테스트 벡터: 00__build/src/testdata/dsp_cases.txt (pc/tests/gen_testdata.py 가 생성, 양쪽 테스트가 읽음)

용도
  - PC  : 사운드 화면의 **응답 곡선** 그리기 + 노브/EQ 값 → mpv 필터 문자열 (실제 소리는 mpv)
  - AN  : 같은 식으로 ExoPlayer 오디오 처리기(SoundProcessor) 에서 실제 소리 처리

구성 (RBJ Audio EQ Cookbook 바이쿼드, 샘플레이트별 계수)
  프리앰프(dB) → 10밴드 피킹 EQ(31~16k, Q=1.41) → 베이스 로우셸프(100Hz) → 트레블 하이셸프(8kHz)
  → 밸런스(L/R 게인) → 컴프레서(피크 검출, threshold/ratio/attack/release/makeup) → 리미터(-1 dBFS, 빠른 attack)
"""
from dataclasses import dataclass, field
import math

EQ_FREQS = (31, 62, 125, 250, 500, 1000, 2000, 4000, 8000, 16000)
EQ_Q = 1.41
BASS_HZ = 100.0
TREBLE_HZ = 8000.0
SHELF_S = 1.0
LIMIT_DB = -1.0
LIMIT_ATTACK_MS = 1.0
LIMIT_RELEASE_MS = 80.0

PRESETS = {
    "평탄": [0] * 10,
    "베이스 강조": [6, 5, 4, 2, 0, 0, 0, 0, 0, 0],
    "고음 강조": [0, 0, 0, 0, 0, 1, 2, 4, 5, 6],
    "보컬": [-2, -2, -1, 1, 3, 4, 3, 1, 0, -1],
    "록": [5, 3, 1, -1, -2, -1, 1, 3, 4, 5],
    "클래식": [4, 3, 2, 1, 0, 0, 0, 1, 2, 3],
    "재즈": [3, 2, 1, 2, -1, -1, 0, 1, 2, 3],
    "댄스": [6, 5, 2, 0, 0, -1, -2, -2, 0, 0],
    "음성": [-8, -6, -3, 0, 1, 3, 4, 3, 1, -2],      # vr0.1.0.010 V4: 녹음·강의 — 저음 줄이고 2~4kHz(말소리) 올림
}


@dataclass
class SoundSettings:
    enabled: bool = False            # EQ·톤 (밸런스·다이내믹은 따로)
    preamp_db: float = 0.0
    bands: list = field(default_factory=lambda: [0.0] * 10)
    bass_db: float = 0.0
    treble_db: float = 0.0
    balance: float = 0.0             # -1 (왼쪽) ~ +1 (오른쪽)
    limiter: bool = False
    comp: bool = False
    comp_threshold_db: float = -18.0
    comp_ratio: float = 3.0
    comp_attack_ms: float = 10.0
    comp_release_ms: float = 120.0
    comp_makeup_db: float = 0.0

    def clamp(self):
        c = lambda v, lo, hi: max(lo, min(hi, float(v)))
        self.preamp_db = c(self.preamp_db, -12, 12)
        self.bands = [c(b, -12, 12) for b in (list(self.bands) + [0.0] * 10)[:10]]
        self.bass_db = c(self.bass_db, -12, 12)
        self.treble_db = c(self.treble_db, -12, 12)
        self.balance = c(self.balance, -1, 1)
        self.comp_threshold_db = c(self.comp_threshold_db, -60, 0)
        self.comp_ratio = c(self.comp_ratio, 1, 20)
        self.comp_attack_ms = c(self.comp_attack_ms, 0.1, 200)
        self.comp_release_ms = c(self.comp_release_ms, 5, 2000)
        self.comp_makeup_db = c(self.comp_makeup_db, 0, 24)
        return self

    # 텍스트 저장 (config.txt / SharedPreferences 공용 형식) ------------------
    def to_text(self) -> str:
        f = lambda v: f"{v:g}"
        return ";".join([
            f"on={int(self.enabled)}", f"pre={f(self.preamp_db)}", "eq=" + ",".join(f(b) for b in self.bands),
            f"bass={f(self.bass_db)}", f"treble={f(self.treble_db)}", f"bal={f(self.balance)}",
            f"lim={int(self.limiter)}", f"comp={int(self.comp)}", f"th={f(self.comp_threshold_db)}",
            f"ratio={f(self.comp_ratio)}", f"att={f(self.comp_attack_ms)}", f"rel={f(self.comp_release_ms)}",
            f"mk={f(self.comp_makeup_db)}"])

    @classmethod
    def from_text(cls, text: str) -> "SoundSettings":
        s = cls()
        for part in (text or "").split(";"):
            k, _, v = part.partition("=")
            k = k.strip()
            try:
                if k == "on": s.enabled = v.strip() == "1"
                elif k == "pre": s.preamp_db = float(v)
                elif k == "eq": s.bands = [float(x) if x.strip() else 0.0 for x in v.split(",")]
                elif k == "bass": s.bass_db = float(v)
                elif k == "treble": s.treble_db = float(v)
                elif k == "bal": s.balance = float(v)
                elif k == "lim": s.limiter = v.strip() == "1"
                elif k == "comp": s.comp = v.strip() == "1"
                elif k == "th": s.comp_threshold_db = float(v)
                elif k == "ratio": s.comp_ratio = float(v)
                elif k == "att": s.comp_attack_ms = float(v)
                elif k == "rel": s.comp_release_ms = float(v)
                elif k == "mk": s.comp_makeup_db = float(v)
            except ValueError:
                pass
        return s.clamp()


# ---------------------------------------------------------------- 바이쿼드 계수 (RBJ)
def peaking(fs, f0, q, gain_db):
    """반환: (b0, b1, b2, a1, a2)  — a0 로 정규화"""
    a = 10 ** (gain_db / 40)
    w = 2 * math.pi * f0 / fs
    al = math.sin(w) / (2 * q)
    cw = math.cos(w)
    a0 = 1 + al / a
    return ((1 + al * a) / a0, (-2 * cw) / a0, (1 - al * a) / a0, (-2 * cw) / a0, (1 - al / a) / a0)


def _shelf_alpha(a, w, s):
    return math.sin(w) / 2 * math.sqrt((a + 1 / a) * (1 / s - 1) + 2)


def low_shelf(fs, f0, s, gain_db):
    a = 10 ** (gain_db / 40)
    w = 2 * math.pi * f0 / fs
    cw = math.cos(w)
    al = _shelf_alpha(a, w, s)
    sq = 2 * math.sqrt(a) * al
    a0 = (a + 1) + (a - 1) * cw + sq
    return ((a * ((a + 1) - (a - 1) * cw + sq)) / a0, (2 * a * ((a - 1) - (a + 1) * cw)) / a0,
            (a * ((a + 1) - (a - 1) * cw - sq)) / a0, (-2 * ((a - 1) + (a + 1) * cw)) / a0,
            ((a + 1) + (a - 1) * cw - sq) / a0)


def high_shelf(fs, f0, s, gain_db):
    a = 10 ** (gain_db / 40)
    w = 2 * math.pi * f0 / fs
    cw = math.cos(w)
    al = _shelf_alpha(a, w, s)
    sq = 2 * math.sqrt(a) * al
    a0 = (a + 1) - (a - 1) * cw + sq
    return ((a * ((a + 1) + (a - 1) * cw + sq)) / a0, (-2 * a * ((a - 1) + (a + 1) * cw)) / a0,
            (a * ((a + 1) + (a - 1) * cw - sq)) / a0, (2 * ((a - 1) - (a + 1) * cw)) / a0,
            ((a + 1) - (a - 1) * cw - sq) / a0)


def chain(s: SoundSettings, fs: int):
    """활성 필터 계수 목록 (0 dB 필터는 뺌 — 계산 절약, 결과 동일)"""
    out = []
    if not s.enabled:
        return out
    nyq = fs / 2
    for f0, g in zip(EQ_FREQS, s.bands):
        if abs(g) >= 0.01 and f0 < nyq * 0.95:
            out.append(peaking(fs, f0, EQ_Q, g))
    if abs(s.bass_db) >= 0.01:
        out.append(low_shelf(fs, BASS_HZ, SHELF_S, s.bass_db))
    if abs(s.treble_db) >= 0.01 and TREBLE_HZ < nyq * 0.95:
        out.append(high_shelf(fs, TREBLE_HZ, SHELF_S, s.treble_db))
    return out


def magnitude_db(coefs, fs, f):
    """한 바이쿼드의 주파수 f 에서의 크기(dB)"""
    b0, b1, b2, a1, a2 = coefs
    w = 2 * math.pi * f / fs
    c1, s1, c2, s2 = math.cos(w), math.sin(w), math.cos(2 * w), math.sin(2 * w)
    nr, ni = b0 + b1 * c1 + b2 * c2, -(b1 * s1 + b2 * s2)
    dr, di = 1 + a1 * c1 + a2 * c2, -(a1 * s1 + a2 * s2)
    num, den = nr * nr + ni * ni, dr * dr + di * di
    return 10 * math.log10(max(num, 1e-30) / max(den, 1e-30))


def response_db(s: SoundSettings, freqs, fs=48000):
    """응답 곡선 (프리앰프 포함). EQ 꺼짐이면 0"""
    if not s.enabled:
        return [0.0 for _ in freqs]
    cs = chain(s, fs)
    return [s.preamp_db + sum(magnitude_db(c, fs, f) for c in cs) for f in freqs]


def log_freqs(n=64, lo=20.0, hi=20000.0):
    return [lo * (hi / lo) ** (i / (n - 1)) for i in range(n)]


# ---------------------------------------------------------------- 실시간 처리 (참조 구현 — Android 와 같은 계산)
def db_to_lin(db):
    return 10 ** (db / 20)


def balance_gains(b):
    """(왼쪽, 오른쪽) 배율 — 가운데 0 이면 (1,1), 오른쪽(+) 으로 갈수록 왼쪽이 줄어듦"""
    return (min(1.0, 1.0 - b), min(1.0, 1.0 + b))


def time_coef(ms, fs):
    return math.exp(-1.0 / (max(ms, 0.01) * 0.001 * fs))


def comp_gain_db(level_db, th, ratio):
    """컴프레서 정적 곡선 (하드 니): 줄일 dB (≤ 0)"""
    over = level_db - th
    return -over * (1 - 1 / ratio) if over > 0 else 0.0


class Processor:
    """인터리브 float 프레임 처리 (채널 1~2). Android SoundProcessor 와 같은 순서·식"""

    def __init__(self, s: SoundSettings, fs: int, ch: int):
        self.s, self.fs, self.ch = s, fs, ch
        self.coefs = chain(s, fs)
        self.z = [[[0.0, 0.0] for _ in self.coefs] for _ in range(ch)]       # 채널별·필터별 상태 (DF2T)
        self.pre = db_to_lin(s.preamp_db) if s.enabled else 1.0
        self.bal = balance_gains(s.balance) if ch == 2 else (1.0, 1.0)
        self.env_c = 0.0       # 컴프레서 검출(dB 아님, 선형 피크 엔벨로프)
        self.env_l = 1.0       # 리미터 게인
        self.c_att, self.c_rel = time_coef(s.comp_attack_ms, fs), time_coef(s.comp_release_ms, fs)
        self.l_att, self.l_rel = time_coef(LIMIT_ATTACK_MS, fs), time_coef(LIMIT_RELEASE_MS, fs)
        self.l_thr = db_to_lin(LIMIT_DB)
        self.makeup = db_to_lin(s.comp_makeup_db)

    def process(self, data):
        """data: list[float] 인터리브. 새 리스트 반환"""
        s, ch, out = self.s, self.ch, list(data)
        n = len(out) // ch
        for i in range(n):
            frame = out[i * ch:(i + 1) * ch]
            for c in range(ch):
                x = frame[c] * self.pre
                for k, (b0, b1, b2, a1, a2) in enumerate(self.coefs):
                    z = self.z[c][k]
                    y = b0 * x + z[0]
                    z[0] = b1 * x - a1 * y + z[1]
                    z[1] = b2 * x - a2 * y
                    x = y
                frame[c] = x * self.bal[c if ch == 2 else 0]
            peak = max(abs(v) for v in frame)
            if s.comp:
                coef = self.c_att if peak > self.env_c else self.c_rel
                self.env_c = coef * self.env_c + (1 - coef) * peak
                lvl = 20 * math.log10(max(self.env_c, 1e-9))
                g = db_to_lin(comp_gain_db(lvl, s.comp_threshold_db, s.comp_ratio)) * self.makeup
                frame = [v * g for v in frame]
                peak *= g
            if s.limiter:
                target = self.l_thr / peak if peak > self.l_thr else 1.0
                coef = self.l_att if target < self.env_l else self.l_rel
                self.env_l = coef * self.env_l + (1 - coef) * target
                frame = [max(-1.0, min(1.0, v * self.env_l)) for v in frame]
            out[i * ch:(i + 1) * ch] = frame
        return out

    @property
    def active(self) -> bool:
        s = self.s
        return bool(self.coefs) or abs(self.pre - 1) > 1e-9 or self.bal != (1.0, 1.0) or s.comp or s.limiter


# ---------------------------------------------------------------- mpv 필터 (PC, audio_backend = mpv)
# 무음 건너뛰기 (vr0.1.0.010, V1): -45dB 아래가 1초 넘게 이어지면 그 부분을 빼고 0.3초만 남김
SILENCE_AF = "lavfi=[silenceremove=stop_periods=-1:stop_duration=1:stop_threshold=-45dB:stop_silence=0.3]"


def mpv_af(s: SoundSettings, pitch_st: int = 0, skip_silence: bool = False) -> str:
    parts = [SILENCE_AF] if skip_silence else []
    if s.enabled:
        lav = []
        if abs(s.preamp_db) >= 0.05:
            lav.append(f"volume={s.preamp_db:g}dB")
        lav += [f"equalizer=f={f}:t=q:w={EQ_Q:g}:g={g:g}" for f, g in zip(EQ_FREQS, s.bands) if abs(g) >= 0.05]
        if abs(s.bass_db) >= 0.05:
            lav.append(f"bass=g={s.bass_db:g}:f={BASS_HZ:g}")
        if abs(s.treble_db) >= 0.05:
            lav.append(f"treble=g={s.treble_db:g}:f={TREBLE_HZ:g}")
        if lav:
            parts.append("lavfi=[" + ",".join(lav) + "]")
    if abs(s.balance) >= 0.01:
        l, r = balance_gains(s.balance)
        parts.append(f"lavfi=[pan=stereo|c0={l:.3f}*c0|c1={r:.3f}*c1]")
    if s.comp:
        parts.append("lavfi=[acompressor=threshold={:.4f}:ratio={:g}:attack={:g}:release={:g}:makeup={:.4f}]".format(
            db_to_lin(s.comp_threshold_db), s.comp_ratio, s.comp_attack_ms, s.comp_release_ms,
            db_to_lin(s.comp_makeup_db)))
    if s.limiter:
        parts.append(f"lavfi=[alimiter=limit={db_to_lin(LIMIT_DB):.4f}:attack={LIMIT_ATTACK_MS:g}:release={LIMIT_RELEASE_MS:g}]")
    if pitch_st:
        parts.append(f"rubberband=pitch-scale={2 ** (pitch_st / 12):.6f}")
    return ",".join(parts)
