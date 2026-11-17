"""NetEase 클라우드 뮤직 (비공식 웹 API) — vr0.1.0.011 (f18 L10), 기본 꺼짐 (config lyrics_netease).

K-pop · J-pop · C-pop 싱크 가사가 많고 번역 가사(tlyric)도 있음 → 번역은 같은 시각의 둘째 줄로 합침.
⚠ 공식 공개 API 아님 · 지역에 따라 막힐 수 있음. Android lyrics/NetEase.kt 와 같은 규칙.
  search: https://music.163.com/api/search/get/web?s=<검색어>&type=1&limit=10
  lyric : https://music.163.com/api/song/lyric?id=<id>&lv=1&tv=-1
"""
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request

from .base import NetError, Provider, Query
from ..query import variants as make_variants
from ..score import MIN_SCORE, score as score_of

SEARCH = "https://music.163.com/api/search/get/web"
LYRIC = "https://music.163.com/api/song/lyric"
_TS_LINE = re.compile(r"^((?:\[\d{1,3}:\d{1,2}(?:[.:]\d{1,3})?\])+)(.*)$")


def parse_search(data: dict) -> list[dict]:
    out = []
    for s in ((data or {}).get("result") or {}).get("songs") or []:
        out.append({"id": s.get("id"), "title": s.get("name") or "",
                    "artist": ", ".join(a.get("name", "") for a in s.get("artists") or [] if a.get("name")),
                    "album": (s.get("album") or {}).get("name") or "",
                    "duration": float(s.get("duration") or 0) / 1000})
    return out


def merge_translation(lrc: str, tlrc: str) -> str:
    """원문 LRC + 번역 LRC → 같은 시각 줄을 원문 다음 줄로 (알송 3단 가사와 같은 모양)"""
    if not tlrc or not tlrc.strip():
        return lrc or ""
    trans: dict[str, str] = {}
    for line in tlrc.splitlines():
        m = _TS_LINE.match(line.strip())
        if m and m.group(2).strip():
            for ts in re.findall(r"\[[^\]]+\]", m.group(1)):
                trans[ts] = m.group(2).strip()
    out = []
    for line in (lrc or "").splitlines():
        out.append(line)
        m = _TS_LINE.match(line.strip())
        if m and m.group(2).strip():
            ts = re.findall(r"\[[^\]]+\]", m.group(1))[0]
            if ts in trans and trans[ts] != m.group(2).strip():
                out.append(ts + trans[ts])
    return "\n".join(out)


def parse_lyric(data: dict) -> str:
    lrc = ((data or {}).get("lrc") or {}).get("lyric") or ""
    tl = ((data or {}).get("tlyric") or {}).get("lyric") or ""
    return merge_translation(lrc, tl).strip()


class NeteaseProvider(Provider):
    name = "netease"
    remote = True

    def __init__(self, timeout: float = 5.0, min_score: int = MIN_SCORE, log_fn=None):
        self.timeout = timeout
        self.min_score = min_score
        self.log = log_fn or (lambda s: None)

    def _get(self, url: str, params: dict) -> dict:
        req = urllib.request.Request(url + "?" + urllib.parse.urlencode(params), headers={
            "User-Agent": "Mozilla/5.0", "Referer": "https://music.163.com/"})
        t0 = time.monotonic()
        try:
            with urllib.request.urlopen(req, timeout=self.call_timeout()) as r:
                b = r.read()
        except urllib.error.HTTPError as e:
            self.log(f"NetEase: HTTP {e.code}")
            raise NetError(f"HTTP {e.code}") from e
        except Exception as e:  # noqa
            self.log(f"NetEase: 연결 실패 {e}")
            raise NetError(str(e)) from e
        self.log(f"NetEase {url.rsplit('/', 1)[-1]}: {len(b)} 바이트 ({(time.monotonic() - t0) * 1000:.0f}ms)")
        return json.loads(b.decode("utf-8"))

    def candidates(self, q: Query, variants=None) -> list[dict]:
        out: list[dict] = []
        errors = calls = 0
        for t, a in (variants or make_variants(q.title, q.artist))[:2]:
            if time.monotonic() > getattr(self, "deadline", float("inf")):      # 전체 제한 시간 넘김 → 그만
                break
            calls += 1
            try:
                songs = parse_search(self._get(SEARCH, {"s": f"{t} {a}".strip(), "type": 1, "limit": 10}))
            except NetError:
                errors += 1
                continue
            songs.sort(key=lambda d: -score_of(q.title, q.artist, q.album, q.duration, d["title"], d["artist"],
                                               d["album"], "", d["duration"]))
            for d in songs[:2]:
                calls += 1
                try:
                    txt = parse_lyric(self._get(LYRIC, {"id": d["id"], "lv": 1, "tv": -1}))
                except NetError:
                    errors += 1
                    continue
                if not txt:
                    continue
                s = score_of(q.title, q.artist, q.album, q.duration, d["title"], d["artist"], d["album"], txt,
                             d["duration"])
                out.append(dict(d, source="netease", lyric=txt, score=s, synced="[" in txt[:12]))
            if out and max(c["score"] for c in out) >= self.min_score:
                break
        if not out and errors:
            raise NetError("NetEase 에 연결하지 못함")
        return out

    def fetch(self, q: Query):
        try:
            cands = self.candidates(q)
        except NetError:
            return None
        best = max(cands, key=lambda c: c["score"], default=None)
        return best["lyric"] if best and best["score"] >= self.min_score else None


def search_candidates(title: str, artist: str, timeout: float = 5.0, album: str = "", duration: float = 0.0) -> list[dict]:
    try:
        return NeteaseProvider(timeout, min_score=101).candidates(Query("", title, artist, album, duration))
    except NetError:
        return []
