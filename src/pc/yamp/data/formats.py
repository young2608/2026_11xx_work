# -*- coding: utf-8 -*-
"""
형식 표 (vr0.1.0.010) — testdata/formats.txt 와 같은 내용 (테스트로 일치 확인). Qt 비의존.
  분류: music voice book web bigwav hires movie tracker playlist cue
  PC 는 FFmpeg (Qt 엔진 · mpv 엔진 모두) 로 디코드. 트래커(mod/xm/it/s3m)는 FFmpeg 에 libopenmpt 가
  있어야 소리가 남 — 없으면 재생 오류 → 자동으로 다음 곡 (목록에는 넣음)
"""
from pathlib import Path

#  확장자: (분류, PC, Android)
TABLE: dict[str, tuple[str, bool, bool]] = {
    "mp3": ("music", True, True), "mp2": ("music", True, False), "flac": ("music", True, True),
    "ogg": ("music", True, True), "oga": ("music", True, True), "opus": ("music", True, True),
    "m4a": ("music", True, True), "mp4": ("music", True, True), "aac": ("music", True, True),
    "adts": ("music", True, True), "alac": ("music", True, False), "wav": ("music", True, True),
    "aif": ("music", True, False), "aiff": ("music", True, False), "aifc": ("music", True, False),
    "wma": ("music", True, False), "ape": ("music", True, False), "wv": ("music", True, False),
    "tta": ("music", True, False), "dsf": ("hires", True, False), "dff": ("hires", True, False),
    "mka": ("music", True, True), "mpc": ("music", True, False), "caf": ("music", True, False),
    "spx": ("voice", True, False), "tak": ("hires", True, False),
    "3gp": ("voice", True, True), "3ga": ("voice", True, True), "amr": ("voice", True, True),
    "awb": ("voice", True, True), "qcp": ("voice", True, False), "gsm": ("voice", True, False),
    "au": ("voice", True, False), "snd": ("voice", True, False), "voc": ("voice", True, False),
    "m4b": ("book", True, True), "m4r": ("book", True, True),
    "webm": ("web", True, True), "weba": ("web", True, True),
    "w64": ("bigwav", True, False), "rf64": ("bigwav", True, False), "bwf": ("bigwav", True, True),
    "ac3": ("movie", True, False), "eac3": ("movie", True, False), "dts": ("movie", True, False),
    "thd": ("movie", True, False), "mlp": ("movie", True, False), "ra": ("movie", True, False),
    "rm": ("movie", True, False),
    "mod": ("tracker", True, False), "xm": ("tracker", True, False), "it": ("tracker", True, False),
    "s3m": ("tracker", True, False),
    "m3u": ("playlist", True, True), "m3u8": ("playlist", True, True), "pls": ("playlist", True, True),
    "xspf": ("playlist", True, True), "wpl": ("playlist", True, True),
    "cue": ("cue", True, True),
}

CATEGORY_NAMES = {"music": "음악", "voice": "녹음·음성", "book": "오디오북·벨소리", "web": "웹 오디오",
                  "bigwav": "큰 WAV", "hires": "고음질", "movie": "영화·방송 음성", "tracker": "트래커 음악",
                  "playlist": "재생목록", "cue": "CUE 시트"}

AUDIO_EXT = {"." + e for e, (cat, pc, _a) in TABLE.items() if pc and cat not in ("playlist", "cue")}
PLAYLIST_EXT = {"." + e for e, (cat, _p, _a) in TABLE.items() if cat == "playlist"}

# 녹음·강의처럼 긴 파일: 이 길이(초) 넘으면 파일별 이어 듣기 (V2)
LONG_FILE_S = 30 * 60


def ext(path: str) -> str:
    return Path(path).suffix.lower().lstrip(".")


def category(path: str) -> str:
    return TABLE.get(ext(path), ("", False, False))[0]


def dialog_filter() -> str:
    """파일 열기 창 필터: 전체 + 분류별 + 모든 파일"""
    groups: dict[str, list[str]] = {}
    for e, (cat, pc, _a) in TABLE.items():
        if pc:
            groups.setdefault(cat, []).append("*." + e)
    allx = " ".join(x for c, xs in groups.items() for x in xs)
    parts = [f"재생 가능한 모든 형식 ({allx})"]
    for cat in ("music", "voice", "book", "web", "bigwav", "hires", "movie", "tracker", "playlist", "cue"):
        if cat in groups:
            parts.append(f"{CATEGORY_NAMES[cat]} ({' '.join(groups[cat])})")
    parts.append("모든 파일 (*)")
    return ";;".join(parts)


def load_table_file(path) -> dict[str, tuple[str, bool, bool]]:
    """testdata/formats.txt 읽기 (테스트용)"""
    out = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        e, cat, pc, an = line.split("|")
        out[e] = (cat, pc == "1", an == "1")
    return out
