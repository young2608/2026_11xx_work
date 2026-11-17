"""Controller 기능 묶음 — 가사: 곡별 싱크 보정 · 다시 찾기 · .lrc 저장 · 결과 수신

Controller(QObject) 가 이 믹스인을 상속. 상태·시그널은 Controller.__init__ 에 있음."""
import logging


from ..core.keys import cache_key
from ..lyrics.providers.local import lrc_save_path

log = logging.getLogger("yamp.ctrl")


class LyricsMixin:
    # ------------------------------------------------ 가사
    def track_offset_key(self):
        t = self.current_track()
        return cache_key(t.uid) if t else ""

    def lyrics_offset(self) -> int:
        k = self.track_offset_key()
        return int(self.cfg["lyrics_offset_ms"] or 0) + int((self.cfg["lyrics_offsets"] or {}).get(k, 0))

    def adjust_offset(self, delta_ms: int | None):
        """곡별 싱크 보정. None = 초기화. (+) = 가사를 더 빨리"""
        k = self.track_offset_key()
        if not k:
            return
        offs = dict(self.cfg["lyrics_offsets"] or {})
        if delta_ms is None:
            offs.pop(k, None)
        else:
            offs[k] = int(offs.get(k, 0)) + delta_ms
            if offs[k] == 0:
                offs.pop(k)
        self.cfg["lyrics_offsets"] = offs
        self.message.emit(f"가사 싱크 {offs.get(k, 0) / 1000:+.1f}초")
        self._on_tick(force=True)

    def research_lyrics(self, index: int | None = None):
        if index is not None and index != self.pl.current:
            self.play_index(index)
        # vr0.1.0.011: 지금 가사는 그대로 두고 다시 찾음 (못 찾으면 유지, 찾으면 바꿈 · 직접 편집본은 백업)
        self.lyricsStatus.emit("가사 다시 찾는 중…")
        self.lyrics.research()

    def save_lyrics_lrc(self) -> str | None:
        t = self.current_track()
        if not t or not self.cur_lyrics:
            return None
        p = lrc_save_path(t.uid)           # CUE 트랙은 album.NN.lrc (vr0.1.0.010)
        with open(p, "w", encoding="utf-8") as f:
            f.write(self.cur_lyrics.to_lrc())
        return p

    def _on_lyrics(self, ly):
        self.cur_lyrics = ly
        self.lyricsChanged.emit(ly)
        res = getattr(self.lyrics, "last_result", None)
        if res is not None and (res.lyrics is ly):
            self.lyricsStatus.emit(res.status_text())          # 출처·점수 / 못 찾은 이유 (f18 L7)
        elif ly is None:
            self.lyricsStatus.emit("가사 없음")
        else:
            from ..lyrics.resolve import SOURCE_NAMES
            self.lyricsStatus.emit(f"가사: {SOURCE_NAMES.get(ly.source, ly.source)}" + ("" if ly.synced else " (싱크 없음)"))
        self._on_tick(force=True)
