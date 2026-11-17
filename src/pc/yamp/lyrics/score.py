# -*- coding: utf-8 -*-
"""가사 후보 점수 (vr0.1.0.011, f18 L3) — Qt 비의존. Android lyrics/Score.kt 와 같은 식.
공용 테스트: testdata/lyrics_score_cases.txt

  제목  : 같음 45 · 포함 35 · 아니면 Dice 유사도 × 30 (0.5 올림 반올림)          — 검색어 제목 이름들 중 최고
  가수  : 같음 30 · 포함 22 · 아니면 Dice × 18   (검색 가수가 비면 15)  — 가수 이름들 중 최고
  앨범  : 둘 다 있고 같음 10
  싱크  : 타임스탬프 1개 이상 +10, 10개 이상 +5
  길이  : 후보 길이 있음 → 차 ≤ 3초 +10, > 15초 −40
          후보 길이 없음 + 싱크 → 마지막 타임스탬프 > 곡 길이 + 10초 −40
  자동 적용 기준 MIN_SCORE (config lyrics_min_score)
"""
import math
import re
from collections import Counter

from .query import artist_names, title_names

MIN_SCORE = 55
_TS = re.compile(r"\[(\d{1,3}):(\d{1,2})(?:[.:](\d{1,3}))?\]")
_NORM = re.compile(r"[\s\-_.,/\\()\[\]{}'\"`!?:;~^·&*+=|<>@#$%]+")


def norm(s: str) -> str:
    return _NORM.sub("", (s or "").lower())


def dice(a: str, b: str) -> float:
    a, b = norm(a), norm(b)
    if not a or not b:
        return 0.0
    if len(a) < 2 or len(b) < 2:
        return 1.0 if a == b else 0.0
    x = Counter(a[i:i + 2] for i in range(len(a) - 1))
    y = Counter(b[i:i + 2] for i in range(len(b) - 1))
    inter = sum((x & y).values())
    return 2.0 * inter / ((len(a) - 1) + (len(b) - 1))


def _name_score(cands: list[str], value: str, eq: int, contains: int, sim: int) -> int:
    v = norm(value)
    best = 0
    for c in cands:
        n = norm(c)
        if not n or not v:
            continue
        if n == v:
            s = eq
        elif (len(n) >= 2 and n in v) or (len(v) >= 2 and v in n):
            s = contains
        else:
            s = int(math.floor(dice(n, v) * sim + 0.5))      # 반올림 (Kotlin Math.round 와 같게)
        best = max(best, s)
    return best


def stamps(lyric: str) -> list[int]:
    out = []
    for m in _TS.finditer(lyric or ""):
        fr = m.group(3) or "0"
        out.append(int(m.group(1)) * 60000 + int(m.group(2)) * 1000 + int(fr.ljust(3, "0")[:3]))
    return out


def score(q_title: str, q_artist: str, q_album: str, q_dur_s: float, c_title: str, c_artist: str,
          c_album: str, c_lyric: str, c_dur_s: float = 0.0) -> int:
    s = _name_score(title_names(q_title) or [q_title], c_title, 45, 35, 30)
    names = artist_names(q_artist)
    s += _name_score(names, c_artist, 30, 22, 18) if names else 15
    if q_album and c_album and norm(q_album) == norm(c_album):
        s += 10
    ts = stamps(c_lyric)
    if ts:
        s += 10 + (5 if len(ts) >= 10 else 0)
    if q_dur_s and q_dur_s > 0:
        if c_dur_s and c_dur_s > 0:
            d = abs(c_dur_s - q_dur_s)
            if d <= 3:
                s += 10
            elif d > 15:
                s -= 40
        elif ts and max(ts) / 1000 > q_dur_s + 10:
            s -= 40
    return int(s)
