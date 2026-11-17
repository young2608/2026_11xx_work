"""미니 가사창: 테두리 없음, 항상 위, 반투명. 현재 줄 + 다음 줄. 드래그로 이동, 우클릭 메뉴."""
from PyQt6.QtCore import QPoint, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter
from PyQt6.QtWidgets import QMenu, QWidget

from ..lyrics.lrc import Lyrics
from . import skin as skinmod
from .qtutil import exec_menu


class MiniLyrics(QWidget):
    closed = pyqtSignal()

    def __init__(self, opacity: float = 0.85, parent=None, font_pt: int = 18, click_through: bool = False,
                 show_pron: bool = True, show_trans: bool = True):
        super().__init__(parent, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
                         | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowTitle("yMp3Player 가사")
        self.resize(640, 96)
        self.ly: Lyrics | None = None
        self.cur = -1
        self.opacity = opacity
        self._drag: QPoint | None = None
        self.f1 = QFont()
        self.f1.setFamilies(["Malgun Gothic", "Segoe UI", "sans-serif"])
        self.f1.setPointSize(18)
        self.f1.setBold(True)
        self.f2 = QFont(self.f1)
        self.f2.setPointSize(12)
        self.f2.setBold(False)
        self.show_pron, self.show_trans = show_pron, show_trans
        self.click_through = False
        self.set_font_pt(font_pt)
        if click_through:
            self.set_click_through(True)

    lockChanged = pyqtSignal(bool)

    def set_font_pt(self, pt):
        self.f1.setPointSize(int(pt))
        self.f2.setPointSize(max(8, int(pt * 0.65)))
        self.resize(max(self.width(), int(pt * 34)), int(pt * 5.4))
        self.update()

    def set_click_through(self, on: bool):
        """잠금: 마우스가 창을 통과 (트레이·메인 메뉴의 '미니 가사 잠금' 으로 해제)"""
        self.click_through = bool(on)
        vis = self.isVisible()
        self.setWindowFlag(Qt.WindowType.WindowTransparentForInput, self.click_through)
        if vis:
            self.show()
        self.lockChanged.emit(self.click_through)
        self.update()

    def set_lyrics(self, ly):
        self.ly = ly
        self.cur = -1
        self.update()

    def set_position(self, ms):
        if self.ly and self.ly.synced:
            i = self.ly.index_at(ms)
            if i != self.cur:
                self.cur = i
                self.update()

    def _texts(self):
        if not self.ly or not self.ly.blocks:
            return "♪", ""
        if not self.ly.synced:
            return self.ly.blocks[0].lines[0] if self.ly.blocks[0].lines else "♪", "(싱크 없는 가사)"
        from .lyrics_view import visible_lines
        b = self.ly.blocks

        def txt(i):
            return " / ".join(visible_lines(b[i].lines, self.show_pron, self.show_trans))
        a = txt(self.cur) if 0 <= self.cur < len(b) else "♪"
        n = txt(self.cur + 1) if self.cur + 1 < len(b) else ""
        return a or "♪", n

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        s = skinmod.current()                        # 테마 색 (써니: 흰 바탕 + 진주황 현재 줄)
        bg = QColor(s.surface)
        bg.setAlphaF(self.opacity)
        p.setBrush(bg)
        p.setPen(skinmod.qcolor("line", int(255 * self.opacity)))
        p.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 10, 10)
        a, n = self._texts()
        r = self.rect().adjusted(12, 6, -12, -6)
        h = r.height()
        p.setFont(self.f1)
        p.setPen(QColor(s.accent_text))
        p.drawText(r.adjusted(0, 0, 0, -h // 2 + 6), Qt.AlignmentFlag.AlignCenter, a)
        p.setFont(self.f2)
        p.setPen(QColor(s.dim))
        p.drawText(r.adjusted(0, h // 2 + 4, 0, 0), Qt.AlignmentFlag.AlignCenter, n)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self._drag is not None:
            self.move(e.globalPosition().toPoint() - self._drag)

    def mouseReleaseEvent(self, e):
        self._drag = None

    def contextMenuEvent(self, e):
        m = QMenu(self)
        for v in (0.5, 0.7, 0.85, 1.0):
            a = m.addAction(f"투명도 {int(v * 100)}%")
            a.triggered.connect(lambda _=False, v=v: self._set_op(v))
        fm = m.addMenu("글자 크기")
        for pt in (14, 18, 24, 32, 40):
            fm.addAction(f"{pt}pt", lambda pt=pt: self.set_font_pt(pt))
        m.addAction("잠금 (클릭 통과)", lambda: self.set_click_through(True))
        m.addSeparator()
        m.addAction("닫기", self.close)
        exec_menu(m, e.globalPos())

    def set_skin(self, _s=None):
        self.update()

    def _set_op(self, v):
        self.opacity = v
        self.update()

    def closeEvent(self, e):
        self.closed.emit()
        super().closeEvent(e)
