"""LRC 파서 (Qt 비의존). Android Lrc.kt 와 같은 규칙 / 같은 테스트 케이스.

- [mm:ss.xx] / [mm:ss.xxx] / [mm:ss:xx] / [mm:ss] 지원, 한 줄에 여러 타임스탬프 가능
- [offset:+500] → 가사를 500ms 빨리 표시
- 같은 시각 여러 줄 = 한 블록 (알송: 원문 / 발음 / 번역)
- 타임스탬프가 하나도 없으면 일반 가사(synced=False)
- 단어별 시각 <mm:ss.xx> 는 표시에서 뺌 (vr0.1.0.011)
"""
from bisect import bisect_right
from dataclasses import dataclass, field
import re

TS_RE = re.compile(r"\[(\d{1,3}):(\d{1,2})(?:[.:](\d{1,3}))?\]")
META_RE = re.compile(r"^\[([a-zA-Z]+):(.*)\]$")
# 단어별 시각 (Enhanced LRC "<00:12.34>단어") — 표시에서 뺌 (vr0.1.0.011, f18 L9)
WORD_RE = re.compile(r"\s*<\d{1,3}:\d{1,2}(?:[.:]\d{1,3})?>\s*")


def _strip_words(s: str) -> str:
    if "<" not in s:
        return s
    return re.sub(r"\s{2,}", " ", WORD_RE.sub(lambda m: " " if m.group(0)[:1].isspace() or m.group(0)[-1:].isspace() else "", s)).strip()


@dataclass
class Block:
    t_ms: int
    lines: list[str]


@dataclass
class Lyrics:
    blocks: list[Block] = field(default_factory=list)
    synced: bool = False
    source: str = ""
    meta: dict = field(default_factory=dict)

    @property
    def times(self) -> list[int]:
        return [b.t_ms for b in self.blocks]

    def index_at(self, pos_ms: int) -> int:
        """pos_ms 에 표시할 블록 인덱스 (첫 줄 이전이면 -1)."""
        if not self.synced or not self.blocks:
            return -1
        # vr0.1.0.009: 시각 목록을 50ms 마다 새로 만들지 않게 캐시 (블록 수·첫/끝 시각이 같으면 재사용)
        b = self.blocks
        sig = (len(b), b[0].t_ms, b[-1].t_ms)
        c = self.__dict__.get("_tcache")
        if c is None or c[0] != sig:
            c = (sig, [x.t_ms for x in b])
            self.__dict__["_tcache"] = c
        return bisect_right(c[1], pos_ms) - 1

    def to_lrc(self) -> str:
        out = []
        for k in ("ti", "ar", "al"):
            if self.meta.get(k):
                out.append(f"[{k}:{self.meta[k]}]")
        for b in self.blocks:
            for ln in b.lines:
                if self.synced:
                    out.append(f"{fmt_ts(b.t_ms)}{ln}")
                else:
                    out.append(ln)
        return "\n".join(out) + "\n"


def fmt_ts(ms: int) -> str:
    ms = max(0, int(ms))
    return f"[{ms // 60000:02d}:{ms // 1000 % 60:02d}.{ms % 1000 // 10:02d}]"


def _frac_ms(frac: str | None) -> int:
    if not frac:
        return 0
    return int(frac.ljust(3, "0")[:3])


def parse(text: str, source: str = "") -> Lyrics:
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n").lstrip("﻿")
    meta: dict = {}
    timed: list[tuple[int, int, str]] = []   # (t, 입력순서, 텍스트)
    plain: list[str] = []
    seq = 0
    for raw in text.split("\n"):
        line = raw.strip()
        if not line:
            plain.append("")
            continue
        pos = 0
        stamps = []
        while True:
            m = TS_RE.match(line, pos)
            if not m:
                break
            mm, ss, fr = m.group(1), m.group(2), m.group(3)
            stamps.append(int(mm) * 60000 + int(ss) * 1000 + _frac_ms(fr))
            pos = m.end()
        if stamps:
            body = _strip_words(line[pos:].strip())
            for t in stamps:
                timed.append((t, seq, body))
                seq += 1
            continue
        mm = META_RE.match(line)
        if mm and not TS_RE.match(line):
            meta[mm.group(1).lower()] = mm.group(2).strip()
            continue
        plain.append(_strip_words(line))

    if timed:
        try:
            off = int(str(meta.get("offset", "0")).replace("+", ""))
        except ValueError:
            off = 0
        timed.sort(key=lambda x: (x[0], x[1]))
        blocks: list[Block] = []
        for t, _, body in timed:
            t = max(0, t - off)
            if blocks and blocks[-1].t_ms == t:
                if body:
                    blocks[-1].lines.append(body)
            else:
                blocks.append(Block(t, [body] if body else []))
        # 빈 블록(간주 표시)은 유지하되 내용 없는 연속 블록은 정리
        return Lyrics(blocks, True, source, meta)

    # 일반 가사: 앞뒤 빈 줄 제거
    while plain and not plain[0]:
        plain.pop(0)
    while plain and not plain[-1]:
        plain.pop()
    return Lyrics([Block(-1, [p]) for p in plain], False, source, meta)


def is_empty(ly: "Lyrics | None") -> bool:
    return ly is None or not any(any(s.strip() for s in b.lines) for b in ly.blocks)
