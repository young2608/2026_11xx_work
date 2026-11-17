# -*- coding: utf-8 -*-
"""
가사 편집기 로직 (Qt 비의존) — 싱크 찍기. Android lyrics/LyricEditor.kt 와 같은 동작.

- 텍스트(줄) 불러오기: 기존 LRC 면 시각 유지, 일반 가사면 시각 없음(-1)
- stamp(pos): 현재 줄에 재생 위치를 찍고 다음 줄로
- nudge(±ms): 선택 줄 시각 조정
- to_lrc(): 시각 있는 줄만 [mm:ss.xx] 로, 시각 없는 줄은 앞 줄 시각을 이어받지 않고 그대로 (일반 가사 줄)
"""
from dataclasses import dataclass

from .lrc import Lyrics, fmt_ts


@dataclass
class EditLine:
    t_ms: int        # -1 = 시각 없음
    text: str


class LyricEditor:
    def __init__(self, lines=None):
        self.lines: list[EditLine] = list(lines or [])
        self.cur = 0

    @classmethod
    def from_lyrics(cls, ly: "Lyrics | None"):
        out = []
        if ly:
            for b in ly.blocks:
                for ln in (b.lines or [""]):
                    out.append(EditLine(b.t_ms if ly.synced else -1, ln))
        return cls(out)

    @classmethod
    def from_text(cls, text: str):
        return cls([EditLine(-1, ln.rstrip()) for ln in (text or "").replace("\r\n", "\n").split("\n")])

    def set_text(self, text: str):
        """텍스트 수정 반영: 같은 순서의 줄은 기존 시각 유지"""
        old = self.lines
        new = [ln.rstrip() for ln in (text or "").replace("\r\n", "\n").split("\n")]
        self.lines = [EditLine(old[i].t_ms if i < len(old) else -1, s) for i, s in enumerate(new)]
        self.cur = min(self.cur, max(0, len(self.lines) - 1))

    def text(self) -> str:
        return "\n".join(l.text for l in self.lines)

    def select(self, i: int):
        if self.lines:
            self.cur = max(0, min(i, len(self.lines) - 1))

    def stamp(self, pos_ms: int) -> int:
        """현재 줄에 시각 → 다음 (빈 줄은 건너뜀). 반환: 새 현재 줄"""
        if not self.lines:
            return 0
        self.lines[self.cur].t_ms = max(0, int(pos_ms))
        i = self.cur + 1
        while i < len(self.lines) and not self.lines[i].text.strip():
            i += 1
        self.cur = min(i, len(self.lines) - 1)
        return self.cur

    def nudge(self, delta_ms: int, i: int | None = None):
        i = self.cur if i is None else i
        if 0 <= i < len(self.lines) and self.lines[i].t_ms >= 0:
            self.lines[i].t_ms = max(0, self.lines[i].t_ms + int(delta_ms))

    def clear_times(self):
        for l in self.lines:
            l.t_ms = -1
        self.cur = 0

    def stamped(self) -> int:
        return sum(1 for l in self.lines if l.t_ms >= 0)

    def to_lrc(self) -> str:
        out = []
        for l in self.lines:
            if l.t_ms >= 0:
                out.append(f"{fmt_ts(l.t_ms)}{l.text}")
            elif l.text.strip():
                out.append(l.text)
        return "\n".join(out) + "\n"
