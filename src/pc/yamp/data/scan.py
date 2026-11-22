# -*- coding: utf-8 -*-
"""폴더 → 곡 목록 · CUE 펼치기 · 정렬 · 형식별 개수 (vr0.1.0.019 R1 — data/playlist.py · ui/folder_view.py 에서 나눔)

Qt 비의존 (테스트 대상). 폴더 재생(F2) · 라이브러리 스캔 · 폴더 탭 요약이 함께 씀.
"""
import os
from collections import Counter
from pathlib import Path

from .track import AUDIO_EXT, CUE_EXT, Track, is_audio, path_name, path_stem


def scan_dir(root: str, recursive: bool = True) -> list[str]:
    out = []
    for dp, dns, fns in os.walk(root):
        dns.sort(key=str.lower)
        for f in sorted(fns, key=str.lower):
            if is_audio(f):
                out.append(os.path.join(dp, f))
        if not recursive:
            break
    return out


def cue_tracks(cue_path: str) -> list[Track]:
    """CUE → 트랙 목록 (가리키는 오디오 파일이 있는 트랙만)"""
    from .cue import load
    try:
        cts = load(cue_path)
    except (OSError, ValueError):
        return []
    out = []
    for c in cts:
        if not os.path.exists(c.file) or not is_audio(c.file):
            continue
        dur = (c.end_ms - c.start_ms) / 1000 if c.end_ms > 0 else 0.0
        out.append(Track(c.file, c.title, c.performer, c.album, dur, True, c.number, c.start_ms, c.end_ms,
                         os.path.abspath(cue_path), dict(c.rg) or None))
    return out


def scan_tracks(root: str, recursive: bool = True, counts=None) -> list[Track]:
    """폴더 → 트랙. CUE 가 있으면 그 CUE 가 가리키는 파일은 트랙별로 펼치고 원본 파일은 빼고 넣음
    counts (v018, f33 P4): Counter 를 넘기면 같은 순회에서 형식별 파일 수도 셈 (MP3 · FLAC … · CUE)
      → 폴더 탭이 요약을 위해 폴더를 한 번 더 돌지 않게"""
    out: list[Track] = []
    for dp, dns, fns in os.walk(root):
        dns.sort(key=str.lower)
        files = sorted(fns, key=str.lower)
        covered = set()
        cue_items = []
        for f in files:
            if f.lower().endswith(CUE_EXT):
                if counts is not None:
                    counts["CUE"] += 1
                ts = cue_tracks(os.path.join(dp, f))
                if ts:
                    cue_items.extend(ts)
                    covered.update(os.path.normcase(os.path.abspath(t.path)) for t in ts)
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext not in AUDIO_EXT:
                continue
            if counts is not None:
                counts[ext[1:].upper()] += 1
            full = os.path.join(dp, f)
            # v018 (f33 P5): CUE 가 없는 폴더(대부분)는 경로 정규화(abspath · normcase) 생략
            if not covered or os.path.normcase(os.path.abspath(full)) not in covered:
                out.append(Track(full))
        out.extend(cue_items)
        if not recursive:
            break
    return out


def sort_tracks(tracks: list[Track], how: str = "name") -> list[Track]:
    """폴더 재생 정렬: name(파일명·CUE 순서) / title / added(파일 수정 시각 최근 순)"""
    if how == "title":
        return sorted(tracks, key=lambda t: ((t.title or path_stem(t.path)).lower(), t.cue_no))     # v032 (f60 P5)
    if how == "added":
        def mt(t):
            try:
                return -os.path.getmtime(t.path)
            except OSError:
                return 0
        return sorted(tracks, key=lambda t: (mt(t), t.path.lower(), t.cue_no))
    return sorted(tracks, key=lambda t: (os.path.dirname(t.path).lower(), path_name(t.path).lower(), t.cue_no))   # v032 (f60 P5)


def folder_summary(path: str, recursive: bool = False, limit: int = 5000) -> tuple[int, Counter]:
    """(곡 수, 형식별 개수) — CUE 는 'CUE' 로 셈"""
    n, c = 0, Counter()
    try:
        for dp, dns, fns in os.walk(path):
            for f in fns:
                ext = Path(f).suffix.lower()
                if is_audio(f):
                    n += 1
                    c[ext[1:].upper()] += 1
                elif ext == CUE_EXT:
                    c["CUE"] += 1
                if n >= limit:
                    return n, c
            if not recursive:
                break
    except OSError:
        pass
    return n, c


def summary_text(c: Counter) -> str:
    return " · ".join(f"{k} {v}" for k, v in c.most_common(6))
