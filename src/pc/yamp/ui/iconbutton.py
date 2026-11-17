# -*- coding: utf-8 -*-
"""
아이콘 버튼 (vr0.1.0.009) — 글자 없이 아이콘만, 마우스를 올리면 tips 설명 팝업.
  - 색은 테마 토큰 (vr0.1.0.011): 기본 = text, 켜짐(checked/active) = accent_text, 채움 버튼 위 = on_fill
    테마가 바뀌면 set_skin() / _paint() 로 다시 칠함
  - setText 는 접근성·테스트용으로 남기지만 화면에는 아이콘만 (ToolButtonIconOnly)
  - 툴팁 지연: TipStyle (앱 스타일 프록시) 가 0.5초로
"""
from PyQt6.QtCore import QSize, Qt
from PyQt6.QtWidgets import QProxyStyle, QStyle, QToolButton

from . import icons, metrics, tips

COLOR = "text"            # 토큰 이름 (skin.color 로 지금 테마 색)
ACTIVE = "accent_text"
TOOLTIP_DELAY_MS = 500


class IconButton(QToolButton):
    def __init__(self, icon: str, tip_key: str, slot=None, checkable=False, size=20, parent=None,
                 color: str = COLOR, active_color: str = ACTIVE):
        super().__init__(parent)
        self.icon_name = icon
        self.color, self.active_color = color, active_color
        self._size = size
        self.setText(tips.name(tip_key))
        self.setCheckable(checkable)
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        n = metrics.dp(size)                                   # v023: 글자 크기를 따라 (10pt = 그대로)
        self.setIconSize(QSize(n, n))
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName("iconBtn")
        self.setProperty("icon_name", icon)
        tips.apply(self, tip_key)
        self.toggled.connect(lambda _on: self._paint())
        if slot:
            self.clicked.connect(slot)
        self._active = False
        self._paint()

    # ---- 상태
    def set_active(self, on: bool):
        """checkable 이 아닌 버튼의 켜짐 표시 (반복 모드 등)"""
        self._active = bool(on)
        self._paint()

    def set_icon_name(self, name: str):
        self.icon_name = name
        self.setProperty("icon_name", name)
        self._paint()

    def set_state(self, text: str | None):
        """툴팁에 현재 상태 줄 추가 (예: '반복: 1곡')"""
        tips.apply(self, self.property("tip_key"), text)

    def set_colors(self, color: str, active: str):
        self.color, self.active_color = color, active
        self._paint()

    def set_skin(self, _s=None):
        self._paint()

    def rescale(self):
        """v023: 글자 크기가 바뀌면 아이콘 크기 다시 (metrics.reapply)"""
        n = metrics.dp(self._size)
        if self.iconSize().width() != n:
            self.setIconSize(QSize(n, n))
            self._paint()

    def _paint(self):
        on = self._active or (self.isCheckable() and self.isChecked())
        self.setIcon(icons.icon(self.icon_name, self.active_color if on else self.color, metrics.dp(self._size) + 4))


class TipStyle(QProxyStyle):
    """툴팁을 0.5초 만에 (Qt 기본 0.7초). 한 번 뜬 뒤 옆 버튼으로 옮기면 바로 (Qt 기본 동작)"""

    def __init__(self, base=None, delay_ms: int = TOOLTIP_DELAY_MS):
        super().__init__(base)
        self.delay_ms = delay_ms

    def pixelMetric(self, metric, option=None, widget=None):
        """v025: 입력칸 안 아이콘(돋보기 · 지우기 ×) = 18px × 글자 배율 (기본 16px 은 얇고 작게 보였음)"""
        if metric == QStyle.PixelMetric.PM_LineEditIconSize:
            return metrics.dp(18)
        return super().pixelMetric(metric, option, widget)

    def styleHint(self, hint, option=None, widget=None, returnData=None):
        if hint == QStyle.StyleHint.SH_ToolTip_WakeUpDelay:
            return self.delay_ms
        if hint == QStyle.StyleHint.SH_ToolTip_FallAsleepDelay:
            return 2000
        return super().styleHint(hint, option, widget, returnData)


def install_tip_style(app, delay_ms: int = TOOLTIP_DELAY_MS):
    if not isinstance(app.style(), TipStyle):
        app.setStyle(TipStyle(None, delay_ms))
