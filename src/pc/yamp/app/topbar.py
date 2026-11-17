# -*- coding: utf-8 -*-
"""상단 바 (vr0.1.0.012, f23) — 메뉴바 오른쪽 모서리: [● XRP ₩3,512 ▲1.24%] │ [11-09(월) 18:56:07 KST] │ [버전__빌드시각]

  TickerService : (v019 R7 → ticker_service.py) 업비트 시세를 ticker_interval_s(기본 10초)마다 백그라운드 스레드에서 가져옴
                  · 3번 연속 실패 → 30초, 6번 → 60초 (성공하면 복귀) · 창이 숨겨지면 멈춤 (요청 0)
  TopBar        : 시세 칸(상승 rise · 하락 fall · 보합 dim, 바뀌면 0.6초 반짝, 실패면 흐리게) · KST 시계(1초) · 버전
                  시세 칸 클릭 → 업비트 거래 화면 · 마우스를 올리면 상세 (전일 대비 · 고가/저가 · 거래대금 · 마지막 갱신)
  색은 모두 테마 토큰 (testdata/themes.txt) — 고정 색 없음
"""
import logging
import time

from PyQt6.QtCore import QTimer, QUrl, Qt, pyqtSignal
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QWidget

from ..core.version import version_label
from ..domain import ticker as T
from ..ui import metrics, skin as skinmod, tips
from .ticker_service import TickerService, _short_err  # noqa: F401  (v019 R7: ticker_service.py 로 나눔, 이전 import 호환)

log = logging.getLogger("yamp.ticker")
ROTATE_MS = 3000            # 마켓이 2개 이상이면 번갈아 표시
FLASH_MS = 600
SKEW_NOTE_S = 30


class _ClickLabel(QLabel):
    clicked = pyqtSignal()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(e)


class TopBar(QWidget):
    """시세 · 시각 (v012: 메뉴바 모서리 위젯 → v014: 화면에는 안 붙이고 제목 줄 글자로 — title_suffix · changed)"""
    changed = pyqtSignal()          # v014: 제목 줄 다시 쓰기 (시세 바뀜 · 분 바뀜)

    def __init__(self, cfg, parent=None, fetch=None):
        super().__init__(parent)
        self.cfg = cfg
        self.setObjectName("topBar")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 4, 0)
        lay.setSpacing(0)
        self.price = _ClickLabel(objectName="tickerLabel")
        self.price.setCursor(Qt.CursorShape.PointingHandCursor)
        self.price.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.price.clicked.connect(self.open_upbit)
        self.sep1 = QLabel("│", objectName="topSep")
        self.clock = QLabel(objectName="clockLabel")
        tips.apply_simple(self.clock, "한국 시각 (KST)", "컴퓨터 시간대와 상관없이 UTC+9 로 표시")
        self.sep2 = QLabel("│", objectName="topSep")
        self.ver = QLabel(version_label(), objectName="verLabel")
        tips.apply_simple(self.ver, "프로그램 버전", "버전__빌드 날짜 시각")
        for w in (self.price, self.sep1, self.clock, self.sep2, self.ver):
            lay.addWidget(w)
        self.svc = TickerService(cfg, self, fetch)
        self.svc.updated.connect(self._on_quote)
        self._rot = 0
        self._shown_price: dict[str, float] = {}
        self._flash = ""                               # "", "rise", "fall"
        self._clock_t = QTimer(self)
        self._clock_t.timeout.connect(self._tick_clock)
        self._rot_t = QTimer(self)
        self._rot_t.timeout.connect(self._rotate)
        self._flash_t = QTimer(self, singleShot=True)
        self._flash_t.timeout.connect(self._end_flash)
        self.apply_settings()

    # ---- 설정 · 보이기
    def apply_settings(self):
        self.price.setVisible(self.svc.enabled())
        self.sep1.setVisible(self.svc.enabled())
        on_clock = bool(self.cfg["topbar_clock"])
        self.clock.setVisible(on_clock)
        self.sep2.setVisible(on_clock or self.svc.enabled())
        self._tick_clock()
        self._render()
        if self.svc.active or not self.svc.enabled():
            self.svc.set_active(False)
        self.set_active(getattr(self, "_want_active", False))

    def set_active(self, on: bool):
        """창이 보일 때만 갱신 (장시간 운용) — MainWindow._sync_active 가 부름"""
        self._want_active = bool(on)
        self.svc.set_active(on)
        if on and self.cfg["topbar_clock"]:
            self._tick_clock()
            self._clock_t.start(1000 if self.cfg["topbar_clock_seconds"] else 5000)
        else:
            self._clock_t.stop()
        if on and len(self.svc.markets()) > 1:
            self._rot_t.start(ROTATE_MS)
        else:
            self._rot_t.stop()

    def shutdown(self):
        self._clock_t.stop()
        self._rot_t.stop()
        self.svc.stop()

    # ---- 표시
    def _tick_clock(self):
        t = T.kst_label(int(time.time() * 1000), bool(self.cfg["topbar_clock_seconds"]))
        self.clock.setText(t)
        self._fit(self.clock, t + "0")
        m = t[:-7] if self.cfg["topbar_clock_seconds"] else t      # 분 단위로만 제목 갱신
        if m != getattr(self, "_last_min", None):
            self._last_min = m
            self.changed.emit()

    def _fit(self, label, sample: str):
        """글자가 잘리지 않게 최소 폭 (메뉴바 모서리 위젯은 처음 크기로 고정되므로 커지면 다시 배치)
        v012 재검: 시세·시각 글자가 늘어나도 메뉴바가 모서리 폭을 다시 계산하지 않아 '▲1.' 처럼 잘리던 문제"""
        f = label.font()
        f.setPointSizeF(skinmod.font_pt("cap"))
        from PyQt6.QtGui import QFontMetrics
        need = QFontMetrics(f).horizontalAdvance(sample) + 16
        if need > label.minimumWidth():
            label.setMinimumWidth(need)
            self.updateGeometry()
            mb = self.parentWidget()
            if mb is not None and hasattr(mb, "setCornerWidget") and mb.cornerWidget(Qt.Corner.TopRightCorner) is self:
                QTimer.singleShot(0, lambda: (mb.setCornerWidget(self, Qt.Corner.TopRightCorner), self.show()))

    def _rotate(self):
        self._rot += 1
        self._render()

    def current_quote(self) -> T.Quote | None:
        ms = self.svc.markets()
        m = ms[self._rot % len(ms)]
        return self.svc.quotes.get(m)

    def _on_quote(self):
        q = self.current_quote()
        if q is not None and not self.svc.error:
            old = self._shown_price.get(q.market)
            if old is not None and q.price != old:
                self._flash = "rise" if q.price > old else "fall"
                self._flash_t.start(FLASH_MS)
            self._shown_price[q.market] = q.price
        self._render()

    def _end_flash(self):
        self._flash = ""
        self._render()

    def title_suffix(self) -> str:
        """제목 줄 뒤쪽: 'XRP ₩1,436 ▲0.12%  │  12:40 KST' (색 없음 → ▲▼ 기호, 실패면 '(갱신 실패)')"""
        parts = []
        if self.svc.enabled():
            q = self.current_quote()
            if q is None:
                parts.append(f"{self.svc.markets()[0].split('-')[-1]} ₩ —")
            else:
                t = f"{q.symbol} {T.fmt_price(q.price)} {T.fmt_rate(q.change, q.change_rate)}"
                parts.append(t + (" (갱신 실패)" if self.svc.error else ""))
        if self.cfg["topbar_clock"]:
            parts.append(T.kst_label(int(time.time() * 1000), False, False))
        return "  │  ".join(parts)

    def _render(self):
        s = skinmod.current()
        q = self.current_quote()
        if q is None:
            sym = self.svc.markets()[self._rot % len(self.svc.markets())].split("-")[-1]
            text, fg = f"● {sym} ₩ —", s.dim
            detail = f"업비트 {self.svc.markets()[0]} 시세를 가져오는 중…" + (f"\n갱신 실패 ({self.svc.error})" if self.svc.error else "")
        else:
            text = f"● {q.symbol} {T.fmt_price(q.price)} {T.fmt_rate(q.change, q.change_rate)}"
            fg = s.rise if q.change == "RISE" else s.fall if q.change == "FALL" else s.dim
            detail = T.tooltip(q, self.svc.last_ok_ms, int(time.time() * 1000), self.svc.error)
            if abs(self.svc.skew_s) > SKEW_NOTE_S:
                detail += f"\nPC 시계가 업비트 서버와 {abs(self.svc.skew_s)}초 다름 ({'빠름' if self.svc.skew_s > 0 else '느림'})"
        stale = self.svc.stale
        dot = s.dim if stale else (s.rise if q and q.change == "RISE" else s.fall if q and q.change == "FALL" else s.accent_text)
        if stale:
            fg = s.dim
        bg = {"rise": s.flash_rise, "fall": s.flash_fall}.get(self._flash, "transparent")
        sym, rest = text[:1], text[1:]
        self.price.setText(f"<span style='color:{dot}'>{sym}</span><span style='color:{fg}'>{rest}</span>")
        self.price.setStyleSheet(metrics.scale_css(            # v025: 모서리 · 여백도 글자 배율 (10pt = 그대로)
            f"QLabel#tickerLabel {{ background:{bg}; border-radius:4px; padding:0 6px; font-size:{skinmod.fs('cap')}; }}"))
        self._fit(self.price, text + " ▲00.00%")
        tips.apply_simple(self.price, "업비트 시세 (" + ("갱신 실패" if self.svc.error else f"{self.svc.interval_s()}초마다") + ")",
                          detail)
        self.changed.emit()

    def set_skin(self, _skin=None):
        self._render()

    def open_upbit(self):
        q = self.current_quote()
        m = q.market if q else self.svc.markets()[0]
        QDesktopServices.openUrl(QUrl(f"https://upbit.com/exchange?code=CRIX.UPBIT.{m}"))
