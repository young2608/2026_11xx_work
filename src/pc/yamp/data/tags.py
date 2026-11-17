"""태그 읽기 (mutagen). mutagen 이 없으면 파일 이름으로 대체."""
from dataclasses import dataclass, field
from pathlib import Path
import logging

log = logging.getLogger("yamp.tags")

try:
    import mutagen
except ImportError:  # pragma: no cover
    mutagen = None


@dataclass
class TagInfo:
    title: str = ""
    artist: str = ""
    album: str = ""
    duration: float = 0.0      # 초
    bitrate: int = 0           # kbps
    samplerate: int = 0        # Hz
    channels: int = 0
    lyrics: str = ""           # 내장 가사 (LRC 또는 일반 텍스트)
    cover: bytes = field(default=b"", repr=False)
    genre: str = ""
    year: str = ""
    rg: dict = field(default_factory=dict)   # replaygain_track_gain / _peak / album_gain / album_peak (문자열)
    codec: str = ""            # FLAC / MP3 / ALAC / AAC / WAV / AIFF / APE / DSD / …
    bits: int = 0              # 비트 깊이 (무손실·PCM 만, 0 = 모름/해당 없음)

    @property
    def format_label(self) -> str:
        return format_label(self.codec, self.bits, self.samplerate, self.bitrate)

    @property
    def hires(self) -> bool:
        return self.bits >= 24 or self.samplerate > 48000


_CODEC_BY_TYPE = {"MP3": "MP3", "FLAC": "FLAC", "OggVorbis": "Vorbis", "OggOpus": "Opus", "OggFLAC": "FLAC",
                  "OggSpeex": "Speex", "WAVE": "WAV", "AIFF": "AIFF", "MonkeysAudio": "APE", "WavPack": "WavPack",
                  "TrueAudio": "TTA", "DSF": "DSD", "DSDIFF": "DSD", "ASF": "WMA", "Musepack": "MPC", "AAC": "AAC",
                  "AC3": "AC3", "OptimFROG": "OFR", "SMF": "MIDI"}


def format_label(codec: str, bits: int, sr: int, kbps: int) -> str:
    """'FLAC 24bit/96kHz', 'MP3 320kbps', 'DSD64'"""
    if not codec:
        return ""
    if codec == "DSD" and sr:
        return f"DSD{round(sr / 44100)}"
    khz = (f"{sr / 1000:g}kHz" if sr else "")
    if bits and codec not in ("MP3", "AAC", "Vorbis", "Opus", "WMA", "MPC", "AC3"):
        return f"{codec} {bits}bit/{khz}".rstrip("/")
    if kbps:
        return f"{codec} {kbps}kbps" + (f" {khz}" if sr and sr != 44100 else "")
    return f"{codec} {khz}".strip()


def guess_from_name(path: str) -> tuple[str, str]:
    """'아티스트 - 제목.mp3' → (artist, title)."""
    stem = Path(path).stem
    if " - " in stem:
        a, t = stem.split(" - ", 1)
        # '01. 아티스트 - 제목' 앞 번호 제거
        a = a.lstrip("0123456789. _-")
        return a.strip(), t.strip()
    return "", stem.strip()


def _first(v):
    if v is None:
        return ""
    if isinstance(v, (list, tuple)):
        v = v[0] if v else ""
    return str(v).strip()


def _sylt_to_lrc(frame) -> str:
    out = []
    for text, t in getattr(frame, "text", []):
        ms = int(t)
        out.append(f"[{ms // 60000:02d}:{ms // 1000 % 60:02d}.{ms % 1000 // 10:02d}]{text}")
    return "\n".join(out)


def read_tags(path: str, want_cover: bool = False) -> TagInfo:
    info = TagInfo()
    ext = Path(path).suffix.lower()
    if ext == ".dff":
        info.codec = "DSD"
    if mutagen is not None:
        try:
            f = mutagen.File(path)
        except Exception as e:  # 손상 파일
            log.debug("tag read fail %s: %s", path, e)
            f = None
        if f is not None:
            _fill(info, f, want_cover)
    if not info.codec:
        info.codec = codec_from_ext(path)
    if not info.title:
        a, t = guess_from_name(path)
        info.title = t
        info.artist = info.artist or a
    return info


def _fill(info: TagInfo, f, want_cover: bool):
    tname = type(f).__name__
    info.codec = _CODEC_BY_TYPE.get(tname, "")
    st = getattr(f, "info", None)
    if st is not None:
        info.bits = int(getattr(st, "bits_per_sample", 0) or 0)
        if tname == "MP4":
            c = str(getattr(st, "codec", "") or "").lower()
            info.codec = "ALAC" if c.startswith("alac") else "AAC"
        if tname in ("MP3", "OggVorbis", "OggOpus", "ASF", "Musepack", "AAC") or info.codec == "AAC":
            info.bits = 0
        info.duration = float(getattr(st, "length", 0) or 0)
        br = getattr(st, "bitrate", 0) or 0
        info.bitrate = int(br // 1000) if br > 10000 else int(br)
        info.samplerate = int(getattr(st, "sample_rate", 0) or 0)
        info.channels = int(getattr(st, "channels", 0) or 0)
    tags = f.tags
    if tags is None:
        return
    keys = set(tags.keys()) if hasattr(tags, "keys") else set()
    # ID3 (mp3)
    if any(k.startswith(("TIT2", "TPE1", "USLT", "SYLT", "APIC")) for k in keys):
        info.title = _first(getattr(tags.get("TIT2"), "text", None))
        info.artist = _first(getattr(tags.get("TPE1"), "text", None))
        info.album = _first(getattr(tags.get("TALB"), "text", None))
        info.genre = _first(getattr(tags.get("TCON"), "text", None))
        info.year = _first(getattr(tags.get("TDRC"), "text", None))[:4]
        for k in keys:
            if k.upper().startswith("TXXX:REPLAYGAIN_"):
                info.rg[k[5:].lower()] = _first(getattr(tags[k], "text", None))
        sylt = [tags[k] for k in keys if k.startswith("SYLT")]
        uslt = [tags[k] for k in keys if k.startswith("USLT")]
        if sylt:
            info.lyrics = _sylt_to_lrc(sylt[0])
        elif uslt:
            info.lyrics = str(uslt[0].text or "")
        if want_cover:
            apic = [tags[k] for k in keys if k.startswith("APIC")]
            if apic:
                info.cover = bytes(apic[0].data)
        return
    # MP4 (m4a)
    if "\xa9nam" in keys or "\xa9ART" in keys:
        info.title = _first(tags.get("\xa9nam"))
        info.artist = _first(tags.get("\xa9ART"))
        info.album = _first(tags.get("\xa9alb"))
        info.lyrics = _first(tags.get("\xa9lyr"))
        info.genre = _first(tags.get("\xa9gen"))
        info.year = _first(tags.get("\xa9day"))[:4]
        for k in keys:
            if k.lower().startswith("----:com.apple.itunes:replaygain_"):
                v = tags[k][0] if tags[k] else b""
                info.rg[k.split(":")[-1].lower()] = v.decode("utf-8", "replace") if isinstance(v, (bytes, bytearray)) else str(v)
        if want_cover and tags.get("covr"):
            info.cover = bytes(tags["covr"][0])
        return
    # Vorbis comment (flac/ogg/opus)
    low = {k.lower(): k for k in keys}

    def g(name):
        k = low.get(name)
        return _first(tags.get(k)) if k else ""
    info.title = g("title")
    info.artist = g("artist")
    info.album = g("album")
    info.lyrics = g("lyrics") or g("unsyncedlyrics")
    info.genre = g("genre")
    info.year = (g("date") or g("year"))[:4]
    for name in ("replaygain_track_gain", "replaygain_track_peak", "replaygain_album_gain", "replaygain_album_peak"):
        if g(name):
            info.rg[name] = g(name)
    if want_cover:
        pics = getattr(f, "pictures", None)
        if pics:
            info.cover = bytes(pics[0].data)


# ---------------------------------------------------------------- 태그 편집 (C5)
EDITABLE = ("title", "artist", "album", "genre", "date", "tracknumber")


def write_tags(path: str, fields: dict) -> None:
    """mutagen easy 인터페이스로 저장 (mp3·flac·ogg·opus·m4a). 빈 값은 그 태그 삭제. 실패 시 예외"""
    if mutagen is None:
        raise RuntimeError("mutagen 없음")
    f = mutagen.File(path, easy=True)
    if f is None:
        raise ValueError("지원하지 않는 파일")
    if f.tags is None:
        f.add_tags()
    for k, v in fields.items():
        if k not in EDITABLE:
            continue
        v = (v or "").strip()
        if v:
            f[k] = [v]
        elif k in f:
            del f[k]
    f.save()


def codec_from_ext(path: str) -> str:
    """태그를 못 읽을 때 확장자로 형식 이름"""
    e = Path(path).suffix.lower().lstrip(".")
    return {"m4a": "AAC", "oga": "Vorbis", "ogg": "Vorbis", "aif": "AIFF", "aiff": "AIFF", "aifc": "AIFF",
            "wv": "WavPack", "dsf": "DSD", "dff": "DSD", "mka": "MKA"}.get(e, e.upper())
