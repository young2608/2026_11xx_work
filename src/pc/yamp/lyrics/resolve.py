# -*- coding: utf-8 -*-
"""가사 찾기 순서 (vr0.1.0.019 R3 — lyrics/service.py 에서 나눔, Qt 비의존 · 테스트 대상)

캐시 → (실패 기억) → 로컬 .lrc → 태그 내장 → 알송 · LRCLIB · NetEase 동시 조회 → 후보 점수 → Result
LyricsService(service.py) 가 백그라운드 스레드에서 resolve_full 을 부름 · 진단(diag.py)도 같은 함수.
"""
import logging
import time
from concurrent.futures import ThreadPoolExecutor, wait as fwait
from dataclasses import dataclass, field
from pathlib import Path

from ..core.keys import cache_key
from . import lrc
from .providers.base import NetError, Query
from .cache import LyricsCache, NotFoundStore
from .providers.local import LocalLrcProvider, EmbeddedProvider, lrc_save_path
from .providers.alsong import AlsongProvider
from .providers.lrclib import LrclibProvider
from .providers.netease import NeteaseProvider
from .query import variants as make_variants
from .score import MIN_SCORE

log = logging.getLogger("yamp.lyrics")


SOURCE_NAMES = {"local": "로컬 .lrc", "embedded": "태그 내장", "alsong": "알송", "lrclib": "LRCLIB",
                "netease": "NetEase", "user": "직접 편집", "cache": "캐시"}


REASONS = {
    "found": "",
    "offline": "인터넷에 연결되지 않아 가사를 못 찾음",
    "server": "가사 서버 응답 오류 — 도구 → 가사 진단으로 확인",
    "not_found": "맞는 가사를 못 찾음",
    "low_score": "비슷한 가사만 있음 (자동 적용 안 함)",
    "remembered": "가사 없음",
    "disabled": "가사 공급자가 모두 꺼져 있음",
    "kept": "",
}


@dataclass
class Result:
    lyrics: object = None                 # lrc.Lyrics | None
    reason: str = "not_found"             # REASONS 키
    source: str = ""
    score: int = 0
    candidates: list = field(default_factory=list)
    days_ago: int = 0                     # remembered 일 때
    errors: list = field(default_factory=list)

    def status_text(self) -> str:
        if self.lyrics is not None and self.reason == "kept":
            return "새 가사를 못 찾아 지금 가사 유지"
        if self.lyrics is not None:
            src = SOURCE_NAMES.get(self.source, self.source)
            sync = "" if getattr(self.lyrics, "synced", True) else " (싱크 없음)"
            return f"가사: {src}" + (f" · {self.score}점" if self.score else "") + sync
        if self.reason == "remembered":
            return f"가사 없음 ({self.days_ago}일 전 확인) — F5 다시 찾기"
        return REASONS.get(self.reason, "가사 없음")


def build_providers(cfg, log_fn=None) -> list:
    t = float(cfg["lyrics_timeout_s"] or 6)
    ms = int(cfg["lyrics_min_score"] if cfg["lyrics_min_score"] is not None else MIN_SCORE)
    out = []
    if cfg["lyrics_local"]:
        out.append(LocalLrcProvider())
    if cfg["lyrics_embedded"]:
        out.append(EmbeddedProvider())
    if cfg["lyrics_alsong"]:
        out.append(AlsongProvider(t, cfg["alsong_enc_data"] or "", ms, log_fn))
    if cfg["lyrics_lrclib"]:
        out.append(LrclibProvider(t, ms, log_fn))
    if cfg["lyrics_netease"]:
        out.append(NeteaseProvider(t, ms, log_fn))
    return out


def _parse_ok(txt, source):
    if not txt:
        return None
    ly = lrc.parse(txt, source)
    return None if lrc.is_empty(ly) else ly


def resolve_full(q: Query, providers, cache: "LyricsCache | None", use_cache: bool = True,
                 notfound: NotFoundStore | None = None, min_score: int = MIN_SCORE,
                 timeout_s: float = 6.0, save_beside: bool = False, log_fn=None) -> Result:
    """Qt 비의존 — 테스트 대상. use_cache=False(다시 찾기)면 캐시·실패 기억을 무시
    순서: 캐시 → ① 로컬 · 내장 (차례대로) → ② 실패 기억 → ③ 원격 동시 조회 → 점수로 고르기
    (vr0.1.0.030 f58: 93줄 → 단계마다 함수)"""
    say = log_fn or (lambda s: None)
    key = cache_key(q.path)
    if cache and use_cache:
        r = _from_cache(q, cache, say)
        if r:
            return r
    simple = [p for p in providers if not getattr(p, "remote", False) or not hasattr(p, "candidates")]
    remote = [p for p in providers if getattr(p, "remote", False) and hasattr(p, "candidates")]
    r = _from_simple(q, simple, cache, say)
    if r:
        return r
    if not remote:
        return Result(None, "not_found" if simple else "disabled")
    if notfound and use_cache:
        age = notfound.age_days(key)
        if age is not None:
            say(f"실패 기억: {age}일 전 확인 → 자동 검색 안 함")
            return Result(None, "remembered", days_ago=age)
    var = make_variants(q.title, q.artist) if q.title else []
    if not var:
        return Result(None, "not_found")
    say("검색어: " + " · ".join(f"{t} / {a}" for t, a in var))
    cands, errors = _gather_remote(q, var, remote, timeout_s, say)
    best = cands[0] if cands else None
    if best and best["score"] >= min_score:
        ly = _parse_ok(best["lyric"], best["source"])
        if ly is not None:
            say(f"선택: {best['source']} {best.get('artist', '')} - {best.get('title', '')} ({best['score']}점)")
            _cache_put(cache, q, best["lyric"], best["source"])
            if notfound:
                notfound.remove(key)
            if save_beside:
                _save_beside(q, best["lyric"])
            return Result(ly, "found", best["source"], best["score"], cands, errors=errors)
    if not cands and errors:
        offline = all(_is_offline_error(e) for e in errors)
        say("결과: " + ("오프라인" if offline else "서버 오류"))
        return Result(None, "offline" if offline else "server", candidates=cands, errors=errors)
    if notfound and not errors:
        notfound.add(key)                      # 오류 없이 검색이 끝났는데 없음 → 기억
    reason = "low_score" if cands else "not_found"
    say(f"결과: {reason} (최고 {best['score'] if best else 0}점, 기준 {min_score})")
    return Result(None, reason, candidates=cands, errors=errors)


def _cache_put(cache, q: Query, text: str, source: str):
    if cache:
        try:
            cache.put(q, text, source)
        except OSError as e:
            log.warning("cache write: %s", e)


def _is_offline_error(e: str) -> bool:
    return "연결" in e or "시간 초과" in e or "urlopen" in e or "Errno" in e


def _from_cache(q: Query, cache, say) -> Result | None:
    hit = cache.get(q)
    if hit:
        ly = lrc.parse(hit[0], hit[1])
        if not lrc.is_empty(ly):
            say(f"캐시: {hit[1]}")
            return Result(ly, "found", hit[1])
    return None


def _from_simple(q: Query, simple, cache, say) -> Result | None:
    """① 로컬 · 내장 · (테스트용 단순 공급자) — 차례대로, 처음 찾은 것"""
    for p in simple:
        try:
            txt = p.fetch(q)
        except Exception as e:  # 공급자 오류가 체인을 끊지 않게
            log.warning("provider %s error: %s", p.name, e)
            txt = None
        ly = _parse_ok(txt, p.name)
        say(f"{p.name}: {'있음' if ly else '없음'}")
        if ly is None:
            continue
        if p.name not in ("local", "embedded"):       # 원격 결과만 캐시
            _cache_put(cache, q, txt, p.name)
        return Result(ly, "found", p.name)
    return None


def _gather_remote(q: Query, var, remote, timeout_s: float, say) -> tuple[list[dict], list[str]]:
    """③ 원격 공급자 동시 조회 → (점수 순 후보, 오류 목록)"""
    cands: list[dict] = []
    errors: list[str] = []
    for p in remote:
        p.deadline = time.monotonic() + max(1.0, timeout_s)
    ex = ThreadPoolExecutor(max_workers=len(remote))
    futs = {ex.submit(p.candidates, q, var): p for p in remote}
    done, pending = fwait(futs, timeout=max(1.0, timeout_s))
    for f in done:
        p = futs[f]
        try:
            cs = f.result()
            cands += cs
            say(f"{p.name}: 후보 {len(cs)}개")
        except NetError as e:
            errors.append(f"{p.name}: {e}")
            say(f"{p.name}: 연결 오류 {e}")
        except Exception as e:  # noqa
            errors.append(f"{p.name}: {e}")
            log.warning("provider %s: %s", p.name, e)
    for f in pending:
        errors.append(f"{futs[f].name}: 시간 초과")
        say(f"{futs[f].name}: 시간 초과 ({timeout_s:g}초)")
    ex.shutdown(wait=False, cancel_futures=True)
    cands.sort(key=lambda c: (-c["score"], 0 if c.get("synced") else 1))
    return cands, errors


def _save_beside(q: Query, text: str):
    """찾은 가사를 음악 옆 .lrc 로 (f18 L11, 기본 꺼짐) — 이미 있으면 덮지 않음"""
    try:
        p = Path(lrc_save_path(q.path))
        if p.parent.is_dir() and not p.exists():
            p.write_text(text.strip() + "\n", encoding="utf-8")
    except OSError as e:
        log.info("save beside: %s", e)


def resolve(q: Query, providers, cache: "LyricsCache | None", use_cache: bool = True):
    """(Lyrics | None) — 이전 호환"""
    return resolve_full(q, providers, cache, use_cache).lyrics
