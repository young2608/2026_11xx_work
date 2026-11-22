"""Controller 기능 묶음 — 라이브러리: 재생 기록 · 추천 홈 · 폴더 스캔 · 태그 편집 · 폴더 재생

Controller(QObject) 가 이 믹스인을 상속. 상태·시그널은 Controller.__init__ 에 있음."""
import logging
import os
import random
import time


from ..data.playlist import Track, scan_tracks, sort_tracks
from ..data.tags import read_tags, write_tags
from ..domain import recommend as R
from .jobs import Job

log = logging.getLogger("yamp.ctrl")


class LibraryMixin:
    # ================================================= v004: 재생 기록 · 추천 · 대기열 · 편의
    def _finish_record(self, ended_naturally: bool):
        rec = self.recorder.finish(ended_naturally)
        if rec and self.cfg["history_enabled"]:
            try:
                self.library.record_play(**rec)
            except Exception as e:  # noqa
                log.warning("record_play: %s", e)

    # ---- 추천 홈 (B2~B4)
    def request_home(self, cb=None):
        self._home_cb = cb
        lib = self.library
        day = time.strftime("%Y%m%d")

        def work():
            now = int(time.time())
            stats = lib.stats(now)
            return ("home", R.build_home(stats, now, lib.co_pairs(), lib.last_played_key(), lib.recent_keys(now),
                                         rng=random.Random(day)))
        self._jobs.start(Job(work, self._jem))

    def scan_library(self):
        folders = [f.strip() for f in str(self.cfg["library_folders"] or "").split(";") if f.strip()]
        lib = self.library

        def stop():
            return self._closed                  # v032 (f60 P7): 종료하면 곡 사이에서 멈춤 (전: 스캔이 끝날 때까지 돌다 DB 가 닫힌 뒤 쓰기)

        def work():
            n = lib.scan(folders, read_tags, stop=stop)
            gone = 0 if stop() else lib.remove_missing(stop=stop)
            return ("scan", (n, gone))
        pool = getattr(self, "_scan_jobs", None) or self._jobs
        pool.start(Job(work, self._jem))

    def smart_list(self, rule: str) -> list[str]:
        """스마트 재생목록 (W7) — 키 목록 (파일이 있는 곡만은 재생할 때 확인)"""
        from ..domain.smart import build
        now = int(time.time())
        return build(rule, self.library.stats(now), now)

    def smart_lists(self, rules) -> dict:
        """v019: 여러 규칙을 한 번에 — 라이브러리 통계(DB 전체 읽기)는 1번만 (메뉴가 규칙 7개를 셀 때)"""
        from ..domain.smart import build
        now = int(time.time())
        stats = self.library.stats(now)
        return {r: build(r, stats, now) for r in rules}

    def maintenance(self):
        """시작 몇 초 뒤 + 실행 중 하루에 한 번 (v020 f40 L1): 오래된 재생 기록·파형 캐시 · 자동 가사 캐시(v022) 정리 · DB 빈 공간 · WAL 비우기
        (장시간 운용 — 며칠 켜 두어도 데이터가 끝없이 커지지 않게. 전에는 시작할 때 한 번뿐)"""
        lib = self.library
        root = self.cfg.data_dir / "waveform"
        lyr = getattr(getattr(self, "lyrics", None), "cache", None)
        ly_max = int(self.cfg["lyrics_cache_max"] or 0)

        def work():
            from ..audio.waveform import WaveformCache
            pruned = lib.prune_plays()
            vac = lib.vacuum_if_needed()
            trimmed = WaveformCache(root).trim()
            ck = lib.checkpoint()                 # v020 (f40 L1): -wal 파일 비움
            ly = lyr.trim(ly_max) if lyr is not None else 0     # v022 (N3): 오래 안 쓴 자동 가사 정리
            return ("maint", (pruned, trimmed, vac, ck, ly))
        self._jobs.start(Job(work, self._jem))

    def _on_job_done(self, r):
        if not r:
            return
        kind, val = r
        if kind == "maint":
            log.info("maintenance: plays pruned=%d, waveform trimmed=%d, vacuum=%s, wal checkpoint=%s, lyrics trimmed=%d", *val)
            return
        if kind == "home":
            self.homeReady.emit(val)
        elif kind == "scan":
            n, gone = val
            if n or gone:
                self.message.emit(f"라이브러리: {n}곡 추가" + (f", {gone}곡 정리" if gone else ""))
            self.libraryChanged.emit()

    def clear_history(self):
        self.library.clear_history()
        self.message.emit("재생 기록을 지웠습니다")
        self.libraryChanged.emit()

    # ---- 태그 편집 (C5)
    def edit_tags(self, index: int, fields: dict):
        t = self.pl.items[index]
        write_tags(t.path, fields)
        info = read_tags(t.path)
        t.title, t.artist, t.album = info.title, info.artist, info.album
        self._lib_upsert(t, info)
        self.playlistChanged.emit()
        self.libraryChanged.emit()

    # ================================================= v006: 라이브러리 upsert (CUE 포함) · 폴더 재생
    def _lib_upsert(self, t: Track, info=None) -> str:
        i = info
        return self.library.upsert(
            t.path, t.title if (t.cue_no or i is None) else i.title, t.artist if (t.cue_no or i is None) else i.artist,
            t.album if (t.cue_no or i is None) else i.album, i.genre if i else "", i.year if i else "",
            t.duration, uid=t.uid, cue=(t.cue_no, t.start_ms, t.end_ms, t.cue_path),
            codec=i.codec if i else "", bits=i.bits if i else 0, sr=i.samplerate if i else 0)

    def folder_tracks(self, folder: str, include_sub: bool = True, sort: str = "name", counts=None) -> list[Track]:
        return sort_tracks(scan_tracks(folder, include_sub, counts=counts), sort)

    def play_folder(self, folder: str, include_sub: bool = True, shuffle: bool = False, sort: str = "name",
                    start: Track | None = None, tracks: list[Track] | None = None):
        """F2: 재생 목록을 이 폴더의 곡으로 바꾸고 재생
        tracks (v018, f33 P4): 폴더 탭이 방금 읽은 (정렬된) 목록 — 있으면 폴더를 다시 돌지 않음"""
        ts = list(tracks) if tracks else self.folder_tracks(folder, include_sub, sort)
        if not ts:
            self.message.emit("이 폴더에 재생할 수 있는 곡이 없습니다")
            return 0
        if shuffle:
            random.shuffle(ts)
        self._finish_record(False)
        self.engine.stop()
        self._tag_gen[0] += 1
        self.pl.clear()
        self.pl.items.extend(ts)
        self.queue.clear()
        self.queueChanged.emit()
        self.playlistChanged.emit()
        self._scan_tags()
        i = 0
        if start is not None:
            i = next((k for k, x in enumerate(ts) if x.uid == start.uid), 0)
        self.play_index(i)
        self.cfg["last_folder"] = folder
        self.library.folder_played(folder)
        self.message.emit(f"폴더 재생: {os.path.basename(folder) or folder} — {len(ts)}곡" + (" (셔플)" if shuffle else ""))
        log.info("play folder %s sub=%s shuffle=%s sort=%s n=%d", folder, include_sub, shuffle, sort, len(ts))
        return len(ts)
