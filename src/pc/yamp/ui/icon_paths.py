# -*- coding: utf-8 -*-
"""아이콘 모양 표 (vr0.1.0.019 R12 — ui/icons.py 에서 나눔)
path(name) → (QPainterPath, 채우기 여부) · 24x24 좌표 · Android ui/Icons.kt 와 같은 모양.
새 아이콘은 여기에 모양만 추가 (그리기 · 색 · 캐시 · 배율 맞춤은 icons.py)."""
import math

from PyQt6.QtCore import QPointF, QRectF
from PyQt6.QtGui import QPainterPath


def _p():
    return QPainterPath()


def path(name: str) -> tuple[QPainterPath, bool]:
    """(경로, 채우기 여부) — 24x24 좌표"""
    p = _p()
    fill = False
    if name == "play":
        p.moveTo(8, 5); p.lineTo(19, 12); p.lineTo(8, 19); p.closeSubpath(); fill = True
    elif name == "pause":
        p.addRoundedRect(QRectF(6, 5, 4, 14), 1, 1); p.addRoundedRect(QRectF(14, 5, 4, 14), 1, 1); fill = True
    elif name == "stop":
        p.addRoundedRect(QRectF(6, 6, 12, 12), 2, 2); fill = True
    elif name == "prev":
        p.addRect(QRectF(5, 5, 2.4, 14)); p.moveTo(19, 5); p.lineTo(9, 12); p.lineTo(19, 19); p.closeSubpath(); fill = True
    elif name == "next":
        p.addRect(QRectF(16.6, 5, 2.4, 14)); p.moveTo(5, 5); p.lineTo(15, 12); p.lineTo(5, 19); p.closeSubpath(); fill = True
    elif name == "shuffle":
        p.moveTo(3, 7); p.lineTo(7, 7); p.cubicTo(12, 7, 12, 17, 17, 17); p.lineTo(20, 17)
        p.moveTo(3, 17); p.lineTo(7, 17); p.cubicTo(9.5, 17, 10.5, 14.5, 11.3, 12.6)
        p.moveTo(13.2, 10); p.cubicTo(14, 8.5, 15, 7, 17, 7); p.lineTo(20, 7)
        p.moveTo(18, 5); p.lineTo(20, 7); p.lineTo(18, 9); p.moveTo(18, 15); p.lineTo(20, 17); p.lineTo(18, 19)
    elif name in ("repeat", "repeat1", "repeatOff"):
        p.moveTo(5, 11); p.lineTo(5, 9); p.cubicTo(5, 7.9, 5.9, 7, 7, 7); p.lineTo(19, 7)
        p.moveTo(17, 5); p.lineTo(19, 7); p.lineTo(17, 9)
        p.moveTo(19, 13); p.lineTo(19, 15); p.cubicTo(19, 16.1, 18.1, 17, 17, 17); p.lineTo(5, 17)
        p.moveTo(7, 15); p.lineTo(5, 17); p.lineTo(7, 19)
        if name == "repeat1":
            p.moveTo(11, 10.5); p.lineTo(12.5, 9.5); p.lineTo(12.5, 14.5)
        if name == "repeatOff":
            p.moveTo(4, 4); p.lineTo(20, 20)
    elif name in ("heart", "heartOutline"):
        p.moveTo(12, 20.5)
        p.cubicTo(5, 15.5, 3, 12.5, 3, 9); p.cubicTo(3, 6.2, 5.2, 4.2, 7.8, 4.2); p.cubicTo(9.6, 4.2, 11, 5.2, 12, 6.6)
        p.cubicTo(13, 5.2, 14.4, 4.2, 16.2, 4.2); p.cubicTo(18.8, 4.2, 21, 6.2, 21, 9); p.cubicTo(21, 12.5, 19, 15.5, 12, 20.5)
        p.closeSubpath(); fill = name == "heart"
    elif name == "moon":
        p.moveTo(20, 14.5); p.cubicTo(18.6, 15.2, 17.1, 15.6, 15.5, 15.6); p.cubicTo(10.3, 15.6, 6.5, 11.6, 6.5, 6.5)
        p.cubicTo(6.5, 5.6, 6.6, 4.8, 6.9, 4); p.cubicTo(3.5, 5.3, 1.6, 8.6, 2.1, 12.2); p.cubicTo(2.6, 16.4, 6.1, 19.6, 10.4, 19.9)
        p.cubicTo(14.6, 20.2, 18.4, 17.9, 20, 14.5); p.closeSubpath(); fill = True
    elif name == "folder":
        p.moveTo(3, 7); p.cubicTo(3, 5.9, 3.9, 5, 5, 5); p.lineTo(9, 5); p.lineTo(11, 7); p.lineTo(19, 7)
        p.cubicTo(20.1, 7, 21, 7.9, 21, 9); p.lineTo(21, 17); p.cubicTo(21, 18.1, 20.1, 19, 19, 19); p.lineTo(5, 19)
        p.cubicTo(3.9, 19, 3, 18.1, 3, 17); p.closeSubpath()
    elif name == "star":
        pts = [(12, 3), (14.5, 9), (21, 9.5), (16, 13.8), (17.6, 20), (12, 16.7), (6.4, 20), (8, 13.8), (3, 9.5), (9.5, 9)]
        p.moveTo(*pts[0])
        for x, y in pts[1:]:
            p.lineTo(x, y)
        p.closeSubpath()
    elif name == "starFill":
        q, _ = path("star"); return q, True
    elif name == "list":
        for y in (6, 12, 18):
            p.moveTo(4, y); p.lineTo(20 if y < 18 else 14, y)
    elif name == "eq":
        for x, y in ((5, 10), (10, 4), (15, 12), (20, 7)):
            p.moveTo(x, 20); p.lineTo(x, y)
    elif name == "more":
        for y in (5, 12, 19):
            p.addEllipse(QPointF(12, y), 1.8, 1.8)
        fill = True
    elif name == "plus":
        p.moveTo(12, 5); p.lineTo(12, 19); p.moveTo(5, 12); p.lineTo(19, 12)
    elif name == "chevronDown":
        p.moveTo(6, 9); p.lineTo(12, 15); p.lineTo(18, 9)
    elif name == "chevronRight":
        p.moveTo(9, 6); p.lineTo(15, 12); p.lineTo(9, 18)
    elif name == "eject":
        p.moveTo(12, 5); p.lineTo(19, 13); p.lineTo(5, 13); p.closeSubpath(); p.addRect(QRectF(5, 16, 14, 2.5)); fill = True
    elif name == "volume":
        p.moveTo(4, 9); p.lineTo(8, 9); p.lineTo(13, 5); p.lineTo(13, 19); p.lineTo(8, 15); p.lineTo(4, 15); p.closeSubpath()
        p.moveTo(16, 9); p.cubicTo(17.5, 10.5, 17.5, 13.5, 16, 15); p.moveTo(18.5, 6.5); p.cubicTo(21.5, 9.5, 21.5, 14.5, 18.5, 17.5)
    elif name == "mute":
        p.moveTo(4, 9); p.lineTo(8, 9); p.lineTo(13, 5); p.lineTo(13, 19); p.lineTo(8, 15); p.lineTo(4, 15); p.closeSubpath()
        p.moveTo(16, 9); p.lineTo(21, 15); p.moveTo(21, 9); p.lineTo(16, 15)
    elif name == "lyrics":
        p.addRoundedRect(QRectF(4, 4, 16, 16), 3, 3); p.moveTo(8, 9); p.lineTo(16, 9); p.moveTo(8, 12.5); p.lineTo(16, 12.5)
        p.moveTo(8, 16); p.lineTo(13, 16)
    elif name == "ab":
        p.moveTo(3, 17); p.lineTo(6, 7); p.lineTo(9, 17); p.moveTo(4.2, 13.5); p.lineTo(7.8, 13.5)
        p.moveTo(14, 7); p.lineTo(14, 17); p.lineTo(18, 17); p.cubicTo(21, 17, 21, 12, 18, 12); p.lineTo(14, 12)
        p.moveTo(14, 7); p.lineTo(17.5, 7); p.cubicTo(20, 7, 20, 12, 17.5, 12)
    elif name == "speed":
        p.moveTo(4, 16); p.cubicTo(4, 9, 9, 5, 12, 5); p.cubicTo(15, 5, 20, 9, 20, 16); p.moveTo(12, 15); p.lineTo(16, 9)
    elif name == "refresh":
        p.moveTo(19, 12); p.cubicTo(19, 16, 15.9, 19, 12, 19); p.cubicTo(8.1, 19, 5, 15.9, 5, 12); p.cubicTo(5, 8.1, 8.1, 5, 12, 5)
        p.lineTo(16, 5); p.moveTo(14, 3); p.lineTo(16, 5); p.lineTo(14, 7)
    # ---- vr0.1.0.009 단순 화면용
    elif name == "now":
        p.addEllipse(QPointF(12, 12), 8.5, 8.5); p.moveTo(10, 8.5); p.lineTo(15.5, 12); p.lineTo(10, 15.5); p.closeSubpath()
    elif name == "library":
        p.addRoundedRect(QRectF(4, 4, 4, 16), 1, 1); p.addRoundedRect(QRectF(10, 4, 4, 16), 1, 1)
        p.moveTo(16.5, 5); p.lineTo(20, 19)
    elif name == "grid":
        for x, y in ((4, 4), (13, 4), (4, 13), (13, 13)):
            p.addRoundedRect(QRectF(x, y, 7, 7), 1.5, 1.5)
    elif name == "listView":
        for y in (6, 12, 18):
            p.addEllipse(QPointF(5, y), 1, 1); p.moveTo(9, y); p.lineTo(20, y)
    elif name == "search":
        p.addEllipse(QPointF(11, 11), 6, 6); p.moveTo(15.5, 15.5); p.lineTo(20, 20)
    elif name == "close":
        p.moveTo(6, 6); p.lineTo(18, 18); p.moveTo(18, 6); p.lineTo(6, 18)
    elif name == "gear":
        p.addEllipse(QPointF(12, 12), 3.2, 3.2)
        import math as _m
        for k in range(8):
            a = _m.radians(k * 45)
            p.moveTo(12 + 6 * _m.cos(a), 12 + 6 * _m.sin(a)); p.lineTo(12 + 9 * _m.cos(a), 12 + 9 * _m.sin(a))
        p.addEllipse(QPointF(12, 12), 6.2, 6.2)
    elif name == "help":
        p.addEllipse(QPointF(12, 12), 9, 9); p.moveTo(9.3, 9.5); p.cubicTo(9.3, 6.5, 14.7, 6.5, 14.7, 9.5)
        p.cubicTo(14.7, 11.5, 12, 11.5, 12, 14); p.moveTo(12, 17); p.lineTo(12, 17.3)
    elif name == "queue":
        p.moveTo(4, 6); p.lineTo(16, 6); p.moveTo(4, 11); p.lineTo(16, 11); p.moveTo(4, 16); p.lineTo(11, 16)
        p.moveTo(15, 14); p.lineTo(20, 17); p.lineTo(15, 20); p.closeSubpath()
    elif name == "mini":
        p.addRoundedRect(QRectF(3, 5, 18, 14), 2, 2); p.addRoundedRect(QRectF(12, 12, 7, 5), 1, 1)
    elif name == "power":
        p.moveTo(12, 3); p.lineTo(12, 11)
        p.moveTo(7.5, 6.5); p.cubicTo(3, 10.5, 5.5, 20, 12, 20); p.cubicTo(18.5, 20, 21, 10.5, 16.5, 6.5)
    elif name == "undo":
        p.moveTo(9, 5); p.lineTo(4, 10); p.lineTo(9, 15); p.moveTo(4, 10); p.lineTo(14, 10)
        p.cubicTo(18, 10, 20, 12.5, 20, 15); p.cubicTo(20, 17.5, 18, 20, 14, 20); p.lineTo(11, 20)
    elif name == "trash":
        p.moveTo(4, 7); p.lineTo(20, 7); p.moveTo(9, 7); p.lineTo(9, 4); p.lineTo(15, 4); p.lineTo(15, 7)
        p.moveTo(6, 7); p.lineTo(7, 20); p.lineTo(17, 20); p.lineTo(18, 7); p.moveTo(10, 11); p.lineTo(10, 16)
        p.moveTo(14, 11); p.lineTo(14, 16)
    elif name == "stamp":
        p.moveTo(6, 21); p.lineTo(6, 4); p.lineTo(18, 4); p.lineTo(15, 8); p.lineTo(18, 12); p.lineTo(6, 12)
    elif name == "back01":
        p.moveTo(11, 6); p.lineTo(5, 12); p.lineTo(11, 18); p.moveTo(14, 12); p.lineTo(20, 12)
    elif name == "fwd01":
        p.moveTo(13, 6); p.lineTo(19, 12); p.lineTo(13, 18); p.moveTo(4, 12); p.lineTo(10, 12)
    elif name == "pin":
        p.moveTo(9, 3); p.lineTo(15, 3); p.lineTo(14, 9); p.lineTo(18, 13); p.lineTo(6, 13); p.lineTo(10, 9); p.closeSubpath()
        p.moveTo(12, 13); p.lineTo(12, 21)
    elif name == "comp":
        p.moveTo(3, 18); p.lineTo(10, 11); p.lineTo(21, 7); p.moveTo(3, 21); p.lineTo(21, 21); p.moveTo(3, 3); p.lineTo(3, 21)
    elif name == "limit":
        p.moveTo(3, 6); p.lineTo(21, 6); p.moveTo(3, 18); p.cubicTo(7, 6, 9, 6, 11, 6); p.lineTo(21, 6)
        p.moveTo(3, 21); p.lineTo(21, 21)
    elif name == "clock":
        p.addEllipse(QPointF(12, 13), 8, 8); p.moveTo(12, 9); p.lineTo(12, 13); p.lineTo(15, 15)
        p.moveTo(4, 5); p.lineTo(7, 3); p.moveTo(20, 5); p.lineTo(17, 3)
    elif name == "smart":
        p.moveTo(12, 3); p.lineTo(13.8, 9); p.lineTo(20, 10.5); p.lineTo(13.8, 12.5); p.lineTo(12, 19)
        p.lineTo(10.2, 12.5); p.lineTo(4, 10.5); p.lineTo(10.2, 9); p.closeSubpath()
    elif name == "check":
        p.moveTo(5, 12.5); p.lineTo(10, 17); p.lineTo(19, 7)
    elif name == "addFile":
        p.moveTo(6, 3); p.lineTo(14, 3); p.lineTo(19, 8); p.lineTo(19, 21); p.lineTo(6, 21); p.closeSubpath()
        p.moveTo(12.5, 10); p.lineTo(12.5, 17); p.moveTo(9, 13.5); p.lineTo(16, 13.5)
    elif name == "addFolder":
        q, _ = path("folder"); p.addPath(q); p.moveTo(12, 10); p.lineTo(12, 16); p.moveTo(9, 13); p.lineTo(15, 13)
    elif name == "stage":
        p.addRoundedRect(QRectF(3, 4, 18, 12), 2, 2); p.moveTo(8, 20); p.lineTo(16, 20); p.moveTo(12, 16); p.lineTo(12, 20)
    elif name == "save":
        p.addRoundedRect(QRectF(4, 4, 16, 16), 2, 2); p.addRect(QRectF(8, 4, 8, 5)); p.addRect(QRectF(7, 13, 10, 7))
    elif name == "sidePanel":
        p.addRoundedRect(QRectF(3, 4, 18, 16), 2, 2); p.moveTo(14, 4); p.lineTo(14, 20)
    elif name == "wave":                      # v014 소리 시각화: 파동
        p.moveTo(2, 12); p.cubicTo(4, 4, 6, 4, 8, 12); p.cubicTo(10, 20, 12, 20, 14, 12); p.cubicTo(16, 4, 18, 4, 20, 12)
        p.lineTo(22, 12)
    elif name == "chart":                     # v014 소리 시각화: 레벨 차트
        p.moveTo(3, 4); p.lineTo(3, 20); p.lineTo(21, 20)
        p.moveTo(6, 16); p.lineTo(10, 10); p.lineTo(13, 13); p.lineTo(17, 6); p.lineTo(20, 9)
    elif name == "radial":                    # v027 비주얼라이저: 원형 스펙트럼
        p.addEllipse(QPointF(12, 12), 4, 4)
        for k in range(8):
            a = math.pi * k / 4
            p.moveTo(12 + 6 * math.cos(a), 12 + 6 * math.sin(a))
            p.lineTo(12 + (9.5 if k % 2 else 8) * math.cos(a), 12 + (9.5 if k % 2 else 8) * math.sin(a))
    elif name == "gram":                      # v027 비주얼라이저: 스펙트로그램 (색 칸)
        p.addRoundedRect(QRectF(3, 4, 18, 16), 2, 2)
        p.moveTo(3, 12); p.lineTo(21, 12); p.moveTo(9, 4); p.lineTo(9, 20); p.moveTo(15, 4); p.lineTo(15, 20)
    elif name == "menu":                      # v014 메뉴 막대 접기/펼치기
        p.moveTo(4, 7); p.lineTo(20, 7); p.moveTo(4, 12); p.lineTo(20, 12); p.moveTo(4, 17); p.lineTo(20, 17)
    else:
        p.addEllipse(QPointF(12, 12), 6, 6)
    return p, fill


NAMES = ("play", "pause", "stop", "prev", "next", "shuffle", "repeat", "repeat1", "repeatOff", "heart", "heartOutline",
         "moon", "folder", "star", "starFill", "list", "eq", "more", "plus", "chevronDown", "chevronRight", "eject",
         "volume", "mute", "lyrics", "ab", "speed", "refresh",
         "now", "library", "grid", "listView", "search", "close", "gear", "help", "queue", "mini", "power", "undo",
         "trash", "stamp", "back01", "fwd01", "pin", "comp", "limit", "clock", "smart", "check", "addFile",
         "addFolder", "stage", "save", "sidePanel", "wave", "chart", "menu", "radial", "gram")
