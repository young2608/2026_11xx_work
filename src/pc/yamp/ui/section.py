# -*- coding: utf-8 -*-
"""접기/펼치기 블럭 Section (vr0.1.0.019 R5 — ui/neon.py 에서 나눔)
제목 줄(▸/▾) 클릭으로 본문 숨김 · 상태는 cfg["folds"] 에 저장 · 제목 줄 오른쪽에 버튼 붙이기"""
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QToolButton, QVBoxLayout, QWidget

from . import icons, metrics


# ---------------------------------------------------------------- 접기/펼치기 블록
class Section(QFrame):
    """제목 줄 + 본문. cfg 를 주면 cfg["folds"][key] 에 접힘 상태 저장"""
    toggled = pyqtSignal(bool)

    def __init__(self, title: str, key: str, cfg=None, body: QWidget | None = None, card: bool = True, parent=None):
        super().__init__(parent)
        if card:
            self.setObjectName("card")
        self.key, self.cfg = key, cfg
        v = QVBoxLayout(self)
        v.setContentsMargins(8, 4, 8, 6)
        v.setSpacing(2)
        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        self.btn = QToolButton(objectName="secHeader")
        self.btn.setText(title)
        self.btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        metrics.fix(self.btn, icon=14)                           # v023: 글자 크기를 따라 (10pt = 14px 그대로)
        self.btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn.setToolTip("접기 / 펼치기")
        self.btn.clicked.connect(self.toggle)
        head.addWidget(self.btn)
        head.addStretch(1)
        self.head = head
        v.addLayout(head)
        self.body = body if body is not None else QWidget()      # (QListWidget 처럼 len()=0 이면 거짓 → or 쓰면 안 됨, v015)
        v.addWidget(self.body, 1)
        folds = (cfg["folds"] or {}) if cfg is not None else {}
        self._open = not folds.get(key, False)
        self._apply()

    def add_action(self, w: QWidget):
        """제목 줄 오른쪽 버튼"""
        self.head.addWidget(w)

    def is_open(self) -> bool:
        return self._open

    def set_open(self, on: bool):
        if on != self._open:
            self._open = on
            self._apply()
            if self.cfg is not None:
                f = dict(self.cfg["folds"] or {})
                if on:
                    f.pop(self.key, None)
                else:
                    f[self.key] = True
                self.cfg["folds"] = f
            self.toggled.emit(on)

    def toggle(self):
        self.set_open(not self._open)

    def set_skin(self, _s=None):
        self._apply()

    def _apply(self):
        self.body.setVisible(self._open)
        self.btn.setIcon(icons.icon("chevronDown" if self._open else "chevronRight", "dim"))
        sp = self.sizePolicy()
        sp.setVerticalStretch(1 if self._open else 0)
        self.setSizePolicy(sp)
