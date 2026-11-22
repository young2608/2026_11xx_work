"""재생 목록 (Playlist: 편집 · 다음/이전 · 셔플) — Qt 비의존.

vr0.1.0.019 (R1) 기능별로 나눔 — 이전처럼 `from .playlist import …` 로도 모두 가져갈 수 있게 다시 내보냄:
  track.py        Track · is_audio · fmt_time · CUE_EXT · AUDIO_EXT
  scan.py         폴더 → 곡 (scan_tracks · cue_tracks · sort_tracks · folder_summary)
  playlist_io.py  재생목록 파일 (M3U/M3U8 · PLS · XSPF · WPL 읽기, M3U 쓰기)
"""
from pathlib import Path
import os
import random

from .formats import AUDIO_EXT, PLAYLIST_EXT  # noqa: F401  (다른 모듈이 여기서 가져감)
from .track import CUE_EXT, Track, fmt_time, is_audio  # noqa: F401
from .scan import cue_tracks, scan_dir, scan_tracks, sort_tracks  # noqa: F401
from .playlist_io import (load_m3u, load_pls, load_playlist, load_wpl, load_xspf, save_m3u,  # noqa: F401
                          _read_text, _resolve, _xml_paths)


class Playlist:
    def __init__(self):
        self.items: list[Track] = []
        self.current: int = -1
        self._order: list[int] = []   # 셔플 순서
        self._opos: int = -1

    def __len__(self):
        return len(self.items)

    # ---- 편집 ----
    def add_paths(self, paths, files_first: bool = False) -> int:
        """파일/폴더 경로 추가. 추가된 개수 반환.
        files_first (v018, f33 P9): 음악 확장자면 폴더인지 확인(디스크 조회)을 건너뜀 — 세션 복원처럼
          방금 존재를 확인한 파일 목록일 때 (만 곡 목록이면 시작 때 디스크 조회 만 번 ↓)"""
        n0 = len(self.items)
        for p in paths:
            p = str(p)
            if files_first and is_audio(p):
                self.items.append(Track(os.path.abspath(p)))
            elif os.path.isdir(p):
                self.items.extend(scan_tracks(p))
            elif is_audio(p):
                self.items.append(Track(os.path.abspath(p)))
            elif Path(p).suffix.lower() == CUE_EXT:
                self.items.extend(cue_tracks(p))
            elif Path(p).suffix.lower() in PLAYLIST_EXT:
                seen_cue = set()
                for f in load_playlist(p):
                    if f.lower().endswith(CUE_EXT):
                        if f not in seen_cue:
                            seen_cue.add(f)
                            self.items.extend(cue_tracks(f))
                    else:
                        self.items.append(Track(f))
        self._order = []
        return len(self.items) - n0

    def remove(self, indices):
        """v032 (f60 P6): 한 번에 새 목록으로 (전: 뒤에서부터 한 곡씩 del — 2만 곡 중 5천 곡 빼기 = 목록 복사 5천 번)"""
        cur_track = self.items[self.current] if 0 <= self.current < len(self.items) else None
        drop = {i for i in indices if 0 <= i < len(self.items)}
        if drop:
            self.items[:] = [t for k, t in enumerate(self.items) if k not in drop]
        self.current = self._index_of(cur_track)
        self._order = []

    def move(self, i: int, j: int):
        if not (0 <= i < len(self.items) and 0 <= j < len(self.items)) or i == j:
            return
        cur_track = self.items[self.current] if 0 <= self.current < len(self.items) else None
        t = self.items.pop(i)
        self.items.insert(j, t)
        self.current = self._index_of(cur_track)
        self._order = []

    def clear(self):
        self.items.clear()
        self.current = -1
        self._order = []

    def _index_of(self, t):
        if t is None:
            return -1
        return next((k for k, x in enumerate(self.items) if x is t), -1)

    # ---- 다음/이전 ----
    def _ensure_order(self):
        if len(self._order) != len(self.items):
            self._order = list(range(len(self.items)))
            random.shuffle(self._order)
            if self.current in self._order:  # 현재 곡을 맨 앞으로
                self._order.remove(self.current)
                self._order.insert(0, self.current)
            self._opos = 0 if self.current >= 0 else -1

    def next_index(self, repeat: str = "all", shuffle: bool = False, manual: bool = False):
        n = len(self.items)
        if n == 0:
            return None
        if repeat == "one" and not manual and self.current >= 0:
            return self.current
        if shuffle:
            self._ensure_order()
            if self.current in self._order:
                self._opos = self._order.index(self.current)
            p = self._opos + 1
            if p >= n:
                if repeat == "off" and not manual:
                    return None
                random.shuffle(self._order)
                p = 0
            self._opos = p
            return self._order[p]
        i = self.current + 1
        if i >= n:
            return 0 if (repeat != "off" or manual) else None
        return i

    def prev_index(self, shuffle: bool = False):
        n = len(self.items)
        if n == 0:
            return None
        if shuffle and self._order and self.current in self._order:
            p = self._order.index(self.current) - 1
            self._opos = max(p, 0)
            return self._order[p % n]
        return (self.current - 1) % n if self.current >= 0 else 0
