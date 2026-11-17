# -*- coding: utf-8 -*-
"""
재생 기록 판정 (Qt·DB 비의존). Android AppViewModel 의 PlayRecorder 와 같은 규칙.

- 들은 시간: 재생 중일 때 위치 변화만 누적 (2초 넘게 건너뛰면 탐색으로 보고 제외)
- completed : 곡 길이의 50% 이상 또는 4분 이상 들음
- skipped   : 30초 미만 듣고 다른 곡으로 넘어감 (끝까지 재생돼 넘어간 경우 제외)
- session   : 마지막 기록 후 30분 넘게 쉬면 새 세션
"""
import time

COMPLETE_RATIO = 0.5
COMPLETE_MS = 4 * 60 * 1000
SKIP_MS = 30 * 1000
SESSION_GAP_S = 30 * 60


class PlayRecorder:
    def __init__(self):
        self.key = None
        self.duration_ms = 0
        self.started_at = 0
        self.listened = 0
        self._last_pos = None
        self.session_id = 0
        self._last_end = 0

    def start(self, key, duration_ms=0, now=None):
        now = int(now or time.time())
        if not self.session_id or now - self._last_end > SESSION_GAP_S:
            self.session_id = now
        self.key, self.duration_ms, self.started_at = key, int(duration_ms or 0), now
        self.listened = 0
        self._last_pos = None

    def set_duration(self, ms):
        if ms and ms > 0:
            self.duration_ms = int(ms)

    def tick(self, pos_ms, playing: bool):
        if self.key is None:
            return
        if playing and self._last_pos is not None:
            d = pos_ms - self._last_pos
            if 0 < d <= 2000:
                self.listened += d
        self._last_pos = pos_ms

    def finish(self, ended_naturally=False, now=None):
        """기록 dict 반환 (들은 시간 0 이면 None) 후 초기화"""
        if self.key is None:
            return None
        now = int(now or time.time())
        lst = self.listened
        rec = None
        if lst > 0:
            completed = lst >= COMPLETE_MS or (self.duration_ms > 0 and lst >= self.duration_ms * COMPLETE_RATIO) \
                or (ended_naturally and lst >= SKIP_MS)
            skipped = (not ended_naturally) and lst < SKIP_MS
            rec = dict(key=self.key, started_at=self.started_at, listened_ms=lst, duration_ms=self.duration_ms,
                       completed=bool(completed), skipped=bool(skipped), session_id=self.session_id)
            self._last_end = now
        self.key = None
        return rec
