# -*- coding: utf-8 -*-
"""
폴더 탭 (vr0.1.0.006, F1–F8)
  ┌ 폴더 (접기) ─────────────────────────────┐   ┌ 이 폴더의 곡 (접기) ────────────┐
  │ ★ 고정 폴더 / ⏱ 마지막 폴더 / 📁 라이브러리 │   │ 형식 요약: FLAC 12 · MP3 3      │
  │   └ 하위 폴더 (펼칠 때 읽음)               │   │ 01 곡.flac   FLAC               │
  └──────────────────────────────────────────┘   └────────────────────────────────┘
  [▶ 이 폴더 재생] [셔플] [☑ 하위 폴더] [정렬 ▼] [★ 고정] [+ 폴더 추가] [↻]
  - 폴더 내용이 바뀌면 (QFileSystemWatcher) 목록 다시 읽음 (F7)
"""
import os
from collections import Counter
from pathlib import Path

from PyQt6.QtCore import Qt, QFileSystemWatcher, QTimer, pyqtSignal
from PyQt6.QtWidgets import (QComboBox, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QSplitter, QTreeWidget,
                             QTreeWidgetItem, QVBoxLayout, QWidget)

from ..data.scan import folder_summary, summary_text  # noqa: F401  (v019 R1: data/scan.py 로 옮김, 이전 import 호환)
from . import icons, metrics, tips
from .iconbutton import IconButton
from .section import Section

ROLE_PATH = Qt.ItemDataRole.UserRole
ROLE_LOADED = Qt.ItemDataRole.UserRole + 1
SORTS = (("name", "파일 이름순"), ("title", "제목순"), ("added", "최근 추가순"))


class FolderView(QWidget):
    addFolderRequested = pyqtSignal()

    def __init__(self, ctrl, parent=None):
        super().__init__(parent)
        self.ctrl = ctrl
        self.cfg = ctrl.cfg
        self._cur = ""
        self._tracks = []
        v = QVBoxLayout(self)
        metrics.margins(v, 2, 2, 2, 2)
        metrics.spacing(v, 6)

        # 동작 줄
        bar = QHBoxLayout()
        metrics.spacing(bar, 4)
        self.b_play = IconButton("play", "folder_play", self.play)
        self.b_shuf = IconButton("shuffle", "folder_shuffle", lambda: self.play(shuffle=True))
        self.sub = IconButton("addFolder", "folder_sub", checkable=True)     # 하위 폴더 포함 (켜짐 = 노란색)
        self.sub.setChecked(bool(self.cfg["folder_include_sub"]))
        self.sub.toggled.connect(self._on_sub)
        self.sort = QComboBox()
        for k, lab in SORTS:
            self.sort.addItem(lab, k)
        self.sort.setCurrentIndex(max(0, [k for k, _ in SORTS].index(self.cfg["folder_sort"])
                                      if self.cfg["folder_sort"] in [k for k, _ in SORTS] else 0))
        self.sort.currentIndexChanged.connect(self._on_sort)
        tips.apply_simple(self.sort, "정렬", "파일 이름 · 제목 · 최근 추가 순")
        self.b_pin = IconButton("pin", "folder_pin", self.toggle_pin, checkable=True)
        self.b_add = IconButton("plus", "add_folder", self.addFolderRequested.emit)
        self.b_ref = IconButton("refresh", "refresh", self.reload)
        for w in (self.b_play, self.b_shuf, self.sub, self.sort, self.b_pin, self.b_add, self.b_ref):
            bar.addWidget(w)
        bar.addStretch(1)
        v.addLayout(bar)

        split = QSplitter(Qt.Orientation.Vertical)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["폴더", "곡"])
        self.tree.setColumnWidth(0, 260)
        self.tree.itemExpanded.connect(self._on_expand)
        self.tree.currentItemChanged.connect(lambda cur, _p: self.select(cur.data(0, ROLE_PATH) if cur else ""))
        self.tree.itemDoubleClicked.connect(lambda it, _c: self.play())
        self.sec_tree = Section("폴더", "folder.tree", self.cfg, self.tree)
        split.addWidget(self.sec_tree)

        tb = QWidget()
        tv = QVBoxLayout(tb)
        tv.setContentsMargins(0, 0, 0, 0)
        self.summary = QLabel("폴더를 선택하세요")
        self.summary.setObjectName("dimLabel")
        tv.addWidget(self.summary)
        self.files = QListWidget()
        self.files.itemDoubleClicked.connect(self._play_item)
        tv.addWidget(self.files, 1)
        self.sec_files = Section("이 폴더의 곡", "folder.files", self.cfg, tb)
        split.addWidget(self.sec_files)
        v.addWidget(split, 1)

        self.watch = QFileSystemWatcher(self)
        self._reload_timer = QTimer(self, singleShot=True, interval=800, timeout=self._on_fs_changed)
        self.watch.directoryChanged.connect(lambda _p: self._reload_timer.start())
        ctrl.libraryChanged.connect(self.reload)
        self.reload()

    # ---- 트리
    def roots(self) -> list[tuple[str, str]]:
        """(종류, 경로): pin / last / lib — 중복 제거, 순서 유지"""
        out, seen = [], set()

        def add(kind, p):
            p = (p or "").strip()
            if p and os.path.isdir(p) and os.path.normcase(p) not in seen:
                seen.add(os.path.normcase(p))
                out.append((kind, p))
        for p in self.ctrl.library.pinned_folders():
            add("pin", p)
        add("last", self.cfg["last_folder"])
        for p in str(self.cfg["library_folders"] or "").split(";"):
            add("lib", p)
        return out

    def reload(self):
        keep = self._cur
        self.tree.clear()
        mark = {"pin": "★ ", "last": "⏱ ", "lib": ""}
        tips = {"pin": "고정 폴더", "last": "마지막으로 재생한 폴더", "lib": "라이브러리 폴더"}
        for kind, p in self.roots():
            it = self._make_item(p, mark[kind] + (os.path.basename(p.rstrip("/\\")) or p))
            it.setToolTip(0, f"{tips[kind]}\n{p}")
            it.setIcon(0, icons.icon("starFill" if kind == "pin" else "folder",
                                     "accent_text" if kind == "pin" else "dim"))
            self.tree.addTopLevelItem(it)
        if not self.tree.topLevelItemCount():
            it = QTreeWidgetItem(["(폴더 없음) — '폴더 추가' 로 음악 폴더를 넣으세요", ""])
            it.setFlags(Qt.ItemFlag.NoItemFlags)
            self.tree.addTopLevelItem(it)
        if keep:
            self.select(keep, refill=False)               # v018: 트리만 다시 — 같은 폴더의 곡 목록은 그대로 (폴더 변경은 감시가 갱신)

    def _make_item(self, path, label):
        n, _c = folder_summary(path, recursive=False)
        it = QTreeWidgetItem([label, str(n) if n else ""])
        it.setData(0, ROLE_PATH, path)
        it.setData(0, ROLE_LOADED, False)
        try:
            if any(e.is_dir() for e in os.scandir(path)):
                it.addChild(QTreeWidgetItem(["…"]))      # 펼침 표시용 자리
        except OSError:
            pass
        return it

    def _on_expand(self, it):
        if it.data(0, ROLE_LOADED):
            return
        it.setData(0, ROLE_LOADED, True)
        it.takeChildren()
        p = it.data(0, ROLE_PATH)
        try:
            subs = sorted((e.path for e in os.scandir(p) if e.is_dir() and not e.name.startswith(".")), key=str.lower)
        except OSError:
            subs = []
        for s in subs:
            ch = self._make_item(s, os.path.basename(s))
            ch.setIcon(0, icons.icon("folder", "dim"))
            it.addChild(ch)

    # ---- 선택 · 곡 목록
    def select(self, path, refill: bool = True):
        if not path:
            return
        same = path == self._cur
        if self._cur and self._cur in self.watch.directories():
            self.watch.removePath(self._cur)
        self._cur = path
        if os.path.isdir(path):
            self.watch.addPath(path)
        pinned = path in self.ctrl.library.pinned_folders()
        self.b_pin.setChecked(pinned)
        self.b_pin.set_state("고정됨" if pinned else None)
        if refill or not same:
            self._fill_files()

    def set_skin(self, _s=None):
        """테마 바뀜: 트리 아이콘 다시 칠함"""
        def walk(it):
            if it.data(0, ROLE_PATH):
                pin = it.text(0).startswith("★")
                it.setIcon(0, icons.icon("starFill" if pin else "folder", "accent_text" if pin else "dim"))
            for i in range(it.childCount()):
                walk(it.child(i))
        for i in range(self.tree.topLevelItemCount()):
            walk(self.tree.topLevelItem(i))

    def current_folder(self) -> str:
        return self._cur

    def _fill_files(self):
        self.files.clear()
        if not self._cur:
            return
        inc = self.sub.isChecked()
        # v018 (f33 P4): 폴더를 한 번만 돎 (곡 목록 + 형식별 개수) — 전에는 목록 · 요약 · 재생 때 3번
        c = Counter()
        self._tracks = self.ctrl.folder_tracks(self._cur, inc, self.sort.currentData(), counts=c)
        self._tracks_key = (self._cur, inc, self.sort.currentData())
        total = sum(t.duration for t in self._tracks)
        from ..data.playlist import fmt_time
        self.summary.setText(f"{len(self._tracks)}곡" + (f" · {fmt_time(total)}" if total else "") +
                             (f"   [{summary_text(c)}]" if c else "") + ("   (하위 폴더 포함)" if inc else ""))
        base = self._cur
        for t in self._tracks[:3000]:
            rel = os.path.relpath(t.path, base) if inc else os.path.basename(t.path)
            label = f"{t.cue_no:02d}. {t.title}  —  {os.path.basename(t.path)}" if t.cue_no else rel
            fmt = Path(t.path).suffix[1:].upper() + (" · CUE" if t.cue_no else "")
            it = QListWidgetItem(f"{label}    [{fmt}]")
            it.setData(ROLE_PATH, t.uid)
            self.files.addItem(it)
        if len(self._tracks) > 3000:
            self.files.addItem(f"… 외 {len(self._tracks) - 3000}곡")

    def _play_item(self, it):
        uid = it.data(ROLE_PATH)
        start = next((t for t in self._tracks if t.uid == uid), None)
        if start is not None:
            self.play(start=start)

    # ---- 동작
    def play(self, shuffle=False, start=None):
        if not self._cur:
            self.ctrl.message.emit("폴더를 먼저 선택하세요")
            return 0
        key = (self._cur, self.sub.isChecked(), self.sort.currentData())
        ready = list(self._tracks) if getattr(self, "_tracks_key", None) == key and self._tracks else None   # v018: 이미 읽은 목록
        n = self.ctrl.play_folder(self._cur, self.sub.isChecked(), shuffle, self.sort.currentData(), start, tracks=ready)
        QTimer.singleShot(0, self.reload)                 # ⏱ 마지막 폴더 갱신
        return n

    def toggle_pin(self):
        if not self._cur:
            return
        pinned = self._cur in self.ctrl.library.pinned_folders()
        self.ctrl.library.pin_folder(self._cur, not pinned)
        self.reload()

    def _on_sub(self, on):
        self.cfg["folder_include_sub"] = on
        self._fill_files()

    def _on_sort(self, _i):
        self.cfg["folder_sort"] = self.sort.currentData()
        self._fill_files()

    def _on_fs_changed(self):
        self._tracks_key = None                           # 폴더 내용이 바뀜 → 재생 때 다시 읽음
        if self._cur:
            self._fill_files()
            self.ctrl.message.emit(f"폴더 변경 감지 — 목록 갱신: {os.path.basename(self._cur)}")
