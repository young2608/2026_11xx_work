# -*- coding: utf-8 -*-
"""긴 파일 이어 듣기 (vr0.1.0.010, V2) — Qt 비의존. Android domain/Resume.kt 와 같은 규칙.
  - 30분(LONG_FILE_S) 넘는 파일만 기억
  - 처음 10초 안 · 끝 30초 안에서 멈추면(=거의 안 들었거나 다 들음) 기억하지 않고 지움
  - 다시 열면 기억한 위치 3초 앞에서 시작 (말이 끊기지 않게)
  - 최근 RESUME_MAX 개만 (오래된 것부터 지움) — 사전 순서 = 넣은 순서 (JSON 에도 그대로 저장)
"""
from ..data.formats import LONG_FILE_S

RESUME_MAX = 200
MIN_MS = 10_000
TAIL_MS = 30_000
BACK_MS = 3_000


def is_long(dur_ms: int) -> bool:
    return dur_ms >= LONG_FILE_S * 1000


def remember(m: dict, uid: str, pos_ms: int, dur_ms: int, ended: bool = False, maxn: int = RESUME_MAX) -> dict:
    """위치 기록 (m 을 바꾸고 돌려줌)"""
    if not uid or not is_long(dur_ms):
        return m
    m.pop(uid, None)
    if not ended and MIN_MS < pos_ms < dur_ms - TAIL_MS:
        m[uid] = int(pos_ms)
        while len(m) > maxn:
            m.pop(next(iter(m)))
    return m


def start_at(m: dict, uid: str, dur_ms: int) -> int:
    """이어 듣기 시작 위치 (ms). 없으면 0"""
    if not is_long(dur_ms):
        return 0
    p = int(m.get(uid, 0) or 0)
    return max(0, p - BACK_MS) if p > 0 else 0
