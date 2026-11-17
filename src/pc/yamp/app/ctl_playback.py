"""Controller 기능 묶음 — 재생 목록 편집 · 재생/일시정지/이동 · 위치(CUE 기준 변환) · 엔진 이벤트 · 세션 저장/복원

Controller(QObject) 가 이 믹스인을 상속. 상태·시그널은 Controller.__init__ 에 있음."""
import logging
import os

from PyQt6.QtCore import QTimer

from ..data.playlist import save_m3u, load_m3u, Track, fmt_time
from ..data.cue import merge_track_info
from ..data.tags import read_tags
from ..lyrics.providers.base import Query
from .jobs import TagJob

log = logging.getLogger("yamp.ctrl")
HIDDEN_UI_EVERY = 10         # 창이 숨겨졌을 때 위치 시그널은 10틱(0.5초)에 한 번


class PlaybackMixin:
    # ------------------------------------------------ 플레이리스트
    def add_paths(self, paths, play_first: bool = False):
        start = len(self.pl)
        n = self.pl.add_paths(paths)
        if n:
            self.playlistChanged.emit()
            self._scan_tags()
            self.message.emit(f"{n}곡 추가")
            if play_first or self.pl.current < 0 and not self.engine.is_playing():
                if play_first:
                    self.play_index(start)
        return n

    # ---- 되돌리기 (W12, vr0.1.0.009): 목록 편집 전 상태를 20단계까지 보관
    UNDO_MAX = 20

    def _snapshot(self, what: str):
        st = getattr(self, "_undo", None)
        if st is None:
            st = self._undo = []
        cur = self.pl.items[self.pl.current] if 0 <= self.pl.current < len(self.pl.items) else None
        st.append((what, list(self.pl.items), cur))
        del st[:-self.UNDO_MAX]

    def can_undo(self) -> bool:
        return bool(getattr(self, "_undo", None))

    def undo(self):
        st = getattr(self, "_undo", None)
        if not st:
            self.message.emit("되돌릴 것이 없습니다")
            return False
        what, items, cur = st.pop()
        self.pl.items[:] = items
        self.pl.current = next((k for k, t in enumerate(items) if t is cur), -1)
        self.pl._order = []
        self.playlistChanged.emit()
        self.message.emit(f"되돌림: {what}")
        return True

    def remove(self, indices):
        self._snapshot(f"{len(set(indices))}곡 빼기")
        was = self.pl.current
        self.pl.remove(indices)
        if was >= 0 and self.pl.current < 0:
            self.engine.stop()
        self.playlistChanged.emit()

    def move(self, i, j):
        self._snapshot("순서 바꾸기")
        self.pl.move(i, j)
        self.playlistChanged.emit()

    def clear(self):
        if self.pl.items:
            self._snapshot("목록 비우기")
        self.engine.stop()
        self.pl.clear()
        self._tag_gen[0] += 1
        self.playlistChanged.emit()

    def _scan_tags(self):
        self._tag_gen[0] += 1
        todo = [t for t in self.pl.items if not t.tagged]
        if todo:
            self._pool.start(TagJob(todo, self._tag_em, self._tag_gen, self._tag_gen[0], self.library))

    def load_playlist(self, path):
        self.clear()
        self.add_paths([path])

    def save_playlist(self, path):
        save_m3u(path, self.pl.items)

    # ------------------------------------------------ 재생
    def current_track(self) -> Track | None:
        i = self.pl.current
        return self.pl.items[i] if 0 <= i < len(self.pl) else None

    def play_index(self, i: int, start_ms: int = 0, autoplay: bool = True):
        if self._closed or not (0 <= i < len(self.pl)):    # 종료 뒤 늦게 온 타이머·엔진 이벤트 무시 (DB 닫힘)
            return
        self._resume_remember(self._ended_flag)          # 이전 곡이 긴 파일이면 위치 기억 (V2)
        self.pl.current = i
        t = self.pl.items[i]
        if not os.path.exists(t.path):
            self.message.emit(f"파일 없음: {t.path}")
            self._on_error("missing")
            return
        self._finish_record(self._ended_flag)
        self._ended_flag = False
        info = read_tags(t.path, want_cover=True)
        if t.cue_no:                          # CUE 트랙: 제목·가수·길이·리플레이게인은 CUE 기준 (v019 R11: cue.merge_track_info)
            merge_track_info(info, t)
        else:
            t.title, t.artist, t.album = info.title, info.artist, info.album
        t.duration = info.duration or t.duration
        t.tagged = True
        self.tag_info = info
        key = self._lib_upsert(t, info)
        self.recorder.start(key, int(info.duration * 1000))
        self.engine.set_gain(self._rg_factor(info))
        self.engine.set_fade(0.0 if int(self.cfg["crossfade_s"] or 0) > 0 else 1.0)
        if self.ab:
            self.ab = None
            self._ab_a = None
            self.abChanged.emit(None)
        self._cue_end_fired = False
        if start_ms == 0 and self.cfg["resume_long"]:     # V2: 긴 파일 이어 듣기
            from ..domain.resume import start_at
            start_ms = start_at(self.cfg["resume_pos"] or {}, t.uid, int(info.duration * 1000))
            if start_ms:
                self.message.emit(f"이어 듣기 {fmt_time(start_ms / 1000)} 부터 (처음부터: 이전 곡 버튼)")
        self.engine.load(t.path, autoplay, start_ms + t.start_ms)
        self.likedChanged.emit(self.library.liked(key))
        self.cur_lyrics = None
        self.lyricsChanged.emit(None)
        self.lyrics.request(Query(t.uid, info.title, info.artist, info.album, info.duration, info.lyrics))
        self.trackChanged.emit(t, info)
        self.currentChanged.emit()            # 목록 전체를 다시 만들지 않고 현재 줄 표시만 갱신
        log.info("play %d %s", i, t.path)

    def toggle(self):
        if self.pl.current < 0 and len(self.pl):
            self.play_index(0)
        else:
            self.engine.toggle()

    def play(self):
        if self.pl.current < 0 and len(self.pl):
            self.play_index(0)
        else:
            self.engine.play()

    def pause(self):
        self.engine.pause()

    def _resume_remember(self, ended: bool = False):
        """지금 곡이 30분 넘는 파일이면 위치를 state.json 에 기억 (V2, 최근 200개)"""
        t = self.current_track()
        if not t or not self.cfg["resume_long"]:
            return
        from ..domain.resume import remember
        dur = int((t.duration or 0) * 1000)
        m = dict(self.cfg["resume_pos"] or {})
        before = dict(m)
        remember(m, t.uid, self.rel_pos(), dur, ended)
        if m != before:
            self.cfg["resume_pos"] = m

    def stop(self):
        self._resume_remember()
        self._finish_record(False)
        self.engine.stop()
        self.engine.set_fade(1.0)

    def next(self, manual: bool = True, from_error: bool = False):
        if self.queue and not (self.cfg["repeat"] == "one" and not manual):
            t = self.queue.pop(0)
            self.queueChanged.emit()
            self.play_index(self._ensure_in_playlist(t))
            return
        i = self.pl.next_index(self.cfg["repeat"], bool(self.cfg["shuffle"]), manual)
        if i is None:
            self.engine.stop()
            if from_error:
                # vr0.1.0.010 (P4): 오류로 넘기다 끝에 닿은 경우 PC 절전·종료를 하지 않음
                self.message.emit("재생 오류로 목록 끝 — 목록 끝 동작은 하지 않음")
            elif not manual:
                self.on_list_end()                # W8: 재생 목록 끝 → 정지 / PC 절전 / PC 종료
            return
        self.play_index(i)

    def prev(self):
        if self.rel_pos() > 3000:
            self.seek(0)
            return
        i = self.pl.prev_index(bool(self.cfg["shuffle"]))
        if i is not None:
            self.play_index(i)

    # ---- 위치: 컨트롤러·화면은 '곡 기준'(CUE 트랙이면 트랙 시작 = 0) 위치를 쓰고, 엔진에는 파일 위치로 변환
    def _off(self) -> int:
        t = self.current_track()
        return t.start_ms if t else 0

    def rel_pos(self) -> int:
        return max(0, self.engine.position() - self._off())

    def rel_dur(self) -> int:
        t = self.current_track()
        d = self.engine.duration()
        if t and t.cue_no:
            end = t.end_ms if t.end_ms > 0 else d
            return max(0, end - t.start_ms)
        return d

    def seek(self, ms):
        self.engine.seek(max(0, int(ms)) + self._off())
        self._on_tick(force=True)

    def seek_rel(self, delta_ms):
        self.seek(max(0, self.rel_pos() + delta_ms))

    def set_volume(self, v):
        self.engine.set_volume(v)
        self.cfg["volume"] = self.engine.volume()

    def toggle_mute(self):
        self.cfg["muted"] = not self.cfg["muted"]
        self.engine.set_muted(self.cfg["muted"])
        self.modesChanged.emit()

    def cycle_repeat(self):
        order = ["off", "all", "one"]
        self.cfg["repeat"] = order[(order.index(self.cfg["repeat"]) + 1) % 3] if self.cfg["repeat"] in order else "all"
        self.modesChanged.emit()

    def toggle_shuffle(self):
        self.cfg["shuffle"] = not self.cfg["shuffle"]
        self.modesChanged.emit()

    # ------------------------------------------------ 엔진 이벤트
    def _on_tick(self, force=False):
        e = self.engine
        pos, dur = self.rel_pos(), self.rel_dur()
        playing = e.is_playing()
        t = self.current_track()
        if t and t.cue_no and t.end_ms > 0 and playing and pos >= dur > 0 and not self._cue_end_fired:
            self._cue_end_fired = True        # CUE 트랙 끝 → 다음 트랙
            QTimer.singleShot(0, self._on_ended)
            return
        self.recorder.tick(pos, playing)
        if dur > 0:
            self.recorder.set_duration(dur)
        # 구간 반복 (A5)
        if self.ab and playing and pos >= self.ab[1]:
            e.seek(self.ab[0] + self._off())
            pos = self.ab[0]
        # 볼륨 배율: 전환 페이드 × 슬립 타이머
        e.set_fade(self._fade_factor(pos, dur))
        self.lyricPosition.emit(pos + self.lyrics_offset())   # 미니 가사창은 메인 창이 숨겨져도 보이므로 항상
        if not self.ui_active and not force:   # 창이 숨겨져 있으면 LCD·시크바 시그널은 0.5초에 한 번
            self._ui_skip = (self._ui_skip + 1) % HIDDEN_UI_EVERY
            if self._ui_skip:
                return
        self.positionChanged.emit(pos, dur)

    def _on_state(self, st):
        if st == "playing":
            self._errors = 0
            self._tick.start()
        else:
            self._tick.stop()
            self._on_tick()
        self.stateChanged.emit(st)

    def _on_ended(self):
        if self._closed:
            return
        self._ended_flag = True
        if self._sleep_track:                 # 슬립 타이머 "곡 끝날 때"
            self._finish_record(True)
            self.sleep_cancel()
            self.engine.set_fade(1.0)
            self.message.emit("슬립 타이머: 정지")
            return
        self.next(manual=False)

    def _on_error(self, msg):
        if self._closed:
            return
        self._errors += 1
        self.message.emit(f"재생 오류: {msg}")
        if self._errors < max(3, len(self.pl)):
            QTimer.singleShot(300, lambda: self.next(manual=False, from_error=True))

    # ------------------------------------------------ 세션
    def save_session(self):
        # vr0.1.0.008: 목록이 바뀌었을 때만 m3u 다시 씀 (만 곡 목록을 5분마다 디스크에 쓰지 않게)
        sig = self._pl_signature()
        if sig != getattr(self, "_saved_sig", None):
            try:
                save_m3u(str(self.cfg.data_dir / "playlist.m3u8"), self.pl.items)
                self._saved_sig = sig
            except OSError as e:
                log.warning("session save: %s", e)
        self.cfg["last_index"] = self.pl.current
        self.cfg["last_position_ms"] = self.rel_pos()

    def _pl_signature(self):
        """목록 내용 지문 (곡 수 + 경로·CUE 번호 해시) — 만 곡이어도 수 ms"""
        return len(self.pl.items), hash(tuple((t.path, t.cue_no) for t in self.pl.items))

    def restore_session(self):
        p = self.cfg.data_dir / "playlist.m3u8"
        if not p.exists():
            sf = str(self.cfg["start_folder"] or "").strip()
            if sf and os.path.isdir(sf):          # config.txt start_folder (첫 실행)
                log.info("start_folder: %s", sf)
                self.add_paths([sf])
            return
        try:
            files = [f for f in load_m3u(str(p)) if os.path.exists(f)]
        except OSError:
            return
        if not files:
            return
        self.pl.add_paths(files, files_first=True)       # v018 (f33 P9): 곡마다 폴더 확인 생략
        self.playlistChanged.emit()
        self._scan_tags()
        i = int(self.cfg["last_index"])
        if self.cfg["resume_on_start"] and 0 <= i < len(self.pl):
            self.play_index(i, int(self.cfg["last_position_ms"] or 0), autoplay=False)
