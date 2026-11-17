from pathlib import Path

from .base import Provider, Query


def read_text_any(p: Path) -> str:
    raw = p.read_bytes()
    for enc in ("utf-8-sig", "cp949", "utf-16"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1")


def lrc_candidates(uid: str) -> list[Path]:
    """곡 uid → 찾아볼 .lrc 경로.
    CUE 트랙 uid('파일|cue:N') 는 앨범 한 파일의 .lrc 가 곡 전체(모든 트랙)용이라 쓰지 않고
    '파일이름.NN.lrc' (예: album.02.lrc) 만 찾음 — vr0.1.0.010 수정"""
    if "|cue:" in uid:
        f, _, n = uid.rpartition("|cue:")
        p = Path(f)
        try:
            no = int(n)
        except ValueError:
            return []
        return [p.with_name(f"{p.stem}.{no:02d}.lrc")]
    p = Path(uid)
    return [p.with_suffix(".lrc"), p.with_suffix(".LRC"), p.with_name(p.name + ".lrc")]


def lrc_save_path(uid: str) -> str:
    """가사 저장 위치 (읽는 첫 후보와 같음)"""
    return str(lrc_candidates(uid)[0])


class LocalLrcProvider(Provider):
    """음악 파일과 같은 폴더·같은 이름의 .lrc"""
    name = "local"

    def fetch(self, q: Query):
        for cand in lrc_candidates(q.path):
            if cand.is_file():
                return read_text_any(cand)
        return None


class EmbeddedProvider(Provider):
    """태그 내장 가사 (ID3 USLT/SYLT, Vorbis LYRICS, MP4 ©lyr)"""
    name = "embedded"

    def fetch(self, q: Query):
        return q.embedded.strip() or None
