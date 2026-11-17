# -*- coding: utf-8 -*-
"""
CUE 시트 파서 (Qt 비의존). Android data/Cue.kt 와 같은 규칙. 공용 테스트: testdata/cue_sample.cue

지원: FILE / TRACK nn AUDIO / TITLE / PERFORMER / INDEX 01 mm:ss:ff (ff = 1/75초) / REM GENRE·DATE
      REM REPLAYGAIN_ALBUM_GAIN·_PEAK (앨범, 전체) · REM REPLAYGAIN_TRACK_GAIN·_PEAK (트랙 안) — vr0.1.0.010
  - 앨범 TITLE·PERFORMER 는 트랙에 값이 없을 때 사용
  - 트랙 끝 = 같은 FILE 의 다음 트랙 INDEX 01, 마지막 트랙은 끝까지(-1)
  - 글자 인코딩: UTF-8(BOM) → CP949 → latin-1 순서로 시도
"""
from dataclasses import dataclass, field
from pathlib import Path
import re

_INDEX = re.compile(r"(\d+):(\d{1,2}):(\d{1,2})")


@dataclass
class CueTrack:
    number: int
    file: str           # 절대 경로
    title: str
    performer: str
    album: str
    start_ms: int
    end_ms: int         # -1 = 파일 끝까지
    genre: str = ""
    date: str = ""
    # 리플레이게인 (태그와 같은 키: replaygain_track_gain · _track_peak · _album_gain · _album_peak)
    rg: dict = field(default_factory=dict)


def _arg(line: str) -> str:
    rest = line.split(None, 1)[1] if len(line.split(None, 1)) > 1 else ""
    rest = rest.strip()
    if rest.startswith('"'):
        end = rest.find('"', 1)
        return rest[1:end] if end > 0 else rest[1:]
    return rest.split()[0] if rest else ""


def index_ms(text: str) -> int:
    m = _INDEX.search(text)
    if not m:
        return 0
    mm, ss, ff = (int(x) for x in m.groups())
    return mm * 60000 + ss * 1000 + (ff * 1000) // 75


def decode(raw: bytes) -> str:
    for enc in ("utf-8-sig", "cp949", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1", "replace")


def parse(text: str, base_dir: str = "") -> list[CueTrack]:
    album = performer = genre = date = ""
    album_rg: dict = {}
    cur_file = ""
    tracks: list[dict] = []
    t = None
    for raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = raw.strip()
        if not line:
            continue
        key = line.split()[0].upper()
        if key == "FILE":
            name = _arg(line)
            cur_file = str(Path(base_dir) / name) if base_dir and not Path(name).is_absolute() else name
        elif key == "TRACK":
            parts = line.split()
            if len(parts) >= 3 and parts[2].upper() != "AUDIO":
                t = None
                continue
            t = {"number": int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else len(tracks) + 1,
                 "file": cur_file, "title": "", "performer": "", "start": None, "rg": {}}
            tracks.append(t)
        elif key == "TITLE":
            if t is None:
                album = _arg(line)
            else:
                t["title"] = _arg(line)
        elif key == "PERFORMER":
            if t is None:
                performer = _arg(line)
            else:
                t["performer"] = _arg(line)
        elif key == "INDEX" and t is not None:
            parts = line.split()
            if len(parts) >= 3 and parts[1] == "01":
                t["start"] = index_ms(parts[2])
        elif key == "REM" and len(line.split()) >= 3 and line.split()[1].upper().startswith("REPLAYGAIN_"):
            parts = line.split(None, 2)
            k = parts[1].lower()
            v = parts[2].strip().strip('"')
            if k in ("replaygain_album_gain", "replaygain_album_peak"):
                album_rg[k] = v
            elif k in ("replaygain_track_gain", "replaygain_track_peak") and t is not None:
                t["rg"][k] = v
        elif key == "REM" and t is None:
            parts = line.split(None, 2)
            if len(parts) >= 3 and parts[1].upper() == "GENRE":
                genre = parts[2].strip().strip('"')
            elif len(parts) >= 3 and parts[1].upper() == "DATE":
                date = parts[2].strip().strip('"')
    out: list[CueTrack] = []
    valid = [x for x in tracks if x["start"] is not None]
    for i, x in enumerate(valid):
        nxt = valid[i + 1] if i + 1 < len(valid) else None
        end = nxt["start"] if nxt is not None and nxt["file"] == x["file"] else -1
        out.append(CueTrack(x["number"], x["file"], x["title"] or f"Track {x['number']:02d}",
                            x["performer"] or performer, album, x["start"], end, genre, date,
                            {**album_rg, **x["rg"]}))
    return out


def load(path: str) -> list[CueTrack]:
    p = Path(path)
    return parse(decode(p.read_bytes()), str(p.parent))


def merge_track_info(info, t):
    """CUE 트랙 재생 시 파일 태그(TagInfo)를 트랙 기준으로 고침 — Qt 비의존 · 테스트 대상
    (v019 R11: ctl_playback.play_index 에서 옮김, 동작 같음)
      제목 = CUE · 가수/앨범 = CUE 값이 있으면 CUE · 길이 = 트랙 구간 · 내장 가사 = 없음(파일 전체 가사는 트랙과 안 맞음)
      리플레이게인: 파일 태그의 '트랙' 값은 앨범 전체(파일) 값 → 앨범 값으로 보고, CUE 값이 있으면 우선"""
    info.title, info.artist = t.title, t.artist or info.artist
    info.album = t.album or info.album
    file_dur = info.duration
    info.duration = ((t.end_ms if t.end_ms > 0 else file_dur * 1000) - t.start_ms) / 1000
    info.lyrics = ""
    rg = dict(info.rg or {})
    for a, b in (("replaygain_track_gain", "replaygain_album_gain"),
                 ("replaygain_track_peak", "replaygain_album_peak")):
        if a in rg:
            rg.setdefault(b, rg.pop(a))
    rg.update(t.rg or {})
    info.rg = rg
    return info
