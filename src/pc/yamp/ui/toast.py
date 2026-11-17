# -*- coding: utf-8 -*-
"""짧은 알림 (vr0.1.0.009) — 상태 막대 문구 대신 창 아래쪽 가운데에 잠깐 떴다가 사라짐 (2.5초)"""
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QLabel

SHOW_MS = 2500
BOTTOM_GAP = 100          # 아래 재생 막대 위


class Toast(QLabel):
    def __init__(self, host):
        super().__init__(host, objectName="toast")
        self.host = host
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.hide()
        self._t = QTimer(self, singleShot=True, interval=SHOW_MS, timeout=self.hide)

    def show_msg(self, text: str, ms: int = SHOW_MS):
        if not text:
            return
        self.setText(text)
        self.adjustSize()
        w, h = self.width(), self.height()
        hw, hh = self.host.width(), self.host.height()
        self.move(max(8, (hw - w) // 2), max(8, hh - h - BOTTOM_GAP))
        self.raise_()
        self.show()
        self._t.start(ms)
