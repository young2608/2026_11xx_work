"""Controller 기능 묶음 — 대기열 · 믹스/라디오 · 좋아요 · 별점

Controller(QObject) 가 이 믹스인을 상속. 상태·시그널은 Controller.__init__ 에 있음."""
import logging
import os
import random
import time


from ..data.playlist import Track
from ..core.keys import track_key
from ..domain import recommend as R

log = logging.getLogger("yamp.ctrl")


class QueueMixin:
    # ---- 대기열 (B5)
    def _ensure_in_playlist(self, t: Track) -> int:
        for i, x in enumerate(self.pl.items):
            if x.uid == t.uid:
                return i
        at = self.pl.current + 1 if self.pl.current >= 0 else len(self.pl)
        self.pl.items.insert(at, Track(t.path, t.title, t.artist, t.album, t.duration, t.tagged,
                                       t.cue_no, t.start_ms, t.end_ms, t.cue_path))
        self.pl._order = []
        self.playlistChanged.emit()
        return at

    def _tracks_from(self, items) -> list[Track]:
        out = []
        for it in items:
            if isinstance(it, Track):
                out.append(it)
            elif isinstance(it, int) and 0 <= it < len(self.pl):
                out.append(self.pl.items[it])
            elif isinstance(it, str):            # 라이브러리 key 또는 경로
                d = self.library.track(it)
                if d and os.path.exists(d["path"]):
                    out.append(Track(d["path"], d["title"] or "", d["artist"] or "", d["album"] or "",
                                     (d["duration_ms"] or 0) / 1000, True, int(d.get("cue_no") or 0),
                                     int(d.get("start_ms") or 0), int(d.get("end_ms") if d.get("end_ms") is not None else -1),
                                     d.get("cue_path") or ""))
                elif os.path.exists(it):
                    out.append(Track(it))
        return out

    def play_next(self, items):
        ts = self._tracks_from(items)
        self.queue[0:0] = ts
        self.queueChanged.emit()
        self.message.emit(f"다음에 재생: {len(ts)}곡")

    def enqueue(self, items):
        ts = self._tracks_from(items)
        self.queue.extend(ts)
        self.queueChanged.emit()
        self.message.emit(f"대기열에 추가: {len(ts)}곡")

    def clear_queue(self):
        self.queue.clear()
        self.queueChanged.emit()

    def remove_queue(self, i):
        if 0 <= i < len(self.queue):
            del self.queue[i]
            self.queueChanged.emit()

    def play_mix(self, keys, title=""):
        """믹스/라디오 재생: 첫 곡 바로, 나머지는 대기열 (기존 대기열 대체)"""
        ts = self._tracks_from(keys)
        if not ts:
            self.message.emit("재생할 곡 없음 (파일이 옮겨졌는지 확인)")
            return
        self.queue = ts[1:]
        self.queueChanged.emit()
        self.play_index(self._ensure_in_playlist(ts[0]))
        self.message.emit(f"{title or '믹스'} 재생 ({len(ts)}곡)")
        log.info("mix %s %d", title, len(ts))

    def radio(self, item=None):
        """B3: 이 곡으로 라디오 (item: 목록 인덱스 / key / None=현재 곡)"""
        t = self._tracks_from([item])[0] if item is not None and self._tracks_from([item]) else self.current_track()
        if not t:
            return
        seed = self._lib_upsert(t) if not self.library.has(t.uid) else track_key(t.uid)
        now = int(time.time())
        keys = R.similar(self.library.stats(now), seed, self.library.co_pairs(),
                         self.library.recent_keys(now), rng=random.Random())
        if len(keys) <= 1:
            self.message.emit("비슷한 곡이 없습니다 (라이브러리 폴더를 추가해 보세요)")
            return
        if self.current_track() and track_key(self.current_track().uid) == seed:
            self.queue = self._tracks_from(keys[1:])
            self.queueChanged.emit()
            self.message.emit(f"라디오: 비슷한 곡 {len(self.queue)}곡을 대기열에")
        else:
            self.play_mix(keys, "라디오")

    # ---- 좋아요 · 별점 (B1)
    def current_key(self):
        t = self.current_track()
        return track_key(t.uid) if t else None

    def toggle_like(self, item=None):
        t = self._tracks_from([item])[0] if item is not None and self._tracks_from([item]) else self.current_track()
        if not t:
            return
        k = track_key(t.uid)
        if not self.library.has(t.uid):
            self._lib_upsert(t)
        v = not self.library.liked(k)
        self.library.set_liked(k, v)
        if k == self.current_key():
            self.likedChanged.emit(v)
        self.message.emit("좋아요 ♥" if v else "좋아요 취소")

    def set_rating(self, item, rating: int):
        t = self._tracks_from([item])
        if t:
            k = track_key(t[0].uid)
            if not self.library.has(t[0].uid):
                self._lib_upsert(t[0])
            self.library.set_rating(k, rating)
            self.message.emit(f"별점 {'★' * rating}{'☆' * (5 - rating)}")
