# -*- coding: utf-8 -*-
"""상단 바 시세 · KST 시각 (vr0.1.0.012, f23) — Qt 비의존. Android domain/Ticker.kt 와 같은 규칙.
공용 테스트: testdata/upbit_ticker_cases.txt

  업비트 공개 시세 API  GET https://api.upbit.com/v1/ticker?markets=KRW-XRP  (키 없음, 시세 그룹 초당 10회 / IP)
  가격 표시  ≥100 → ₩3,512 · 1~100 → ₩12.34 · <1 → ₩0.5123   (0.5 올림 반올림)
  변화율     RISE ▲1.23% · FALL ▼0.85% · EVEN 0.00%
  KST       컴퓨터 시간대와 상관없이 UTC+9
  실패 간격  연속 실패 3번부터 30초, 6번부터 60초 (성공하면 기본 주기)
"""
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal

KST = timezone(timedelta(hours=9))
WEEK = "월화수목금토일"
URL = "https://api.upbit.com/v1/ticker"
MIN_INTERVAL_S = 5
DEFAULT_MARKET = "KRW-XRP"


@dataclass
class Quote:
    market: str
    price: float
    change: str = "EVEN"          # RISE / FALL / EVEN
    change_price: float = 0.0     # 부호 있음
    change_rate: float = 0.0      # 부호 있음 (0.0124 = +1.24%)
    high: float = 0.0
    low: float = 0.0
    value_24h: float = 0.0        # 24시간 거래대금(원)
    ts_ms: int = 0                # 체결 시각 (epoch ms)

    @property
    def symbol(self) -> str:
        return self.market.split("-", 1)[-1] if "-" in self.market else self.market


def parse_markets(text: str) -> list[str]:
    """'krw-xrp, KRW-BTC' → ['KRW-XRP', 'KRW-BTC'] (빈 값 → 기본)"""
    out = []
    for m in (text or "").replace(";", ",").split(","):
        m = m.strip().upper()
        if m and m not in out:
            out.append(m)
    return out or [DEFAULT_MARKET]


def parse_upbit(body: bytes | str) -> list[Quote]:
    data = json.loads(body.decode("utf-8") if isinstance(body, (bytes, bytearray)) else body)
    if isinstance(data, dict):                 # 오류 응답 {"error": {...}}
        raise ValueError(str(data.get("error") or data)[:120])
    out = []
    for d in data or []:
        out.append(Quote(
            market=str(d.get("market", "")), price=float(d.get("trade_price") or 0),
            change=str(d.get("change") or "EVEN"), change_price=float(d.get("signed_change_price") or 0),
            change_rate=float(d.get("signed_change_rate") or 0), high=float(d.get("high_price") or 0),
            low=float(d.get("low_price") or 0), value_24h=float(d.get("acc_trade_price_24h") or 0),
            ts_ms=int(d.get("trade_timestamp") or d.get("timestamp") or 0)))
    return out


def _round(x: float, places: int) -> Decimal:
    q = Decimal(1).scaleb(-places)
    return Decimal(repr(float(x))).quantize(q, rounding=ROUND_HALF_UP)


def _places(ref: float) -> int:
    a = abs(ref)
    return 0 if a >= 100 else 2 if a >= 1 else 4


def fmt_num(p: float, ref: float | None = None) -> str:
    """가격 숫자 (₩ 없이). ref = 자릿수 기준 가격 (전일 대비 금액은 현재가 기준 자릿수)"""
    n = _places(p if ref is None else ref)
    if n == 0:
        return f"{int(_round(p, 0)):,}"
    if n == 2:
        return f"{_round(p, 2):,.2f}"
    return f"{_round(p, 4):.4f}"


def fmt_price(p: float) -> str:
    return "₩" + fmt_num(p)


def fmt_rate(change: str, rate: float) -> str:
    r = _round(abs(rate) * 100, 2)
    if change == "RISE":
        return f"▲{r:.2f}%"
    if change == "FALL":
        return f"▼{r:.2f}%"
    return f"{r:.2f}%"


def fmt_change_price(cp: float, ref: float) -> str:
    s = fmt_num(abs(cp), ref)
    return ("+" if cp > 0 else "-" if cp < 0 else "") + s


def fmt_won_big(v: float) -> str:
    """거래대금: 1.2조원 / 3,456억원 / 12억원"""
    if v >= 1e12:
        return f"{_round(v / 1e12, 1)}조원"
    if v >= 1e8:
        return f"{int(_round(v / 1e8, 0)):,}억원"
    return f"{int(_round(v, 0)):,}원"


def kst_label(epoch_ms: int, seconds: bool = True, date: bool = True) -> str:
    t = datetime.fromtimestamp(epoch_ms / 1000, KST)
    hm = t.strftime("%H:%M:%S" if seconds else "%H:%M")
    return (f"{t:%m-%d}({WEEK[t.weekday()]}) " if date else "") + hm + " KST"


def next_interval(fails: int, base_s: int) -> int:
    base = max(MIN_INTERVAL_S, int(base_s))
    if fails >= 6:
        return max(base, 60)
    if fails >= 3:
        return max(base, 30)
    return base


def tooltip(q: Quote, last_ok_ms: int, now_ms: int, error: str = "") -> str:
    lines = [f"업비트 {q.market} · 현재가 {fmt_num(q.price)}원",
             f"전일 대비 {fmt_change_price(q.change_price, q.price)}원 ({fmt_rate(q.change, q.change_rate)})",
             f"고가 {fmt_num(q.high)} · 저가 {fmt_num(q.low)} · 24시간 거래대금 {fmt_won_big(q.value_24h)}",
             f"마지막 갱신 {kst_label(last_ok_ms, True, False)}" if last_ok_ms else "아직 갱신 전"]
    if error:
        lines.append(f"갱신 실패 ({error})")
    if q.ts_ms and last_ok_ms and abs(last_ok_ms - q.ts_ms) > 30 * 60_000:
        pass                                   # 거래가 뜸한 시간 — 체결 시각이 오래될 수 있음 (안내 안 함)
    lines.append("업비트 시세 · 정보 표시용 (지연 가능) · 누르면 업비트 화면")
    return "\n".join(lines)


def clock_skew_s(server_ms: int, local_ms: int) -> int:
    """서버 응답 시각(Date 헤더)과 PC 시각 차이(초, + = PC 가 빠름)"""
    return int(round((local_ms - server_ms) / 1000)) if server_ms else 0
