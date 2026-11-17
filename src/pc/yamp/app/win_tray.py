"""MainWindow 기능 묶음 — 시스템 트레이 · 종료

MainWindow(QMainWindow) 가 이 믹스인을 상속 (vr0.1.0.007 모듈화)."""

from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from ..core.version import title_label


class TrayMixin:
    # ================================================= v004 기능
    def quit_app(self):
        self._quitting = True
        self.close()

    def _build_tray(self):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self.tray = QSystemTrayIcon(self.windowIcon() if not self.windowIcon().isNull()
                                    else QApplication.style().standardIcon(QApplication.style().StandardPixmap.SP_MediaPlay), self)
        c = self.ctrl
        m = QMenu(self)
        m.addAction("보이기", self._show_from_tray)
        m.addSeparator()
        m.addAction("재생 / 일시정지", c.toggle)
        m.addAction("다음 곡", c.next)
        m.addAction("이전 곡", c.prev)
        m.addAction("좋아요 ♥", lambda: c.toggle_like())
        m.addSeparator()
        m.addAction("미니 가사창", self.toggle_mini)
        m.addAction("미니 가사 잠금 해제", lambda: self.mini and self.mini.set_click_through(False))
        m.addSeparator()
        m.addAction("종료", self.quit_app)
        self.tray.setContextMenu(m)
        self.tray.activated.connect(lambda r: self._show_from_tray() if r == QSystemTrayIcon.ActivationReason.DoubleClick else None)
        self.tray.setToolTip(title_label())
        self.tray.show()
        c.trackChanged.connect(lambda t, i: self.tray.setToolTip(f"{t.display}\n{title_label()}"))

    def _show_from_tray(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()
