"""MainWindow 기능 묶음 — 사용자 동작: 파일/폴더/플레이리스트 열기 · 미니 가사 · 대화상자 · 라이브러리 · 폴더 재생 · 사운드 탭 · 파형 · 블럭 접기

MainWindow(QMainWindow) 가 이 믹스인을 상속 (vr0.1.0.007 모듈화)."""
import os
import subprocess
import sys

from PyQt6.QtCore import QByteArray, Qt, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import QFileDialog, QInputDialog, QMenu, QMessageBox

from ..core.version import APP_NAME
from ..data.formats import dialog_filter
from ..ui.mini_lyrics import MiniLyrics
from ..ui.section import Section
from ..ui import dialogs as dlg
from ..ui.qtutil import exec_dialog, exec_menu

AUDIO_FILTER = dialog_filter()      # 분류별 묶음 (vr0.1.0.010)
PLAYLIST_FILTER = "재생목록 (*.m3u *.m3u8 *.pls *.xspf *.wpl);;모든 파일 (*)"


class ActionsMixin:
    # ================================================= 동작
    def open_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "파일 열기", "", AUDIO_FILTER)
        if files:
            self.ctrl.add_paths(files, play_first=not self.ctrl.engine.is_playing())

    def open_folder(self):
        d = QFileDialog.getExistingDirectory(self, "폴더 열기")
        if d:
            self.ctrl.add_paths([d], play_first=not self.ctrl.engine.is_playing())

    def open_playlist(self):
        f, _ = QFileDialog.getOpenFileName(self, "플레이리스트 열기", "", PLAYLIST_FILTER)
        if f:
            self.ctrl.load_playlist(f)

    def save_playlist(self):
        f, _ = QFileDialog.getSaveFileName(self, "플레이리스트 저장", "playlist.m3u8", "M3U8 (*.m3u8)")
        if f:
            self.ctrl.save_playlist(f)
            self._on_message(f"저장: {f}")

    def save_lrc(self):
        try:
            p = self.ctrl.save_lyrics_lrc()
        except OSError as e:
            QMessageBox.warning(self, APP_NAME, f"저장 실패: {e}")
            return
        self._on_message(f"저장: {p}" if p else "저장할 가사 없음")

    def open_config(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.cfg.path)))
        self._on_message("config.txt 를 고친 뒤 프로그램을 다시 시작하면 적용됩니다")

    def open_log_dir(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.cfg.path_of("log_dir"))))

    def open_cache(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.ctrl.lyrics.cache.root)))

    def _open_folder_of(self, i):
        t = self.ctrl.pl.items[i]
        if sys.platform == "win32":
            subprocess.Popen(["explorer", "/select,", os.path.normpath(t.path)])
        else:
            QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(t.path)))

    def toggle_mini(self):
        if self.mini and self.mini.isVisible():
            self.mini.close()
            return
        self.mini = MiniLyrics(float(self.cfg["mini_opacity"]), font_pt=int(self.cfg["mini_font_pt"]),
                               click_through=bool(self.cfg["mini_click_through"]),
                               show_pron=bool(self.cfg["lyric_show_pron"]), show_trans=bool(self.cfg["lyric_show_trans"]))
        self.mini.lockChanged.connect(self._on_mini_lock)
        self.mini.closed.connect(self._mini_closed)
        g = self.cfg["mini_geometry"]
        if g:
            self.mini.restoreGeometry(QByteArray.fromBase64(g.encode()))
        self.mini.set_lyrics(self.ctrl.cur_lyrics)
        self.mini.show()
        self.cfg["mini_lyrics"] = True
        self.b_mini.setChecked(True)
        self.a_mini.setChecked(True)

    def _mini_closed(self):
        if self.mini:
            self.cfg["mini_geometry"] = bytes(self.mini.saveGeometry().toBase64()).decode()
            self.cfg["mini_opacity"] = self.mini.opacity
        self.cfg["mini_lyrics"] = False
        self.b_mini.setChecked(False)
        self.a_mini.setChecked(False)

    def toggle_on_top(self):
        on = self.a_top.isChecked()
        self.cfg["always_on_top"] = on
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, on)
        self.show()

    def _toggle_spec(self, on):
        self.cfg["spectrum"] = on
        self.spec.setVisible(on)
        self.ctrl.sync_spectrum()

    def _set_lyrics_font(self, pt):
        self.cfg["lyrics_font_pt"] = pt
        self.lyv.set_font_pt(pt)
        self.lyv.update()

    def show_speed(self):
        exec_dialog(dlg.SpeedDialog(self.ctrl, self))

    def show_sleep_menu(self):
        m = QMenu(self)
        rem = self.ctrl.sleep_remaining()
        if rem:
            a = m.addAction(f"현재: {rem}")
            a.setEnabled(False)
        self._fill_sleep_menu(m)
        exec_menu(m, self.b_sleep.mapToGlobal(self.b_sleep.rect().bottomLeft()))
        self.b_sleep.setChecked(bool(self.ctrl.sleep_remaining()))

    def _sleep_custom(self):
        v, ok = QInputDialog.getInt(self, "슬립 타이머", "몇 분 뒤에 멈출까요?", 20, 1, 600)
        if ok:
            self.ctrl.sleep_start(v)

    def _set_three(self, key, v):
        self.cfg[key] = v
        self.lyv.set_three_line(bool(self.cfg["lyric_show_pron"]), bool(self.cfg["lyric_show_trans"]))
        if self.mini:
            self.mini.show_pron, self.mini.show_trans = bool(self.cfg["lyric_show_pron"]), bool(self.cfg["lyric_show_trans"])
            self.mini.update()

    def _toggle_mini_lock(self):
        on = self.a_mini_lock.isChecked()
        self.cfg["mini_click_through"] = on
        if self.mini:
            self.mini.set_click_through(on)

    def _on_mini_lock(self, on):
        self.cfg["mini_click_through"] = on
        self.a_mini_lock.setChecked(on)
        if on:
            self._on_message("미니 가사창 잠금 — 해제: 가사 메뉴 / 트레이 메뉴")

    def show_lyrics_editor(self):
        if not self.ctrl.current_track():
            self._on_message("재생 중인 곡이 없습니다")
            return
        exec_dialog(dlg.LyricsEditorDialog(self.ctrl, self))

    def show_lyrics_pick(self):
        if not self.ctrl.lyrics.last_query:
            self._on_message("재생 중인 곡이 없습니다")
            return
        exec_dialog(dlg.LyricsPickDialog(self.ctrl, self))

    def show_lyrics_diag(self):
        """가사 진단 (vr0.1.0.011) — 못 찾는 이유를 단계별로"""
        if not self.ctrl.lyrics.last_query:
            self._on_message("재생 중인 곡이 없습니다")
            return
        from ..ui.lyrics_diag import LyricsDiagDialog
        exec_dialog(LyricsDiagDialog(self.ctrl, self))

    def edit_current_tags(self):
        sel = self.listv.selected_real()
        i = sel[0] if sel else self.ctrl.pl.current
        if not (0 <= i < len(self.ctrl.pl)):
            return
        from ..data.tags import read_tags
        t = self.ctrl.pl.items[i]
        d = dlg.TagEditDialog(t.path, read_tags(t.path), self)
        if exec_dialog(d):
            try:
                self.ctrl.edit_tags(i, d.values())
                self._on_message("태그 저장 완료")
            except Exception as e:  # noqa
                QMessageBox.warning(self, "태그 편집", f"저장 실패: {e}\n(재생 중인 파일은 잠겨 있을 수 있습니다)")

    def add_library_folder(self):
        d = QFileDialog.getExistingDirectory(self, "라이브러리 폴더 추가")
        if not d:
            return
        cur = [f for f in str(self.cfg["library_folders"] or "").split(";") if f.strip()]
        if d not in cur:
            cur.append(d)
        self.cfg["library_folders"] = ";".join(cur)
        self.ctrl.scan_library()
        self._on_message(f"라이브러리 폴더: {len(cur)}개 — 스캔 중…")

    def clear_history(self):
        if QMessageBox.question(self, "재생 기록 지우기",
                                "재생 기록(재생 횟수·건너뜀·최근 재생)을 모두 지울까요?\n좋아요·별점은 유지됩니다.") \
                == QMessageBox.StandardButton.Yes:
            self.ctrl.clear_history()
            self.home.refresh()

    def sections(self) -> list:
        return self.findChildren(Section)

    def set_all_sections(self, on: bool):
        for sec in self.sections():
            sec.set_open(on)

    def _on_lyrics_fold(self, on):
        sizes = self.split.sizes()
        if not on:
            self._lyr_sizes = sizes
            total = sum(sizes)
            self.split.setSizes([max(1, total - 110), 110])
        elif getattr(self, "_lyr_sizes", None):
            self.split.setSizes(self._lyr_sizes)

    def show_sound(self):
        self.go_page(self.soundv)

    # ================================================= v009: 미니 플레이어 · 빠른 찾기 · 도움말 · 배치 · 알람
    def toggle_mini_player(self):
        from ..ui.mini_player import MiniPlayer
        if self.mini_player is not None:
            self.mini_player.close()
            return
        mp = MiniPlayer(self.ctrl)
        mp.closed.connect(self._mini_player_closed)
        mp.restore.connect(self._mini_player_restore)   # v020 (f40 L5): 람다가 mp 를 붙잡아 닫아도 창이 안 지워지던 순환 참조 제거
        g = self.geometry()
        mp.move(g.right() - mp.width() - 20, g.bottom() - mp.height() - 40)
        mp.set_cover_image(getattr(self, "_cover_src", None))   # v022: 지금 표지 (메인 창이 디코드해 둔 그림)
        mp.show()
        self.mini_player = mp
        self.showMinimized()

    def _mini_player_restore(self):
        if self.mini_player is not None:
            self.mini_player.close()
        self._show_from_tray()

    def _mini_player_closed(self):
        """v020 (f40 L5): 닫힌 미니 플레이어를 지움 — 전에는 열고 닫을 때마다 창 1개(버튼 · 표지 포함)가 메모리에 남음.
        closeEvent 안에서 불리므로 바로 지우지 않고 C++ 쪽 소유로 넘긴 뒤 deleteLater (이벤트 처리 끝나고 삭제)"""
        mp, self.mini_player = self.mini_player, None
        if mp is not None:
            try:
                from PyQt6 import sip
                sip.transferto(mp, None)
                mp.deleteLater()
            except (RuntimeError, TypeError):
                pass
        if self.isMinimized():
            self.showNormal()

    def quick_commands(self) -> dict:
        """빠른 찾기(Ctrl+K)에서 실행할 수 있는 명령 — tips 키 → 함수"""
        c = self.ctrl
        cmd = {"play": c.toggle, "next": c.next, "prev": c.prev, "stop": c.stop, "shuffle": c.toggle_shuffle,
               "repeat": c.cycle_repeat, "like": lambda: c.toggle_like(), "ab": c.cycle_ab, "speed": self.show_speed,
               "sleep": self.show_sleep_menu, "mini_lyrics": self.toggle_mini, "mini_player": self.toggle_mini_player,
               "open": self.open_files, "undo": c.undo, "scan": c.scan_library, "add_folder": self.add_library_folder,
               "help": self.show_help_overlay, "nav_sound": self.show_sound,
               "nav_folder": lambda: self.go_page(self.folderv), "nav_lib": lambda: self.go_page(self.libv),
               "nav_list": lambda: self.go_page(self.listv), "nav_home": lambda: self.go_page(self.home),
               "panel_lyrics": lambda: self.toggle_panel("lyrics", force=True),
               "panel_queue": lambda: self.toggle_panel("queue", force=True),
               "skip_silence": lambda: self.a_silence.toggle(),
               "resume_long": lambda: self.a_resume_long.toggle(),
               "voice_preset": lambda: c.apply_preset("음성")}
        return cmd

    def show_quick_find(self):
        from ..ui.quick_find import QuickFind
        d = QuickFind(self, self.quick_commands())
        g = self.geometry()
        d.move(g.center().x() - 280, g.top() + 80)
        exec_dialog(d)

    def show_help_overlay(self):
        from ..ui.help_overlay import HelpOverlay
        ov = HelpOverlay(self)
        ov.show()
        ov.raise_()
        ov.setFocus()
        return ov

    def _set_layout(self, name):
        if name != self.cfg["layout"]:
            self.cfg["layout"] = name
            QMessageBox.information(self, "화면 배치", "다음에 프로그램을 시작하면 바뀐 배치로 열립니다.")

    def show_alarm_dialog(self):
        cur = str(self.cfg["alarm_time"] or "")
        txt, ok = QInputDialog.getText(self, "알람", "울릴 시각 HH:MM (비우면 끔)\n그 시각에 마지막 폴더를 볼륨을 서서히 올리며 재생",
                                       text=cur or "07:00")
        if not ok:
            return
        txt = txt.strip()
        import re
        if txt and not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", txt):
            QMessageBox.warning(self, "알람", "시각은 07:30 처럼 HH:MM 으로 입력하세요")
            return
        self.ctrl.set_alarm(txt)

    def play_folder_dialog(self):
        d = QFileDialog.getExistingDirectory(self, "폴더 재생", self.cfg["last_folder"] or "")
        if d:
            self.ctrl.play_folder(d, bool(self.cfg["folder_include_sub"]), bool(self.cfg["shuffle"]),
                                  str(self.cfg["folder_sort"]))
            self.folderv.reload()

    def play_last_folder(self):
        d = self.cfg["last_folder"]
        if d and os.path.isdir(d):
            self.ctrl.play_folder(d, bool(self.cfg["folder_include_sub"]), False, str(self.cfg["folder_sort"]))
        else:
            self._on_message("마지막 폴더가 없습니다")

    def _toggle_wave(self, on):
        self.cfg["waveform"] = on
        if not on:
            self.wave.cancel()
            self.seek.set_peaks([])
        else:
            t = self.ctrl.current_track()
            if t:
                self._wave_uid = t.uid
                self.wave.request(t.uid, t.path, t.start_ms, t.end_ms)
