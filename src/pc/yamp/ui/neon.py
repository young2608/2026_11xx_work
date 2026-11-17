# -*- coding: utf-8 -*-
"""
네온 스타일 위젯 (vr0.1.0.006)
  Knob            원형 노브 — 270° 색 호 + 빛, 바늘. 위/아래 드래그·휠로 값, 더블클릭 = 기본값
  EqSliders       프리앰프 + 10밴드 세로 슬라이더 (밴드별 색, 빛, 흰 손잡이)
  ResponseCurve   EQ 응답 곡선 + 스펙트럼 막대 (dsp.response_db)
  (v019 R5 나눔) Section → section.py · WaveformSeek → wave_seek.py · 공통 도우미 → neon_base.py
vr0.1.0.011: 색은 모두 테마 토큰 (skin.current()) — set_skin() 이 오면 다시 그림
"""
import math

from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QLabel, QSizePolicy, QWidget

from .hidpi import snap
from . import skin as skinmod
from .neon_base import _Skinned, _glow_pen, band_color  # noqa: F401
# v019 (R5): 곡 파형 시크바 · 접기 블럭은 각자 파일로 — 이전처럼 neon 에서도 가져갈 수 있게 다시 내보냄
from .section import Section  # noqa: F401
from .wave_seek import WaveformSeek, bars_played  # noqa: F401


# ---------------------------------------------------------------- 노브
class Knob(_Skinned, QWidget):
    valueChanged = pyqtSignal(float)

    def __init__(self, label: str, lo: float, hi: float, value: float = 0.0, default: float | None = None,
                 color: int | str = 4, fmt=None, step: float = 0.0, parent=None):
        """color: 밴드 번호(0..10, 테마의 bands) 또는 토큰 이름"""
        super().__init__(parent)
        self.label, self.lo, self.hi = label, float(lo), float(hi)
        self.default = float(default if default is not None else value)
        self.color_key = color
        self.fmt = fmt or (lambda v: f"{v:+.1f}")
        self.step = step
        self._v = float(value)
        self._drag = None
        self.setMinimumSize(74, 96)
        self.setCursor(Qt.CursorShape.SizeVerCursor)
        self.setToolTip(f"{label}: 위·아래로 끌기 / 휠 — 더블클릭 = 초기화")

    def value(self) -> float:
        return self._v

    def setValue(self, v: float, emit: bool = False):
        v = max(self.lo, min(self.hi, float(v)))
        if self.step:
            v = round(v / self.step) * self.step
        if abs(v - self._v) > 1e-9:
            self._v = v
            self.update()
            if emit:
                self.valueChanged.emit(v)

    def _frac(self):
        return (self._v - self.lo) / (self.hi - self.lo) if self.hi > self.lo else 0

    def mousePressEvent(self, e):
        self._drag = (e.position().y(), self._v)

    def mouseMoveEvent(self, e):
        if self._drag:
            y0, v0 = self._drag
            self.setValue(v0 + (y0 - e.position().y()) / 150.0 * (self.hi - self.lo), emit=True)

    def mouseReleaseEvent(self, e):
        self._drag = None

    def mouseDoubleClickEvent(self, e):
        self.setValue(self.default, emit=True)

    def wheelEvent(self, e):
        st = self.step or (self.hi - self.lo) / 50
        self.setValue(self._v + (st if e.angleDelta().y() > 0 else -st), emit=True)

    @property
    def color(self) -> QColor:
        k = self.color_key
        return band_color(self.skin, k) if isinstance(k, int) else skinmod.qcolor(k)

    def paintEvent(self, e):
        s = self.skin
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        size = min(self.width(), self.height() - 30)
        r = QRectF((self.width() - size) / 2 + 6, 6, size - 12, size - 12)
        start, span = 225, -270                     # Qt: 0° = 3시, 반시계 +
        # 배경 호
        p.setPen(_glow_pen(QColor(s.knob_rim), 5, 255))
        p.drawArc(r, start * 16, span * 16)
        # 값 호 (빛 + 선)
        val_span = int(span * self._frac() * 16)
        col = self.color
        p.setPen(_glow_pen(col, 11, 50))
        p.drawArc(r, start * 16, val_span)
        p.setPen(_glow_pen(col, 5, 255))
        p.drawArc(r, start * 16, val_span)
        # 안쪽 원 + 바늘
        inner = r.adjusted(9, 9, -9, -9)
        p.setPen(QPen(QColor(s.knob_rim), 1))
        p.setBrush(QColor(s.knob))
        p.drawEllipse(inner)
        ang = math.radians(start + span * self._frac())
        c = inner.center()
        rad = inner.width() / 2 - 5
        p.setPen(_glow_pen(QColor(s.text), 3, 255))
        p.drawLine(c, QPointF(c.x() + rad * math.cos(ang), c.y() - rad * math.sin(ang)))
        # 글자
        p.setPen(QColor(s.dim))
        p.setFont(skinmod.role_font(self.font(), "tiny"))
        p.drawText(QRectF(0, size - 6, self.width(), 14), Qt.AlignmentFlag.AlignHCenter, self.label)
        p.setPen(QColor(s.text))
        p.drawText(QRectF(0, size + 8, self.width(), 14), Qt.AlignmentFlag.AlignHCenter, self.fmt(self._v))


# ---------------------------------------------------------------- 10밴드 EQ
class EqSliders(_Skinned, QWidget):
    """값: [프리앰프] + 10밴드 (dB, −12..12). changed(index, value) — index 0 = 프리앰프"""
    changed = pyqtSignal(int, float)
    LABELS = ("Pre", "31", "62", "125", "250", "500", "1k", "2k", "4k", "8k", "16k")

    def __init__(self, parent=None):
        super().__init__(parent)
        self.vals = [0.0] * 11
        self.enabled_look = True
        self._drag = -1
        self.setMinimumSize(340, 200)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setToolTip("위·아래로 끌기 — 더블클릭 = 0 dB")

    def set_values(self, pre, bands):
        self.vals = [float(pre)] + [float(b) for b in (list(bands) + [0] * 10)[:10]]
        self.update()

    def _geom(self):
        top, bot = 10, self.height() - 40
        step = self.width() / 11
        return top, bot, step

    def _x(self, i):
        return self._geom()[2] * (i + 0.5)

    def _hit(self, x):
        return max(0, min(10, int(x / self._geom()[2])))

    def _val_at(self, y):
        top, bot, _ = self._geom()
        mid = (top + bot) / 2
        return max(-12.0, min(12.0, round((mid - y) / ((bot - top) / 2) * 12 * 2) / 2))

    def mousePressEvent(self, e):
        self._drag = self._hit(e.position().x())
        self.mouseMoveEvent(e)

    def mouseMoveEvent(self, e):
        if self._drag >= 0:
            v = self._val_at(e.position().y())
            if v != self.vals[self._drag]:
                self.vals[self._drag] = v
                self.update()
                self.changed.emit(self._drag, v)

    def mouseReleaseEvent(self, e):
        self._drag = -1

    def mouseDoubleClickEvent(self, e):
        i = self._hit(e.position().x())
        self.vals[i] = 0.0
        self.update()
        self.changed.emit(i, 0.0)

    def paintEvent(self, e):
        s = self.skin
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        top, bot, step = self._geom()
        mid = (top + bot) / 2
        alpha = 255 if self.enabled_look else 90
        p.setPen(QPen(QColor(s.graph_grid), 1, Qt.PenStyle.DashLine))
        p.drawLine(QPointF(4, snap(mid)), QPointF(self.width() - 4, snap(mid)))     # v016 G6: 1px 선 픽셀 가운데
        f = skinmod.role_font(self.font(), "tiny")
        p.setFont(f)
        for i, v in enumerate(self.vals):
            x = self._x(i)
            col = band_color(s, i)
            p.setPen(_glow_pen(QColor(s.knob_rim), 4, 255))
            p.drawLine(QPointF(x, top), QPointF(x, bot))
            y = mid - v / 12 * (bot - top) / 2
            p.setPen(_glow_pen(col, 10, 45 * alpha // 255))
            p.drawLine(QPointF(x, mid), QPointF(x, y))
            p.setPen(_glow_pen(col, 4, alpha))
            p.drawLine(QPointF(x, mid), QPointF(x, y))
            p.setPen(_glow_pen(col, 4, 60 * alpha // 255))
            p.drawLine(QPointF(x, y), QPointF(x, bot))
            hc = QColor(col)
            hc.setAlpha(alpha)
            p.setPen(QPen(hc, 1.5))
            p.setBrush(skinmod.qcolor("surface", alpha))
            p.drawRoundedRect(QRectF(x - 9, y - 6, 18, 12), 3, 3)
            p.setPen(QPen(skinmod.qcolor("dim", alpha), 1.5))
            p.drawLine(QPointF(x - 5, y), QPointF(x + 5, y))
            p.setPen(QColor(s.dim))
            p.drawText(QRectF(x - step / 2, bot + 6, step, 14), Qt.AlignmentFlag.AlignHCenter, self.LABELS[i])
            p.setPen(QColor(s.text))
            p.drawText(QRectF(x - step / 2, bot + 20, step, 14), Qt.AlignmentFlag.AlignHCenter, f"{v:+g}" if v else "0")


# ---------------------------------------------------------------- 응답 곡선
class ResponseCurve(_Skinned, QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.curve: list[float] = []     # dB (log_freqs 순서)
        self.levels: list[float] = []    # 스펙트럼 0..1
        self.setMinimumHeight(80)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_curve(self, db_list):
        self.curve = list(db_list)
        self.update()

    def set_levels(self, lv):
        self.levels = list(lv)
        if self.isVisible():
            self.update()

    def paintEvent(self, e):
        s = self.skin
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(self.rect(), QColor(s.graph_bg))
        if self.levels:
            n = len(self.levels)
            bw = w / n
            lv = skinmod.qcolor("spectrum_lo", 60)
            for i, v in enumerate(self.levels):
                bh = v * (h - 6)
                p.fillRect(QRectF(i * bw + 1, h - bh, bw - 2, bh), lv)
        mid = h / 2
        p.setPen(QPen(QColor(s.graph_grid), 1, Qt.PenStyle.DashLine))
        p.drawLine(QPointF(0, snap(mid)), QPointF(w, snap(mid)))
        if not self.curve:
            return
        path = QPainterPath()
        n = len(self.curve)
        for i, db in enumerate(self.curve):
            x = i / (n - 1) * w
            y = mid - max(-24, min(24, db)) / 24 * (h / 2 - 4)
            path.moveTo(x, y) if i == 0 else path.lineTo(x, y)
        col = QColor(s.wave_played)
        p.setPen(_glow_pen(col, 8, 45))
        p.drawPath(path)
        p.setPen(_glow_pen(col, 2.5, 255))
        p.drawPath(path)
        p.setPen(QColor(s.dim))
        p.setFont(skinmod.role_font(self.font(), "tiny"))
        p.drawText(QRectF(4, 2, 80, 14), Qt.AlignmentFlag.AlignLeft, "+24 dB")
        p.drawText(QRectF(4, h - 14, 80, 12), Qt.AlignmentFlag.AlignLeft, "−24 dB")


def label(text, dim=True):
    l = QLabel(text)
    if dim:
        l.setObjectName("dimLabel")
    return l
