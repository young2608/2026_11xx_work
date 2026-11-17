# -*- coding: utf-8 -*-
"""
빠른 찾기 Ctrl+K (vr0.1.0.009) — 곡 · 가수 · 폴더 · 명령을 한 칸에서 찾아 바로 실행
  - 명령: tips 표 + MainWindow 가 넘겨 준 (key → 함수) 목록 ("슬립", "사운드" 처럼 이름 일부로)
  - 곡: 라이브러리 DB (제목·가수·앨범) — 최대 30개
  - 폴더: 라이브러리 폴더 · 고정 폴더 · 마지막 폴더
  ↑↓ 고르기 · Enter 실행 · Esc 닫기
"""
import os

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QLineEdit, QListWidget, QListWidgetItem, QVBoxLayout

from . import icons, tips

MAX_TRACKS = 30
ROLE = Qt.ItemDataRole.UserRole


def match(text: str, query: str) -> bool:
    """모든 단어가 (대소문자 무시) 들어 있으면 True"""
    t = text.lower()
    return all(w in t for w in query.lower().split())


def search_tracks(rows, query: str, limit: int = MAX_TRACKS):
    out = []
    for r in rows:
        s = " ".join(str(r.get(k) or "") for k in ("title", "artist", "album", "path"))
        if match(s, query):
            out.append(r)
            if len(out) >= limit:
                break
    return out


class QuickFind(QDialog):
    def __init__(self, win, commands: dict):
        super().__init__(win, Qt.WindowType.Popup)
        self.win, self.ctrl, self.commands = win, win.ctrl, commands
        self.setMinimumWidth(560)
        v = QVBoxLayout(self)
        v.setContentsMargins(8, 8, 8, 8)
        self.edit = QLineEdit()
        self.edit.addAction(icons.icon("search", "dim"), QLineEdit.ActionPosition.LeadingPosition)
        tips.apply(self.edit, "quick_find")
        self.list = QListWidget()
        self.list.setMinimumHeight(320)
        v.addWidget(self.edit)
        v.addWidget(self.list)
        self.edit.textChanged.connect(self.refresh)
        self.edit.returnPressed.connect(self.run_current)
        self.list.itemActivated.connect(lambda it: self.run(it))
        self._rows = None
        self.refresh("")

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key.Key_Down, Qt.Key.Key_Up):
            r = self.list.currentRow() + (1 if e.key() == Qt.Key.Key_Down else -1)
            self.list.setCurrentRow(max(0, min(self.list.count() - 1, r)))
            return
        super().keyPressEvent(e)

    def _add(self, icon, text, data):
        it = QListWidgetItem(icons.icon(icon, "dim"), text)
        it.setData(ROLE, data)
        self.list.addItem(it)

    def refresh(self, q=None):
        q = (q if q is not None else self.edit.text()).strip()
        self.list.clear()
        for key, fn in self.commands.items():
            n, sc, d = tips.TIPS.get(key, (key, "", ""))
            if not q or match(f"{n} {d}", q):
                self._add("smart", f"{n}" + (f"   {sc}" if sc else ""), ("cmd", key))
        if q:
            folders = [f for f in str(self.ctrl.cfg["library_folders"] or "").split(";") if f.strip()]
            folders += self.ctrl.library.pinned_folders()
            lf = self.ctrl.cfg["last_folder"]
            if lf:
                folders.append(lf)
            for f in dict.fromkeys(folders):
                if match(f, q):
                    self._add("folder", f"{os.path.basename(f.rstrip('/')) or f}   —  {f}", ("folder", f))
            if self._rows is None:
                self._rows = self.ctrl.library.all_tracks()
            for r in search_tracks(self._rows, q):
                label = (f"{r['artist']} - " if r.get("artist") else "") + (r.get("title") or os.path.basename(r["path"]))
                self._add("play", label, ("track", r["key"]))
        if self.list.count():
            self.list.setCurrentRow(0)

    def run_current(self):
        it = self.list.currentItem()
        if it:
            self.run(it)

    def run(self, it):
        kind, val = it.data(ROLE)
        self.accept()
        if kind == "cmd":
            self.commands[val]()
        elif kind == "folder":
            self.ctrl.play_folder(val, bool(self.ctrl.cfg["folder_include_sub"]), False, str(self.ctrl.cfg["folder_sort"]))
        elif kind == "track":
            self.ctrl.play_mix([val], tips.name("quick_find"))
