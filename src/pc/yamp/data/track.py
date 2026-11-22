# -*- coding: utf-8 -*-
"""곡 (Track) · 형식 판별 · 시간 표시 (vr0.1.0.019 R1 — data/playlist.py 에서 나눔, Qt 비의존)"""
from dataclasses import dataclass
import os

# 재생 가능한 형식 — vr0.1.0.010 부터 formats.py 표 (testdata/formats.txt 와 같음) 에서 만듦
from .formats import AUDIO_EXT


CUE_EXT = ".cue"
_SEPS = "/\\" if os.sep == "\\" else "/"      # Windows: 두 구분자 모두


def is_audio(path: str) -> bool:
    # v018 (f33 P5): Path 객체를 만들지 않음 (폴더 스캔에서 파일마다 호출). '.mp3' 처럼 이름이 점으로 시작하면
    # Path.suffix 와 같게 확장자 없음으로 봄 (os.path.splitext 도 같음)
    return os.path.splitext(path)[1].lower() in AUDIO_EXT


def path_name(path: str) -> str:
    """Path(path).name 과 같은 값 — Path 객체를 만들지 않음 (v032 f60 P5: 목록 표시 · 거르기 · 정렬이 곡마다 부름)"""
    return os.path.basename(path.rstrip(_SEPS))


def path_stem(path: str) -> str:
    """Path(path).stem 과 같은 값 (마지막 '.' 앞, 이름이 '.' 으로 시작하거나 '.' 으로 끝나면 이름 그대로)"""
    name = path_name(path)
    i = name.rfind(".")
    return name[:i] if 0 < i < len(name) - 1 else name


@dataclass
class Track:
    path: str
    title: str = ""
    artist: str = ""
    album: str = ""
    duration: float = 0.0
    tagged: bool = False
    # CUE 트랙 (한 파일 앨범의 일부) — 0 이면 일반 파일
    cue_no: int = 0
    start_ms: int = 0
    end_ms: int = -1            # -1 = 파일 끝까지
    cue_path: str = ""
    rg: dict | None = None      # CUE REM REPLAYGAIN (vr0.1.0.010) — 없으면 파일 태그 사용

    @property
    def uid(self) -> str:
        """곡 고유 문자열 (라이브러리·캐시 키). CUE 트랙은 파일 경로 + 트랙 번호"""
        return f"{self.path}|cue:{self.cue_no}" if self.cue_no else self.path

    @property
    def display(self) -> str:
        if self.title:
            return f"{self.artist} - {self.title}" if self.artist else self.title
        return path_stem(self.path)                 # v032 (f60 P5): Path 객체 없이 (곡당 약 3µs → 0.5µs)


def fmt_time(sec: float) -> str:
    if sec is None or sec < 0:
        return "--:--"
    s = int(sec)
    return f"{s // 3600}:{s // 60 % 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60}:{s % 60:02d}"
