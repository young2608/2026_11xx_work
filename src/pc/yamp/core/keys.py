# -*- coding: utf-8 -*-
"""곡 키 (vr0.1.0.019 R2) — 라이브러리 DB · 가사 캐시 · 곡별 싱크 보정이 함께 쓰는 '경로 → 12자리 키'.

전에는 lyrics/service.py 에 있어 data/library.py(데이터 층)가 가사 모듈을 불러야 했음 → 의존 없는 core 로.
Android LyricsRepo.keyOf 와 같은 규칙: 경로 소문자 UTF-8 MD5 앞 12자리.
"""
import functools
import hashlib


@functools.lru_cache(maxsize=4096)
def cache_key(path: str) -> str:
    """v018 (f33 P11): 같은 경로는 다시 계산하지 않음 (재생 중 50ms 틱 · 라이브러리 재스캔에서 반복 호출)"""
    return hashlib.md5(path.lower().encode("utf-8")).hexdigest()[:12]


def track_key(path_or_uid: str) -> str:
    """라이브러리 키 (CUE 트랙은 'path|cue:n' 을 넘김)"""
    return cache_key(path_or_uid)
