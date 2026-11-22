# -*- coding: utf-8 -*-
"""
직접 그린 벡터 아이콘 (QPainterPath) — 글꼴 기호(⏾ 🔀 등)는 PC·폰 글꼴에 따라 네모(□)로 깨질 수 있어 대체.
Android ui/Icons.kt 와 같은 24x24 좌표계 모양 (모양 표 = icon_paths.py, 여기는 그리기 · 색 · 캐시 · 배율 맞춤 — v019 R12).
"""
import math
from functools import lru_cache

from PyQt6.QtCore import QPointF, QRectF, QSize, Qt
from PyQt6.QtGui import QColor, QIcon, QIconEngine, QPainter, QPainterPath, QPen, QPixmap, QTransform

from . import skin
from .icon_paths import NAMES, path  # noqa: F401  (v019 R12: 모양 표는 icon_paths.py — icons.path · icons.NAMES 그대로)


def icon(name: str, color: str | None = None, size: int = 24, stroke: float = 2.0) -> QIcon:
    """color: 토큰 이름('text' · 'dim' · 'accent_text' · 'on_fill' …) 또는 #rrggbb. None = 지금 테마의 text"""
    return _icon(name, skin.color(color), size, stroke)


class _VecEngine(QIconEngine):
    """v014 (f26 §3.5): 벡터 아이콘 엔진 — 요청된 크기 × 화면 배율(125·150·175·200·300%)로 그때그때 그림 → 늘 선명.
    (예전: 2배 픽스맵 1장 → 125·150·175% 에서 축소/확대 흐림)"""

    def __init__(self, name: str, color: str, stroke: float):
        super().__init__()
        self.name, self.color, self.stroke = name, color, stroke
        self._cache: dict = {}

    def paint(self, painter, rect, mode, state):
        painter.save()
        if mode == QIcon.Mode.Disabled:
            painter.setOpacity(0.38)
        _draw(painter, self.name, self.color, self.stroke, QRectF(rect))
        painter.restore()

    def scaledPixmap(self, size, mode, state, scale):
        key = (size.width(), size.height(), int(mode.value), float(scale))
        pm = self._cache.get(key)
        if pm is None:
            w, h = max(1, round(size.width() * scale)), max(1, round(size.height() * scale))
            pm = QPixmap(w, h)
            pm.fill(Qt.GlobalColor.transparent)
            p = QPainter(pm)
            if mode == QIcon.Mode.Disabled:
                p.setOpacity(0.38)
            _draw(p, self.name, self.color, self.stroke, QRectF(0, 0, w, h))
            p.end()
            pm.setDevicePixelRatio(scale)
            if len(self._cache) > 12:
                self._cache.clear()
            self._cache[key] = pm
        return pm

    def pixmap(self, size, mode, state):
        return self.scaledPixmap(size, mode, state, 1.0)

    def clone(self):
        return _VecEngine(self.name, self.color, self.stroke)


@lru_cache(maxsize=256)       # vr0.1.0.008: 같은 (이름·색·크기) 아이콘은 다시 만들지 않음
def _icon(name: str, color: str, size: int = 24, stroke: float = 2.0) -> QIcon:
    return QIcon(_VecEngine(name, color, stroke))


def _draw(p: QPainter, name: str, color: str, stroke: float, r: QRectF):
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.translate(r.x(), r.y())
    p.scale(r.width() / 24.0, r.height() / 24.0)
    pth, fill = path(name)
    c = QColor(skin.color(color))
    if fill:
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(c)
    else:
        # v017: 실제 픽셀 격자에 맞춰 그림 — 선 굵기 = 정수 px, 직선 끝점 = 픽셀 경계(홀수 굵기는 .5)
        #   (125 · 150 % 에서 2.5px 선 · 반 픽셀 위치 → 두 줄로 번지던 것 방지. 곡선은 모양 유지)
        dev = p.device()
        d = float(dev.devicePixelRatioF()) if dev is not None else 1.0       # 위젯에 바로 그릴 때(배율) 포함
        t = p.worldTransform() * QTransform.fromScale(d, d)
        k = abs(t.m11()) or 1.0
        spx = max(1, round(stroke * k))
        dp = t.map(pth)
        off = 0.5 if spx % 2 else 0.0
        snap_types = (QPainterPath.ElementType.MoveToElement, QPainterPath.ElementType.LineToElement)
        for i in range(dp.elementCount()):
            e = dp.elementAt(i)
            if e.type in snap_types:
                dp.setElementPositionAt(i, math.floor(e.x) + off if off else round(e.x),
                                        math.floor(e.y) + off if off else round(e.y))
        p.setWorldTransform(QTransform.fromScale(1 / d, 1 / d))
        pth = dp
        pen = QPen(c, spx)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawPath(pth)


def paint(device, name: str, color: str, stroke: float = 2.0, rect: QRectF | None = None):
    p = QPainter(device)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    r = rect or QRectF(0, 0, device.width(), device.height())
    p.translate(r.x(), r.y())
    p.scale(r.width() / 24.0, r.height() / 24.0)
    pth, fill = path(name)
    c = QColor(skin.color(color))
    if fill:
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(c)
    else:
        # v017: 실제 픽셀 격자에 맞춰 그림 — 선 굵기 = 정수 px, 직선 끝점 = 픽셀 경계(홀수 굵기는 .5)
        #   (125 · 150 % 에서 2.5px 선 · 반 픽셀 위치 → 두 줄로 번지던 것 방지. 곡선은 모양 유지)
        dev = p.device()
        d = float(dev.devicePixelRatioF()) if dev is not None else 1.0       # 위젯에 바로 그릴 때(배율) 포함
        t = p.worldTransform() * QTransform.fromScale(d, d)
        k = abs(t.m11()) or 1.0
        spx = max(1, round(stroke * k))
        dp = t.map(pth)
        off = 0.5 if spx % 2 else 0.0
        snap_types = (QPainterPath.ElementType.MoveToElement, QPainterPath.ElementType.LineToElement)
        for i in range(dp.elementCount()):
            e = dp.elementAt(i)
            if e.type in snap_types:
                dp.setElementPositionAt(i, math.floor(e.x) + off if off else round(e.x),
                                        math.floor(e.y) + off if off else round(e.y))
        p.setWorldTransform(QTransform.fromScale(1 / d, 1 / d))
        pth = dp
        pen = QPen(c, spx)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawPath(pth)
    p.end()


def _swatch_draw(p: QPainter, S: float, colors, on: bool, s=None):
    """색 견본 한 장을 S×S 실제 픽셀에 그림 (선 굵기 · 모서리는 S 에 비례 — 예전 36px 그림과 같은 비율)"""
    u = S / 36.0
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    clip = QPainterPath()
    clip.addRoundedRect(QRectF(2 * u, 2 * u, S - 4 * u, S - 4 * u), 7 * u, 7 * u)
    p.setClipPath(clip)
    if colors:
        cw = S / len(colors)
        for i, c in enumerate(colors):
            p.fillRect(QRectF(i * cw, 0, cw + 1, S), QColor(c))
    p.setClipping(False)
    s = s or skin.current()
    p.setPen(QPen(QColor(s.fill2 if on else s.knob_rim), max(1.0, (3 if on else 2) * u)))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawPath(clip)
    if on:                                     # 고른 것: 가운데 체크 표시 (흰 원 + 진회색 체크)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(s.surface))
        p.drawEllipse(QPointF(S / 2, S / 2), S * 0.26, S * 0.26)
        pen = QPen(QColor(s.accent_text), max(1.0, 3 * u))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        ck = QPainterPath()
        ck.moveTo(S * 0.38, S * 0.5); ck.lineTo(S * 0.47, S * 0.6); ck.lineTo(S * 0.63, S * 0.41)
        p.drawPath(ck)


def _swatch_pm(colors, on: bool, side: int, ratio: float = 2.0) -> QPixmap:
    """(예전 이름 그대로) 고정 배율 그림 한 장"""
    S = max(1, round(side * ratio))
    pm = QPixmap(S, S)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    _swatch_draw(p, S, colors, on)
    p.end()
    pm.setDevicePixelRatio(ratio)
    return pm


class _SwatchEngine(QIconEngine):
    """v033 (f61 H8): 색 견본 · 켜기 표시도 요청 크기 × 화면 배율로 그때그때 그림 (예전: 2배 그림 1장 →
    큰 글자(메뉴 아이콘이 커짐) · 300 % 화면에서 늘려 흐림). 그릴 때의 테마 색을 기억 (테마가 바뀌면 apply_skin 이 새로 만듦)"""

    def __init__(self, off_colors, on_colors):
        super().__init__()
        self.off_colors, self.on_colors = tuple(off_colors), tuple(on_colors)
        self.s = skin.current()
        self._cache: dict = {}

    def scaledPixmap(self, size, mode, state, scale):
        on = state == QIcon.State.On
        key = (size.width(), size.height(), on, float(scale))
        pm = self._cache.get(key)
        if pm is None:
            S = max(1, round(min(size.width(), size.height()) * scale))
            pm = QPixmap(S, S)
            pm.fill(Qt.GlobalColor.transparent)
            p = QPainter(pm)
            if mode == QIcon.Mode.Disabled:
                p.setOpacity(0.38)
            _swatch_draw(p, S, self.on_colors if on else self.off_colors, on, self.s)
            p.end()
            pm.setDevicePixelRatio(scale)
            if len(self._cache) > 8:
                self._cache.clear()
            self._cache[key] = pm
        return pm

    def pixmap(self, size, mode, state):
        return self.scaledPixmap(size, mode, state, 1.0)

    def paint(self, painter, rect, mode, state):
        d = float(painter.device().devicePixelRatioF()) if painter.device() is not None else 1.0
        painter.drawPixmap(rect, self.scaledPixmap(rect.size(), mode, state, d))

    def clone(self):
        e = _SwatchEngine(self.off_colors, self.on_colors)
        e.s = self.s
        return e


def swatch(colors, side: int = 18) -> QIcon:
    """테마 메뉴 색 견본 (3칸: 배경 · fill1 · fill2). 체크된 메뉴 항목은 On 그림 (테두리 + 체크)"""
    return QIcon(_SwatchEngine(colors, colors))


def toggle(side: int = 18) -> QIcon:
    """켜고 끄는 메뉴 항목 표시 (끔: 빈 칸 / 켬: 채움 + 체크) — 테마 색"""
    s = skin.current()
    return QIcon(_SwatchEngine((s.surface,), (s.fill1,)))


# ---- 테마가 바뀌면 다시 칠할 고정 아이콘 (검색 칸 돋보기 · 탭 아이콘 등) — bind(owner, setter, 이름, 토큰)
#   v011b: 주인 위젯(owner)을 함께 기억하고, 주인이 지워지면 목록에서 뺌.
#   (예전: QLineEdit.addAction 이 돌려준 QAction 의 setIcon 을 그대로 기억 → 창이 닫힌 뒤 테마를 바꾸면
#    이미 지워진 C++ 객체를 불러 Windows 에서 access violation — 파이썬 예외로 잡히지 않음)
_bound: list = []


def _alive(obj) -> bool:
    try:
        from PyQt6 import sip
        return obj is not None and not sip.isdeleted(obj)
    except Exception:  # noqa
        return False


def bind(owner, setter, name: str, color: str = "dim", size: int = 24):
    """setter(QIcon) 를 지금 테마로 부르고, 테마가 바뀌면 refresh_bound() 에서 다시 부름.
    owner = 파이썬에서 만든 위젯(QLineEdit · QTabWidget …) — 지워지면 자동으로 목록에서 빠짐"""
    entry = [owner, setter, name, color, size]
    _bound.append(entry)
    try:
        owner.destroyed.connect(lambda *_a, e=entry: _drop(e))
    except (AttributeError, RuntimeError, TypeError):
        pass
    setter(icon(name, color, size))


def _drop(entry):
    try:
        _bound.remove(entry)
    except ValueError:
        pass


def refresh_bound():
    keep = []
    for entry in list(_bound):
        owner, setter, name, color, size = entry
        if not _alive(owner):                 # 주인 위젯이 지워짐 → 부르지 않고 버림
            continue
        try:
            setter(icon(name, color, size))
            keep.append(entry)
        except RuntimeError:
            pass
    _bound[:] = keep


ICON_SIZE = QSize(20, 20)
