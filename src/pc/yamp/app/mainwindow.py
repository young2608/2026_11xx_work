"""메인 창 — vr0.1.0.009 단순 배치 (아이콘 버튼 + 마우스를 올리면 설명 팝업)

모듈: mainwindow = 시그널 연결 · 이벤트 · 창 상태 / win_layout = 화면 구성(단순) · win_classic = 클래식 배치
      win_menus = 메뉴 · 단축키 / win_actions = 사용자 동작 / win_tray = 트레이 · 종료
      win_native = Windows 연동 (작업 표시줄 · 전역 단축키 · 미디어 제어 · 강조색)

┌ 메뉴바 ─────────────────────────────────────── vr0.1.0.009__빌드시각 ┐
│레일│ 화면 (지금 재생 · 목록 · 라이브러리 · 폴더 · 추천 · 사운드)  │ 가사/대기열 │
├────┴─────────────────────────────────────────────────┴───────────┤
│ 표지 제목 ♡ │ ⤨ ⏮ (▶) ⏭ ⟳  ─ 파형 ─ │ 가사 대기열 AB 속도 슬립 🔊━ 미니 ⋯ │
└──────────────────────────────────────────────────────────────────┘
"""
import sys

from PyQt6.QtCore import QByteArray, QEvent, Qt, QTimer
from PyQt6.QtGui import QAction, QColor
from PyQt6.QtWidgets import QApplication, QMainWindow, QSystemTrayIcon, QWidget

from ..core.version import title_label
from ..data.playlist import fmt_time
from ..ui import icons, metrics, skin as skinmod, tips
from ..ui.iconbutton import IconButton, install_tip_style
from ..ui.mini_lyrics import MiniLyrics
from ..audio.waveform import WaveformLoader
from .controller import Controller
from .mediakeys import WinMediaKeys
from .win_menus import MenuMixin
from .win_actions import ActionsMixin
from .win_tray import TrayMixin
from .win_layout import LayoutMixin
from .win_now import NowMixin
from .win_native import NativeMixin

ALARM_CHECK_MS = 30_000


class MainWindow(MenuMixin, ActionsMixin, TrayMixin, NowMixin, LayoutMixin, NativeMixin, QMainWindow):
    def __init__(self, cfg, ctrl: Controller | None = None):
        super().__init__()
        self.cfg = cfg
        self.ctrl = ctrl or Controller(cfg, self)
        self._theme_notice = self._migrate_theme()
        self._sys_light = None
        if cfg["follow_system_dark"]:                 # 첫 화면부터 맞는 테마로 (감시는 native_start 에서)
            from ..winplat.win_theme import system_theme
            self._sys_light = system_theme().get("light")
        self.skin = skinmod.get(self.effective_theme())
        skinmod.set_current(self.skin)
        self.mini: MiniLyrics | None = None
        self.mediakeys = None
        self.tray = None
        self._quitting = False
        self.mini_player = None
        install_tip_style(QApplication.instance(), int(cfg["tooltip_delay_ms"]))
        self.setWindowTitle(title_label())
        skinmod.apply_app_font(QApplication.instance(), self.effective_font_pt(), str(self.cfg["font_hinting"]))   # v016 G2 · G9
        self._first_size()
        self.setAcceptDrops(True)
        self._build_ui()
        self._build_menu()
        self._wire_menu()
        self._build_shortcuts()
        self._page_shortcuts()
        self._wire()
        self.apply_skin()
        self._restore_geometry()
        self._update_modes()
        self._toggle_spec(bool(self.cfg["spectrum"]))
        m = self.menuBar().actions()[0].menu()
        m.insertAction(m.actions()[-2], QAction("config.txt 열기", self, triggered=self.open_config))
        m.insertAction(m.actions()[-2], QAction("로그 폴더 열기", self, triggered=self.open_log_dir))
        self.lyv.set_three_line(bool(cfg["lyric_show_pron"]), bool(cfg["lyric_show_trans"]))
        self._build_tray()
        if self.ctrl.backend_message:
            QTimer.singleShot(500, lambda: self._on_message(self.ctrl.backend_message))
        QTimer.singleShot(300, self.ctrl.scan_library)
        QTimer.singleShot(8000, self.ctrl.maintenance)   # 오래된 재생 기록·파형 캐시 정리 (장시간 운용)
        QTimer.singleShot(800, self.home.refresh)
        self._alarm_t = QTimer(self, interval=ALARM_CHECK_MS, timeout=self.ctrl.check_alarm)   # 알람 (W8)
        self._alarm_t.start()
        if not self.cfg["help_overlay_shown"] and self.is_simple():
            QTimer.singleShot(1200, self._first_help)
        if self._theme_notice:
            QTimer.singleShot(1500, lambda: self._on_message(self._theme_notice))
    def _wire(self):
        c = self.ctrl
        c.trackChanged.connect(self._on_track)
        c.positionChanged.connect(self._on_pos)
        c.lyricPosition.connect(self.lyv.set_position)
        c.lyricPosition.connect(lambda ms: self.mini and self.mini.set_position(ms))
        c.lyricsChanged.connect(self._on_lyrics)
        c.lyricsStatus.connect(self._on_lyrics_status)
        c.stateChanged.connect(self._on_state)
        c.playlistChanged.connect(self._on_playlist)
        c.currentChanged.connect(self.model.refresh_rows)
        c.tagsUpdated.connect(self.model.refresh_rows)
        c.modesChanged.connect(self._update_modes)
        c.levels.connect(self.spec.set_levels)
        self._wire_now()                                     # v014 소리 시각화 · 다음 곡 (win_now)
        c.message.connect(self._on_message)
        self.seek.seekRequested.connect(c.seek)
        self.lcd.toggled.connect(lambda v: self.cfg.__setitem__("time_remaining", v))
        self.lyv.seekRequested.connect(c.seek)
        lv = self.listv
        lv.playRequested.connect(c.play_index)
        lv.filesDropped.connect(lambda p: c.add_paths(p))
        lv.removeRequested.connect(c.remove)
        lv.moveRequested.connect(self._move)
        lv.researchLyrics.connect(c.research_lyrics)
        lv.openFolder.connect(self._open_folder_of)
        self.search.textChanged.connect(self.model.request_filter)   # v022 (N4): 큰 목록은 입력이 멈춘 뒤
        c.likedChanged.connect(self._on_liked)
        c.abChanged.connect(self._on_ab)
        c.sleepChanged.connect(self._on_sleep)
        self.lyv.repeatRequested.connect(self._repeat_line)
        self.lyv.editRequested.connect(self.show_lyrics_editor)
        self.lyv.pickRequested.connect(self.show_lyrics_pick)
        self.libv.addFolderRequested.connect(self.add_library_folder)
        self.folderv.addFolderRequested.connect(self.add_library_folder)
        self.wave = WaveformLoader(self.cfg.data_dir / "waveform", self)
        self.wave.ready.connect(self._on_wave)
        c.queueChanged.connect(self._on_queue)
        c.modesChanged.connect(self._refresh_now)
    # ================================================= 이벤트
    def _on_track(self, t, info):
        fl = getattr(info, "format_label", "")
        parts = [fl or (f"{info.bitrate} kbps" if info.bitrate else ""),
                 "" if fl else (f"{info.samplerate // 1000} kHz" if info.samplerate else ""),
                 {1: "mono", 2: "stereo"}.get(info.channels, f"{info.channels}ch" if info.channels else ""),
                 "Hi-Res" if getattr(info, "hires", False) else "",
                 f"CUE {t.cue_no:02d}" if t.cue_no else ""]
        alb = f"   {info.album}" if info.album and getattr(self, "now_title", None) is None else ""   # 단순 배치는 now_sub 에
        self.info.setText("  ".join(p for p in parts if p) + alb)
        idx = self.ctrl.pl.current + 1
        self.title.set_text(f"{idx}. {t.display} ({fmt_time(info.duration)})")
        if getattr(self, "now_title", None) is not None:      # v014 지금 재생 카드: 큰 제목 + 아티스트 · 앨범
            self.now_title.setText(t.title or t.display)
            sub = " · ".join(x for x in (getattr(t, "artist", "") or getattr(info, "artist", ""),
                                         getattr(info, "album", "")) if x)
            self.now_sub.setText(f"{idx} / {len(self.ctrl.pl)}" + (f"   {sub}" if sub else ""))
            self._info_head()
        self._refresh_now()
        self.load_cover(t, info)                  # v022 (N1): 표지 디코드는 백그라운드 (win_now)
        if self.is_simple():
            self.bar_title.setText(t.display)
            self.bar_sub.setText(" · ".join(x for x in (info.artist or t.artist, fl) if x))
        self.native_track(t, info)
        self.update_title()
        self._wave_uid = t.uid
        self.seek.set_peaks([])
        self.seek.set_ab(None)
        if self.cfg["waveform"]:
            self.wave.request(t.uid, t.path, t.start_ms, t.end_ms)
        r = self.model.row_of(self.ctrl.pl.current)
        if r >= 0:
            self.listv.scrollTo(self.model.index(r))
    def _on_pos(self, pos, dur):
        self.lcd.set_time(pos, dur)
        if self.bar_pos is not None:
            ps, ds = fmt_time(pos / 1000), fmt_time(dur / 1000)
            if ps != self.bar_pos.text():
                self.bar_pos.setText(ps)
            if ds != self.bar_dur.text():
                self.bar_dur.setText(ds)
        self.native_pos(pos, dur)
        if self.seek.maximum() != dur:
            self.seek.setRange(0, max(0, dur))
        self.seek.set_pos(pos)
    def _on_lyrics(self, ly):
        self.lyv.set_lyrics(ly, "가사 찾는 중…" if ly is None else "")
        if self.mini:
            self.mini.set_lyrics(ly)
    def _on_lyrics_status(self, s):
        self.st_lyrics.setText(s)
        if self.ctrl.cur_lyrics is None:
            hint = "F5 다시 찾기 · Ctrl+Shift+F 다른 가사 찾기 · Ctrl+Shift+K 가사 편집기(붙여넣기) · 같은 폴더에 .lrc"
            self.lyv.set_message(s if s.endswith("…") else f"{s}\n\n{hint}")      # vr0.1.0.011 못 찾은 이유 + 방법
    def _on_state(self, st):
        self.lcd.set_paused(st == "paused")
        if self.is_simple():
            self.b_play.set_icon_name("pause" if st == "playing" else "play")
            self.b_play.set_state("재생 중" if st == "playing" else ("일시정지" if st == "paused" else "정지"))
        self.native_state(st)
        if st == "stopped":
            self.spec.set_levels([0.0] * self.spec.n)
            if getattr(self, "vis", None) is not None:
                self.vis.view.clear()
        self._sync_vis()
    def _on_playlist(self):
        self.model.refresh()
        n = len(self.ctrl.pl)
        total = sum(t.duration for t in self.ctrl.pl.items)
        self.st_count.setText(f"{n}곡  {fmt_time(total)}" if n else "파일을 끌어다 놓으세요")
        self._refresh_now()
    def _update_modes(self):
        sh = bool(self.cfg["shuffle"])
        self.b_shuf.setChecked(sh)
        self.b_shuf.set_state("켜짐" if sh else "꺼짐")
        self.a_shuf.setChecked(sh)
        rep = self.cfg["repeat"]
        rep_name = dict(off="끔", all="전체", one="1곡").get(rep, "전체")
        self.b_rep.setText({"off": "➡", "all": "🔁", "one": "🔂"}.get(rep, "🔁"))
        self.b_rep.set_icon_name({"off": "repeatOff", "all": "repeat", "one": "repeat1"}.get(rep, "repeat"))
        self.b_rep.set_active(rep != "off")
        self.b_rep.set_state(f"지금: {rep_name}")
        self.a_rep.setText(f"반복: {rep_name}")
        muted = bool(self.cfg["muted"])
        self.b_mute.setText("🔇" if muted else "🔊")
        self.b_mute.set_icon_name("mute" if muted else "volume")
        self.b_mute.set_state("음소거 중" if muted else None)
        sp = float(self.cfg["speed"] or 1.0)
        st = int(self.cfg["pitch_st"] or 0)
        sp_txt = f"{sp:.2f}".rstrip("0")
        sp_txt = (sp_txt + "0" if sp_txt.endswith(".") else sp_txt) + "x"
        self.b_speed.setText(sp_txt + (f" {st:+d}" if st else ""))
        self.b_speed.set_active(abs(sp - 1.0) > 1e-6 or st != 0)
        self.b_speed.set_state(f"속도 {sp_txt}" + (f" · 음정 {st:+d}" if st else ""))

    def _move(self, i, j):
        self.ctrl.move(i, j)
        r = self.model.row_of(j)
        if r >= 0:
            self.listv.setCurrentIndex(self.model.index(r))
    # ================================================= 테마 (vr0.1.0.011)
    def _migrate_theme(self):
        """D2: 이 버전 첫 실행에 한 번 — 이전 기본 neon → sunny (+알림) / light → clean_blue"""
        new, notice = skinmod.migrate_theme(self.cfg["theme"], bool(self.cfg["theme_migrated"]))
        if new != self.cfg["theme"]:
            self.cfg["theme"] = new
        self.cfg["theme_migrated"] = True
        return notice

    def effective_theme(self) -> str:
        """설정 테마 + 어두운 모드 따라가기 → 실제로 그릴 테마 키"""
        return skinmod.follow_dark(self.cfg["theme"], bool(self.cfg["follow_system_dark"]), self._sys_light)

    def set_follow_system_dark(self, on: bool):
        """보기 → 테마 → Windows 어두운 모드 따라가기"""
        self.cfg["follow_system_dark"] = bool(on)
        if on:
            self.ensure_theme_watcher()
        elif self._theme_watcher is not None and not self.cfg["follow_system_accent"]:
            self._theme_watcher.stop()                # 감시 필요 없음 → 폴링 0
            self._theme_watcher = None
        self.apply_skin()

    def apply_skin(self, name=None):
        """name 을 주면 설정 테마로 저장. 모든 위젯 바로 다시 칠함 (다시 시작 없음)"""
        if name is not None:
            self.cfg["theme"] = name
        self.skin = skinmod.get(self.effective_theme())
        skinmod.set_current(self.skin)
        app = QApplication.instance()
        app.setPalette(skinmod.palette(self.skin))
        app.setStyleSheet(skinmod.stylesheet(self.skin))
        icons.refresh_bound()
        acc = self.native_accent()
        self.seek.accent_override = QColor(acc) if acc else None
        roots = [self] + [w for w in (self.mini, self.mini_player) if w is not None]
        for r in roots:
            for w in [r] + r.findChildren(QWidget):
                fn = getattr(w, "set_skin", None)
                if callable(fn) and w is not self:
                    fn(self.skin)
            tips.refresh_all(r)
            r.update()
        if hasattr(self, "a_shuf"):
            self._update_modes()
        self.model.cur_color = QColor(self.skin.accent_text)
        self.model.refresh_rows()
        self.render_covers()                          # v024: 표지 없는 칸(♪ · 첫 글자)도 새 테마 색으로 (시작 때 ♪ 도 여기서)
        for key, a in getattr(self, "theme_actions", {}).items():
            a.setChecked(key == skinmod.resolve(self.cfg["theme"]))
            t = skinmod.SKINS[key]
            a.setIcon(icons.swatch((t.bg, t.fill1, t.fill2)))      # 테두리·체크 색 = 지금 테마
        if getattr(self, "a_follow_dark", None) is not None:
            self.a_follow_dark.setIcon(icons.toggle())

    # ================================================= 창 상태
    def _restore_geometry(self):
        g = self.cfg["geometry"]
        if g:
            self.restoreGeometry(QByteArray.fromBase64(g.encode()))
            metrics.keep_on_screen(self)                      # v023: 없는 모니터 위치 → 주 화면
        s = self.cfg["splitter"]
        if s and not self.is_simple():
            self.split.restoreState(QByteArray.fromBase64(s.encode()))
        elif self.cfg["splitter_simple"]:
            self.split.restoreState(QByteArray.fromBase64(str(self.cfg["splitter_simple"]).encode()))
        if self.cfg["always_on_top"]:
            self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
    # ---- v014: 처음 창 크기 · 메뉴 막대 접기 (Alt 로 잠깐)
    def _first_size(self):
        """v023: 10pt 기준 1280×800 × 글자 배율, 큰 화면은 화면의 60 % 까지 (화면 밖으로 넘지 않게)"""
        scr = QApplication.primaryScreen()
        av = scr.availableGeometry() if scr is not None else None
        kk = metrics.k()
        w, h = int(1280 * kk), int(800 * kk)
        if av is not None:
            w, h = max(w, int(av.width() * 0.6)), max(h, int(av.height() * 0.6))
            w, h = min(w, int(av.width() * 0.92)), min(h, int(av.height() * 0.9))
        self.resize(max(900, w), max(600, h))

    def _wire_menu(self):
        """메뉴 막대가 접혀도 단축키가 되도록 모든 메뉴 동작을 창에도 붙임 + 메뉴가 닫히면 다시 접기"""
        def walk(menu):
            for a in menu.actions():
                if a.menu() is not None:
                    a.menu().aboutToHide.connect(self._menu_closed)
                    walk(a.menu())
                elif not a.isSeparator() and not a.shortcut().isEmpty():
                    self.addAction(a)
        walk(self.menuBar())
        self._alt_alone = False
        self.set_menu_bar(bool(self.cfg["menu_bar"]))
        self.update_title()

    def changeEvent(self, e):
        super().changeEvent(e)
        if e.type() == QEvent.Type.WindowStateChange:
            QTimer.singleShot(0, self._sync_active)
        elif e.type() == getattr(QEvent.Type, "DevicePixelRatioChange", None):      # v016 G5 (Qt 6.6+)
            QTimer.singleShot(0, self.on_dpr_changed)

    def hideEvent(self, e):
        super().hideEvent(e)
        self._sync_active()

    def showEvent(self, e):
        super().showEvent(e)
        self._sync_active()
        wh = self.windowHandle()
        if wh is not None and not getattr(self, "_scr_hooked", False):            # v016 G5: 다른 모니터로
            self._scr_hooked = True
            wh.screenChanged.connect(lambda _s: QTimer.singleShot(0, self.on_dpr_changed))
        if self.mediakeys is None and sys.platform == "win32":
            self.mediakeys = WinMediaKeys(int(self.winId()), self._on_mediakey)
            QApplication.instance().installNativeEventFilter(self.mediakeys)
        if self.cfg["mini_lyrics"] and not self.mini:
            QTimer.singleShot(0, self.toggle_mini)
        QTimer.singleShot(0, self.native_start)        # 작업 표시줄 · 전역 단축키 · 미디어 제어 (Windows)
    def _on_mediakey(self, name):
        getattr(self.ctrl, name)()
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
    def dropEvent(self, e):
        paths = [u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()]
        if paths:
            self.ctrl.add_paths(paths)
    def closeEvent(self, e):
        if self.cfg["close_to_tray"] and self.tray is not None and not self._quitting:
            e.ignore()
            self.hide()
            self.tray.showMessage("yMp3Player", "트레이에서 계속 재생합니다", QSystemTrayIcon.MessageIcon.Information, 2000)
            return
        if self.tray is not None:
            self.tray.hide()
        self.cfg["geometry"] = bytes(self.saveGeometry().toBase64()).decode()
        key = "splitter_simple" if self.is_simple() else "splitter"
        self.cfg[key] = bytes(self.split.saveState().toBase64()).decode()
        if self.mini_player is not None:
            self.mini_player.close()
        self.libv.grid.shutdown()
        self.native_stop()
        if self.mini:
            self.mini.close()
        self.wave.cancel()
        if self.mediakeys:
            self.mediakeys.unregister()
        self.topbar.shutdown()
        self.ctrl.save_session()
        self.ctrl.shutdown()
        try:
            self.cfg.save()
        except OSError:
            pass
        super().closeEvent(e)
    def _on_sleep(self, txt):
        self.b_sleep.setChecked(bool(txt))
        self.b_sleep.set_state(f"남은 시간: {txt}" if txt else None)
        if txt:
            self._on_message(f"슬립 타이머: {txt}")

    def _on_ab(self, ab):
        self.seek.set_ab(ab)
        self.b_ab.setChecked(ab is not None)
        if ab is None:
            self.b_ab.setText("A-B")
            self.b_ab.set_state(None)
        elif ab[0] == "A":
            self.b_ab.setText("A-…")
            self.b_ab.set_state(f"A = {ab[1] / 1000:.1f}초 — B 를 기다리는 중")
        else:
            self.b_ab.setText("A-B ●")
            self.b_ab.set_state(f"{ab[0] / 1000:.1f}초 ~ {ab[1] / 1000:.1f}초 반복 중")

    def _repeat_line(self, t0, t1):
        off = self.ctrl.lyrics_offset()
        self.ctrl.repeat_range(t0 - off, t1 - off)
    # ================================================= v006: 아이콘 · 접기/펼치기 · 폴더 · 사운드 · 파형
    def _set_icon(self, b, name, color=None):
        if isinstance(b, IconButton):
            b.set_icon_name(name)

    def _on_liked(self, v):
        self.b_like.setText("♥" if v else "♡")
        self.b_like.set_icon_name("heart" if v else "heartOutline")
        self.b_like.set_active(bool(v))
        self.b_like.set_state("좋아요 한 곡" if v else None)

    # ================================================= v009: 알림 · 대기열 표시 · 창 크기 · 도움말
    def _on_message(self, s):
        if self.is_simple():
            self.toast.show_msg(s)
        else:
            self.statusBar().showMessage(s, 4000)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if hasattr(self, "split"):
            self._auto_panel()

    def _first_help(self):
        self.cfg["help_overlay_shown"] = True
        if self.isVisible():
            self.show_help_overlay()

    def _on_wave(self, uid, bars):
        if uid == getattr(self, "_wave_uid", None):
            self.seek.set_peaks(bars)
