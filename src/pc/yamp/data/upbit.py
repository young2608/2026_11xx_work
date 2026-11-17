# -*- coding: utf-8 -*-
"""업비트 공개 시세 조회 (vr0.1.0.012, f23) — 키 필요 없음. 순수 계산은 domain/ticker.py"""
import urllib.parse
import urllib.request
from email.utils import parsedate_to_datetime

from ..domain.ticker import URL, Quote, parse_upbit
from ..version import APP_NAME, VERSION


def fetch(markets: list[str], timeout: float = 3.0) -> tuple[list[Quote], int]:
    """(시세 목록, 서버 시각 epoch ms — Date 헤더, 없으면 0). 실패는 예외 (URLError · HTTPError · ValueError)"""
    url = URL + "?" + urllib.parse.urlencode({"markets": ",".join(markets)})
    req = urllib.request.Request(url, headers={"User-Agent": f"{APP_NAME}/{VERSION}", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = r.read()
        date = r.headers.get("Date") if getattr(r, "headers", None) is not None else None
    server_ms = 0
    if date:
        try:
            server_ms = int(parsedate_to_datetime(date).timestamp() * 1000)
        except (TypeError, ValueError):
            server_ms = 0
    return parse_upbit(body), server_ms
