"""MainWindow 기능 묶음 — 메뉴바 만들기 · 단축키 · 슬립 메뉴 · 도움말

MainWindow(QMainWindow) 가 이 믹스인을 상속 (vr0.1.0.007 모듈화).
vr0.1.0.030 (f58): 233줄 _build_menu → 메뉴마다 함수 하나 (_menu_file … _menu_help)
                   + 반복되던 '설정 켜기/끄기' · '하나만 고르기' 를 _check · _radio 로.
                   제목 줄 · 메뉴 막대 접기 · Alt · 상단 바 설정은 win_menubar.py."""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QActionGroup, QKeySequence, QShortcut
from PyQt6.QtWidgets import QMessageBox

from ..core.version import APP_NAME, version_label
from ..ui import skin as skinmod

CROSSFADE_S = (0, 2, 4, 6, 8, 12)
REPLAYGAIN = (("off", "끔"), ("track", "곡 기준"), ("album", "앨범 기준"))
LYRIC_FONT_PT = (11, 13, 15, 18, 22)
LYRIC_PROVIDERS = (("lyrics_local", "같은 폴더 .lrc"), ("lyrics_embedded", "태그 내장 가사"),
                   ("lyrics_alsong", "알송 (비공식)"), ("lyrics_lrclib", "LRCLIB"),
                   ("lyrics_netease", "NetEase (비공식, K-pop·J-pop·번역)"),
                   ("lyrics_save_beside", "찾은 가사를 음악 옆 .lrc 로도 저장"))
FONT_LABELS = ("작게", "보통", "조금 크게", "크게", "더 크게", "아주 크게", "아주 크게+", "가장 크게")   # v033: 15 · 16pt (4K 100 % · 큰 화면)
TOPBAR_OPTS = (("topbar_ticker", "업비트 시세 표시"), ("topbar_clock", "KST 시계"),
               ("topbar_clock_seconds", "초까지 표시"))
LAYOUTS = (("simple", "단순 (아이콘 레일 · 아래 재생 막대)"), ("classic", "클래식 (Winamp 모양)"))
SLEEP_MIN = (15, 30, 45, 60, 90)


class MenuMixin:
    # ================================================================ 공용 도우미
    def _check(self, menu, label, cfg_key, on_toggle=None, key=None):
        """설정 값 하나를 켜고 끄는 체크 메뉴 (기본 동작 = cfg[cfg_key] 에 저장)"""
        a = menu.addAction(label)
        if key:
            a.setShortcut(QKeySequence(key))
        a.setCheckable(True)
        a.setChecked(bool(self.cfg[cfg_key]))
        a.toggled.connect(on_toggle or (lambda v, k=cfg_key: self.cfg.__setitem__(k, v)))
        return a

    def _radio(self, menu, items, current, fn):
        """(값, 이름) 목록 중 하나만 고르는 메뉴 → {값: QAction}"""
        g = QActionGroup(self)
        out = {}
        for v, label in items:
            a = menu.addAction(label, lambda v=v: fn(v))
            a.setCheckable(True)
            a.setChecked(v == current)
            g.addAction(a)
            out[v] = a
        return out

    def _set_cfg(self, key):
        return lambda v: self.cfg.__setitem__(key, v)

    # ================================================================ 메뉴바
    def _build_menu(self):
        mb = self.menuBar()
        self._menu_file(mb.addMenu("파일(&F)"))
        self._menu_play(mb.addMenu("재생(&P)"))
        self._menu_lyrics(mb.addMenu("가사(&L)"))
        self.menu_view = mb.addMenu("보기(&V)")
        self._menu_view(self.menu_view)
        self._menu_tools(mb.addMenu("도구(&T)"))
        self._menu_help(mb.addMenu("도움말(&H)"))
        # 규칙 9 '버전__빌드시각' — vr0.1.0.014 (f26): 제목 줄 한 곳에 [곡 - 앱 버전 │ XRP │ KST]
        from .topbar import TopBar
        self.topbar = TopBar(self.cfg, self)
        self.topbar.hide()                                  # 시세 · 시각 계산만 (화면에는 제목 줄 글자로)
        self.ver_label = self.topbar.ver
        self.topbar.changed.connect(self.update_title)

    def _menu_file(self, m):
        c = self.ctrl
        m.addAction("파일 열기…", QKeySequence("Ctrl+O"), self.open_files)
        m.addAction("폴더 열기…", QKeySequence("Ctrl+Shift+O"), self.open_folder)
        m.addAction("폴더 재생…", QKeySequence("Ctrl+Shift+P"), self.play_folder_dialog)
        m.addAction("마지막 폴더 다시 재생", self.play_last_folder)
        m.addSeparator()
        m.addAction("플레이리스트 열기…", self.open_playlist)
        m.addAction("플레이리스트 저장…", QKeySequence("Ctrl+S"), self.save_playlist)
        m.addAction("목록 비우기", c.clear)
        m.addAction("되돌리기", QKeySequence("Ctrl+Z"), c.undo)
        m.addSeparator()
        m.addAction("종료", QKeySequence("Ctrl+Q"), self.quit_app)

    def _menu_play(self, m):
        c = self.ctrl
        m.addAction("재생 / 일시정지", c.toggle)
        m.addAction("정지", c.stop)
        m.addAction("이전 곡", c.prev)
        m.addAction("다음 곡", c.next)
        m.addSeparator()
        m.addAction("5초 뒤로", lambda: c.seek_rel(-5000))
        m.addAction("5초 앞으로", lambda: c.seek_rel(5000))
        m.addSeparator()
        self.a_shuf = m.addAction("셔플", c.toggle_shuffle)
        self.a_shuf.setCheckable(True)
        self.a_rep = m.addAction("반복 전환", c.cycle_repeat)
        m.addSeparator()
        m.addAction("재생 속도 · 음정…", self.show_speed)
        m.addAction("구간 반복 A-B", QKeySequence("["), c.cycle_ab)
        self._fill_sleep_menu(m.addMenu("슬립 타이머"))
        m.addAction("사운드 (이퀄라이저 · 톤 · 다이내믹)", QKeySequence("Ctrl+E"), self.show_sound)
        self._radio(m.addMenu("곡 전환 페이드"), [(s, "끔" if s == 0 else f"{s}초") for s in CROSSFADE_S],
                    int(self.cfg["crossfade_s"] or 0), self._set_cfg("crossfade_s"))
        self._radio(m.addMenu("음량 맞춤 (ReplayGain)"), REPLAYGAIN, self.cfg["replaygain"], self._set_cfg("replaygain"))
        m.addSeparator()
        m.addAction("좋아요 ♥", QKeySequence("F"), lambda: c.toggle_like())
        m.addAction("이 곡으로 라디오", QKeySequence("Ctrl+R"), lambda: c.radio())
        m.addSeparator()
        self.a_resume = self._check(m, "시작 시 이어 듣기", "resume_on_start")
        vm = m.addMenu("녹음·강의 듣기")                     # vr0.1.0.010 (V1 · V2)
        self.a_silence = self._check(vm, "무음 건너뛰기 (mpv 엔진)", "skip_silence", lambda v: c.set_skip_silence(v))
        self.a_resume_long = self._check(vm, "30분 넘는 파일 이어 듣기", "resume_long")
        vm.addAction("음성 또렷하게 (사운드 프리셋 '음성')", lambda: c.apply_preset("음성"))

    def _menu_lyrics(self, m):
        c = self.ctrl
        m.addAction("가사 다시 찾기", QKeySequence("F5"), lambda: c.research_lyrics())
        m.addAction("가사를 .lrc 로 저장 (음악 폴더)", self.save_lrc)
        m.addAction("가사 편집기…", QKeySequence("Ctrl+Shift+K"), self.show_lyrics_editor)
        m.addAction("다른 가사 찾기…", QKeySequence("Ctrl+Shift+F"), self.show_lyrics_pick)
        m.addAction("가사 진단… (못 찾는 이유 확인)", self.show_lyrics_diag)
        tl = m.addMenu("3단 가사 (원문/발음/번역)")
        self.a_pron = self._check(tl, "발음 줄 표시", "lyric_show_pron", lambda v: self._set_three("lyric_show_pron", v))
        self.a_trans = self._check(tl, "번역 줄 표시", "lyric_show_trans", lambda v: self._set_three("lyric_show_trans", v))
        m.addSeparator()
        m.addAction("싱크 +0.5초 (가사 빠르게)", QKeySequence("Ctrl+]"), lambda: c.adjust_offset(500))
        m.addAction("싱크 -0.5초 (가사 느리게)", QKeySequence("Ctrl+["), lambda: c.adjust_offset(-500))
        m.addAction("싱크 초기화", lambda: c.adjust_offset(None))
        m.addSeparator()
        self.a_mini = m.addAction("미니 가사창", QKeySequence("Ctrl+L"), self.toggle_mini)
        self.a_mini.setCheckable(True)
        self.a_mini_lock = m.addAction("미니 가사 잠금 (클릭 통과)", self._toggle_mini_lock)
        self.a_mini_lock.setCheckable(True)
        self.a_mini_lock.setChecked(bool(self.cfg["mini_click_through"]))
        fm = m.addMenu("글자 크기")
        for pt in LYRIC_FONT_PT:
            fm.addAction(f"{pt}pt", lambda pt=pt: self._set_lyrics_font(pt))
        pm = m.addMenu("가사 공급자")
        for key, label in LYRIC_PROVIDERS:
            self._check(pm, label, key)
        m.addAction("가사 캐시 폴더 열기", self.open_cache)

    def _menu_view(self, m):
        self._menu_theme(m.addMenu("테마"))
        self.a_top = m.addAction("항상 위", self.toggle_on_top)
        self.a_top.setCheckable(True)
        self.a_top.setChecked(bool(self.cfg["always_on_top"]))
        self.a_spec = self._check(m, "스펙트럼", "spectrum", self._toggle_spec)
        self.a_wave = self._check(m, "파형 시크바", "waveform", self._toggle_wave)
        m.addSeparator()
        m.addAction("모든 블럭 펼치기", lambda: self.set_all_sections(True))
        m.addAction("모든 블럭 접기", lambda: self.set_all_sections(False))
        m.addAction("지금 재생 블럭 기본 크기 (모두 펼침)", lambda: self.reset_now_blocks())
        self._menu_font(m.addMenu("글자 크기"))
        m.addSeparator()
        self._menu_pages(m)
        m.addSeparator()
        m.addAction("가사 패널", QKeySequence("Ctrl+Shift+L"), lambda: self.toggle_panel("lyrics"))
        self._menu_topbar(m.addMenu("상단 바 (시세 · 시각)"))
        self.a_menubar = m.addAction("메뉴 막대 접기 (Alt = 잠깐 보기)", QKeySequence("Ctrl+Shift+M"))
        self.a_menubar.setCheckable(True)
        self.a_menubar.setChecked(not bool(self.cfg["menu_bar"]))
        self.a_menubar.toggled.connect(lambda v: self.set_menu_bar(not v))
        m.addAction("대기열 패널", QKeySequence("Ctrl+J"), lambda: self.toggle_panel("queue"))
        m.addAction("미니 플레이어", QKeySequence("Ctrl+M"), self.toggle_mini_player)
        m.addAction("빠른 찾기", QKeySequence("Ctrl+K"), self.show_quick_find)
        m.addSeparator()
        self._radio(m.addMenu("화면 배치 (다시 시작하면 적용)"), LAYOUTS, self.layout_name, self._set_layout)

    def _menu_theme(self, tm):
        """vr0.1.0.011 색 견본 · 바로 적용 / v024 단계 테마 묶음 / v025 한 단계씩"""
        from ..ui import icons as _icons
        g = QActionGroup(self)
        self.theme_actions = {}
        extra = {skinmod.DEFAULT: " (기본)", "neon": " (이전 기본)"}
        levels = getattr(skinmod, "LEVELS", ())
        cur = skinmod.resolve(self.cfg["theme"])
        for name, s in skinmod.SKINS.items():
            if name in levels and name.endswith("1"):
                tm.addSection("라이트 5단계 (+ = 덜 눈부시게)" if name.startswith("light") else "다크 5단계 (+ = 더 어둡게)")
            a = tm.addAction(_icons.swatch((s.bg, s.fill1, s.fill2)), s.label + extra.get(name, ""),
                             lambda n=name: self.apply_skin(n))
            a.setCheckable(True)
            a.setChecked(name == cur)
            g.addAction(a)
            self.theme_actions[name] = a
        tm.addSeparator()
        self.a_follow_dark = self._check(tm, "Windows 어두운 모드 따라가기", "follow_system_dark", self.set_follow_system_dark)
        self.a_follow_dark.setToolTip("켜면 Windows 가 어두운 모드일 때 써니 → 나이트 써니, 라이트 n단계 → 다크 n단계, 다른 밝은 테마 → 다크 블루")
        tm.addSeparator()
        tm.addAction("한 단계 밝게", QKeySequence("Ctrl+Shift+PgUp"), lambda: self.step_theme(-1))
        tm.addAction("한 단계 어둡게", QKeySequence("Ctrl+Shift+PgDown"), lambda: self.step_theme(1))

    def _menu_font(self, fsm):
        """v016 바로 적용 / v023 자동 / v025 한 단계씩"""
        gf = QActionGroup(self)
        self.a_font_sizes = {}
        self.a_font_auto = fsm.addAction("자동 (화면 크기에 맞춤)", lambda: self.set_font_size(None))
        self.a_font_auto.setCheckable(True)
        self.a_font_auto.setChecked(bool(self.cfg["font_auto"]))
        gf.addAction(self.a_font_auto)
        fsm.addAction("크게", QKeySequence("Ctrl+="), lambda: self.step_font(1))
        fsm.addAction("작게", QKeySequence("Ctrl+-"), lambda: self.step_font(-1))
        self.a_font_auto.setShortcut(QKeySequence("Ctrl+0"))
        fsm.addSeparator()
        for pt, label in zip(skinmod.FONT_SIZES, FONT_LABELS):
            a = fsm.addAction(f"{label} ({pt}pt)", lambda p=pt: self.set_font_size(p))
            a.setCheckable(True)
            a.setData(pt)
            a.setChecked(not self.cfg["font_auto"] and int(self.cfg["font_size"]) == pt)
            gf.addAction(a)
            self.a_font_sizes[pt] = a

    def _menu_pages(self, m):
        """화면 이동 (단순 배치: 왼쪽 레일과 같음 / 클래식: 탭 — '지금 재생' 은 단순 배치에만)"""
        if self.is_simple():
            m.addAction("지금 재생", QKeySequence("Ctrl+1"), lambda: self.go_page(self.page_now))
        for label, key, target in (("재생 목록", "Ctrl+2", self.listv), ("라이브러리", "Ctrl+3", self.libv),
                                   ("폴더", "Ctrl+4", self.folderv), ("추천", "Ctrl+5", self.home),
                                   ("사운드", "Ctrl+6", self.soundv)):
            m.addAction(label, QKeySequence(key), lambda t=target: self.go_page(t))

    def _menu_topbar(self, bm):
        """vr0.1.0.012 (f23) 업비트 시세 · KST 시계"""
        self.topbar_actions = {k: self._check(bm, label, k, lambda v, k=k: self.set_topbar_option(k, v))
                               for k, label in TOPBAR_OPTS}
        bm.addAction("마켓 바꾸기… (예: KRW-XRP,KRW-BTC)", self.ask_ticker_market)
        bm.addAction("시세 지금 새로 고침", lambda: self.topbar.svc.refresh())
        bm.addAction("시세 상세 보기…", self.show_ticker_detail)

    def _menu_tools(self, m):
        m.addAction("곡 정보(태그) 편집…", self.edit_current_tags)
        m.addAction("라이브러리 폴더 추가…", self.add_library_folder)
        m.addAction("라이브러리 다시 스캔", self.ctrl.scan_library)
        m.addAction("추천 새로고침", self.home.refresh)
        m.addSeparator()
        self.a_hist = self._check(m, "재생 기록 사용 (추천)", "history_enabled")
        m.addAction("재생 기록 지우기…", self.clear_history)
        self.a_tray = self._check(m, "닫기(X) = 트레이로", "close_to_tray")

    def _menu_help(self, m):
        m.addAction("버튼 이름 보기", QKeySequence("F1"), self.show_help_overlay)
        m.addAction("단축키", self.show_keys)
        m.addAction("화면 정보 (배율 · 글꼴)…", self.show_screen_info)      # v016 (f29 G10)
        m.addAction("정보", self.show_about)

    def _fill_sleep_menu(self, m):
        for mins in SLEEP_MIN:
            m.addAction(f"{mins}분 뒤", lambda mins=mins: self.ctrl.sleep_start(mins))
        m.addAction("곡 끝날 때", lambda: self.ctrl.sleep_start("track"))
        m.addAction("직접 입력…", self._sleep_custom)
        m.addSeparator()
        m.addAction("끄기", self.ctrl.sleep_cancel)
        m.addSeparator()
        em = m.addMenu("재생 목록이 끝나면")
        for k, label in self.ctrl.END_ACTIONS.items():
            a = em.addAction(label, lambda k=k: self.ctrl.set_end_action(k))
            a.setCheckable(True)
            a.setChecked(str(self.cfg["end_action"]) == k)
        m.addAction("PC 종료 취소", self.ctrl.cancel_shutdown)
        m.addAction(f"알람… ({self.cfg['alarm_time'] or '끔'})", self.show_alarm_dialog)

    # ================================================================ 단축키 · 도움말
    def _build_shortcuts(self):
        c = self.ctrl
        keys = {
            "Space": c.toggle, "Z": c.prev, "X": c.play, "C": c.toggle, "V": c.stop, "B": c.next,
            "Left": lambda: c.seek_rel(-5000), "Right": lambda: c.seek_rel(5000),
            "Ctrl+Left": c.prev, "Ctrl+Right": c.next,
            "+": lambda: self.vol.setValue(self.vol.value() + 5),
            "=": lambda: self.vol.setValue(self.vol.value() + 5),
            "-": lambda: self.vol.setValue(self.vol.value() - 5),
            "S": c.toggle_shuffle, "R": c.cycle_repeat, "M": c.toggle_mute, "L": self.toggle_mini,
            "Ctrl+F": lambda: self.search.setFocus(),
            "Media Play": c.toggle, "Media Next": c.next, "Media Previous": c.prev, "Media Stop": c.stop,
            "Toggle Media Play/Pause": c.toggle,
        }
        for k, fn in keys.items():
            sc = QShortcut(QKeySequence(k), self)
            sc.setContext(Qt.ShortcutContext.WindowShortcut)
            sc.activated.connect(fn)

    def show_keys(self):
        from ..ui import tips
        rows = "".join(f"<tr><td style='padding-right:18px'>{n}</td><td><b>{k}</b></td></tr>" for n, k in tips.shortcut_rows())
        QMessageBox.information(self, "단축키", (
            f"<table>{rows}</table><br>Del : 선택 삭제 · Ctrl+↑/↓ : 순서 이동 · 가사 줄 더블클릭 : 그 위치로<br>"
            "가사 편집기 Ctrl+Shift+K · 다른 가사 찾기 Ctrl+Shift+F · 가사 싱크 Ctrl+] / Ctrl+[ · 다시 찾기 F5<br>"
            "글자 크게 / 작게 / 자동 Ctrl+= / Ctrl+- / Ctrl+0 · 테마 한 단계 밝게 / 어둡게 Ctrl+Shift+PgUp / PgDown"))

    def show_about(self):
        QMessageBox.about(self, APP_NAME, (
            f"<b>{APP_NAME}</b> {version_label()}<br>Winamp 컨셉 음악 플레이어 + 싱크 가사<br><br>"
            "가사: 로컬 .lrc · 태그 내장 · 알송(비공식, 개인 사용) · LRCLIB · NetEase(선택, 비공식)<br>"
            "가사는 저작물입니다. 캐시는 개인 사용 목적으로만 저장됩니다.<br><br>"
            f"설정: {self.cfg.path}<br>데이터: {self.cfg.data_dir}"))
