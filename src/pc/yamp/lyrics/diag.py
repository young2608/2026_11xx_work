# -*- coding: utf-8 -*-
"""가사 진단 (vr0.1.0.011, f18 L8) — 지금 곡으로 전체 가사 검색을 한 단계씩 기록. Qt 비의존.
  도구 → 가사 진단… / python main.py --lyrics-test "곡.mp3"
  결과는 log/lyrics_diag_YYYYMMDD_HHMMSS.txt 로도 저장 (보내 주면 서버 쪽 변경도 확인 가능)
"""
import time
from datetime import datetime
from pathlib import Path

from .providers.base import Query
from .query import variants
from .resolve import build_providers, resolve_full, REASONS, SOURCE_NAMES
from ..core.version import title_label


def run(cfg, q: Query, log_dir: Path | None = None, cache=None) -> tuple[str, str | None]:
    """(보고서 글, 저장한 파일 경로 | None). 캐시·실패 기억은 무시하고 새로 찾음 (캐시는 바꾸지 않음)"""
    lines: list[str] = []
    t0 = time.monotonic()

    def say(s):
        lines.append(f"[{(time.monotonic() - t0) * 1000:6.0f}ms] {s}")
    head = [f"{title_label()} 가사 진단 · {datetime.now():%Y-%m-%d %H:%M:%S}",
            f"파일   : {q.path}",
            f"태그   : 제목 '{q.title}' · 가수 '{q.artist}' · 앨범 '{q.album}' · 길이 {q.duration:.0f}초",
            "공급자 : " + ", ".join(k for k in ("lyrics_local", "lyrics_embedded", "lyrics_alsong", "lyrics_lrclib",
                                                "lyrics_netease") if cfg[k]),
            f"설정   : 제한 {cfg['lyrics_timeout_s']}초 · 최저 점수 {cfg['lyrics_min_score']} · "
            f"알송 encData {'내장' if not (cfg['alsong_enc_data'] or '').strip() else cfg['alsong_enc_data'][:8] + '…'}",
            "검색어 : " + " | ".join(f"{t} / {a}" for t, a in variants(q.title, q.artist)), ""]
    provs = build_providers(cfg, say)
    for p in [p for p in provs if not getattr(p, "remote", False)]:      # 로컬 · 내장 (있어도 원격 검색은 계속)
        try:
            txt = p.fetch(q)
        except Exception as e:  # noqa
            say(f"{p.name}: 오류 {e}")
            txt = None
        say(f"{SOURCE_NAMES.get(p.name, p.name)}: {'있음 (%d줄)' % len(txt.splitlines()) if txt else '없음'}")
    res = resolve_full(q, [p for p in provs if getattr(p, "remote", False)], None, use_cache=False, notfound=None,
                       min_score=int(cfg["lyrics_min_score"] or 0), timeout_s=float(cfg["lyrics_timeout_s"] or 6),
                       log_fn=say)
    tail = ["", "---- 후보 (점수순, 상위 8) ----"]
    for c in res.candidates[:8]:
        tail.append(f"{c['score']:4d}점  {SOURCE_NAMES.get(c['source'], c['source'])}  {c.get('artist', '')} - "
                    f"{c.get('title', '')}  ({c.get('album', '')}) {'싱크' if c.get('synced') else '일반'}"
                    + (f" {c['duration']:.0f}초" if c.get('duration') else ""))
    if not res.candidates:
        tail.append("(없음)")
    if res.errors:
        tail += ["", "---- 오류 ----"] + res.errors
    tail += ["", "결과: " + (f"찾음 — {SOURCE_NAMES.get(res.source, res.source)} {res.score}점" if res.lyrics is not None
                            else REASONS.get(res.reason, res.reason))]
    text = "\n".join(head + lines + tail) + "\n"
    saved = None
    if log_dir:
        try:
            Path(log_dir).mkdir(parents=True, exist_ok=True)
            p = Path(log_dir) / f"lyrics_diag_{datetime.now():%Y%m%d_%H%M%S}.txt"
            p.write_text(text, encoding="utf-8")
            saved = str(p)
        except OSError:
            pass
    return text, saved
