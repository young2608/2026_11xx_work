# -*- coding: utf-8 -*-
"""
추천 엔진 (Qt·DB 비의존 — 순수 함수). Android domain/Recommend.kt 와 **같은 규칙**,
공용 테스트 벡터: 00__build/src/testdata/recommend_cases.txt (양쪽 테스트가 같은 파일을 읽음)

모든 데이터는 기기 안의 재생 기록에서 나옴 (외부 서버·AI 없음).

선호 점수   score = 3·liked + rating + ln(1+completed) − 1.5·ln(1+skipped)
믹스
  favorites   좋아요 또는 최근 30일 완청 곡 — score + 2·ln(1+completed_recent) 순
  rediscover  완청 3회 이상 & 30일 이상 안 들은 곡 — score 순
  daily       오늘의 믹스 = 선호(3일 안 들은 곡) 50% + 다시 발견 30% + 새 곡(좋아하는 가수·장르, 미청취) 20%
  similar     기준 곡과 비슷한 곡 (같은 가수 3, 같은 앨범 2, 같은 장르 2, 같은 폴더 1, 같이 들은 곡 최대 3)
  mood        상황 믹스 (사용자 태그 우선, 없으면 장르 매핑)
정렬 동점은 key 오름차순 (플랫폼 간 결과 일치). rng 를 주면 그룹 안에서 섞음 (테스트는 rng=None).
"""
from dataclasses import dataclass, field
import math

DAY = 86400
N_DEFAULT = 25

MOODS = {
    "study": ("공부·집중", ("classical", "ambient", "piano", "lo-fi", "lofi", "jazz", "instrumental", "ost")),
    "workout": ("운동", ("dance", "edm", "electronic", "hip hop", "hip-hop", "rap", "rock", "k-pop", "kpop")),
    "drive": ("드라이브", ("pop", "rock", "k-pop", "kpop", "r&b", "indie")),
    "sleep": ("수면·휴식", ("classical", "ambient", "jazz", "ballad", "발라드", "new age", "piano")),
}
MIX_TITLES = {"daily": "오늘의 믹스", "favorites": "자주 듣는 곡 · 좋아요", "rediscover": "다시 발견",
              "recent": "최근 추가"}


@dataclass
class TrackStat:
    key: str
    artist: str = ""
    album: str = ""
    genre: str = ""
    folder: str = ""
    liked: bool = False
    rating: int = 0
    completed: int = 0
    skipped: int = 0
    last_played: int = 0          # epoch 초, 0 = 안 들음
    added_at: int = 0
    completed_recent: int = 0     # 최근 30일 완청 수
    tags: tuple = field(default_factory=tuple)


def score(t: TrackStat) -> float:
    return 3.0 * (1 if t.liked else 0) + t.rating + math.log(1 + t.completed) - 1.5 * math.log(1 + t.skipped)


def _days_since(t: TrackStat, now: int) -> float:
    return (now - t.last_played) / DAY if t.last_played > 0 else 1e9


def _norm(s: str) -> str:
    return (s or "").strip().lower()


def favorites(tracks, n=N_DEFAULT):
    pool = [t for t in tracks if t.liked or t.completed_recent > 0]
    pool.sort(key=lambda t: (-(score(t) + 2.0 * math.log(1 + t.completed_recent)), t.key))
    return [t.key for t in pool[:n]]


def rediscover(tracks, now, n=N_DEFAULT):
    pool = [t for t in tracks if t.completed >= 3 and _days_since(t, now) >= 30]
    pool.sort(key=lambda t: (-score(t), t.key))
    return [t.key for t in pool[:n]]


def recent_added(tracks, n=N_DEFAULT):
    pool = sorted(tracks, key=lambda t: (-t.added_at, t.key))
    return [t.key for t in pool[:n]]


def top_artists_genres(tracks, k=5):
    sa, sg = {}, {}
    for t in tracks:
        s = score(t)
        if s <= 0:
            continue
        if _norm(t.artist):
            sa[_norm(t.artist)] = sa.get(_norm(t.artist), 0.0) + s
        if _norm(t.genre):
            sg[_norm(t.genre)] = sg.get(_norm(t.genre), 0.0) + s
    ta = [a for a, _ in sorted(sa.items(), key=lambda x: (-x[1], x[0]))[:k]]
    tg = [g for g, _ in sorted(sg.items(), key=lambda x: (-x[1], x[0]))[:k]]
    return ta, tg


def diversify(keys, artist_of, max_run=2):
    """같은 가수가 max_run 곡 넘게 연속되지 않게 (가능한 범위에서 뒤로 미룸, 안정적)"""
    out, pending = [], list(keys)
    while pending:
        picked = None
        for i, k in enumerate(pending):
            a = _norm(artist_of(k))
            run = 0
            for x in reversed(out):
                if a and _norm(artist_of(x)) == a:
                    run += 1
                else:
                    break
            if run < max_run:
                picked = i
                break
        if picked is None:
            picked = 0
        out.append(pending.pop(picked))
    return out


def daily(tracks, now, n=N_DEFAULT, rng=None):
    by = {t.key: t for t in tracks}
    fav = [t for t in tracks if score(t) > 0 and _days_since(t, now) >= 3]
    fav.sort(key=lambda t: (-score(t), t.key))
    red = [by[k] for k in rediscover(tracks, now, n=10 ** 9)]
    ta, tg = top_artists_genres(tracks)
    new = [t for t in tracks if t.completed == 0 and t.skipped == 0
           and (_norm(t.artist) in ta or _norm(t.genre) in tg)]
    new.sort(key=lambda t: (-t.added_at, t.key))
    if rng is not None:
        for g in (fav, red, new):
            rng.shuffle(g)
    quota = [("fav", fav, round(n * 0.5)), ("red", red, round(n * 0.3)), ("new", new, n)]
    out, seen = [], set()
    for _, group, q in quota:
        cnt = 0
        for t in group:
            if len(out) >= n or cnt >= q:
                break
            if t.key not in seen:
                out.append(t.key)
                seen.add(t.key)
                cnt += 1
    # 모자라면 선호 → 나머지 점수 순으로 채움
    rest = sorted(tracks, key=lambda t: (-score(t), t.key))
    for t in fav + rest:
        if len(out) >= n:
            break
        if t.key not in seen:
            out.append(t.key)
            seen.add(t.key)
    return diversify(out, lambda k: by[k].artist)


def similarity(seed: TrackStat, t: TrackStat, co: dict) -> int:
    s = 0
    if _norm(seed.artist) and _norm(seed.artist) == _norm(t.artist):
        s += 3
    if _norm(seed.album) and _norm(seed.album) == _norm(t.album) and _norm(seed.artist) == _norm(t.artist):
        s += 2
    if _norm(seed.genre) and _norm(seed.genre) == _norm(t.genre):
        s += 2
    if seed.folder and seed.folder == t.folder:
        s += 1
    c = co.get((seed.key, t.key), 0) + co.get((t.key, seed.key), 0)
    s += min(3, c)
    return s


def similar(tracks, seed_key, co=None, recent=(), n=N_DEFAULT, rng=None):
    """co: {(a, b): 같이 들은 횟수}, recent: 최근 1시간 재생 key (제외)"""
    co = co or {}
    by = {t.key: t for t in tracks}
    seed = by.get(seed_key)
    if seed is None:
        return []
    recent = set(recent)
    cand = []
    for t in tracks:
        if t.key == seed_key or t.key in recent:
            continue
        s = similarity(seed, t, co)
        if s > 0:
            cand.append((s, score(t), t.key))
    cand.sort(key=lambda x: (-x[0], -x[1], x[2]))
    top = cand[:50]
    if rng is None:
        keys = [k for _, _, k in top[:n]]
    else:                                   # 유사도 가중 무작위
        pool = list(top)
        keys = []
        while pool and len(keys) < n:
            w = [max(0.1, s) for s, _, _ in pool]
            i = rng.choices(range(len(pool)), weights=w)[0]
            keys.append(pool.pop(i)[2])
    return [seed_key] + diversify(keys, lambda k: by[k].artist)


def mood(tracks, name, n=N_DEFAULT, rng=None):
    label, genres = MOODS.get(name, (name, ()))
    tagged = [t for t in tracks if name in t.tags or label in t.tags]
    if tagged:
        pool = tagged
    else:
        pool = [t for t in tracks if any(g in _norm(t.genre) for g in genres)]
    pool = sorted(pool, key=lambda t: (-score(t), t.key))
    if rng is not None:
        rng.shuffle(pool)
    by = {t.key: t for t in tracks}
    return diversify([t.key for t in pool[:n]], lambda k: by[k].artist)


def build_home(tracks, now, co=None, last_key=None, recent=(), rng=None):
    """추천 홈 카드 목록 [(id, 제목, [keys])] — 비어 있는 카드는 뺌"""
    cards = [("daily", MIX_TITLES["daily"], daily(tracks, now, rng=rng)),
             ("favorites", MIX_TITLES["favorites"], favorites(tracks)),
             ("rediscover", MIX_TITLES["rediscover"], rediscover(tracks, now)),
             ("recent", MIX_TITLES["recent"], recent_added(tracks))]
    if last_key:
        by = {t.key: t for t in tracks}
        if last_key in by:
            cards.insert(1, ("similar", "비슷한 곡 라디오 (마지막 재생 곡)", similar(tracks, last_key, co, recent, rng=rng)))
    for m, (label, _) in MOODS.items():
        cards.append((f"mood:{m}", f"상황 믹스 · {label}", mood(tracks, m, rng=rng)))
    return [c for c in cards if c[2]]


# ---------------------------------------------------------------- ReplayGain (C1)
def parse_gain(s) -> float | None:
    """'-6.52 dB' / '+1.2' → dB (float). 잘못되면 None"""
    if s is None:
        return None
    txt = str(s).strip().lower().replace("db", "").replace(",", ".").replace("−", "-").strip()
    try:
        return float(txt)
    except ValueError:
        return None


def gain_factor(gain_db, peak=None, preamp_db=0.0) -> float:
    """선형 배율 (1.0 = 그대로). peak 가 있으면 클리핑 방지 (배율 ≤ 1/peak). 범위 0.05 ~ 4.0"""
    if gain_db is None:
        return 1.0
    f = 10 ** ((gain_db + preamp_db) / 20.0)
    if peak and peak > 0:
        f = min(f, 1.0 / peak)
    return max(0.05, min(4.0, f))
