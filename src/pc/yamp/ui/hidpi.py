# -*- coding: utf-8 -*-
"""고해상도(HiDPI) 도우미 (vr0.1.0.016, f29 G4 · G5 · G6)

  dpr(w)          위젯이 있는 화면의 배율 (1.0 · 1.25 · 1.5 · 2.0 …)
  hi_pixmap(...)  그림을 '표시 크기 × 배율' 실제 픽셀로 줄이고 devicePixelRatio 지정 → 배율과 상관없이 선명
  snap(v, width)  1px(홀수 폭) 선을 픽셀 가운데(.5)에 — 안티앨리어싱으로 두 픽셀에 번지지 않게
"""
import math

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QImage, QPixmap


def dpr(w=None) -> float:
    try:
        if w is not None:
            v = float(w.devicePixelRatioF())
            if v > 0:
                return v
    except (AttributeError, RuntimeError):
        pass
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance()
    scr = app.primaryScreen() if app is not None else None
    return float(scr.devicePixelRatio()) if scr is not None else 1.0


def hi_pixmap(src, w: int, h: int | None = None, ratio: float = 1.0, expand: bool = False) -> QPixmap:
    """src(QImage · QPixmap · bytes) → 논리 크기 w×h 를 ratio 배 실제 픽셀로 (원본이 작으면 원본 크기까지만)"""
    h = w if h is None else h
    if isinstance(src, (bytes, bytearray)):
        img = QImage()
        if not img.loadFromData(bytes(src)):
            return QPixmap()
        src = img
    pm = QPixmap.fromImage(src) if isinstance(src, QImage) else QPixmap(src)
    if pm.isNull():
        return pm
    pm.setDevicePixelRatio(1.0)
    ratio = max(1.0, float(ratio))
    tw, th = max(1, math.ceil(w * ratio)), max(1, math.ceil(h * ratio))
    mode = Qt.AspectRatioMode.KeepAspectRatioByExpanding if expand else Qt.AspectRatioMode.KeepAspectRatio
    out = pm.scaled(QSize(tw, th), mode, Qt.TransformationMode.SmoothTransformation)
    if expand and (out.width() > tw or out.height() > th):          # 가운데 자르기 (정사각 표지 칸)
        out = out.copy((out.width() - tw) // 2, (out.height() - th) // 2, tw, th)
    out.setDevicePixelRatio(ratio)
    return out


def snap(v: float, width: float = 1.0) -> float:
    """선 폭이 홀수 px 이면 x.5, 짝수면 정수 좌표 (논리 좌표 기준, 100 % 에서 정확 · 분수 배율에서도 덜 번짐)"""
    if int(round(width)) % 2 == 1:
        return math.floor(v) + 0.5
    return float(round(v))
