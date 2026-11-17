"""MainWindow 클래식(Winamp) 배치 — v008 까지의 모양 (보기 → 배치 → 클래식, 다시 시작하면 적용)"""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QSplitter, QTabWidget, QVBoxLayout, QWidget

from ..ui import icons, metrics, tips
from ..ui.section import Section


class ClassicMixin:
    # ================================================= 클래식 배치 (v008 모양)
    def _arrange_classic(self, root):
        v = QVBoxLayout(root)
        v.setContentsMargins(6, 6, 6, 6)
        v.setSpacing(6)
        top = QFrame(objectName="topPanel")
        tv = QVBoxLayout(top)
        tv.setContentsMargins(8, 4, 8, 8)
        now = QWidget()
        nv = QVBoxLayout(now)
        nv.setContentsMargins(0, 0, 0, 0)
        row1 = QHBoxLayout()
        lcd = QFrame(objectName="lcd")
        lh = QHBoxLayout(lcd)
        lh.setContentsMargins(4, 2, 4, 2)
        lh.addWidget(self.lcd)
        lh.addWidget(self.spec, 1)
        row1.addWidget(lcd, 0)
        metrics.fix(self.cover, 52, 52)
        row1.addWidget(self.cover)
        right = QVBoxLayout()
        right.addWidget(self.title)
        right.addWidget(self.info)
        row1.addLayout(right, 1)
        nv.addLayout(row1)
        nv.addWidget(self.seek)
        self.sec_now = Section("지금 재생", "main.now", self.cfg, now, card=False)
        tv.addWidget(self.sec_now)
        row3 = QHBoxLayout()
        self.b_play.clicked.disconnect()
        self.b_play.clicked.connect(self.ctrl.play)
        tips.apply(self.b_play, "play")
        for b in (self.b_prev, self.b_play, self.b_pause, self.b_stop, self.b_next, self.b_open):
            row3.addWidget(b)
        row3.addSpacing(10)
        for b in (self.b_shuf, self.b_rep):
            row3.addWidget(b)
        row3.addSpacing(10)
        row3.addWidget(self.b_mute)
        row3.addWidget(self.vol)
        row3.addStretch(1)
        for b in (self.b_like, self.b_ab, self.b_speed, self.b_sleep, self.b_mini, self.b_miniplayer, self.b_help):
            row3.addWidget(b)
        row3.addWidget(self.search)
        tv.addLayout(row3)
        v.addWidget(top)
        self.split = QSplitter(Qt.Orientation.Horizontal)
        self.tabs = QTabWidget()
        self.tabs.addTab(self.listv, "재생목록")
        self.tabs.addTab(self.home, "추천")
        self.tabs.addTab(self.libv, "라이브러리")
        self.tabs.addTab(self.queuev, "대기열")
        self.tabs.addTab(self.folderv, "폴더")
        self.tabs.addTab(self.soundv, "사운드")
        for i, name in ((4, "folder"), (5, "eq")):           # 탭 아이콘: 테마가 바뀌면 다시 칠함
            icons.bind(self.tabs, lambda ic, i=i: self.tabs.setTabIcon(i, ic), name, "dim")
        self.sec_lists = Section("목록", "main.lists", self.cfg, self.tabs)
        self.sec_lyrics = Section("가사", "main.lyrics", self.cfg, self.lyv)
        self.sec_lyrics.toggled.connect(self._on_lyrics_fold)
        self.split.addWidget(self.sec_lists)
        self.split.addWidget(self.sec_lyrics)
        self.split.setStretchFactor(0, 1)
        self.split.setStretchFactor(1, 1)
        v.addWidget(self.split, 1)
        self.pages = None
        self.side = None
        self.bar_cover = self.bar_title = self.bar_sub = self.bar_pos = self.bar_dur = None
        self.b_panel_lyrics = self.b_panel_queue = None
