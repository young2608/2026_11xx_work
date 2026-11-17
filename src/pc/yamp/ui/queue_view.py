# -*- coding: utf-8 -*-
"""대기열 탭 (B5) — 다음에 재생할 곡 (vr0.1.0.019 R6 — library_views.py 에서 나눔)"""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMenu, QVBoxLayout, QWidget

from .iconbutton import IconButton
from .qtutil import exec_menu


class QueueView(QWidget):
    def __init__(self, ctrl, parent=None):
        super().__init__(parent)
        self.ctrl = ctrl
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        top = QHBoxLayout()
        self.title = QLabel()
        b = IconButton("trash", "queue_clear", ctrl.clear_queue)
        top.addWidget(self.title, 1)
        top.addWidget(b)
        v.addLayout(top)
        self.list = QListWidget()
        self.list.itemDoubleClicked.connect(self._dbl)
        self.list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self._menu)
        v.addWidget(self.list, 1)
        ctrl.queueChanged.connect(self.reload)
        self.reload()

    def reload(self):
        self.list.clear()
        for t in self.ctrl.queue:
            self.list.addItem(QListWidgetItem(t.display))
        n = len(self.ctrl.queue)
        self.title.setText(f"다음 재생 {n}곡" if n else "대기열이 비어 있습니다 — 곡 우클릭 → 다음에 재생")

    def _dbl(self, item):
        i = self.list.row(item)
        q = self.ctrl.queue
        if 0 <= i < len(q):
            t = q.pop(i)
            self.ctrl.queueChanged.emit()
            self.ctrl.play_index(self.ctrl._ensure_in_playlist(t))

    def _menu(self, pos):
        it = self.list.itemAt(pos)
        if not it:
            return
        i = self.list.row(it)
        m = QMenu(self)
        m.addAction("대기열에서 빼기", lambda: self.ctrl.remove_queue(i))
        m.addAction("비우기", self.ctrl.clear_queue)
        exec_menu(m, self.list.viewport().mapToGlobal(pos))

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Delete and self.list.currentRow() >= 0:
            self.ctrl.remove_queue(self.list.currentRow())
            return
        super().keyPressEvent(e)
