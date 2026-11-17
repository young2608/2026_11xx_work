# -*- coding: utf-8 -*-
"""
스마트 재생목록 (W7, vr0.1.0.009) — 라이브러리 기록으로 자동으로 만들어지는 목록. Qt·DB 비의존 (테스트 대상)
입력: domain/recommend.TrackStat 목록 (library.stats()) / 출력: 키 목록
"""
DAY = 86400
LIMIT = 100

RULES: dict[str, tuple[str, str]] = {
    "liked":        ("좋아요 곡", "좋아요 표시한 곡 — 최근 들은 순"),
    "liked_rest":   ("좋아요 · 한동안 안 들은 곡", "좋아요인데 30일 넘게 안 들은 곡"),
    "top":          ("많이 들은 100곡", "끝까지 들은 횟수가 많은 순"),
    "recent_added": ("최근 추가 100곡", "라이브러리에 새로 들어온 순"),
    "never":        ("아직 안 들은 곡", "한 번도 재생 기록이 없는 곡 — 추가된 순"),
    "rated4":       ("별점 4개 이상", "별점 4~5 인 곡"),
    "skipped":      ("자주 건너뛴 곡", "30초 안에 넘긴 횟수가 많은 곡 (정리용)"),
}


def build(rule: str, stats, now: int, limit: int = LIMIT) -> list[str]:
    s = list(stats)
    if rule == "liked":
        r = sorted((t for t in s if t.liked), key=lambda t: (-t.last_played, t.key))
    elif rule == "liked_rest":
        r = sorted((t for t in s if t.liked and now - t.last_played > 30 * DAY), key=lambda t: (t.last_played, t.key))
    elif rule == "top":
        r = sorted((t for t in s if t.completed > 0), key=lambda t: (-t.completed, -t.last_played, t.key))
    elif rule == "recent_added":
        r = sorted(s, key=lambda t: (-t.added_at, t.key))
    elif rule == "never":
        r = sorted((t for t in s if t.completed == 0 and t.last_played == 0), key=lambda t: (-t.added_at, t.key))
    elif rule == "rated4":
        r = sorted((t for t in s if t.rating >= 4), key=lambda t: (-t.rating, -t.completed, t.key))
    elif rule == "skipped":
        r = sorted((t for t in s if t.skipped >= 2), key=lambda t: (-t.skipped, t.key))
    else:
        return []
    return [t.key for t in r[:limit]]
