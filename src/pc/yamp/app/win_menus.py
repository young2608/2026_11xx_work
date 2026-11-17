"""MainWindow 기능 묶음 — 메뉴바 · 단축키 · 슬립 메뉴 · 도움말

MainWindow(QMainWindow) 가 이 믹스인을 상속 (vr0.1.0.007 모듈화)."""

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QActionGroup, QKeySequence, QShortcut
from PyQt6.QtWidgets import QInputDialog, QMessageBox

from ..core.version import APP_NAME, title_label, version_label
from ..ui import skin as skinmod


class MenuMixin:
    def _build_menu(self):
        mb = self.menuBar()
        c = self.ctrl
        m = mb.addMenu("파일(&F)")
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

        m = mb.addMenu("재생(&P)")
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
        sm = m.addMenu("슬립 타이머")
        self._fill_sleep_menu(sm)
        m.addAction("사운드 (이퀄라이저 · 톤 · 다이내믹)", QKeySequence("Ctrl+E"), self.show_sound)
        fm2 = m.addMenu("곡 전환 페이드")
        g2 = QActionGroup(self)
        for sec in (0, 2, 4, 6, 8, 12):
            a = fm2.addAction("끔" if sec == 0 else f"{sec}초", lambda s=sec: self.cfg.__setitem__("crossfade_s", s))
            a.setCheckable(True)
            a.setChecked(int(self.cfg["crossfade_s"] or 0) == sec)
            g2.addAction(a)
        rgm = m.addMenu("음량 맞춤 (ReplayGain)")
        g3 = QActionGroup(self)
        for k, label in (("off", "끔"), ("track", "곡 기준"), ("album", "앨범 기준")):
            a = rgm.addAction(label, lambda k=k: self.cfg.__setitem__("replaygain", k))
            a.setCheckable(True)
            a.setChecked(self.cfg["replaygain"] == k)
            g3.addAction(a)
        m.addSeparator()
        m.addAction("좋아요 ♥", QKeySequence("F"), lambda: c.toggle_like())
        m.addAction("이 곡으로 라디오", QKeySequence("Ctrl+R"), lambda: c.radio())
        m.addSeparator()
        self.a_resume = m.addAction("시작 시 이어 듣기")
        self.a_resume.setCheckable(True)
        self.a_resume.setChecked(bool(self.cfg["resume_on_start"]))
        self.a_resume.toggled.connect(lambda v: self.cfg.__setitem__("resume_on_start", v))
        # vr0.1.0.010 녹음·강의 (V1·V2)
        vm = m.addMenu("녹음·강의 듣기")
        self.a_silence = vm.addAction("무음 건너뛰기 (mpv 엔진)")
        self.a_silence.setCheckable(True)
        self.a_silence.setChecked(bool(self.cfg["skip_silence"]))
        self.a_silence.toggled.connect(lambda v: c.set_skip_silence(v))
        self.a_resume_long = vm.addAction("30분 넘는 파일 이어 듣기")
        self.a_resume_long.setCheckable(True)
        self.a_resume_long.setChecked(bool(self.cfg["resume_long"]))
        self.a_resume_long.toggled.connect(lambda v: self.cfg.__setitem__("resume_long", v))
        vm.addAction("음성 또렷하게 (사운드 프리셋 '음성')", lambda: c.apply_preset("음성"))

        m = mb.addMenu("가사(&L)")
        m.addAction("가사 다시 찾기", QKeySequence("F5"), lambda: c.research_lyrics())
        m.addAction("가사를 .lrc 로 저장 (음악 폴더)", self.save_lrc)
        m.addAction("가사 편집기…", QKeySequence("Ctrl+Shift+K"), self.show_lyrics_editor)
        m.addAction("다른 가사 찾기…", QKeySequence("Ctrl+Shift+F"), self.show_lyrics_pick)
        m.addAction("가사 진단… (못 찾는 이유 확인)", self.show_lyrics_diag)
        tl = m.addMenu("3단 가사 (원문/발음/번역)")
        self.a_pron = tl.addAction("발음 줄 표시")
        self.a_trans = tl.addAction("번역 줄 표시")
        for a, k in ((self.a_pron, "lyric_show_pron"), (self.a_trans, "lyric_show_trans")):
            a.setCheckable(True)
            a.setChecked(bool(self.cfg[k]))
            a.toggled.connect(lambda v, k=k: self._set_three(k, v))
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
        for pt in (11, 13, 15, 18, 22):
            fm.addAction(f"{pt}pt", lambda pt=pt: self._set_lyrics_font(pt))
        pm = m.addMenu("가사 공급자")
        for key, label in (("lyrics_local", "같은 폴더 .lrc"), ("lyrics_embedded", "태그 내장 가사"),
                           ("lyrics_alsong", "알송 (비공식)"), ("lyrics_lrclib", "LRCLIB"),
                           ("lyrics_netease", "NetEase (비공식, K-pop·J-pop·번역)"),
                           ("lyrics_save_beside", "찾은 가사를 음악 옆 .lrc 로도 저장")):
            a = pm.addAction(label)
            a.setCheckable(True)
            a.setChecked(bool(self.cfg[key]))
            a.toggled.connect(lambda v, k=key: self.cfg.__setitem__(k, v))
        m.addAction("가사 캐시 폴더 열기", self.open_cache)

        m = mb.addMenu("보기(&V)")
        self.menu_view = m
        tm = m.addMenu("테마")                       # vr0.1.0.011: 색 견본(배경·노랑·주황) · 바로 적용
        from ..ui import icons as _icons
        g = QActionGroup(self)
        self.theme_actions = {}
        extra = {skinmod.DEFAULT: " (기본)", "neon": " (이전 기본)"}
        levels = getattr(skinmod, "LEVELS", ())
        for name, s in skinmod.SKINS.items():
            if name in levels and name.endswith("1"):            # v024: 단계 테마 묶음 제목 (라이트 5단계 · 다크 5단계)
                tm.addSection("라이트 5단계 (+ = 덜 눈부시게)" if name.startswith("light") else "다크 5단계 (+ = 더 어둡게)")
            a = tm.addAction(_icons.swatch((s.bg, s.fill1, s.fill2)), s.label + extra.get(name, ""),
                             lambda n=name: self.apply_skin(n))
            a.setCheckable(True)
            a.setChecked(name == skinmod.resolve(self.cfg["theme"]))
            g.addAction(a)
            self.theme_actions[name] = a
        tm.addSeparator()
        self.a_follow_dark = tm.addAction("Windows 어두운 모드 따라가기")
        self.a_follow_dark.setCheckable(True)
        self.a_follow_dark.setChecked(bool(self.cfg["follow_system_dark"]))
        self.a_follow_dark.setToolTip("켜면 Windows 가 어두운 모드일 때 써니 → 나이트 써니, 라이트 n단계 → 다크 n단계, 다른 밝은 테마 → 다크 블루")
        self.a_follow_dark.toggled.connect(self.set_follow_system_dark)
        tm.addSeparator()                                    # v025: 단계 테마 한 칸씩 (라이트 ↔ 다크 10단계)
        tm.addAction("한 단계 밝게", QKeySequence("Ctrl+Shift+PgUp"), lambda: self.step_theme(-1))
        tm.addAction("한 단계 어둡게", QKeySequence("Ctrl+Shift+PgDown"), lambda: self.step_theme(1))
        self.a_top = m.addAction("항상 위", self.toggle_on_top)
        self.a_top.setCheckable(True)
        self.a_top.setChecked(bool(self.cfg["always_on_top"]))
        self.a_spec = m.addAction("스펙트럼")
        self.a_spec.setCheckable(True)
        self.a_spec.setChecked(bool(self.cfg["spectrum"]))
        self.a_spec.toggled.connect(self._toggle_spec)
        self.a_wave = m.addAction("파형 시크바")
        self.a_wave.setCheckable(True)
        self.a_wave.setChecked(bool(self.cfg["waveform"]))
        self.a_wave.toggled.connect(self._toggle_wave)
        m.addSeparator()
        m.addAction("모든 블럭 펼치기", lambda: self.set_all_sections(True))
        m.addAction("모든 블럭 접기", lambda: self.set_all_sections(False))
        m.addAction("지금 재생 블럭 기본 크기 (모두 펼침)", lambda: self.reset_now_blocks())
        fsm = m.addMenu("글자 크기")                         # v016 (f29 G9): 바로 적용
        gf = QActionGroup(self)
        self.a_font_sizes = {}
        self.a_font_auto = fsm.addAction("자동 (화면 크기에 맞춤)", lambda: self.set_font_size(None))   # v023
        self.a_font_auto.setCheckable(True)
        self.a_font_auto.setChecked(bool(self.cfg["font_auto"]))
        gf.addAction(self.a_font_auto)
        fsm.addAction("크게", QKeySequence("Ctrl+="), lambda: self.step_font(1))          # v025: 한 단계씩
        fsm.addAction("작게", QKeySequence("Ctrl+-"), lambda: self.step_font(-1))
        self.a_font_auto.setShortcut(QKeySequence("Ctrl+0"))
        fsm.addSeparator()
        for pt, label in zip(skinmod.FONT_SIZES, ("작게", "보통", "조금 크게", "크게", "아주 크게", "가장 크게")):
            a = fsm.addAction(f"{label} ({pt}pt)", lambda p=pt: self.set_font_size(p))
            a.setCheckable(True)
            a.setData(pt)
            a.setChecked(not self.cfg["font_auto"] and int(self.cfg["font_size"]) == pt)
            gf.addAction(a)
            self.a_font_sizes[pt] = a
        m.addSeparator()
        # 화면 이동 (단순 배치: 왼쪽 레일과 같음 / 클래식: 탭)
        pages = [("지금 재생", "Ctrl+1", "now"), ("재생 목록", "Ctrl+2", self.listv), ("라이브러리", "Ctrl+3", self.libv),
                 ("폴더", "Ctrl+4", self.folderv), ("추천", "Ctrl+5", self.home), ("사운드", "Ctrl+6", self.soundv)]
        for label, key, target in pages:
            if target == "now":
                if self.is_simple():
                    m.addAction(label, QKeySequence(key), lambda: self.go_page(self.page_now))
                continue
            m.addAction(label, QKeySequence(key), lambda t=target: self.go_page(t))
        m.addSeparator()
        m.addAction("가사 패널", QKeySequence("Ctrl+Shift+L"), lambda: self.toggle_panel("lyrics"))
        bm = m.addMenu("상단 바 (시세 · 시각)")             # vr0.1.0.012 (f23)
        self.topbar_actions = {}
        for key, label in (("topbar_ticker", "업비트 시세 표시"), ("topbar_clock", "KST 시계"),
                           ("topbar_clock_seconds", "초까지 표시")):
            a = bm.addAction(label)
            a.setCheckable(True)
            a.setChecked(bool(self.cfg[key]))
            a.toggled.connect(lambda v, k=key: self.set_topbar_option(k, v))
            self.topbar_actions[key] = a
        bm.addAction("마켓 바꾸기… (예: KRW-XRP,KRW-BTC)", self.ask_ticker_market)
        bm.addAction("시세 지금 새로 고침", lambda: self.topbar.svc.refresh())
        bm.addAction("시세 상세 보기…", self.show_ticker_detail)
        self.a_menubar = m.addAction("메뉴 막대 접기 (Alt = 잠깐 보기)", QKeySequence("Ctrl+Shift+M"))
        self.a_menubar.setCheckable(True)
        self.a_menubar.setChecked(not bool(self.cfg["menu_bar"]))
        self.a_menubar.toggled.connect(lambda v: self.set_menu_bar(not v))
        m.addAction("대기열 패널", QKeySequence("Ctrl+J"), lambda: self.toggle_panel("queue"))
        m.addAction("미니 플레이어", QKeySequence("Ctrl+M"), self.toggle_mini_player)
        m.addAction("빠른 찾기", QKeySequence("Ctrl+K"), self.show_quick_find)
        m.addSeparator()
        lm = m.addMenu("화면 배치 (다시 시작하면 적용)")
        from PyQt6.QtGui import QActionGroup as _AG
        g = _AG(self)
        for k, label in (("simple", "단순 (아이콘 레일 · 아래 재생 막대)"), ("classic", "클래식 (Winamp 모양)")):
            a = lm.addAction(label, lambda k=k: self._set_layout(k))
            a.setCheckable(True)
            a.setChecked(self.layout_name == k)
            g.addAction(a)

        m = mb.addMenu("도구(&T)")
        m.addAction("곡 정보(태그) 편집…", self.edit_current_tags)
        m.addAction("라이브러리 폴더 추가…", self.add_library_folder)
        m.addAction("라이브러리 다시 스캔", c.scan_library)
        m.addAction("추천 새로고침", self.home.refresh)
        m.addSeparator()
        self.a_hist = m.addAction("재생 기록 사용 (추천)")
        self.a_hist.setCheckable(True)
        self.a_hist.setChecked(bool(self.cfg["history_enabled"]))
        self.a_hist.toggled.connect(lambda v: self.cfg.__setitem__("history_enabled", v))
        m.addAction("재생 기록 지우기…", self.clear_history)
        self.a_tray = m.addAction("닫기(X) = 트레이로")
        self.a_tray.setCheckable(True)
        self.a_tray.setChecked(bool(self.cfg["close_to_tray"]))
        self.a_tray.toggled.connect(lambda v: self.cfg.__setitem__("close_to_tray", v))

        m = mb.addMenu("도움말(&H)")
        m.addAction("버튼 이름 보기", QKeySequence("F1"), self.show_help_overlay)
        m.addAction("단축키", self.show_keys)
        m.addAction("화면 정보 (배율 · 글꼴)…", self.show_screen_info)      # v016 (f29 G10)
        m.addAction("정보", self.show_about)

        # 규칙 9 '버전__빌드시각' — vr0.1.0.014 (f26): 제목 줄 한 곳에 [곡 - 앱 버전 │ XRP │ KST] (메뉴바 모서리 칸 삭제)
        from .topbar import TopBar
        self.topbar = TopBar(self.cfg, self)
        self.topbar.hide()                                  # 시세 · 시각 계산만 (화면에는 제목 줄 글자로)
        self.ver_label = self.topbar.ver
        self.topbar.changed.connect(self.update_title)

    # ---- 제목 줄 · 메뉴 막대 (vr0.1.0.014, f26)
    def update_title(self):
        t = self.ctrl.current_track() if hasattr(self, "ctrl") else None
        base = f"{t.display} - {title_label()}" if t else title_label()
        suf = self.topbar.title_suffix() if getattr(self, "topbar", None) is not None else ""
        self.setWindowTitle(base + (f"  │  {suf}" if suf else ""))

    def show_ticker_detail(self):
        q = self.topbar.current_quote()
        txt = self.topbar.price.toolTip() if q else "아직 시세를 가져오지 못했습니다 (인터넷 확인)"
        QMessageBox.information(self, "업비트 시세", txt)

    def set_menu_bar(self, on: bool):
        """메뉴 막대 펼침/접힘 (접히면 Alt 로 잠깐 보기)"""
        self.cfg["menu_bar"] = bool(on)
        self._menu_peek = False
        self.menuBar().setVisible(bool(on))
        if getattr(self, "a_menubar", None) is not None and self.a_menubar.isChecked() == bool(on):
            self.a_menubar.blockSignals(True)
            self.a_menubar.setChecked(not on)
            self.a_menubar.blockSignals(False)
        if getattr(self, "b_menu", None) is not None:
            self.b_menu.setChecked(bool(on))

    def peek_menu_bar(self):
        """접힌 상태에서 Alt: 잠깐 펼치고 첫 메뉴에 초점 → 메뉴를 닫거나 다른 곳을 누르면 다시 접힘"""
        if self.cfg["menu_bar"]:
            return
        mb = self.menuBar()
        self._menu_peek = True
        mb.setVisible(True)
        mb.setFocus(Qt.FocusReason.ShortcutFocusReason)
        acts = [a for a in mb.actions() if a.menu() is not None]
        if acts:
            mb.setActiveAction(acts[0])
        if getattr(self, "_peek_timer", None) is None:
            self._peek_timer = QTimer(self, interval=300, timeout=self._hide_peek)
        self._peek_timer.start()

    def _menu_closed(self):
        if getattr(self, "_menu_peek", False) and not self.cfg["menu_bar"]:
            QTimer.singleShot(150, self._hide_peek)

    def _hide_peek(self, force=False):
        """메뉴가 열려 있지 않고 메뉴 막대에 초점이 없으면 다시 접음"""
        from PyQt6.QtWidgets import QApplication
        mb = self.menuBar()
        busy = QApplication.activePopupWidget() is not None or mb.hasFocus()
        if self.cfg["menu_bar"] or force or not busy:
            if not self.cfg["menu_bar"]:
                mb.setVisible(False)
            self._menu_peek = False
            if getattr(self, "_peek_timer", None) is not None:
                self._peek_timer.stop()

    # ---- 상단 바 (vr0.1.0.012)
    def set_topbar_option(self, key, on):
        self.cfg[key] = bool(on)
        self.topbar.apply_settings()

    def ask_ticker_market(self):
        cur = str(self.cfg["ticker_market"] or "KRW-XRP")
        txt, ok = QInputDialog.getText(self, "업비트 마켓", "마켓 코드 (쉼표로 여러 개, 예: KRW-XRP,KRW-BTC)", text=cur)
        if ok:
            from ..domain.ticker import parse_markets
            self.cfg["ticker_market"] = ",".join(parse_markets(txt))
            self.topbar.svc.quotes.clear()
            self.topbar.apply_settings()
            self.topbar.svc.refresh()

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

    def _fill_sleep_menu(self, m):
        for mins in (15, 30, 45, 60, 90):
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

    # ---- Alt 만 눌렀다 떼면 숨긴 메뉴 막대를 잠깐 보임 (v014)
    def keyPressEvent(self, e):
        self._alt_alone = e.key() == Qt.Key.Key_Alt and e.modifiers() == Qt.KeyboardModifier.AltModifier
        super().keyPressEvent(e)

    def keyReleaseEvent(self, e):
        if e.key() == Qt.Key.Key_Alt and getattr(self, "_alt_alone", False) and not self.cfg["menu_bar"]:
            self._alt_alone = False
            self.peek_menu_bar()
            return
        self._alt_alone = False
        super().keyReleaseEvent(e)
