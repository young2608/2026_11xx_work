# -*- coding: utf-8 -*-
"""vr0.1.0.012 — 상단 바: 업비트 시세 · KST 시각 · 버전 (f23)"""
import os
import time
import urllib.error
from pathlib import Path

import pytest

from yamp.domain import ticker as T

TD = Path(__file__).resolve().parents[2] / "testdata"


@pytest.fixture
def app():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


# ---------------------------------------------------------------- 공용 벡터 (Android 와 같은 결과)
def test_ticker_shared_vectors():
    n = 0
    for line in (TD / "upbit_ticker_cases.txt").read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        f = line.split("|")
        k = f[0]
        if k == "price":
            got, want = T.fmt_price(float(f[1])), f[2]
        elif k == "rate":
            got, want = T.fmt_rate(f[1], float(f[2])), f[3]
        elif k == "cp":
            got, want = T.fmt_change_price(float(f[1]), float(f[2])), f[3]
        elif k == "won":
            got, want = T.fmt_won_big(float(f[1])), f[2]
        elif k == "kst":
            got, want = T.kst_label(int(f[1]), f[2] == "1", f[3] == "1"), f[4]
        elif k == "interval":
            got, want = str(T.next_interval(int(f[1]), int(f[2]))), f[3]
        elif k == "markets":
            got, want = ";".join(T.parse_markets(f[1])), f[2]
        else:
            continue
        assert got == want, line
        n += 1
    assert n >= 40


def test_parse_sample_and_errors():
    q = T.parse_upbit((TD / "upbit_ticker_sample.json").read_bytes())[0]
    assert (q.market, q.price, q.change, q.symbol) == ("KRW-XRP", 3512.0, "RISE", "XRP")
    assert T.fmt_rate(q.change, q.change_rate) == "▲1.24%" and q.ts_ms == 1794218167000
    tip = T.tooltip(q, q.ts_ms, q.ts_ms)
    assert "전일 대비 +43원 (▲1.24%)" in tip and "1.2조원" in tip and "18:56:07 KST" in tip
    with pytest.raises(ValueError):
        T.parse_upbit('{"error": {"name": "404", "message": "Code not found"}}')
    assert T.clock_skew_s(1_000_000, 1_045_000) == 45 and T.clock_skew_s(0, 5) == 0


def test_kst_independent_of_local_timezone(monkeypatch):
    monkeypatch.setenv("TZ", "America/Los_Angeles")
    if hasattr(time, "tzset"):
        time.tzset()
    try:
        assert T.kst_label(1794218167000) == "11-09(월) 18:56:07 KST"
    finally:
        monkeypatch.delenv("TZ")
        if hasattr(time, "tzset"):
            time.tzset()


# ---------------------------------------------------------------- 서비스 · 화면
class _Fake:
    def __init__(self):
        self.calls = 0
        self.mode = "ok"
        self.price = 3512.0

    def __call__(self, markets, timeout):
        self.calls += 1
        if self.mode == "fail":
            raise urllib.error.URLError("[Errno 11001] getaddrinfo failed")
        qs = [T.Quote(m, self.price if m == "KRW-XRP" else 95_000_000.0, "RISE" if m == "KRW-XRP" else "FALL",
                      43, 0.0124, 3540, 3455, 1.23e12, int(time.time() * 1000)) for m in markets]
        return qs, int(time.time() * 1000) - 50_000          # 서버 시각이 50초 느림 → PC 시계 차이 안내


def _wait(app, svc, n=200):
    for _ in range(n):
        app.processEvents()
        if not svc._busy:
            return
        time.sleep(0.01)


def test_topbar_quote_flash_fail_and_backoff(app, tmp_path):
    os.environ["YAMP_HOME"] = str(tmp_path)
    from yamp.core.config import Config
    from yamp.app.topbar import TopBar
    from yamp.ui import skin
    cfg = Config(tmp_path)
    assert cfg["topbar_ticker"] is True and cfg["ticker_market"] == "KRW-XRP" and cfg["ticker_interval_s"] == 10
    fake = _Fake()
    bar = TopBar(cfg, None, fake)
    try:
        assert bar.svc.active is False and fake.calls == 0           # 창이 보이기 전엔 요청 안 함
        bar.set_active(True)
        _wait(app, bar.svc)
        assert fake.calls == 1 and "XRP ₩3,512 ▲1.24%" in bar.price.text()
        assert skin.current().rise in bar.price.text()                # 상승 = rise 색
        assert "PC 시계가 업비트 서버와 50초 다름" in bar.price.toolTip()
        assert bar.svc._timer.isActive() and bar.svc._timer.interval() == 10_000
        assert "KST" in bar.clock.text() and bar.ver.text() == bar.ver.text().strip()
        from PyQt6.QtGui import QFontMetrics                          # 재검: 글자가 잘리지 않을 최소 폭
        f = bar.clock.font()
        f.setPointSizeF(9.0)
        assert bar.clock.minimumWidth() >= QFontMetrics(f).horizontalAdvance(bar.clock.text())
        assert bar.price.minimumWidth() >= QFontMetrics(f).horizontalAdvance("● XRP ₩3,512 ▲1.24%")
        fake.price = 3500.0
        bar.svc.refresh()
        _wait(app, bar.svc)
        assert bar._flash == "fall" and bar._flash_t.isActive()      # 가격 바뀜 → 반짝
        assert skin.current().flash_fall in bar.price.styleSheet()
        fake.mode = "fail"
        for _ in range(3):
            bar.svc.refresh()
            _wait(app, bar.svc)
        assert bar.svc.fails == 3 and bar.svc.interval_s() == 30 and "인터넷 연결 없음" in bar.price.toolTip()
        assert skin.current().dim in bar.price.text()                 # 실패 → 흐리게 (마지막 값은 유지)
        assert "₩3,500" in bar.price.text()
        fake.mode = "ok"
        bar.svc.refresh()
        _wait(app, bar.svc)
        assert bar.svc.fails == 0 and bar.svc.interval_s() == 10
        bar.set_active(False)                                         # 창 숨김 → 타이머 멈춤
        assert not bar.svc._timer.isActive() and not bar._clock_t.isActive()
        assert cfg["last_quote"]["KRW-XRP"]["price"] == 3500.0
    finally:
        bar.shutdown()


def test_topbar_multi_market_rotation_and_options(app, tmp_path):
    os.environ["YAMP_HOME"] = str(tmp_path)
    from yamp.core.config import Config
    from yamp.app.topbar import TopBar
    cfg = Config(tmp_path)
    cfg["ticker_market"] = "krw-xrp, KRW-BTC"
    fake = _Fake()
    bar = TopBar(cfg, None, fake)
    try:
        bar.set_active(True)
        _wait(app, bar.svc)
        assert "XRP" in bar.price.text() and bar._rot_t.isActive()
        bar._rotate()
        assert "BTC ₩95,000,000 ▼1.24%" in bar.price.text()
        cfg["topbar_ticker"] = False
        bar.apply_settings()
        assert bar.price.isHidden() and not bar.svc.active
        calls = fake.calls
        bar.set_active(True)
        assert fake.calls == calls                                    # 끄면 요청 안 함
        cfg["topbar_clock_seconds"] = False
        bar.apply_settings()
        assert bar.clock.text().strip().count(":") == 1
    finally:
        bar.shutdown()


def test_last_quote_shown_dim_before_first_refresh(app, tmp_path):
    os.environ["YAMP_HOME"] = str(tmp_path)
    from yamp.core.config import Config
    from yamp.app.topbar import TopBar
    from yamp.ui import skin
    cfg = Config(tmp_path)
    cfg["last_quote"] = {"KRW-XRP": T.Quote("KRW-XRP", 3400.0, "FALL", -10, -0.003).__dict__}
    bar = TopBar(cfg, None, _Fake())
    try:
        assert "₩3,400" in bar.price.text() and skin.current().dim in bar.price.text()
    finally:
        bar.shutdown()


def test_mainwindow_has_topbar_and_menu(app, tmp_path, monkeypatch):
    os.environ["YAMP_HOME"] = str(tmp_path)
    from yamp.core.config import Config
    from yamp.core.version import version_label
    from yamp.data import upbit
    from yamp.app.mainwindow import MainWindow
    monkeypatch.setattr(upbit, "fetch", _Fake())
    w = MainWindow(Config(tmp_path))
    try:
        assert w.menuBar().cornerWidget() is None and w.ver_label.text() == version_label()   # v014: 제목 표시줄로 이동
        assert version_label() in w.windowTitle() and "KST" in w.windowTitle()
        assert set(w.topbar_actions) == {"topbar_ticker", "topbar_clock", "topbar_clock_seconds"}
        w.topbar_actions["topbar_clock"].setChecked(False)
        assert w.topbar.clock.isHidden() and w.cfg["topbar_clock"] is False
        for name in ("sunny", "night_sunny", "neon"):
            w.apply_skin(name)                                        # 테마 바꾸면 색도 다시
    finally:
        w.topbar.shutdown()
        w.ctrl.shutdown()
        w.deleteLater()


def test_theme_rise_fall_tokens_contrast():
    from yamp.ui import skin
    for s in skin.SKINS.values():
        for k in ("rise", "fall", "flash_rise", "flash_fall"):
            assert getattr(s, k).startswith("#")


def test_fetch_uses_upbit_url(monkeypatch):
    import io
    import urllib.request
    from yamp.data import upbit
    seen = {}

    class R(io.BytesIO):
        headers = {"Date": "Mon, 09 Nov 2026 09:56:07 GMT"}

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake(req, timeout=None):
        seen["url"], seen["timeout"] = req.full_url, timeout
        return R((TD / "upbit_ticker_sample.json").read_bytes())
    monkeypatch.setattr(urllib.request, "urlopen", fake)
    qs, server_ms = upbit.fetch(["KRW-XRP"], 3)
    assert seen["url"] == "https://api.upbit.com/v1/ticker?markets=KRW-XRP" and seen["timeout"] == 3
    assert qs[0].price == 3512.0 and server_ms == 1794218167000
