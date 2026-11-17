# -*- coding: utf-8 -*-
"""직접 그리는 위젯 공통 도우미 (vr0.1.0.019 R5 — ui/neon.py 에서 나눔): 테마 따라가기 · 밴드 색 · 빛 펜"""
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPen

from . import skin as skinmod


def band_color(s, i: int) -> QColor:
    """밴드 색. 밝은 테마는 옅은 앞쪽 색(흰 바탕에서 안 보임)을 건너뛰고 진한 쪽(4..10)으로 펼침"""
    b = s.bands
    return QColor(b[i] if s.dark else b[min(len(b) - 1, 4 + round(i * 0.6))])


class _Skinned:
    """직접 그리는 위젯 공통: 지금 테마를 따라가고 set_skin 이 오면 다시 그림"""
    def set_skin(self, _s=None):
        self.update()

    @property
    def skin(self):
        return skinmod.current()


def _glow_pen(color: QColor, width: float, alpha: int):
    c = QColor(color)
    c.setAlpha(alpha)
    pen = QPen(c, width)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    return pen
