# -*- coding: utf-8 -*-
"""앱 아이콘 (vr0.1.0.033, f61 H7) — 창 제목 줄 · 작업 표시줄 · Alt+Tab · 트레이 · exe 파일

전에는 앱 아이콘이 없어 Qt 기본 그림(트레이는 스타일의 작은 재생 그림)이 나왔고, 큰 화면 · 고배율에서 흐렸음.
Android 런처 아이콘(res/drawable/ic_launcher_*.xml: 어두운 바탕 + 초록 스펙트럼 막대 6개 + 금색 바닥선)과 같은 모양을
벡터로 그려 요청한 크기 × 화면 배율로 그때그때 만듦 → 16px ~ 256px · 100 ~ 300 % 어디서나 또렷.
작은 크기(32px 이하)에서는 막대 · 바닥선 가장자리를 픽셀 경계에 맞춤 (번짐 없음).

  app_icon()            QIcon (QApplication.setWindowIcon 에)
  render(side)          side×side QImage (ICO 만들기 · 테스트)
  write_ico(path)       여러 크기를 담은 Windows .ico (PNG 형식 항목) — build.sh exe 가 PyInstaller --icon 으로
"""
import struct

from PyQt6.QtCore import QByteArray, QBuffer, QIODevice, QRectF, Qt
from PyQt6.QtGui import QColor, QIcon, QIconEngine, QImage, QPainter, QPainterPath, QPixmap

# Android ic_launcher (108 단위 보기 영역) 와 같은 값 — 둥근 사각형은 안전 영역 18..90 (72 단위)
from .themes import APP_ICON

BG, BAR, BASE = APP_ICON["bg"], APP_ICON["bar"], APP_ICON["base"]     # 색 표는 themes.py 한 곳 (색 직접 쓰기 금지 규칙)
BARS = ((30, 56), (39, 46), (48, 38), (57, 50), (66, 42), (75, 58))    # (x, 위 y) · 폭 6 · 아래 y 70
BAR_W, BAR_BOTTOM = 6, 70
BASE_LINE = (28, 74, 54, 4)                                             # x, y, 폭, 높이
FRAME = (18.0, 72.0)                                                    # 보기 영역 안 아이콘 테두리 (시작, 크기)
ICO_SIZES = (16, 20, 24, 32, 40, 48, 64, 96, 128, 256)


def draw(p: QPainter, side: float):
    """side × side 실제 픽셀에 아이콘을 그림"""
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    k = side / FRAME[1]
    o = FRAME[0]
    snap = side <= 32                                                   # 작은 크기 = 픽셀 경계에 맞춤

    def px(v):                                                          # 108 단위 → 픽셀
        x = (v - o) * k
        return float(round(x)) if snap else x
    bg = QPainterPath()
    m = max(0.5, side * 0.02)
    bg.addRoundedRect(QRectF(m, m, side - 2 * m, side - 2 * m), side * 0.22, side * 0.22)
    p.fillPath(bg, QColor(BG))
    for x, top in BARS:
        x0, x1 = px(x), px(x + BAR_W)
        if snap and x1 - x0 < 1:
            x1 = x0 + 1
        p.fillRect(QRectF(x0, px(top), x1 - x0, px(BAR_BOTTOM) - px(top)), QColor(BAR))
    bx, by, bw, bh = BASE_LINE
    y0, y1 = px(by), px(by + bh)
    if snap and y1 - y0 < 1:
        y1 = y0 + 1
    p.fillRect(QRectF(px(bx), y0, px(bx + bw) - px(bx), y1 - y0), QColor(BASE))


def render(side: int) -> QImage:
    img = QImage(side, side, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    draw(p, side)
    p.end()
    return img


class _AppEngine(QIconEngine):
    def __init__(self):
        super().__init__()
        self._cache: dict = {}

    def scaledPixmap(self, size, mode, state, scale):
        side = max(1, round(min(size.width(), size.height()) * scale))
        pm = self._cache.get(side)
        if pm is None:
            pm = QPixmap.fromImage(render(side))
            if len(self._cache) > 12:
                self._cache.clear()
            self._cache[side] = pm
        out = QPixmap(pm)
        out.setDevicePixelRatio(scale)
        return out

    def pixmap(self, size, mode, state):
        return self.scaledPixmap(size, mode, state, 1.0)

    def paint(self, painter, rect, mode, state):
        d = float(painter.device().devicePixelRatioF()) if painter.device() is not None else 1.0
        painter.drawPixmap(rect, self.scaledPixmap(rect.size(), mode, state, d))

    def availableSizes(self, mode=QIcon.Mode.Normal, state=QIcon.State.Off):
        from PyQt6.QtCore import QSize
        return [QSize(n, n) for n in ICO_SIZES]

    def clone(self):
        return _AppEngine()


_ICON = None


def app_icon() -> QIcon:
    global _ICON
    if _ICON is None:
        _ICON = QIcon(_AppEngine())
    return _ICON


def _png(img: QImage) -> bytes:
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    img.save(buf, "PNG")
    buf.close()
    return bytes(ba)


def ico_bytes(sizes=ICO_SIZES) -> bytes:
    """Windows ICO: 머리(6바이트) + 항목(16바이트 × n) + PNG 들 (Vista 이후 모든 크기 PNG 항목 지원)"""
    pngs = [(n, _png(render(n))) for n in sizes]
    out = struct.pack("<HHH", 0, 1, len(pngs))
    off = 6 + 16 * len(pngs)
    for n, data in pngs:
        out += struct.pack("<BBBBHHII", n % 256, n % 256, 0, 0, 1, 32, len(data), off)
        off += len(data)
    return out + b"".join(d for _, d in pngs)


def write_ico(path, sizes=ICO_SIZES) -> int:
    data = ico_bytes(sizes)
    with open(path, "wb") as f:
        f.write(data)
    return len(data)
