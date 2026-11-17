# -*- coding: utf-8 -*-
"""추천 홈 탭 (B2~B4) — 카드 더블클릭 = 믹스 재생, 곡 더블클릭 = 그 곡부터 (vr0.1.0.019 R6 — library_views.py 에서 나눔)"""
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget

from .iconbutton import IconButton
from .qtutil import exec_menu
from .track_menu import KEY_ROLE, _label, show_smart_menu, track_menu


class HomeView(QWidget):
    """추천 카드: 카드 더블클릭 = 믹스 재생, 곡 더블클릭 = 그 곡부터"""

    def __init__(self, ctrl, parent=None):
        super().__init__(parent)
        self.ctrl = ctrl
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        top = QHBoxLayout()
        self.info = QLabel("추천 — 기기 안의 재생 기록으로 만듭니다")
        self.info.setWordWrap(True)
        b = IconButton("refresh", "refresh", self.refresh)
        self.b_smart = IconButton("smart", "smart", self.show_smart_menu)
        top.addWidget(self.info, 1)
        top.addWidget(self.b_smart)
        top.addWidget(b)
        v.addLayout(top)
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.itemDoubleClicked.connect(self._dbl)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._menu)
        v.addWidget(self.tree, 1)
        self.cards = []
        ctrl.homeReady.connect(self.set_cards)

    def refresh(self):
        self.info.setText("추천 계산 중…")
        self.ctrl.request_home()

    def show_smart_menu(self):
        show_smart_menu(self, self.ctrl, self.b_smart)

    def set_cards(self, cards):
        self.cards = cards or []
        self.tree.clear()
        lib = self.ctrl.library
        bold = QFont()
        bold.setBold(True)
        total = 0
        for cid, title, keys in self.cards:
            top = QTreeWidgetItem([f"▶ {title}  ({len(keys)}곡)"])
            top.setFont(0, bold)
            top.setData(0, KEY_ROLE, ("card", cid))
            for k in keys:
                d = lib.track(k)
                if not d:
                    continue
                c = QTreeWidgetItem([_label(d)])
                c.setData(0, KEY_ROLE, ("track", k))
                c.setToolTip(0, d.get("path", ""))
                top.addChild(c)
            self.tree.addTopLevelItem(top)
            total += len(keys)
        if self.tree.topLevelItemCount():
            self.tree.topLevelItem(0).setExpanded(True)
            self.info.setText("카드를 더블클릭하면 믹스 재생 · 곡을 더블클릭하면 그 곡부터 · 우클릭 메뉴")
        else:
            self.info.setText("아직 추천할 곡이 없습니다 — 음악을 몇 곡 듣거나 라이브러리 폴더를 추가하세요")

    def _card_keys(self, cid):
        for c, t, keys in self.cards:
            if c == cid:
                return t, keys
        return "", []

    def _dbl(self, item, _col):
        kind, val = item.data(0, KEY_ROLE)
        if kind == "card":
            t, keys = self._card_keys(val)
            self.ctrl.play_mix(keys, t)
        else:
            parent = item.parent()
            t, keys = self._card_keys(parent.data(0, KEY_ROLE)[1])
            i = keys.index(val) if val in keys else 0
            self.ctrl.play_mix(keys[i:], t)

    def _menu(self, pos):
        it = self.tree.itemAt(pos)
        if not it:
            return
        kind, val = it.data(0, KEY_ROLE)
        if kind == "card":
            _, keys = self._card_keys(val)
            exec_menu(track_menu(self, self.ctrl, lambda: keys), self.tree.viewport().mapToGlobal(pos))
        else:
            exec_menu(track_menu(self, self.ctrl, lambda: [val], val), self.tree.viewport().mapToGlobal(pos))
