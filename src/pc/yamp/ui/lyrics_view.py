"""싱크 가사 뷰: 현재 블록 강조 + 부드러운 자동 스크롤.

- 휠로 수동 스크롤하면 3초간 자동 추적 멈춤
- 싱크 가사 줄 더블클릭 → 그 시각으로 이동
- 블록 = 같은 시각의 여러 줄 (알송: 원문/발음/번역)
"""
from PyQt6.QtCore import QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QFontMetrics, QPainter
from PyQt6.QtWidgets import QWidget

from ..lyrics.lrc import Lyrics
from . import metrics
from .skin import Skin
from .qtutil import exec_menu


def visible_lines(lines, show_pron=True, show_trans=True):
    """3단 가사 (A3): 블록의 0번 = 원문, 1번 = 발음, 2번 이후 = 번역"""
    if len(lines) < 2:
        return list(lines)
    out = [lines[0]]
    if show_pron:
        out.append(lines[1])
    if show_trans:
        out += lines[2:]
    return out


class LyricsView(QWidget):
    seekRequested = pyqtSignal(int)
    repeatRequested = pyqtSignal(int, int)        # 가사 줄 반복 (블록 시작, 다음 블록 시작)
    editRequested = pyqtSignal()
    pickRequested = pyqtSignal()

    def __init__(self, skin: Skin, font_pt: int = 13, parent=None):
        super().__init__(parent)
        self.skin = skin
        self.ly: Lyrics | None = None
        self.message = "가사 없음"
        self.cur = -1
        self.scroll_y = 0.0      # 현재 표시 오프셋
        self.target_y = 0.0
        self.manual_until = 0
        self._layout: list[tuple[float, float]] = []   # 블록별 (y, h)
        self.show_pron = True
        self.show_trans = True
        self.set_font_pt(font_pt)
        self._anim = QTimer(self, interval=16, timeout=self._animate)
        self._manual_t = QTimer(self, singleShot=True, interval=3000, timeout=self._end_manual)
        metrics.fix(self, min_w=240, min_h=160)  # v033 (f61 H5): 글자 배율

    # ---- 외부 ----
    def set_skin(self, s):
        self.skin = s
        self.update()

    def set_font_pt(self, pt: int):
        """pt = 설정 값(10pt 화면 기준). v025: 실제 크기 = pt × 글자 배율 (자동 글자 · 13 · 14pt 에서 가사도 같이 커짐, 10pt = 그대로)"""
        from . import metrics
        self._base_pt = int(pt)
        n = max(6, int(round(int(pt) * metrics.k())))
        self._real_pt = n
        self.font_n = QFont()
        self.font_n.setFamilies(["Malgun Gothic", "Segoe UI", "Noto Sans CJK KR", "sans-serif"])
        self.font_n.setPointSize(n)
        self.font_c = QFont(self.font_n)
        self.font_c.setPointSize(n + max(1, int(round(3 * metrics.k()))))
        self.font_c.setBold(True)
        # v018 (f33 P10): 줄 간격을 글꼴이 바뀔 때만 계산 (전에는 현재 줄이 바뀔 때마다 블록 수만큼 QFontMetrics 생성)
        self._ls_n = QFontMetrics(self.font_n).lineSpacing()
        self._ls_c = QFontMetrics(self.font_c).lineSpacing()
        self._relayout()

    def rescale(self):
        """metrics.reapply 가 부름: 글자 배율이 바뀌었으면 가사 글꼴 다시"""
        from . import metrics
        if max(6, int(round(self._base_pt * metrics.k()))) != self._real_pt:
            self.set_font_pt(self._base_pt)
            self.update()

    def set_three_line(self, pron: bool, trans: bool):
        self.show_pron, self.show_trans = bool(pron), bool(trans)
        self._relayout()
        self.update()

    def _lines(self, k):
        return visible_lines(self.ly.blocks[k].lines, self.show_pron, self.show_trans)

    def set_lyrics(self, ly: Lyrics | None, message: str = "가사 없음"):
        self.ly = ly
        self.message = message
        self.cur = -1
        self.scroll_y = self.target_y = 0.0
        self._relayout()
        self.update()

    def set_message(self, msg: str):
        if self.ly is None:
            self.message = msg
            self.update()

    def set_position(self, pos_ms: int):
        if not self.ly or not self.ly.synced:
            return
        i = self.ly.index_at(pos_ms)
        if i != self.cur:
            self.cur = i
            self._relayout()   # 현재 줄 글꼴 크기 변경 반영
            if not self._manual_t.isActive():
                self._aim()
            self.update()

    # ---- 레이아웃 ----
    def _block_h(self, k: int) -> float:
        n = max(1, len(self._lines(k)))
        return n * (self._ls_c if k == self.cur else self._ls_n) + 10

    def _relayout(self):
        self._layout = []
        if not self.ly:
            return
        y = 0.0
        for k in range(len(self.ly.blocks)):
            h = self._block_h(k)
            self._layout.append((y, h))
            y += h

    def _aim(self):
        if 0 <= self.cur < len(self._layout):
            y, h = self._layout[self.cur]
            self.target_y = y + h / 2
        else:
            self.target_y = 0.0
        if not self._anim.isActive():
            self._anim.start()

    def _animate(self):
        d = self.target_y - self.scroll_y
        if abs(d) < 0.5:
            self.scroll_y = self.target_y
            self._anim.stop()
        else:
            self.scroll_y += d * 0.18
        self.update()

    def _end_manual(self):
        self._aim()

    def resizeEvent(self, e):
        self._relayout()
        super().resizeEvent(e)

    # ---- 입력 ----
    def wheelEvent(self, e):
        if not self.ly:
            return
        self._anim.stop()
        self.scroll_y -= e.angleDelta().y() / 2
        total = self._layout[-1][0] + self._layout[-1][1] if self._layout else 0
        self.scroll_y = max(0.0, min(self.scroll_y, total))
        self.target_y = self.scroll_y
        if self.ly.synced:
            self._manual_t.start()
        self.update()

    def mouseDoubleClickEvent(self, e):
        if not self.ly or not self.ly.synced:
            return
        y = e.position().y() - self._origin()
        for k, (by, bh) in enumerate(self._layout):
            if by <= y < by + bh:
                self.seekRequested.emit(self.ly.blocks[k].t_ms)
                self._manual_t.stop()
                return

    def _block_at(self, y_widget):
        y = y_widget - self._origin()
        for k, (by, bh) in enumerate(self._layout):
            if by <= y < by + bh:
                return k
        return -1

    def contextMenuEvent(self, e):
        from PyQt6.QtWidgets import QMenu
        m = QMenu(self)
        k = self._block_at(e.pos().y()) if self.ly and self.ly.synced else -1
        if k >= 0:
            b = self.ly.blocks
            t0 = b[k].t_ms
            t1 = b[k + 1].t_ms if k + 1 < len(b) else t0 + 5000
            m.addAction("여기로 이동", lambda: self.seekRequested.emit(t0))
            m.addAction("이 줄 반복 (A-B)", lambda: self.repeatRequested.emit(t0, t1))
            m.addSeparator()
        m.addAction("가사 편집…", self.editRequested)
        m.addAction("다른 가사 찾기…", self.pickRequested)
        exec_menu(m, e.globalPos())

    def _origin(self) -> float:
        # 동기 가사: 현재 줄이 화면 가운데. 일반 가사: 위에서부터
        if self.ly and self.ly.synced:
            return self.height() / 2 - self.scroll_y
        return 12 - self.scroll_y

    # ---- 그리기 ----
    def paintEvent(self, e):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(self.skin.list_bg))
        if not self.ly:
            p.setPen(QColor(self.skin.dim))
            p.setFont(self.font_n)
            p.drawText(self.rect().adjusted(16, 8, -16, -8), int(Qt.AlignmentFlag.AlignCenter) | int(Qt.TextFlag.TextWordWrap), self.message)
            return
        oy = self._origin()
        W = self.width()
        c_norm, c_cur = QColor(self.skin.list_fg), QColor(self.skin.lyric_cur)
        c_norm.setAlpha(170 if self.ly.synced else 255)
        for k, (by, bh) in enumerate(self._layout):
            top = oy + by
            if top + bh < 0:
                continue
            if top > self.height():
                break
            is_cur = k == self.cur
            p.setFont(self.font_c if is_cur else self.font_n)
            p.setPen(c_cur if is_cur else c_norm)
            ls = self._ls_c if is_cur else self._ls_n
            lines = self._lines(k) or ["♪"]
            y = top + 5
            for j, ln in enumerate(lines):
                if j > 0:                      # 발음·번역 줄은 흐리게
                    c = QColor(c_cur if is_cur else c_norm)
                    c.setAlpha(150)
                    p.setPen(c)
                p.drawText(QRectF(8, y, W - 16, ls),
                           Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter, ln)
                y += ls
