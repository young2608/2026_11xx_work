# -*- coding: utf-8 -*-
"""
미니 플레이어 (vr0.1.0.009, Ctrl+M) — 항상 위에 뜨는 작은 창 (360×96)
  표지 · 제목/가수 · 이전/재생/다음 · 진행 막대 · 가사 한 줄. 끌어서 이동, 더블클릭 = 큰 창으로.
"""
from PyQt6.QtCore import QPoint, Qt, pyqtSignal
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QProgressBar, QVBoxLayout

from . import metrics
from .iconbutton import IconButton


class MiniPlayer(QFrame):
    closed = pyqtSignal()
    restore = pyqtSignal()

    def __init__(self, ctrl):
        super().__init__(None, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.ctrl = ctrl
        self.setObjectName("card")
        metrics.fix(self, 380, 100)                       # v023: 글자 크기를 따라
        h = QHBoxLayout(self)
        metrics.margins(h, 10, 8, 8, 8)
        self.cover = QLabel()
        metrics.fix(self.cover, 64, 64)
        self.cover.setScaledContents(True)
        h.addWidget(self.cover)
        v = QVBoxLayout()
        metrics.spacing(v, 2)
        self.title = QLabel("yMp3Player", objectName="barTitle")
        self.sub = QLabel("", objectName="barSub")
        self.line = QLabel("", objectName="barSub")
        for lb in (self.title, self.sub, self.line):
            metrics.fix(lb, max_w=200)
        v.addWidget(self.title)
        v.addWidget(self.sub)
        v.addWidget(self.line)
        self.prog = QProgressBar()
        self.prog.setTextVisible(False)
        metrics.fix(self.prog, height=4)
        v.addWidget(self.prog)
        h.addLayout(v, 1)
        self.b_prev = IconButton("prev", "prev", ctrl.prev, size=16)
        self.b_play = IconButton("play", "play", ctrl.toggle, size=18)
        self.b_next = IconButton("next", "next", ctrl.next, size=16)
        self.b_close = IconButton("close", "panel_close", self.close, size=14)
        for b in (self.b_prev, self.b_play, self.b_next):
            h.addWidget(b)
        h.addWidget(self.b_close, 0, Qt.AlignmentFlag.AlignTop)
        self._drag = None
        ctrl.trackChanged.connect(self.set_track)
        ctrl.positionChanged.connect(self.set_pos)
        ctrl.stateChanged.connect(self.set_state)
        ctrl.lyricPosition.connect(self._lyric)
        t = ctrl.current_track()
        if t:
            self.set_track(t, ctrl.tag_info)

    def set_track(self, t, info):
        self.title.setText(t.display)
        self.sub.setText(" · ".join(x for x in (info.album, getattr(info, "format_label", "")) if x))
        # v022 (N1): 표지는 메인 창이 백그라운드에서 디코드한 그림을 set_cover_image 로 받음 (곡마다 여기서 또 디코드하지 않음)

    def set_cover_image(self, img):
        """img: QImage(최대 800px) 또는 None"""
        from .hidpi import dpr, hi_pixmap
        pm = hi_pixmap(img, 64, 64, dpr(self), expand=True) if img is not None else None   # v016 G4: 화면 배율로
        if pm is not None and not pm.isNull():
            self.cover.setPixmap(pm)
        else:
            self.cover.clear()

    def set_pos(self, pos, dur):
        if dur > 0:
            self.prog.setRange(0, dur)
            self.prog.setValue(pos)

    def set_state(self, st):
        self.b_play.set_icon_name("pause" if st == "playing" else "play")

    def _lyric(self, ms):
        ly = self.ctrl.cur_lyrics
        if not ly or not ly.synced:
            self.line.setText("")
            return
        i = ly.index_at(ms)
        txt = ly.blocks[i].lines[0] if 0 <= i < len(ly.blocks) and ly.blocks[i].lines else ""
        if txt != self.line.text():
            self.line.setText(txt)

    def mousePressEvent(self, e):
        self._drag = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self._drag is not None:
            self.move(e.globalPosition().toPoint() - self._drag)

    def mouseReleaseEvent(self, e):
        self._drag = None

    def mouseDoubleClickEvent(self, e):
        self.restore.emit()

    def closeEvent(self, e):
        for sig, slot in ((self.ctrl.trackChanged, self.set_track), (self.ctrl.positionChanged, self.set_pos),
                          (self.ctrl.stateChanged, self.set_state), (self.ctrl.lyricPosition, self._lyric)):
            try:
                sig.disconnect(slot)
            except TypeError:
                pass
        self.closed.emit()
        super().closeEvent(e)

    def pos_text(self) -> QPoint:
        return self.pos()
