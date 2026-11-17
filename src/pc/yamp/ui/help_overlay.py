# -*- coding: utf-8 -*-
"""
도움말 이름표 오버레이 (F1) — vr0.1.0.009
아이콘만 있는 화면에서 "이 버튼이 뭐지?" 를 한 번에: 보이는 모든 버튼 아래에 이름표를 그림.
아무 곳이나 누르거나 Esc / F1 → 닫힘. 처음 실행 때 한 번 자동으로 보여 줌.
"""
from PyQt6.QtCore import QPoint, QRect, Qt
from PyQt6.QtGui import QColor, QFontMetrics, QPainter, QPen
from PyQt6.QtWidgets import QWidget

from . import skin as skinmod, tips


class HelpOverlay(QWidget):
    def __init__(self, host):
        super().__init__(host)
        self.host = host
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setGeometry(host.rect())
        self.items = self._collect()

    def _collect(self):
        out = []
        for w in self.host.findChildren(QWidget):
            key = w.property("tip_key")
            if not key or not w.isVisible() or w.width() < 8:
                continue
            if w.window() is not self.host:
                continue
            r = QRect(w.mapTo(self.host, QPoint(0, 0)), w.size())
            if not self.host.rect().intersects(r):
                continue
            out.append((r, tips.name(key)))
        return out

    def fonts(self):
        """이름표 = 보조 굵게 · 안내 = 본문 굵게 (v016 G7: 글자 크기 단계)"""
        return skinmod.role_font(self.font(), "cap", bold=True), skinmod.role_font(self.font(), "body", bold=True)

    HINT = "버튼 위에 마우스를 올리면 설명이 나옵니다 — 아무 곳이나 누르면 닫힘 (F1 로 다시 보기)"

    def paintEvent(self, e):
        s = skinmod.current()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), skinmod.qcolor("nav" if s.dark else "text", 170))   # 어둡게 덮기 (밝은 테마도 진회색)
        f, fh = self.fonts()
        fm = QFontMetrics(f)
        hint = hint_box(QFontMetrics(fh), self.HINT, self.width(), self.height())
        boxes = place_labels([r for r, _ in self.items],
                             [(fm.horizontalAdvance(n) + 12, fm.height() + 4) for _, n in self.items],
                             self.width(), self.height(), [hint])
        p.setPen(QPen(QColor(s.fill1), 2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        for r, _ in self.items:
            p.drawRoundedRect(r.adjusted(-2, -2, 2, 2), 6, 6)
        p.setFont(f)
        for (r, name), box in zip(self.items, boxes):
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(s.tooltip_bg))
            p.drawRoundedRect(box, 4, 4)
            p.setPen(QColor(s.text))
            p.drawText(box, Qt.AlignmentFlag.AlignCenter, name)
        # 안내 글: 이름표와 겹치지 않게 미리 비워 둔 칸 (위쪽 가운데, 테두리 상자)
        p.setPen(QPen(QColor(s.fill1), 1))
        p.setBrush(QColor(s.tooltip_bg))
        p.drawRoundedRect(hint, 8, 8)
        p.setPen(QColor(s.text))
        p.setFont(fh)
        p.drawText(hint, Qt.AlignmentFlag.AlignCenter, self.HINT)

    def mousePressEvent(self, e):
        self.close()

    def keyPressEvent(self, e):
        self.close()


# ---------------------------------------------------------------- 배치 (vr0.1.0.015: 글자 겹침 없앰, 테스트용 순수 함수)
def hint_box(fm, text, w, h) -> QRect:
    tw = min(w - 16, fm.horizontalAdvance(text) + 28)
    return QRect((w - tw) // 2, 6, tw, fm.height() + 12)


def place_labels(rects, sizes, w, h, reserved=()) -> list:
    """버튼 rect 마다 이름표 상자 위치.
    후보: 아래 · 위 · 오른쪽 · 왼쪽 (+ 옆으로 민 자리) — 왼쪽 끝 줄(세로 메뉴)은 오른쪽부터, 오른쪽 끝은 왼쪽부터.
    1순위 = 다른 이름표 · 안내 칸 · 다른 버튼과 겹치지 않음, 2순위 = 이름표 · 안내 칸만 안 겹침, 마지막 = 아래로 밀기"""
    placed: list[QRect] = []
    hard = list(reserved)
    out: list = [None] * len(rects)
    order = sorted(range(len(rects)), key=lambda k: rects[k].width() * rects[k].height())   # v016: 작은 버튼부터 (큰 막대는 자리가 많음)
    for i in order:
        r, (tw, th) = rects[i], sizes[i]
        cx, cy = r.center().x(), r.center().y()
        below = QRect(cx - tw // 2, r.bottom() + 5, tw, th)
        above = QRect(cx - tw // 2, r.top() - th - 5, tw, th)
        right = QRect(r.right() + 8, cy - th // 2, tw, th)
        left = QRect(r.left() - tw - 8, cy - th // 2, tw, th)
        if r.right() < w * 0.12:
            cands = [right, right.translated(0, th // 2 + 2), right.translated(0, -th // 2 - 2), below, above]
        elif r.left() > w * 0.88:
            cands = [left, below, above, left.translated(0, th // 2 + 2)]
        else:
            cands = [below, above, below.translated(tw // 2, 0), below.translated(-tw // 2, 0),
                     above.translated(tw // 2, 0), above.translated(-tw // 2, 0),
                     above.translated(0, -th - 2), below.translated(0, th + 2), right, left]   # v016: 한 줄 더 위/아래가 옆보다 먼저
        others = [o for k, o in enumerate(rects) if k != i]
        inside = [_clamp(c, w, h) for c in cands]
        pick = next((c for c in inside if not _hits(c, placed + hard) and not _hits(c, others)), None)
        if pick is None:
            pick = next((c for c in inside if not _hits(c, placed + hard)), None)
        if pick is None:
            pick = inside[0]
            while _hits(pick, placed + hard) and pick.bottom() < h - 2:
                pick = pick.translated(0, th + 1)
        placed.append(pick)
        out[i] = pick
    return out


def _clamp(c: QRect, w, h) -> QRect:
    x = max(2, min(c.left(), w - c.width() - 2))
    y = max(2, min(c.top(), h - c.height() - 2))
    return QRect(x, y, c.width(), c.height())


def _hits(c: QRect, rs) -> bool:
    return any(c.intersects(o) for o in rs)
