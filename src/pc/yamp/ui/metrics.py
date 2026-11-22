# -*- coding: utf-8 -*-
"""화면 크기 · 글자 크기에 맞춘 틀(프레임) 크기 (vr0.1.0.023, f45)

  화면 배율(125 · 150 · 200 %)은 Qt 가 px 를 알아서 키움 → 여기서는 '글자 크기'만 따라감
  k()             글자 배율 = 본문 pt / 10  (기본 10pt = 1.0 → v022 와 픽셀까지 같음)
  dp(n)           고정 크기 n(px, 10pt 기준) × k
  scale_css(css)  스타일시트의 px 값 × k  (1 · 2px 선은 그대로 — 선이 흐려지지 않게)
  fix(w, ...)     위젯 고정 크기를 '10pt 기준값'으로 기억하고 적용 → reapply(root) 로 글자 크기가 바뀌면 다시
  auto_font_pt(h) 글자 크기 '자동': 화면(논리) 높이가 클수록 크게 (1080p = 10 · 1440p = 11 · 4K 100 % = 13)
                  v033: + 실제 밀도(물리 dpi ÷ 배율)가 120 dpi 넘으면 더 크게 (4K 27" 100 % ≈ 14 · 24" ≈ 15, 최대 16)
  CenterBox       아주 넓은 창에서 내용 폭을 max 로 제한하고 가운데 정렬 (좁을 때는 그대로)
"""
import re

from PyQt6.QtCore import QSize
from PyQt6.QtWidgets import QVBoxLayout, QWidget

from . import skin

BASE_PT = 10.0
_PX = re.compile(r"(-?)(\d+)px")
AUTO_STEPS = ((1300, 10), (1700, 11), (2050, 12))      # 화면 높이(논리 px) 미만 → pt, 그 이상 = 13
# v033 (f61 H1): 화면 실제 밀도도 봄 — 4K 27" 를 100 % 로 쓰면 논리 px 하나가 아주 작음(163 dpi) → 높이만으로는 13pt 가 끝이었음.
#   논리 px 당 실제 밀도(물리 dpi ÷ 화면 배율)가 120 dpi 를 넘는 만큼 키움 (최대 16pt). 120 이하(보통 모니터 · 권장 배율) = 전과 같음.
#   물리 크기를 모르는 화면(TV · 프로젝터 · 가짜 값)은 70~400 dpi 밖이면 무시
DPI_TARGET = 120.0
DPI_RANGE = (70.0, 400.0)
AUTO_MAX = 16


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


def auto_font_pt(avail_h, phys_dpi=None, scale: float = 1.0) -> int:
    """글자 크기 자동 = max(화면 높이 단계, 실제 밀도 단계). phys_dpi = 화면 물리 dpi, scale = 화면 배율(1.0 · 1.5 …)"""
    try:
        h = int(avail_h)
    except (TypeError, ValueError):
        return int(BASE_PT)
    pt = 13
    for lim, v in AUTO_STEPS:
        if h < lim:
            pt = v
            break
    return max(pt, dpi_font_pt(phys_dpi, scale))


def dpi_font_pt(phys_dpi, scale: float = 1.0) -> int:
    """v033 (f61 H1): 논리 px 당 실제 밀도로 정한 pt (10 · 11 … 16). 모르는 값 = 10 (높이 단계만 씀)"""
    try:
        d, sc = float(phys_dpi), max(0.5, float(scale or 1.0))
    except (TypeError, ValueError):
        return int(BASE_PT)
    if not (DPI_RANGE[0] <= d <= DPI_RANGE[1]):
        return int(BASE_PT)
    return int(max(BASE_PT, min(AUTO_MAX, round(BASE_PT * (d / sc) / DPI_TARGET))))


USE_DPI = True                     # config font_auto_dpi (0 = 예전처럼 화면 높이만)


def screen_font_pt(widget=None) -> int:
    """위젯(없으면 주 화면)이 있는 화면의 사용 가능 높이 + 실제 밀도로 auto_font_pt"""
    from PyQt6.QtWidgets import QApplication
    scr = None
    try:
        scr = widget.screen() if widget is not None else None
    except (AttributeError, RuntimeError):
        scr = None
    if scr is None:
        app = QApplication.instance()
        scr = app.primaryScreen() if app is not None else None
    if scr is None:
        return int(BASE_PT)
    dpi = None
    if USE_DPI:
        try:
            dpi = float(scr.physicalDotsPerInch())
        except (AttributeError, RuntimeError):
            dpi = None
    return auto_font_pt(scr.availableGeometry().height(), dpi, float(scr.devicePixelRatio() or 1.0))


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
def fix(w, width=None, height=None, min_w=None, max_w=None, icon=None, min_h=None):
    """10pt 기준 크기를 위젯에 기억(_yamp_base)하고 지금 배율로 적용. 돌려줌 = w"""
    base = getattr(w, "_yamp_base", {})
    for key, v in (("width", width), ("height", height), ("min_w", min_w), ("max_w", max_w), ("icon", icon), ("min_h", min_h)):
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
    if "min_h" in b:                                           # v033 (f61 H5)
        w.setMinimumHeight(dp(b["min_h"]))
    if "icon" in b:
        n = dp(b["icon"])
        w.setIconSize(QSize(n, n))


# ---- v033 (f61 H4): 레이아웃 여백 · 간격도 글자 배율 (전에는 글자 · 버튼만 커지고 카드 안 여백 · 줄 간격은 10pt 크기 그대로라 빽빽)
def _lay_px(v: int) -> int:
    return int(v) if int(v) <= 2 else dp(v)                  # 1 · 2px 은 그대로 (scale_css 와 같은 규칙)


def margins(lay, left: int, top: int, right: int, bottom: int):
    """lay.setContentsMargins 대신 — 10pt 기준값을 기억하고 지금 배율로 (10pt = 같은 값)"""
    lay.setProperty("_yamp_m", (left, top, right, bottom))
    lay.setContentsMargins(*(_lay_px(v) for v in (left, top, right, bottom)))
    return lay


def spacing(lay, n: int):
    """lay.setSpacing 대신 (위와 같음)"""
    lay.setProperty("_yamp_s", int(n))
    lay.setSpacing(_lay_px(n))
    return lay


def _apply_lay(lay) -> bool:
    m, sp = lay.property("_yamp_m"), lay.property("_yamp_s")
    if m:
        lay.setContentsMargins(*(_lay_px(v) for v in m))
    if sp is not None:
        lay.setSpacing(_lay_px(sp))
    return bool(m) or sp is not None


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
    from PyQt6.QtWidgets import QLayout
    for lay in root.findChildren(QLayout):                     # v033 (f61 H4)
        if _apply_lay(lay):
            n += 1
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
