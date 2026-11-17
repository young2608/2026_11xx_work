"""상단 패널 위젯: LCD 시간, 스크롤 제목, 스펙트럼, 클릭 이동 슬라이더."""
from PyQt6.QtCore import QRectF, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QFont, QFontMetrics, QLinearGradient, QPainter
from PyQt6.QtWidgets import QLabel, QSlider, QStyle, QStyleOptionSlider, QWidget

from .skin import Skin


def mono_font(pt: int, bold: bool = True) -> QFont:
    f = QFont("Consolas")
    f.setStyleHint(QFont.StyleHint.Monospace)
    f.setFamilies(["Consolas", "DejaVu Sans Mono", "Courier New", "monospace"])
    f.setPointSize(pt)
    f.setBold(bold)
    return f


class LcdTime(QWidget):
    """mm:ss 큰 숫자. 클릭 → 경과/남은 시간 전환."""
    toggled = pyqtSignal(bool)

    def __init__(self, skin: Skin, parent=None):
        super().__init__(parent)
        self.skin = skin
        self.pos_ms = 0
        self.dur_ms = 0
        self.remaining = False
        self.playing = False
        self.blink = True
        self.setMinimumSize(120, 44)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._font = mono_font(24)
        self._blink_t = QTimer(self, interval=500, timeout=self._on_blink)

    def set_skin(self, s):
        self.skin = s
        self.update()

    def set_time(self, pos, dur):
        if pos // 1000 != self.pos_ms // 1000 or dur != self.dur_ms:
            self.pos_ms, self.dur_ms = pos, dur
            self.update()
        else:
            self.pos_ms = pos

    BLINK_MAX = 1200                  # 일시정지 깜빡임은 10분(500ms × 1200)까지만 — 며칠 멈춰 둬도 계속 깨어나지 않게

    def set_paused(self, paused: bool):
        if paused:
            self._blinks = 0
            self._blink_t.start()
        else:
            self._blink_t.stop()
            self.blink = True
            self.update()

    def _on_blink(self):
        self._blinks = getattr(self, "_blinks", 0) + 1
        if self._blinks >= self.BLINK_MAX:
            self._blink_t.stop()
            self.blink = True
        elif not self.isVisible() or (self.window() and self.window().isMinimized()):
            return                         # 안 보이면 그리지 않음
        else:
            self.blink = not self.blink
        self.update()

    def mousePressEvent(self, e):
        self.remaining = not self.remaining
        self.toggled.emit(self.remaining)
        self.update()

    def text(self) -> str:
        if self.remaining and self.dur_ms > 0:
            s = max(0, (self.dur_ms - self.pos_ms) // 1000)
            return f"-{s // 60:02d}:{s % 60:02d}"
        s = max(0, self.pos_ms // 1000)
        return f" {s // 60:02d}:{s % 60:02d}"

    def paintEvent(self, e):
        p = QPainter(self)
        p.setFont(self._font)
        p.setPen(QColor(self.skin.lcd_dim))
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, " 88:88")
        if self.blink:
            p.setPen(QColor(self.skin.lcd_fg))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.text())


class ScrollTitle(QWidget):
    """폭보다 긴 제목은 좌로 흐르는 마퀴."""

    def __init__(self, skin: Skin, parent=None):
        super().__init__(parent)
        self.skin = skin
        self._text = "yMp3Player"
        self._x = 0
        self._font = mono_font(11, False)
        self.setMinimumHeight(22)
        self._t = QTimer(self, interval=40, timeout=self._step)   # 제목이 칸보다 길고 보일 때만 돎 (_sync_timer)

    def set_skin(self, s):
        self.skin = s
        self.update()

    def set_text(self, t: str):
        if t != self._text:
            self._text = t
            self._x = 0
            self.update()
            self._sync_timer()

    def _overflow(self) -> bool:
        return QFontMetrics(self._font).horizontalAdvance(self._text) > self.width() - 8

    def _sync_timer(self):
        """장시간 운용: 흐를 필요가 없으면(짧은 제목·숨김) 타이머를 멈춤 — 25fps 가 계속 깨어나지 않게"""
        run = self.isVisible() and self._overflow() and not (self.window() and self.window().isMinimized())
        if run and not self._t.isActive():
            self._t.start()
        elif not run and self._t.isActive():
            self._t.stop()
            if self._x:
                self._x = 0
                self.update()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._sync_timer()

    def showEvent(self, e):
        super().showEvent(e)
        self._sync_timer()

    def hideEvent(self, e):
        super().hideEvent(e)
        self._sync_timer()

    def _tw(self):
        return QFontMetrics(self._font).horizontalAdvance(self._text + "   ***   ")

    def _step(self):
        if not self.isVisible() or not self._overflow():
            self._sync_timer()
            return
        self._x = (self._x + 1) % max(1, self._tw())
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(self.skin.lcd_bg))
        p.setFont(self._font)
        p.setPen(QColor(self.skin.lcd_fg))
        fm = QFontMetrics(self._font)
        y = (self.height() + fm.ascent() - fm.descent()) // 2
        if fm.horizontalAdvance(self._text) <= self.width() - 8:
            p.drawText(4, y, self._text)
        else:
            unit = self._text + "   ***   "
            w = self._tw()
            x = 4 - self._x
            while x < self.width():
                p.drawText(x, y, unit)
                x += w


class SpectrumWidget(QWidget):
    """LCD 옆 작은 스펙트럼. v026 (f51): 움직임 = BandSmoother (비주얼라이저와 같은 규칙 — 천천히 내려앉고 꼭대기는 머문 뒤 낙하)"""
    STEP_S = 0.033

    def __init__(self, skin: Skin, n: int = 24, parent=None):
        super().__init__(parent)
        from ..domain.vis_math import BandSmoother
        self.skin = skin
        self.n = n
        self.sm = BandSmoother(n)
        self.setMinimumSize(110, 36)
        self._decay = QTimer(self, interval=33, timeout=self._fall)   # 막대가 다 내려가면 멈춤, set_levels 때 다시 시작

    vals = property(lambda self: self.sm.v)
    peaks = property(lambda self: self.sm.peaks)

    def set_skin(self, s):
        self.skin = s
        self.update()

    def set_levels(self, lv):
        self.sm.set_target(lv)
        if not self._decay.isActive() and self.isVisible():
            self._decay.start()

    def _fall(self):
        if not self.isVisible():
            self._decay.stop()
            return
        self.sm.step(self.STEP_S)
        self.update()
        if self.sm.idle():
            self._decay.stop()                 # 다 내려감 → 다음 set_levels 까지 쉼

    def paintEvent(self, e):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(self.skin.lcd_bg))
        w = self.width() / self.n
        h = self.height() - 2
        fg = QLinearGradient(0, self.height(), 0, 0)          # 아래 spectrum_lo → 위 spectrum_hi
        fg.setColorAt(0, QColor(self.skin.spectrum_lo))
        fg.setColorAt(1, QColor(self.skin.spectrum_hi))
        fg = QBrush(fg)
        pk = QColor(self.skin.peak)
        for i in range(self.n):
            x = i * w + 1
            bh = self.vals[i] * h
            p.fillRect(QRectF(x, self.height() - bh, w - 2, bh), fg)
            py = self.height() - self.peaks[i] * h
            p.fillRect(QRectF(x, py - 1, w - 2, 2), pk)


class SeekSlider(QSlider):
    """클릭한 위치로 바로 이동, 드래그 중에는 외부 갱신 무시."""
    seekRequested = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(Qt.Orientation.Horizontal, parent)
        self.setRange(0, 0)
        self.sliderReleased.connect(lambda: self.seekRequested.emit(self.value()))

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self.maximum() > 0:
            opt = QStyleOptionSlider()
            self.initStyleOption(opt)
            v = QStyle.sliderValueFromPosition(self.minimum(), self.maximum(),
                                               int(e.position().x()), self.width())
            self.setValue(v)
            self.seekRequested.emit(v)
        super().mousePressEvent(e)

    def set_pos(self, v):
        if not self.isSliderDown():
            self.blockSignals(True)
            self.setValue(v)
            self.blockSignals(False)


class ElideLabel(QLabel):
    """긴 글자는 끝을 '…' 로 (잘려 보이지 않게) · 잘렸으면 마우스를 올리면 전체 — v016 (f29 G8)"""

    def minimumSizeHint(self):
        sh = super().minimumSizeHint()
        return QSize(min(sh.width(), 40), sh.height())

    def sizeHint(self):
        sh = super().sizeHint()
        return QSize(min(sh.width(), self.maximumWidth()), sh.height())

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setPen(self.palette().color(self.foregroundRole()))
        p.setFont(self.font())
        r = self.contentsRect()
        full = self.text()
        txt = QFontMetrics(self.font()).elidedText(full, Qt.TextElideMode.ElideRight, r.width())
        p.drawText(r, int(self.alignment()), txt)
        p.end()
        tip = full if txt != full else ""
        if self.toolTip() != tip:
            self.setToolTip(tip)
