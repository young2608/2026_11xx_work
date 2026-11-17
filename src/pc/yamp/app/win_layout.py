"""MainWindow 화면 구성 — vr0.1.0.009

  _make_widgets()      두 배치가 함께 쓰는 위젯 만들기 (버튼은 모두 아이콘 + 설명 팝업)
  _arrange_simple()    단순 배치 (기본): 왼쪽 아이콘 레일 · 가운데 화면 · 오른쪽 가사/대기열 패널 · 아래 재생 막대
  _arrange_classic()   클래식(Winamp) 배치: 위 재생 블럭 + 탭 + 가사 (v008 까지의 모양)
  go_page() / toggle_panel()  화면 이동 · 패널 열고 닫기 (두 배치 공통 API)

┌ 메뉴바 ─────────────────────────────────────── 버전__빌드시각 ┐
│레일│ 화면 (지금 재생 · 목록 · 라이브러리 · 폴더 · 추천 · 사운드)  │ 가사/대기열 │
├────┴────────────────────────────────────────────────┴──────────┤
│ 표지 제목 ♡ │ ⤨ ⏮ (▶) ⏭ ⟳  ─ 파형 ─ │ 가사 대기열 AB 속도 슬립 🔊━ 미니 ⋯ │
└────────────────────────────────────────────────────────────────┘
"""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QButtonGroup, QFrame, QHBoxLayout, QLabel, QLineEdit, QMenu,
                             QSlider, QSplitter, QStackedWidget, QVBoxLayout, QWidget)

from ..ui import icons, metrics, tips
from ..ui.folder_view import FolderView
from ..ui.iconbutton import IconButton
from ..ui.home_view import HomeView
from ..ui.library_views import LibraryView
from ..ui.queue_view import QueueView
from ..ui.lyrics_view import LyricsView
from ..ui.metrics import CenterBox
from ..ui.wave_seek import WaveformSeek
from ..ui.playlist_view import PlaylistModel, PlaylistView
from ..ui.qtutil import exec_menu
from ..ui.sound_view import SoundView
from ..ui.toast import Toast
from ..ui.widgets import ElideLabel, LcdTime, ScrollTitle, SpectrumWidget
from .win_classic import ClassicMixin

LAYOUTS = ("simple", "classic")
PANEL_AUTO_HIDE_W = 900        # 창 폭이 이보다 좁으면 오른쪽 패널 자동으로 닫힘
COMPACT_BAR_W = 980            # 이보다 좁으면 재생 막대의 A-B · 속도 · 슬립 · 볼륨 막대를 숨김 (메뉴 · 단축키로 사용)
NOW_MAX_W = 1280              # v023: 지금 재생 카드 최대 폭(10pt 기준 px) — 넘으면 가운데 정렬


class LayoutMixin(ClassicMixin):
    # ================================================= 공통 위젯
    def _make_widgets(self):
        c = self.ctrl
        self.lcd = LcdTime(self.skin)
        self.lcd.remaining = bool(self.cfg["time_remaining"])
        self.spec = SpectrumWidget(self.skin)
        self.cover = QLabel()
        self.cover.setScaledContents(True)
        self.title = ScrollTitle(self.skin)
        self.info = QLabel("  ", objectName="info")
        self.seek = WaveformSeek()                       # 색 = 테마 wave_played / wave_rest
        tips.apply(self.seek, "seek")

        B = IconButton
        self.b_prev = B("prev", "prev", c.prev)
        self.b_play = B("play", "play", c.toggle, size=22)
        self.b_pause = B("pause", "pause", c.toggle)
        self.b_stop = B("stop", "stop", c.stop)
        self.b_next = B("next", "next", c.next)
        self.b_open = B("eject", "open", self.open_files)
        self.b_shuf = B("shuffle", "shuffle", c.toggle_shuffle, checkable=True)
        self.b_rep = B("repeat", "repeat", c.cycle_repeat)
        self.b_mute = B("volume", "mute", c.toggle_mute)
        self.vol = QSlider(Qt.Orientation.Horizontal)
        self.vol.setRange(0, 100)
        self.vol.setValue(int(self.cfg["volume"]))
        metrics.fix(self.vol, width=96)
        tips.apply(self.vol, "volume")
        self.vol.valueChanged.connect(c.set_volume)
        self.b_like = B("heartOutline", "like", lambda: c.toggle_like(), active_color="accent_text")
        self.b_ab = B("ab", "ab", c.cycle_ab, checkable=True)
        self.b_speed = B("speed", "speed", self.show_speed)
        self.b_sleep = B("moon", "sleep", self.show_sleep_menu, checkable=True)
        self.b_mini = B("lyrics", "mini_lyrics", self.toggle_mini, checkable=True)
        self.b_miniplayer = B("mini", "mini_player", self.toggle_mini_player)
        self.b_more = B("more", "more", self.show_more_menu)
        self.b_help = B("help", "help", self.show_help_overlay)
        self.search = QLineEdit()
        self.search.setClearButtonEnabled(True)
        icons.bind(self.search, self.search.addAction(icons.icon("search", "dim"),
                                                      QLineEdit.ActionPosition.LeadingPosition).setIcon, "search", "dim")
        tips.apply(self.search, "search")
        metrics.fix(self.search, width=180)

        self.model = PlaylistModel(self.ctrl.pl, self)
        self.listv = PlaylistView()
        self.listv.setModel(self.model)
        self.lyv = LyricsView(self.skin, int(self.cfg["lyrics_font_pt"]))
        self.home = HomeView(self.ctrl)
        self.libv = LibraryView(self.ctrl)
        self.queuev = QueueView(self.ctrl)
        self.folderv = FolderView(self.ctrl)
        self.soundv = SoundView(self.ctrl)
        self.toast = Toast(self)
        self.st_count = QLabel()
        self.st_lyrics = QLabel()
        self.statusBar().addWidget(self.st_count)
        self.statusBar().addPermanentWidget(self.st_lyrics)

    def _build_ui(self):
        self.layout_name = self.cfg["layout"] if self.cfg["layout"] in LAYOUTS else "simple"
        self._make_widgets()
        root = QWidget(objectName="root")
        if self.layout_name == "classic":
            self._arrange_classic(root)
        else:
            self._arrange_simple(root)
        self.setCentralWidget(root)

    # ================================================= 단순 배치 (기본)
    def _arrange_simple(self, root):
        c = self.ctrl
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        mid = QHBoxLayout()
        mid.setContentsMargins(0, 0, 0, 0)
        mid.setSpacing(0)
        outer.addLayout(mid, 1)

        # ---- 페이지
        self.pages = QStackedWidget()
        self.page_now = CenterBox(self._page_now(), NOW_MAX_W)       # v023: 아주 넓은 창에서 카드 폭 제한 · 가운데
        self.page_list = self._page(tips.name("nav_list"), self.listv,
                                    [self.search, IconButton("undo", "undo", c.undo),
                                     IconButton("addFile", "open", self.open_files)])
        self.page_lib = self._page(tips.name("nav_lib"), self.libv, [IconButton("search", "quick_find", self.show_quick_find)])
        self.page_folder = self._page(tips.name("nav_folder"), self.folderv, [])
        self.page_home = self._page(tips.name("nav_home"), self.home, [])
        self.page_sound = self._page(tips.name("nav_sound"), self.soundv, [])
        for p in (self.page_now, self.page_list, self.page_lib, self.page_folder, self.page_home, self.page_sound):
            self.pages.addWidget(p)

        # ---- 왼쪽 레일
        rail = QFrame(objectName="rail")
        metrics.fix(rail, width=56)
        rv = QVBoxLayout(rail)
        rv.setContentsMargins(8, 10, 8, 10)
        rv.setSpacing(6)
        self.rail_group = QButtonGroup(self)
        self.rail_group.setExclusive(True)
        self.rail_btns = {}
        # v014 (f26 §3.4): 맨 위 ☰ 메뉴 막대 접기/펼치기 · 그룹 [재생] [찾기] [소리] 사이 가는 선
        self.b_menu = IconButton("menu", "menu_bar", lambda: self.set_menu_bar(not bool(self.cfg["menu_bar"])),
                                 checkable=True, size=22)
        self.b_menu.setObjectName("railBtn")
        self.b_menu.setChecked(bool(self.cfg["menu_bar"]))
        rv.addWidget(self.b_menu, 0, Qt.AlignmentFlag.AlignHCenter)

        def sep():
            f = QFrame(objectName="railSep")
            f.setFixedSize(28, 1)
            rv.addWidget(f, 0, Qt.AlignmentFlag.AlignHCenter)
        for icon, key, page in (("|", "", None), ("now", "nav_now", self.page_now), ("list", "nav_list", self.page_list),
                                ("|", "", None), ("library", "nav_lib", self.page_lib), ("folder", "nav_folder", self.page_folder),
                                ("star", "nav_home", self.page_home), ("|", "", None), ("eq", "nav_sound", self.page_sound)):
            if icon == "|":
                sep()
                continue
            b = IconButton(icon, key, checkable=True, size=22)
            b.setObjectName("railBtn")
            b.clicked.connect(lambda _=False, p=page: self.go_page(p))
            self.rail_group.addButton(b)
            self.rail_btns[page] = b
            rv.addWidget(b, 0, Qt.AlignmentFlag.AlignHCenter)
        rv.addStretch(1)
        b_set = IconButton("gear", "nav_settings", self.show_settings_menu, size=22)
        b_set.setObjectName("railBtn")
        self.b_settings = b_set
        rv.addWidget(self.b_help, 0, Qt.AlignmentFlag.AlignHCenter)
        rv.addWidget(b_set, 0, Qt.AlignmentFlag.AlignHCenter)
        mid.addWidget(rail)
        mid.addWidget(self.pages, 1)

        # ---- 오른쪽 패널 (가사 / 대기열)
        self.side = QFrame(objectName="sidePanel")
        metrics.fix(self.side, min_w=260, max_w=720)           # v023: 큰 화면에서 가사 패널이 너무 넓어지지 않게
        sv = QVBoxLayout(self.side)
        sv.setContentsMargins(8, 6, 8, 8)
        head = QHBoxLayout()
        self.b_tab_lyrics = IconButton("lyrics", "panel_lyrics", checkable=True)
        self.b_tab_queue = IconButton("queue", "panel_queue", checkable=True)
        g = QButtonGroup(self)
        g.addButton(self.b_tab_lyrics)
        g.addButton(self.b_tab_queue)
        self.b_tab_lyrics.clicked.connect(lambda: self.toggle_panel("lyrics", force=True))
        self.b_tab_queue.clicked.connect(lambda: self.toggle_panel("queue", force=True))
        head.addWidget(self.b_tab_lyrics)
        head.addWidget(self.b_tab_queue)
        head.addStretch(1)
        head.addWidget(IconButton("close", "panel_close", lambda: self.toggle_panel(None), size=16))
        sv.addLayout(head)
        self.side_stack = QStackedWidget()
        self.side_stack.addWidget(self.lyv)
        self.side_stack.addWidget(self.queuev)
        sv.addWidget(self.side_stack, 1)
        self.split = QSplitter(Qt.Orientation.Horizontal)
        self.split.addWidget(self.pages)
        self.split.addWidget(self.side)
        self.split.setStretchFactor(0, 3)
        self.split.setStretchFactor(1, 2)
        self.split.setChildrenCollapsible(False)
        mid.addWidget(self.split, 1)

        # ---- 아래 재생 막대
        outer.addWidget(self._player_bar())

        # 클래식 전용 위젯 (숨김: 두 배치 공통 코드가 참조)
        self.tabs = None
        self.sec_now = self.sec_lists = self.sec_lyrics = None
        for w in (self.b_pause, self.b_stop, self.b_open, self.b_mini):
            w.setParent(self)
            w.hide()

        start = {"now": self.page_now, "list": self.page_list, "lib": self.page_lib, "folder": self.page_folder,
                 "home": self.page_home, "sound": self.page_sound}.get(str(self.cfg["last_page"]), self.page_now)
        self.go_page(start)
        panel = str(self.cfg["side_panel"])
        self.toggle_panel(panel if panel in ("lyrics", "queue") else None, force=True)

    def _page(self, title, body, tools):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(14, 10, 14, 8)
        v.setSpacing(8)
        h = QHBoxLayout()
        t = QLabel(title, objectName="pageTitle")
        h.addWidget(t)
        h.addStretch(1)
        for tw in tools:
            h.addWidget(tw)
        v.addLayout(h)
        v.addWidget(body, 1)
        w.tools = tools
        w.title_label = t
        return w

    def _player_bar(self):
        bar = QFrame(objectName="playerBar")
        metrics.fix(bar, height=84)
        h = QHBoxLayout(bar)
        h.setContentsMargins(12, 6, 12, 6)
        h.setSpacing(10)
        # 왼쪽: 표지 · 제목 · 가수/형식 · 좋아요
        left = QHBoxLayout()
        self.bar_cover = QLabel()
        metrics.fix(self.bar_cover, 52, 52)
        self.bar_cover.setScaledContents(True)
        left.addWidget(self.bar_cover)
        tv = QVBoxLayout()
        tv.setSpacing(0)
        self.bar_title = ElideLabel("yMp3Player", objectName="barTitle")      # v016: 길면 … (잘림 없음)
        self.bar_sub = ElideLabel("", objectName="barSub")
        for lb in (self.bar_title, self.bar_sub):
            metrics.fix(lb, max_w=220)
            lb.setMinimumWidth(40)
        tv.addStretch(1)
        tv.addWidget(self.bar_title)
        tv.addWidget(self.bar_sub)
        tv.addStretch(1)
        left.addLayout(tv)
        left.addWidget(self.b_like)
        lw = QWidget()
        lw.setLayout(left)
        metrics.fix(lw, min_w=190, max_w=320)
        h.addWidget(lw)
        # 가운데: 조작 + 파형
        mid = QVBoxLayout()
        mid.setSpacing(2)
        row = QHBoxLayout()
        row.addStretch(1)
        self.b_play.setObjectName("playBig")
        self.b_play.set_colors("on_fill", "on_fill")        # 노랑→주황 채움 위 아이콘
        for b in (self.b_shuf, self.b_prev, self.b_play, self.b_next, self.b_rep):
            row.addWidget(b)
        row.addStretch(1)
        mid.addLayout(row)
        srow = QHBoxLayout()
        self.bar_pos = QLabel("0:00", objectName="barTime")
        self.bar_dur = QLabel("0:00", objectName="barTime")
        metrics.fix(self.seek, height=max(24, min(80, int(self.cfg["wave_height"]))))   # v017: 곡 파형 높이 (config wave_height)
        srow.addWidget(self.bar_pos)
        srow.addWidget(self.seek, 1)
        srow.addWidget(self.bar_dur)
        mid.addLayout(srow)
        h.addLayout(mid, 1)
        # 오른쪽: 패널 · A-B · 속도 · 슬립 · 볼륨 · 미니 · 더보기
        self.b_panel_lyrics = IconButton("lyrics", "panel_lyrics", lambda: self.toggle_panel("lyrics"), checkable=True)
        self.b_panel_queue = IconButton("queue", "panel_queue", lambda: self.toggle_panel("queue"), checkable=True)
        right = QHBoxLayout()
        right.setSpacing(2)
        def bsep():                                          # v014: 그룹 구분선 [패널] ┃ [재생 도구] ┃ [볼륨] ┃ [창]
            f = QFrame(objectName="barSep")
            metrics.fix(f, 1, 22)
            right.addSpacing(4)
            right.addWidget(f)
            right.addSpacing(4)
        for b in (self.b_panel_lyrics, self.b_panel_queue):
            right.addWidget(b)
        bsep()
        for b in (self.b_ab, self.b_speed, self.b_sleep):
            right.addWidget(b)
        bsep()
        right.addWidget(self.b_mute)
        right.addWidget(self.vol)
        bsep()
        right.addWidget(self.b_miniplayer)
        right.addWidget(self.b_more)
        rw = QWidget()
        rw.setLayout(right)
        h.addWidget(rw)
        return bar


    # ================================================= 공통 API
    def is_simple(self) -> bool:
        return self.layout_name != "classic"

    def go_page(self, page):
        """page: 페이지 위젯 또는 내용 위젯 (soundv · folderv …)"""
        if not self.is_simple():
            target = page
            for content in (self.listv, self.home, self.libv, self.queuev, self.folderv, self.soundv):
                if page is content:
                    target = content
            if self.sec_lists is not None:
                self.sec_lists.set_open(True)
            if self.tabs.indexOf(target) >= 0:
                self.tabs.setCurrentWidget(target)
            return
        by_content = {self.listv: self.page_list, self.libv: self.page_lib, self.folderv: self.page_folder,
                      self.home: self.page_home, self.soundv: self.page_sound}
        if page is self.queuev:
            self.toggle_panel("queue", force=True)
            return
        page = by_content.get(page, page)
        if self.pages.indexOf(page) < 0:
            return
        self.pages.setCurrentWidget(page)
        self.rail_btns[page].setChecked(True)
        names = {self.page_now: "now", self.page_list: "list", self.page_lib: "lib", self.page_folder: "folder",
                 self.page_home: "home", self.page_sound: "sound"}
        self.cfg["last_page"] = names.get(page, "now")
        if hasattr(self, "_sync_vis"):
            self._sync_vis()

    def current_page(self):
        return self.pages.currentWidget() if self.is_simple() else self.tabs.currentWidget()

    def toggle_panel(self, which, force=False):
        """오른쪽 패널: 'lyrics' / 'queue' / None(닫기). 같은 버튼을 다시 누르면 닫힘"""
        if not self.is_simple():
            if which == "lyrics" and self.sec_lyrics is not None:
                self.sec_lyrics.set_open(not self.sec_lyrics.is_open() if not force else True)
            elif which == "queue":
                self.tabs.setCurrentWidget(self.queuev)
            return
        cur = self.cfg["side_panel"] if self.side.isVisible() else ""
        if which and which == cur and not force:
            which = None
        if which is None:
            self.side.hide()
            self.cfg["side_panel"] = ""
        else:
            self.side_stack.setCurrentWidget(self.lyv if which == "lyrics" else self.queuev)
            self.side.show()
            self.cfg["side_panel"] = which
        for b, k in ((self.b_panel_lyrics, "lyrics"), (self.b_panel_queue, "queue"),
                     (self.b_tab_lyrics, "lyrics"), (self.b_tab_queue, "queue")):
            b.blockSignals(True)
            b.setChecked(which == k)
            b.blockSignals(False)
            b._paint()

    def _auto_panel(self):
        """창이 좁아지면 패널 닫기, 넓어지면 다시 (사용자가 연 상태였으면)"""
        if not self.is_simple():
            return
        kk = metrics.k()                                     # v023: 글자가 크면 더 일찍 줄임
        narrow = self.width() < COMPACT_BAR_W * kk
        for b in (self.b_ab, self.b_speed, self.b_sleep, self.vol):
            b.setVisible(not narrow)
        want = str(self.cfg["side_panel"] or "")
        if self.width() < PANEL_AUTO_HIDE_W * kk:
            if self.side.isVisible():
                self.side.hide()
        elif want and not self.side.isVisible():
            self.toggle_panel(want, force=True)

    def show_more_menu(self):
        m = QMenu(self)
        m.addAction(icons.icon("stop", "dim"), tips.plain("stop"), self.ctrl.stop)
        m.addAction(icons.icon("eject", "dim"), tips.plain("open"), self.open_files)
        m.addAction(icons.icon("lyrics", "dim"), tips.plain("mini_lyrics"), self.toggle_mini)
        m.addAction(icons.icon("search", "dim"), tips.plain("quick_find"), self.show_quick_find)
        m.addSeparator()
        m.addAction("목록 비우기", self.ctrl.clear)
        exec_menu(m, self.b_more.mapToGlobal(self.b_more.rect().bottomLeft()))

    def show_settings_menu(self):
        self.menu_view.exec(self.b_settings.mapToGlobal(self.b_settings.rect().topRight()))   # 보기 메뉴 그대로 (삭제하지 않음)

    def _page_shortcuts(self):
        """화면 이동 단축키는 보기 메뉴(Ctrl+1~6)에 있음 — 메뉴와 겹치는 QShortcut 은 만들지 않음 (둘 다 안 먹는 문제)"""
