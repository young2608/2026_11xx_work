"""MainWindow 기능 묶음 — 제목 줄 · 메뉴 막대 접기/잠깐 보기(Alt) · 상단 바(시세 · 시각) 설정

vr0.1.0.030 (f58): win_menus.py 에서 나눔 (메뉴 '만들기' 와 메뉴 막대 '동작' 을 분리)."""

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QInputDialog, QMessageBox

from ..core.version import title_label


class MenuBarMixin:
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
