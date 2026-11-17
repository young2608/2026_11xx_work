# -*- coding: utf-8 -*-
"""업비트 시세 주기 조회 서비스 (vr0.1.0.019 R7 — app/topbar.py 에서 나눔, 화면 없음)

TickerService  창이 보일 때만 ticker_interval_s 마다 백그라운드 조회 → updated 시그널 · 실패하면 간격을 늘림
TopBar(topbar.py) 와 제목 표시줄이 이 서비스의 quotes 를 그림.
"""
import logging
import time

from PyQt6.QtCore import QObject, QThreadPool, QTimer, pyqtSignal

from ..core.bg import BgEmitter, BgTask
from ..domain import ticker as T

log = logging.getLogger("yamp.ticker")


def _short_err(e) -> str:
    s = str(getattr(e, "reason", "") or e)
    code = getattr(e, "code", None)
    if code:
        return f"HTTP {code}" + (" (요청 너무 많음)" if code == 429 else "")
    if "timed out" in s or "timeout" in s.lower():
        return "응답 시간 초과"
    if "getaddrinfo" in s or "Name or service" in s or "Errno" in s or "refused" in s or "인터넷" in s:
        return "인터넷 연결 없음"
    return s[:60]


class TickerService(QObject):
    """시세 주기 조회. fetch(markets, timeout) → ([Quote], server_ms) — 테스트에서 바꿔 끼움"""
    updated = pyqtSignal()

    def __init__(self, cfg, parent=None, fetch=None):
        super().__init__(parent)
        from ..data import upbit
        self.cfg = cfg
        self.fetch = fetch or upbit.fetch
        self.quotes: dict[str, T.Quote] = {}
        self.fails = 0
        self.error = ""
        self.last_ok_ms = 0
        self.skew_s = 0
        self.active = False
        self._seq = 0
        self._busy = False
        self._last_req = 0.0
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(1)
        self._em = BgEmitter(self)                 # v022 (N7): 공통 백그라운드 작업 (core/bg)
        self._em.done.connect(self._on_bg)
        self._timer = QTimer(self, singleShot=True)
        self._timer.timeout.connect(self.refresh)
        self._load_last()

    # ---- 설정
    def markets(self) -> list[str]:
        return T.parse_markets(str(self.cfg["ticker_market"] or ""))

    def enabled(self) -> bool:
        return bool(self.cfg["topbar_ticker"])

    def interval_s(self) -> int:
        return T.next_interval(self.fails, int(self.cfg["ticker_interval_s"] or 10))

    # ---- 시작 · 멈춤 (창이 보일 때만)
    def set_active(self, on: bool):
        on = bool(on) and self.enabled()
        if on == self.active:
            return
        self.active = on
        if not on:
            self._timer.stop()
            return
        due = time.monotonic() - self._last_req >= self.interval_s() or not self.quotes
        if due:
            self.refresh()
        else:
            self._schedule()

    def _schedule(self):
        if self.active:
            self._timer.start(self.interval_s() * 1000)

    def refresh(self):
        if not self.enabled() or self._busy:
            return
        self._busy = True
        self._seq += 1
        self._last_req = time.monotonic()
        seq, markets, fetch = self._seq, self.markets(), self.fetch

        def work():
            quotes, server_ms = fetch(markets, 3.0)
            return seq, quotes, server_ms, ""
        # 인터넷 없음 · 서버 오류 · 응답 형식 → 빈 결과 + 짧은 오류 문구 (전과 같음)
        self._pool.start(BgTask(work, self._em, on_error=lambda e: (seq, [], 0, _short_err(e))))

    def _on_bg(self, r):
        self._done(*r)

    def _done(self, seq, quotes, server_ms, err):
        self._busy = False
        if seq != self._seq:
            return
        if quotes:
            for q in quotes:
                self.quotes[q.market] = q
            self.fails, self.error = 0, ""
            self.last_ok_ms = int(time.time() * 1000)
            self.skew_s = T.clock_skew_s(server_ms, self.last_ok_ms)
            self._save_last()
        else:
            self.fails += 1
            self.error = err or "응답에 시세 없음"
            log.info("ticker fail %d: %s", self.fails, self.error)
        self.updated.emit()
        self._schedule()

    def stop(self):
        self.active = False
        self._timer.stop()
        self._seq += 1
        self._pool.waitForDone(3500)

    # ---- 마지막 시세 기억 (다음 실행 때 첫 갱신 전까지 흐리게)
    def _save_last(self):
        try:
            self.cfg["last_quote"] = {m: q.__dict__ for m, q in self.quotes.items()}
        except Exception:  # noqa
            pass

    def _load_last(self):
        d = self.cfg["last_quote"] or {}
        for m, v in (d.items() if isinstance(d, dict) else []):
            try:
                self.quotes[m] = T.Quote(**v)
            except TypeError:
                pass

    @property
    def stale(self) -> bool:
        return self.last_ok_ms == 0 or bool(self.error)
