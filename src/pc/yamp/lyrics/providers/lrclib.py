"""LRCLIB (https://lrclib.net) — 공개 무료 싱크 가사 API (키 없음).

vr0.1.0.011 (f18 L4): /api/get 에서 앨범 이름을 뺌 (앨범 표기가 조금만 달라도 404 이던 문제)
  get(제목·가수·길이) → search(track_name·artist_name) → search(q="가수 제목") — 검색어 변형마다, 점수(score.py)로 고름
"""
import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request

from .base import NetError, Provider, Query
from ..query import variants as make_variants
from ..score import MIN_SCORE, score as score_of
from ...version import APP_NAME, VERSION

log = logging.getLogger("yamp.lrclib")
BASE = "https://lrclib.net/api"


def pick(items: list[dict], duration: float) -> str | None:
    """(이전 호환) 싱크 우대 + 길이 가까운 것"""
    best, best_d = None, 1e9
    for d in items or []:
        txt = d.get("syncedLyrics") or d.get("plainLyrics")
        if not txt:
            continue
        dd = abs(float(d.get("duration") or 0) - duration) if duration else 0
        if d.get("syncedLyrics"):
            dd -= 3   # 싱크 가사 우대 (재생시간 3초 차이까지)
        if dd < best_d:
            best, best_d = txt, dd
    if best and duration and best_d > 8:
        return None
    return best


def to_cand(d: dict) -> dict | None:
    txt = d.get("syncedLyrics") or d.get("plainLyrics")
    if not txt:
        return None
    return {"source": "lrclib", "title": d.get("trackName") or d.get("name") or "",
            "artist": d.get("artistName") or "", "album": d.get("albumName") or "", "lyric": txt,
            "synced": bool(d.get("syncedLyrics")), "duration": float(d.get("duration") or 0), "id": d.get("id", "")}


class LrclibProvider(Provider):
    name = "lrclib"
    remote = True

    def __init__(self, timeout: float = 5.0, min_score: int = MIN_SCORE, log_fn=None):
        self.timeout = timeout
        self.min_score = min_score
        self.log = log_fn or (lambda s: None)

    def _get(self, path: str, params: dict):
        url = f"{BASE}/{path}?" + urllib.parse.urlencode({k: v for k, v in params.items() if v})
        req = urllib.request.Request(url, headers={"User-Agent": f"{APP_NAME}/{VERSION} (https://lrclib.net)"})
        t0 = time.monotonic()
        try:
            with urllib.request.urlopen(req, timeout=self.call_timeout()) as r:
                b = r.read()
        except urllib.error.HTTPError as e:
            self.log(f"LRCLIB {path}: HTTP {e.code} ({(time.monotonic() - t0) * 1000:.0f}ms)")
            if e.code == 404:
                return None
            raise NetError(f"HTTP {e.code}") from e
        except Exception as e:  # noqa
            self.log(f"LRCLIB {path}: 연결 실패 {e}")
            raise NetError(str(e)) from e
        self.log(f"LRCLIB {path}: HTTP 200 · {len(b)} 바이트 ({(time.monotonic() - t0) * 1000:.0f}ms)")
        return json.loads(b.decode("utf-8"))

    def candidates(self, q: Query, variants=None) -> list[dict]:
        out: list[dict] = []
        seen = set()
        errors = calls = 0

        def add(d):
            c = to_cand(d) if isinstance(d, dict) else None
            if not c:
                return
            k = c.get("id") or (c["title"], c["artist"], c["duration"])
            if k in seen:
                return
            seen.add(k)
            c["score"] = score_of(q.title, q.artist, q.album, q.duration, c["title"], c["artist"], c["album"],
                                  c["lyric"], c["duration"])
            out.append(c)

        def good():
            return out and max(c["score"] for c in out) >= self.min_score

        for t, a in (variants or make_variants(q.title, q.artist)):
            if time.monotonic() > getattr(self, "deadline", float("inf")):      # 전체 제한 시간 넘김 → 그만
                break
            for path, params in (("get", {"track_name": t, "artist_name": a, "duration": int(q.duration) or None}),
                                 ("search", {"track_name": t, "artist_name": a}),
                                 ("search", {"q": f"{a} {t}".strip()})):
                if path == "get" and not a:
                    continue
                calls += 1
                try:
                    r = self._get(path, params)
                except NetError:
                    errors += 1
                    continue
                for d in (r if isinstance(r, list) else [r] if r else []):
                    add(d)
                if good():
                    break
            self.log(f"LRCLIB '{t}' / '{a}': 후보 {len(out)}개, 최고 {max([c['score'] for c in out] or [0])}점")
            if good():
                break
        if not out and errors:
            raise NetError("LRCLIB 에 연결하지 못함")
        return out

    def fetch(self, q: Query):
        if not q.title:
            return None
        try:
            cands = self.candidates(q)
        except NetError:
            return None
        best = max(cands, key=lambda c: c["score"], default=None)
        return best["lyric"] if best and best["score"] >= self.min_score else None


def search_candidates(title: str, artist: str, timeout: float = 5.0, album: str = "", duration: float = 0.0) -> list[dict]:
    """가사 후보 목록 ('다른 가사 찾기'). 네트워크 오류는 빈 목록"""
    try:
        return LrclibProvider(timeout, min_score=101).candidates(Query("", title, artist, album, duration),
                                                                make_variants(title, artist)[:2])
    except NetError as e:
        log.info("lrclib candidates: %s", e)
        return []
