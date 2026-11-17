# -*- coding: utf-8 -*-
"""재생목록 파일 읽기 · 쓰기 — M3U/M3U8 · PLS · XSPF · WPL (vr0.1.0.019 R1 — data/playlist.py 에서 나눔, Qt 비의존)"""
import os
from pathlib import Path


def load_m3u(path: str) -> list[str]:
    p = Path(path)
    raw = p.read_bytes()
    for enc in ("utf-8-sig", "cp949", "latin-1"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    out = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        q = Path(line)
        if not q.is_absolute():
            q = p.parent / q
        out.append(str(q))
    return out


def _read_text(p: Path) -> str:
    raw = p.read_bytes()
    for enc in ("utf-8-sig", "utf-16", "cp949", "latin-1"):
        try:
            t = raw.decode(enc)
            if enc == "utf-16" and not raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
                continue
            return t
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1")


def _resolve(base: Path, ref: str) -> str | None:
    """재생목록 안의 경로 → 절대 경로. file:// URL 풀기, http(s) 등 원격은 무시(None)"""
    from urllib.parse import unquote, urlparse
    ref = ref.strip()
    if not ref:
        return None
    if "://" in ref:
        u = urlparse(ref)
        if u.scheme != "file":
            return None
        ref = unquote(u.path)
        if len(ref) > 2 and ref[0] == "/" and ref[2] == ":":   # file:///C:/x → C:/x
            ref = ref[1:]
    q = Path(ref.replace("\\", os.sep) if os.sep == "/" else ref)
    if not q.is_absolute() and not (len(ref) > 1 and ref[1] == ":"):
        q = base / q
    return str(q)


def load_pls(path: str) -> list[str]:
    """PLS: [playlist] File1=경로 ... (번호 순)"""
    p = Path(path)
    items = []
    for line in _read_text(p).splitlines():
        k, sep, v = line.strip().partition("=")
        if sep and k.lower().startswith("file") and k[4:].isdigit():
            r = _resolve(p.parent, v)
            if r:
                items.append((int(k[4:]), r))
    return [r for _n, r in sorted(items, key=lambda x: x[0])]


def _xml_paths(path: str, tag: str, attr: str | None) -> list[str]:
    import xml.etree.ElementTree as ET
    p = Path(path)
    try:
        root = ET.fromstring(_read_text(p).lstrip("\ufeff"))
    except ET.ParseError:
        return []
    out = []
    for el in root.iter():
        name = el.tag.rsplit("}", 1)[-1].lower()   # 네임스페이스 떼기
        if name != tag:
            continue
        v = el.get(attr) if attr else (el.text or "")
        r = _resolve(p.parent, v or "")
        if r:
            out.append(r)
    return out


def load_xspf(path: str) -> list[str]:
    """XSPF: <track><location>file:///...</location></track>"""
    return _xml_paths(path, "location", None)


def load_wpl(path: str) -> list[str]:
    """WPL (Windows Media Player): <media src="..."/>"""
    return _xml_paths(path, "media", "src")


def load_playlist(path: str) -> list[str]:
    e = Path(path).suffix.lower()
    if e == ".pls":
        return load_pls(path)
    if e == ".xspf":
        return load_xspf(path)
    if e == ".wpl":
        return load_wpl(path)
    return load_m3u(path)


def save_m3u(path: str, tracks) -> None:
    lines = ["#EXTM3U"]
    seen_cue = set()
    for t in tracks:
        if t.cue_no and t.cue_path:            # CUE 트랙은 .cue 파일 한 줄로 (불러올 때 다시 펼침)
            if t.cue_path in seen_cue:
                continue
            seen_cue.add(t.cue_path)
            lines.append(f"#EXTINF:-1,{t.album or Path(t.cue_path).stem}")
            lines.append(t.cue_path)
            continue
        dur = int(t.duration) if t.duration else -1
        lines.append(f"#EXTINF:{dur},{t.display}")
        lines.append(t.path)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    os.replace(tmp, path)
