# -*- coding: utf-8 -*-
"""화면 크기 · 글자 크기에 맞춘 틀(프레임) 크기 (vr0.1.0.023, f45)

  화면 배율(125 · 150 · 200 %)은 Qt 가 px 를 알아서 키움 → 여기서는 '글자 크기'만 따라감
  k()             글자 배율 = 본문 pt / 10  (기본 10pt = 1.0 → v022 와 픽셀까지 같음)
  dp(n)           고정 크기 n(px, 10pt 기준) × k
  scale_css(css)  스타일시트의 px 값 × k  (1 · 2px 선은 그대로 — 선이 흐려지지 않게)
  fix(w, ...)     위젯 고정 크기를 '10pt 기준값'으로 기억하고 적용 → reapply(root) 로 글자 크기가 바뀌면 다시
  auto_font_pt(h) 글자 크기 '자동': 화면(논리) 높이가 클수록 크게 (1080p = 10 · 1440p = 11 · 4K 100 % = 13)
  CenterBox       아주 넓은 창에서 내용 폭을 max 로 제한하고 가운데 정렬 (좁을 때는 그대로)
"""
import re

from PyQt6.QtCore import QSize
from PyQt6.QtWidgets import QVBoxLayout, QWidget

from . import skin

BASE_PT = 10.0
_PX = re.compile(r"(-?)(\d+)px")
AUTO_STEPS = ((1300, 10), (1700, 11), (2050, 12))      # 화면 높이(논리 px) 미만 → pt, 그 이상 = 13


def k() -> float:
    return skin.font_pt("body") / BASE_PT


def dp(n: float) -> int:
    return int(round(float(n) * k()))


def scale_css(css: str, kk: float | None = None) -> str:
    kk = k() if kk is None else float(kk)
    if abs(kk - 1.0) < 1e-6:
        return css

    def rep(m):
        v = int(m.group(2))
        return m.group(0) if v <= 2 else f"{m.group(1)}{int(round(v * kk))}px"
    return _PX.sub(rep, css)


def auto_font_pt(avail_h) -> int:
    try:
        h = int(avail_h)
    except (TypeError, ValueError):
        return int(BASE_PT)
    for lim, pt in AUTO_STEPS:
        if h < lim:
            return pt
    return 13


def screen_font_pt(widget=None) -> int:
    """위젯(없으면 주 화면)이 있는 화면의 사용 가능 높이로 auto_font_pt"""
    from PyQt6.QtWidgets import QApplication
    scr = None
    try:
        scr = widget.screen() if widget is not None else None
    except (AttributeError, RuntimeError):
        scr = None
    if scr is None:
        app = QApplication.instance()
        scr = app.primaryScreen() if app is not None else None
    return auto_font_pt(scr.availableGeometry().height()) if scr is not None else int(BASE_PT)


def keep_on_screen(win) -> bool:
    """저장된 창 위치가 지금 없는 모니터(뽑힌 모니터 · 해상도 변경)면 주 화면 가운데로 (옮겼으면 True)"""
    from PyQt6.QtWidgets import QApplication
    fg = win.frameGeometry()
    if any(s.availableGeometry().intersects(fg) for s in QApplication.screens()):
        return False
    scr = QApplication.primaryScreen()
    if scr is None:
        return False
    av = scr.availableGeometry()
    win.resize(min(win.width(), av.width()), min(win.height(), av.height()))
    win.move(av.center() - win.rect().center())
    return True


# ---- 고정 크기 기억 · 다시 적용
def fix(w, width=None, height=None, min_w=None, max_w=None, icon=None):
    """10pt 기준 크기를 위젯에 기억(_yamp_base)하고 지금 배율로 적용. 돌려줌 = w"""
    base = getattr(w, "_yamp_base", {})
    for key, v in (("width", width), ("height", height), ("min_w", min_w), ("max_w", max_w), ("icon", icon)):
        if v is not None:
            base[key] = v
    w._yamp_base = base
    _apply(w, base)
    return w


def _apply(w, b):
    if "width" in b and "height" in b:
        w.setFixedSize(dp(b["width"]), dp(b["height"]))
    elif "width" in b:
        w.setFixedWidth(dp(b["width"]))
    elif "height" in b:
        w.setFixedHeight(dp(b["height"]))
    if "min_w" in b:
        w.setMinimumWidth(dp(b["min_w"]))
    if "max_w" in b:
        w.setMaximumWidth(dp(b["max_w"]))
    if "icon" in b:
        n = dp(b["icon"])
        w.setIconSize(QSize(n, n))


def reapply(root) -> int:
    """root 와 그 아래 fix() 위젯 · 아이콘 버튼을 지금 글자 배율로 (적용 개수)"""
    if root is None:
        return 0
    n = 0
    for w in [root] + root.findChildren(QWidget):
        b = getattr(w, "_yamp_base", None)
        if b:
            _apply(w, b)
            n += 1
        if hasattr(w, "rescale"):
            w.rescale()
            n += 1
        if isinstance(w, CenterBox):
            w._center()
    return n


class CenterBox(QWidget):
    """child 를 담아 폭이 dp(max_w) 를 넘으면 양쪽 여백으로 가운데 (넘지 않으면 여백 0 = 이전과 같음)"""

    def __init__(self, child, max_w: int, parent=None):
        super().__init__(parent)
        self.child, self.max_w = child, max_w
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(child)

    def side_margin(self, width=None) -> int:
        width = self.width() if width is None else width
        return max(0, (int(width) - dp(self.max_w)) // 2)

    def _center(self):
        m = self.side_margin()
        lay = self.layout()
        if lay.contentsMargins().left() != m:
            lay.setContentsMargins(m, 0, m, 0)

    def resizeEvent(self, e):
        self._center()
        super().resizeEvent(e)
