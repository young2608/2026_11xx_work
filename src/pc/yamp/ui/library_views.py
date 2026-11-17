# -*- coding: utf-8 -*-
"""라이브러리 탭 (C2) — 가수 · 앨범 · 장르 · 폴더 묶음 트리 / 앨범 격자 (W10)

vr0.1.0.019 (R6): 추천 홈 → home_view.py · 대기열 → queue_view.py · 곡 메뉴 → track_menu.py 로 나눔
                  (이전처럼 library_views 에서도 가져갈 수 있게 다시 내보냄)
"""
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (QButtonGroup, QComboBox, QHBoxLayout, QLabel, QLineEdit, QSlider, QStackedWidget,
                             QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)

from ..data.track import fmt_time
from . import icons, metrics, tips
from .album_grid import AlbumGrid
from .iconbutton import IconButton
from .qtutil import exec_menu
from .track_menu import KEY_ROLE, _label, show_smart_menu, track_menu  # noqa: F401
from .home_view import HomeView  # noqa: F401
from .queue_view import QueueView  # noqa: F401

SEARCH_DELAY_MS = 250                                   # v018: 검색 입력이 멈추면 이 시간 뒤 한 번
SEARCH_KEYS = ("title", "artist", "album", "genre", "path")


class LibraryView(QWidget):
    GROUPS = (("artist", "가수"), ("album", "앨범"), ("genre", "장르"), ("folder", "폴더"))
    addFolderRequested = pyqtSignal()

    def __init__(self, ctrl, parent=None):
        super().__init__(parent)
        self.ctrl = ctrl
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        top = QHBoxLayout()
        self.group = QComboBox()
        for k, label in self.GROUPS:
            self.group.addItem(label, k)
        self.search = QLineEdit()
        self.search.setClearButtonEnabled(True)
        icons.bind(self.search, self.search.addAction(icons.icon("search", "dim"),
                                                      QLineEdit.ActionPosition.LeadingPosition).setIcon, "search", "dim")
        tips.apply(self.search, "search")
        self.b_tree = IconButton("listView", "view_tree", lambda: self.set_view("tree"), checkable=True)
        self.b_grid = IconButton("grid", "view_grid", lambda: self.set_view("grid"), checkable=True)
        g = QButtonGroup(self)
        g.addButton(self.b_tree)
        g.addButton(self.b_grid)
        self.size = QSlider(Qt.Orientation.Horizontal)
        self.size.setRange(72, 220)
        metrics.fix(self.size, width=90)
        tips.apply_simple(self.size, "표지 크기", "앨범 격자 표지 크기")
        self.b_smart = IconButton("smart", "smart", lambda: show_smart_menu(self, ctrl, self.b_smart))
        b_add = IconButton("addFolder", "add_folder", self.addFolderRequested.emit)
        b_scan = IconButton("refresh", "scan", ctrl.scan_library)
        for w in (self.group, self.search, self.b_tree, self.b_grid, self.size, self.b_smart, b_add, b_scan):
            top.addWidget(w)
        top.setStretch(1, 1)
        v.addLayout(top)
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.itemDoubleClicked.connect(self._dbl)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._menu)
        self.grid = AlbumGrid()
        self.grid.playRequested.connect(lambda keys, t: ctrl.play_mix(keys, t))
        self.grid.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.grid.customContextMenuRequested.connect(self._grid_menu)
        self.stack = QStackedWidget()
        self.stack.addWidget(self.tree)
        self.stack.addWidget(self.grid)
        v.addWidget(self.stack, 1)
        side = int(ctrl.cfg["grid_size"] or 120)
        self.size.setValue(side)
        self.grid.set_side(side)
        self.size.valueChanged.connect(self._on_size)
        self.count = QLabel()
        v.addWidget(self.count)
        # v018 (f33 P1): 검색은 입력이 멈추면(250ms) 한 번 · DB 행은 캐시 · 안 보일 때 바뀌면 보일 때 한 번
        self._rows_cache = None                 # [(행 dict, 검색용 소문자 문자열)] — libraryChanged 때 비움
        self._dirty = False
        self._search_t = QTimer(self, singleShot=True, interval=SEARCH_DELAY_MS, timeout=self.reload)
        self.group.currentIndexChanged.connect(self._fresh_reload)
        self.search.textChanged.connect(lambda _t: self._search_t.start())
        ctrl.libraryChanged.connect(self._on_library_changed)
        self.set_view(str(ctrl.cfg["lib_view"] or "tree"))

    def set_view(self, mode: str):
        """tree = 가수·앨범·장르·폴더 목록 / grid = 앨범 표지 격자 (W10)"""
        mode = "grid" if mode == "grid" else "tree"
        self.ctrl.cfg["lib_view"] = mode
        self.stack.setCurrentWidget(self.grid if mode == "grid" else self.tree)
        self.b_tree.setChecked(mode == "tree")
        self.b_grid.setChecked(mode == "grid")
        self.size.setVisible(mode == "grid")
        self.group.setVisible(mode == "tree")
        if mode == "grid":
            self._fresh_reload()

    def _on_size(self, v):
        self.ctrl.cfg["grid_size"] = int(v)
        self.grid.set_side(int(v))

    def _grid_menu(self, pos):
        it = self.grid.itemAt(pos)
        if it:
            keys = it.data(Qt.ItemDataRole.UserRole)[0]
            exec_menu(track_menu(self, self.ctrl, lambda: keys), self.grid.viewport().mapToGlobal(pos))

    # ---- v018 (f33 P1) 지연 · 캐시
    def _visible(self) -> bool:
        w = self.window()
        return self.isVisibleTo(w) if w is not None and w is not self else self.isVisible()

    def _on_library_changed(self):
        self._rows_cache = None
        if self._visible():
            self.reload()
        else:
            self._dirty = True                   # 라이브러리 탭을 열 때 한 번 다시 만듦

    def _fresh_reload(self, *_a):
        """DB 를 다시 읽고 다시 만듦 (보기 · 묶음을 바꿀 때 — 좋아요 같은 바뀐 값 반영)"""
        self._rows_cache = None
        self.reload()

    def showEvent(self, e):
        super().showEvent(e)
        if self._dirty:
            self.reload()
        else:
            self._rows_cache = None              # 탭을 다시 열면 다음 검색은 새 DB 값으로

    def hideEvent(self, e):
        """v020 (f40 L3): 탭을 떠나면 DB 행 캐시를 놓음 (5만 곡이면 수십 MB — 전에는 프로그램을 끌 때까지 남음).
        다시 열면 showEvent 가 새로 읽음 (트리는 그대로 보임)"""
        super().hideEvent(e)
        self._rows_cache = None

    def _all_rows(self):
        if self._rows_cache is None:
            self._rows_cache = [(r, " ".join(str(r.get(k) or "") for k in SEARCH_KEYS).lower())
                                for r in self.ctrl.library.all_tracks()]
        return self._rows_cache

    def reload(self):
        self._search_t.stop()
        self._dirty = False
        g = self.group.currentData()
        q = self.search.text().strip().lower()
        rows = [r for r, hay in self._all_rows() if not q or q in hay]
        groups = {}
        for r in rows:
            name = (r.get(g) or "").strip() or "(없음)"
            groups.setdefault(name, []).append(r)
        if self.stack.currentWidget() is self.grid:
            self.grid.set_rows(rows)
            self.count.setText(f"{len(rows)}곡 · 앨범 {self.grid.count()}개" if rows else "라이브러리가 비어 있습니다")
            return
        tree = self.tree
        tree.setUpdatesEnabled(False)            # 항목을 한꺼번에 만들고 마지막에 한 번 그림
        try:
            tree.clear()
            tops = []
            for name in sorted(groups, key=str.lower):
                items = groups[name]
                top = QTreeWidgetItem([f"{name}  ({len(items)})"])
                top.setData(0, KEY_ROLE, ("group", [r["key"] for r in items]))
                kids = []
                for r in items:
                    c = QTreeWidgetItem([_label(r) + (f"   [{fmt_time((r['duration_ms'] or 0) / 1000)}]" if r["duration_ms"] else "")
                                         + ("  ♥" if r["liked"] else "")])
                    c.setData(0, KEY_ROLE, ("track", r["key"]))
                    c.setToolTip(0, r["path"])
                    kids.append(c)
                top.addChildren(kids)
                tops.append(top)
            tree.addTopLevelItems(tops)
            if q:
                for top in tops:
                    top.setExpanded(True)
        finally:
            tree.setUpdatesEnabled(True)
        self.count.setText(f"{len(rows)}곡 · {len(groups)}개 {self.group.currentText()}"
                           if rows else "라이브러리가 비어 있습니다 — 폴더 추가 버튼으로 음악 폴더를 등록하세요")

    def _dbl(self, item, _c):
        kind, val = item.data(0, KEY_ROLE)
        if kind == "group":
            self.ctrl.play_mix(val, item.text(0))
        else:
            keys = item.parent().data(0, KEY_ROLE)[1]
            self.ctrl.play_mix(keys[keys.index(val):], item.parent().text(0))

    def _menu(self, pos):
        it = self.tree.itemAt(pos)
        if not it:
            return
        kind, val = it.data(0, KEY_ROLE)
        gp = self.tree.viewport().mapToGlobal(pos)
        if kind == "group":
            exec_menu(track_menu(self, self.ctrl, lambda: val), gp)
        else:
            exec_menu(track_menu(self, self.ctrl, lambda: [val], val), gp)
        self._rows_cache = None                  # 메뉴로 좋아요 · 별점을 바꿨을 수 있음 → 다음 검색은 새 값
