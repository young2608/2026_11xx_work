# -*- coding: utf-8 -*-
"""재생 막대 곡 파형 시크바 (vr0.1.0.019 R5 — ui/neon.py 에서 나눔)

WaveformSeek  peaks(0..1) 막대 · 재생한 부분 강조 · A-B 구간 · 클릭/드래그 이동 (v017 픽셀 격자 · v018 막대 그림 캐시)
bars_played   재생한 막대 수 규칙 (Qt 비의존 — 테스트 대상)
"""
import math

from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPixmap
from PyQt6.QtWidgets import QSizePolicy, QWidget

from .hidpi import snap
from . import skin as skinmod
from .neon_base import _Skinned, _glow_pen


# ---------------------------------------------------------------- 파형 시크바
class WaveformSeek(_Skinned, QWidget):
    """peaks(0..1) 가 없으면 일반 막대. seekRequested(ms)"""
    seekRequested = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.peaks: list[float] = []
        self.pos_ms = 0
        self.dur_ms = 0
        self.ab = None
        self.accent_override: QColor | None = None     # Windows 강조색 따라가기 (W6) — 없으면 테마 wave_played
        self._drag = False
        self.setMinimumHeight(34)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    @property
    def accent(self) -> QColor:
        return QColor(self.accent_override) if self.accent_override is not None else QColor(self.skin.wave_played)

    @property
    def rest(self) -> QColor:
        return QColor(self.skin.wave_rest)

    # QSlider 호환 (기존 코드·테스트)
    def maximum(self):
        return self.dur_ms

    def setRange(self, lo, hi):
        self.dur_ms = int(hi)
        self.update()

    def set_pos(self, ms):
        if not self._drag and int(ms) // 200 != self.pos_ms // 200:
            self.pos_ms = int(ms)
            self.update()
        elif not self._drag:
            self.pos_ms = int(ms)

    def set_peaks(self, peaks):
        self.peaks = list(peaks or [])
        self.update()

    def set_ab(self, ab):
        self.ab = ab if ab and ab[0] != "A" else None
        self.update()

    def _bars(self, width_px: int, r: float) -> list:
        """peaks → 화면 막대 수(3px 간격)로 다시 나눔 (구간 최대값 · 0.8 제곱으로 작은 소리 키움). 크기 · 곡이 같으면 캐시"""
        step = max(3, round(3 * r))
        nb = max(1, width_px // step)
        key = (nb, id(self.peaks), len(self.peaks))
        if getattr(self, "_bars_key", None) != key:
            pk, n = self.peaks, len(self.peaks)
            out = []
            for k in range(nb):
                a, b = k * n // nb, max(k * n // nb + 1, (k + 1) * n // nb)
                v = max(pk[a:b]) if a < n else 0.0
                out.append(min(1.0, max(0.0, float(v))) ** 0.8)
            self._bars_key, self._bars_cache = key, out
        return self._bars_cache

    def _bar_sheets(self, w: int, h: int, r: float, acc: QColor, rest: QColor):
        """막대 그림 두 장 (재생한 색 / 나머지 색) — (크기 · 배율 · 곡 · 색) 이 같으면 캐시 (v018)"""
        key = (w, h, r, id(self.peaks), len(self.peaks), acc.rgba(), rest.rgba())
        c = getattr(self, "_sheets", None)
        if c is not None and c[0] == key:
            return c[1]
        bars = self._bars(int(w * r), r)
        step = max(3, round(3 * r))
        bar_px = max(2, step - max(1, round(r)))
        mid_px = round(h * r / 2)
        maxh = max(2.0, (h - 4) * r)
        sheets = []
        for color in (acc, rest):
            pm = QPixmap(max(1, round(w * r)), max(1, round(h * r)))
            pm.setDevicePixelRatio(r)
            pm.fill(Qt.GlobalColor.transparent)
            q = QPainter(pm)
            q.setRenderHint(QPainter.RenderHint.Antialiasing, False)
            for k, v in enumerate(bars):
                bh = max(2, int(round(v * maxh / 2)) * 2)          # 짝수 픽셀 → 가운데선 기준 정확히 대칭
                q.fillRect(QRectF(k * step / r, (mid_px - bh // 2) / r, bar_px / r, bh / r), color)
            q.end()
            sheets.append(pm)
        val = (sheets[0], sheets[1], len(bars), step)
        self._sheets = (key, val)
        return val

    def _ms_at(self, x):
        return int(max(0.0, min(1.0, x / max(1, self.width()))) * self.dur_ms)

    def mousePressEvent(self, e):
        if self.dur_ms > 0:
            self._drag = True
            self.pos_ms = self._ms_at(e.position().x())
            self.update()

    def mouseMoveEvent(self, e):
        if self._drag:
            self.pos_ms = self._ms_at(e.position().x())
            self.update()

    def mouseReleaseEvent(self, e):
        if self._drag:
            self._drag = False
            self.seekRequested.emit(self._ms_at(e.position().x()))

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        acc, rest = self.accent, self.rest
        frac = self.pos_ms / self.dur_ms if self.dur_ms > 0 else 0
        if self.ab and self.dur_ms > 0:
            a, b = self.ab
            p.fillRect(QRectF(a / self.dur_ms * w, 0, (b - a) / self.dur_ms * w, h), skinmod.qcolor("fill1", 70))
        if self.peaks:
            # v017: 실제 픽셀 격자에 맞춘 막대(가장자리 번짐 없음) · 위아래 대칭 · 작은 소리도 보이게 살짝 키움
            # v018 (f33 P7): 막대 전체를 '재생한 색' · '나머지 색' 두 장으로 미리 그려 두고(크기 · 곡 · 색이 같으면 재사용)
            #   매번은 재생 위치에서 잘라 두 장을 붙이기만 함 → 막대 수백 개를 다시 칠하지 않음 (그림은 같음)
            r = self.devicePixelRatioF() or 1.0
            pm_play, pm_rest, n, step = self._bar_sheets(w, h, r, acc, rest)
            kcut = bars_played(n, frac)                            # (k + 0.5) / n <= frac 인 막대 수
            cut_px = min(pm_play.width(), kcut * step)
            p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
            if cut_px > 0:
                p.drawPixmap(QRectF(0, 0, cut_px / r, pm_play.height() / r), pm_play,
                             QRectF(0, 0, cut_px, pm_play.height()))
            if cut_px < pm_rest.width():
                p.drawPixmap(QRectF(cut_px / r, 0, (pm_rest.width() - cut_px) / r, pm_rest.height() / r), pm_rest,
                             QRectF(cut_px, 0, pm_rest.width() - cut_px, pm_rest.height()))
            p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        else:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(rest)
            p.drawRoundedRect(QRectF(0, h / 2 - 3, w, 6), 3, 3)
            p.setBrush(acc)
            p.drawRoundedRect(QRectF(0, h / 2 - 3, w * frac, 6), 3, 3)
        if self.dur_ms > 0:
            x = snap(frac * w, 2)                            # v016 G6
            p.setPen(_glow_pen(acc, 6, 60))
            p.drawLine(QPointF(x, 2), QPointF(x, h - 2))
            p.setPen(_glow_pen(QColor(self.skin.accent_text), 2, 230))
            p.drawLine(QPointF(x, 2), QPointF(x, h - 2))


def bars_played(n: int, frac: float) -> int:
    """막대 n 개 중 재생한 막대 수 = #{k : (k + 0.5) / n <= frac} (v017 색칠 규칙과 같음). Qt 비의존 — 테스트 대상"""
    if n <= 0:
        return 0
    k = max(0, min(n, math.floor(frac * n - 0.5) + 1))
    while k > 0 and (k - 0.5) / n > frac:                 # 실수 오차 보정 → 규칙식과 정확히 같게
        k -= 1
    while k < n and (k + 0.5) / n <= frac:
        k += 1
    return k
