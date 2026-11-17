# -*- coding: utf-8 -*-
"""가사 검색어 정리 · 변형 (vr0.1.0.011, f18 L2) — Qt 비의존. Android lyrics/Query.kt 와 같은 규칙.
공용 테스트: testdata/lyrics_query_cases.txt

clean_title : 앞 번호 "01. " 제거 → 괄호 속 군더더기(feat·prod·MV·remaster·live …) 제거 → " - Remastered 2011" 같은
              꼬리 제거 → 괄호 없는 "feat. X" 꼬리 제거 → 공백 정리
split_alt   : "좋은 날 (Good Day)" → ("좋은 날", "Good Day")   "IU(아이유)" → ("IU", "아이유")
main_artist : "아이유, 김창완" / "A & B" / "A x B" / "A feat. B" / "A/B" → 첫 가수
variants    : (원본) → 정리 제목 × 가수 이름들 — 중복 빼고 최대 4개
"""
import re

_KW = (r"feat|ft|featuring|prod|produced|remaster|remastered|mv|m/v|official|audio|video|live|inst|instrumental"
       r"|ver|version|lyric|lyrics|explicit|clean|radio edit|edit|mono|stereo|bonus|hq|hd|4k|visualizer|teaser|full")
_KEEP_RE = re.compile(r"(?i)remix|\bmix\b|acoustic|cover|unplugged|piano|orchestra|demo|sped up|slowed|english|japanese|korean|chinese|\bjp\b|\beng\b|\bkor\b")
_BR = re.compile(r"\s*[\(\[\{【]([^\)\]\}】]*)[\)\]\}】]")
_KW_RE = re.compile(r"(?i)(?:^|[\s.\-_/])(?:" + _KW + r")(?:$|[\s.\-_/:0-9])")
_TAIL_DASH = re.compile(r"(?i)\s+[-–—]\s+[^-–—]*?(?:" + _KW + r")[^-–—]*$")
_TAIL_FEAT = re.compile(r"(?i)\s+(?:feat\.?|ft\.?|featuring)\s+.*$")
_NUM = re.compile(r"^\s*\d{1,3}\s*[.\-_)]\s*(?=\S)")
_ART_SEP = re.compile(r"(?i)\s*(?:,|&|/|;|\s+x\s+|\s+with\s+|\s+feat\.?\s+|\s+ft\.?\s+|\s+featuring\s+)\s*")
_SPACES = re.compile(r"\s+")
MAX_VARIANTS = 4


def _ws(s: str) -> str:
    return _SPACES.sub(" ", s or "").strip()


def _is_kw(inner: str) -> bool:
    return bool(_KW_RE.search(" " + inner + " "))


def clean_title(t: str) -> str:
    s = _ws(t)
    n = _NUM.sub("", s)
    if n.strip():
        s = n
    s = _BR.sub(lambda m: "" if _is_kw(m.group(1)) else m.group(0), s)
    s = _TAIL_DASH.sub("", s)
    s = _TAIL_FEAT.sub("", s)
    s = _ws(s)
    return s or _ws(t)


def split_alt(s: str) -> tuple[str, str]:
    """바깥 이름, 괄호 속 다른 이름 (없으면 "")"""
    s = _ws(s)
    m = re.match(r"^(.*?)\s*[\(\[]([^\)\]]+)[\)\]]\s*$", s)
    if m and m.group(1).strip() and not _is_kw(m.group(2)) and not _KEEP_RE.search(m.group(2)):
        return _ws(m.group(1)), _ws(m.group(2))
    return s, ""


def main_artist(a: str) -> str:
    a = _ws(a)
    parts = [p for p in _ART_SEP.split(a) if p.strip()]
    return _ws(parts[0]) if parts else a


def artist_names(a: str) -> list[str]:
    """가수 이름 후보: 첫 가수 바깥 이름, 괄호 속 이름"""
    out: list[str] = []
    m, alt = split_alt(main_artist(a))
    for x in (m, alt):
        if x and x not in out:
            out.append(x)
    return out


def title_names(t: str) -> list[str]:
    c = clean_title(t)
    m, alt = split_alt(c)
    out: list[str] = []
    for x in (c, m, alt):
        if x and x not in out:
            out.append(x)
    return out


def variants(title: str, artist: str) -> list[tuple[str, str]]:
    """검색에 쓸 (제목, 가수) 목록 — 첫 항목은 원본"""
    out: list[tuple[str, str]] = []

    def add(t, a):
        p = (_ws(t), _ws(a))
        if p[0] and p not in out and len(out) < MAX_VARIANTS:
            out.append(p)
    add(title, artist)
    ts = title_names(title)
    arts = artist_names(artist) or [""]
    # 정리 제목 + 첫 가수 → 바깥 제목 + 첫 가수 → 정리 제목 + 다른 이름 → 괄호 속 제목 + 첫 가수 …
    for t in ts[1:2] + ts[:1] + ts[2:]:
        add(t, arts[0])
    for a in arts[1:]:
        for t in ts:
            add(t, a)
    return out
