"""알송 가사 (비공식 SOAP). Android Alsong.kt 와 같은 규칙.

⚠ ESTsoft 공식 공개 API 아님 — 오픈소스 구현들이 쓰는 방식. 개인 사용 용도.
   서버 쪽 변경 시 동작하지 않을 수 있음 → 설정에서 끌 수 있고, 실패 시 다른 공급자 결과 사용.

vr0.1.0.011 (f18 L1) — 검색 결과가 늘 0건이던 문제 수정
  1) mp3 오디오 MD5 (ID3v2 건너뛰고 첫 MPEG 프레임부터 163840 바이트) → GetLyric7 (encData) → 없으면 GetLyric5
  2) GetResembleLyric2 (encData + 제목·가수) → 응답 항목 ST_GET_RESEMBLELYRIC2_RETURN (옛 ST_SEARCHLYRIC_LIST 도 인식)
  3) 2) 가 0건이면 GetResembleLyricList2 → 고른 항목 GetLyricByID2
  encData: config alsong_enc_data 비어 있으면 내장 값 (MIT 오픈소스 alsong-lyrics 에 공개된 값), off = 안 보냄
응답 가사: "[mm:ss.xx]텍스트<br>[...]" → 줄바꿈으로 변환
진단: python main.py --lyrics-test "파일.mp3" (도구 → 가사 진단)
"""
import hashlib
import html
import logging
import re
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape

from .base import NetError, Provider, Query
from ..query import variants as make_variants
from ..score import MIN_SCORE, score as score_of

log = logging.getLogger("yamp.alsong")

URL = "http://lyrics.alsong.co.kr/alsongwebservice/service1.asmx"
# 공개 오픈소스(npm alsong-lyrics, MIT)에 실린 encData — 음원과 무관한 고정 값
BUILTIN_ENC = ("7c2d15b8f51ac2f3b2a37d7a445c3158455defb8a58d621eb77a3ff8ae4921318e49cefe24e515f79892a4c29c9a3e20"
               "4358698c1cfe79c151c04f9561e945096ccd1d1c0a8d8f265a2f3fa7995939b21d8f663b246bbc433c7589da7e68047524"
               "b80e16f9671b6ea0faaf9d6cde1b7dbcf1b89aa8a1d67a8bbc566664342e12")
MD5_LEN = 163840

_ENV_HEAD = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<SOAP-ENV:Envelope xmlns:SOAP-ENV="http://www.w3.org/2003/05/soap-envelope" '
    'xmlns:SOAP-ENC="http://www.w3.org/2003/05/soap-encoding" '
    'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
    'xmlns:xsd="http://www.w3.org/2001/XMLSchema" '
    'xmlns:ns2="ALSongWebServer/Service1Soap" xmlns:ns1="ALSongWebServer" '
    'xmlns:ns3="ALSongWebServer/Service1Soap12"><SOAP-ENV:Body>')
_ENV_TAIL = "</SOAP-ENV:Body></SOAP-ENV:Envelope>"


# ---------------------------------------------------------------- MD5
def audio_start_offset(head: bytes) -> int:
    """ID3v2 태그를 건너뛴 뒤 첫 프레임 동기(0xFFEx) 위치. 못 찾으면 태그 끝."""
    pos = 0
    if len(head) >= 10 and head[:3] == b"ID3":
        size = ((head[6] & 0x7F) << 21) | ((head[7] & 0x7F) << 14) | ((head[8] & 0x7F) << 7) | (head[9] & 0x7F)
        pos = 10 + size + (10 if head[5] & 0x10 else 0)
    end = min(len(head) - 1, pos + 65536)
    for i in range(pos, end):
        if head[i] == 0xFF and (head[i + 1] & 0xE0) == 0xE0:
            return i
    return pos


def audio_md5(path: str) -> str | None:
    try:
        with open(path, "rb") as f:
            head = f.read(10)
            if head[:3] == b"ID3" and len(head) == 10:
                size = ((head[6] & 0x7F) << 21) | ((head[7] & 0x7F) << 14) | ((head[8] & 0x7F) << 7) | (head[9] & 0x7F)
                f.seek(0)
                head = f.read(10 + size + 10 + 65536 + 2)
            else:
                f.seek(0)
                head = f.read(65536 + 2)
            start = audio_start_offset(head)
            f.seek(start)
            data = f.read(MD5_LEN)
        if len(data) < 1024:
            return None
        return hashlib.md5(data).hexdigest()
    except OSError:
        return None


# ---------------------------------------------------------------- SOAP
def enc_value(cfg_value: str) -> str:
    """config alsong_enc_data → 실제 encData ("" 이면 내장, off 면 없음)"""
    v = (cfg_value or "").strip()
    if v.lower() == "off":
        return ""
    return v or BUILTIN_ENC


def _enc(enc_data: str) -> str:
    return f"<ns1:encData>{escape(enc_data)}</ns1:encData>" if enc_data else ""


def _env(body: str) -> bytes:
    return (_ENV_HEAD + body + _ENV_TAIL).encode("utf-8")


def build_lyric_request(md5: str, enc_data: str = "") -> bytes:
    """MD5 매칭: encData 있으면 GetLyric7, 없으면 GetLyric5"""
    q = ("<ns1:stQuery>"
         f"<ns1:strChecksum>{escape(md5)}</ns1:strChecksum>"
         "<ns1:strVersion>3.46</ns1:strVersion>"
         "<ns1:strMACAddress>00ff667f9a08</ns1:strMACAddress>"
         "<ns1:strIPAddress>192.168.0.2</ns1:strIPAddress>"
         "</ns1:stQuery>")
    if enc_data:
        return _env(f"<ns1:GetLyric7>{_enc(enc_data)}{q}</ns1:GetLyric7>")
    return _env(f"<ns1:GetLyric5>{q}</ns1:GetLyric5>")


def build_search_request(title: str, artist: str, page: int = 0, enc_data: str = "") -> bytes:
    """GetResembleLyric2 (가사 본문까지 옴)"""
    return _env("<ns1:GetResembleLyric2>" + _enc(enc_data) + "<ns1:stQuery>"
                f"<ns1:strTitle>{escape(title)}</ns1:strTitle>"
                f"<ns1:strArtistName>{escape(artist)}</ns1:strArtistName>"
                f"<ns1:nCurPage>{int(page)}</ns1:nCurPage>"
                "</ns1:stQuery></ns1:GetResembleLyric2>")


def build_list_request(title: str, artist: str, page: int = 1, enc_data: str = "") -> bytes:
    """GetResembleLyricList2 (목록만: lyricID·제목·가수·앨범·길이)"""
    return _env("<ns1:GetResembleLyricList2>" + _enc(enc_data) +
                f"<ns1:title>{escape(title)}</ns1:title><ns1:artist>{escape(artist)}</ns1:artist>"
                f"<ns1:pageNo>{int(page)}</ns1:pageNo></ns1:GetResembleLyricList2>")


def build_byid_request(lyric_id, enc_data: str = "") -> bytes:
    return _env("<ns1:GetLyricByID2>" + _enc(enc_data) +
                f"<ns1:lyricID>{escape(str(lyric_id))}</ns1:lyricID></ns1:GetLyricByID2>")


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def clean_lyric(s: str) -> str:
    s = html.unescape(s or "")
    s = html.unescape(s) if "&lt;br" in s.lower() or "&amp;" in s else s     # 두 번 이스케이프된 응답
    s = re.sub(r"<br\s*/?>", "\n", s, flags=re.I)
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    return s.strip()


def _xml(xml_bytes: bytes):
    try:
        return ET.fromstring(xml_bytes)
    except ET.ParseError:
        return None


def parse_lyric_response(xml_bytes: bytes) -> str | None:
    """GetLyric5/7 · GetLyricByID2 응답 → 가사 (strLyric 또는 output/lyric)"""
    root = _xml(xml_bytes)
    if root is None:
        m = re.search(rb"<(?:strLyric|lyric)>(.*?)</(?:strLyric|lyric)>", xml_bytes or b"", re.S)
        return (clean_lyric(m.group(1).decode("utf-8", "replace")) or None) if m else None
    for el in root.iter():
        if _local(el.tag) in ("strLyric", "lyric"):
            txt = clean_lyric(el.text or "")
            if txt:
                return txt
    return None


ITEM_TAGS = ("ST_GET_RESEMBLELYRIC2_RETURN", "ST_SEARCHLYRIC_LIST")


def parse_search_response(xml_bytes: bytes) -> list[dict]:
    """GetResembleLyric2 응답 (가사 포함 항목) / GetResembleLyricList2 응답 (목록) 모두"""
    out = []
    root = _xml(xml_bytes)
    if root is None:
        return out
    for el in root.iter():
        if _local(el.tag) not in ITEM_TAGS:
            continue
        d = {_local(c.tag): (c.text or "") for c in el}
        out.append({
            "title": html.unescape(d.get("strTitle") or d.get("title") or ""),
            "artist": html.unescape(d.get("strArtistName") or d.get("artist") or ""),
            "album": html.unescape(d.get("strAlbumName") or d.get("album") or ""),
            "lyric": clean_lyric(d.get("strLyric") or d.get("lyric") or ""),
            "id": d.get("strInfoID") or d.get("lyricID") or d.get("infoID") or "",
            "duration": (int(d["playtime"]) / 1000) if (d.get("playtime") or "").isdigit() else 0.0,
        })
    return out


def item_tag_names(xml_bytes: bytes) -> list[str]:
    """진단용: 응답 Body 안 태그 이름들 (처음 12개)"""
    root = _xml(xml_bytes)
    if root is None:
        return ["(XML 아님)"]
    seen = []
    for el in root.iter():
        n = _local(el.tag)
        if n not in seen:
            seen.append(n)
    return seen[:12]


def pick_best(items: list[dict], title: str, artist: str, album: str = "", dur: float = 0.0,
              min_score: int = MIN_SCORE) -> dict | None:
    """점수(score.py) 최고 · min_score 이상 (가사 있는 항목만)"""
    best, bs = None, -999
    for d in items:
        if not d.get("lyric"):
            continue
        s = score_of(title, artist, album, dur, d["title"], d["artist"], d["album"], d["lyric"], d.get("duration", 0))
        if s > bs:
            best, bs = d, s
    if best is not None and bs >= min_score:
        return dict(best, score=bs)
    return None


def _post(payload: bytes, timeout: float, method: str = "") -> bytes:
    ct = "application/soap+xml; charset=utf-8" + (f'; action="ALSongWebServer/{method}"' if method else "")
    req = urllib.request.Request(URL, data=payload, method="POST", headers={
        "Content-Type": ct, "User-Agent": "gSOAP/2.7", "Accept-Charset": "utf-8"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


class AlsongProvider(Provider):
    name = "alsong"
    remote = True

    def __init__(self, timeout: float = 5.0, enc_data: str = "", min_score: int = MIN_SCORE, log_fn=None):
        self.timeout = timeout
        self.enc_data = enc_value(enc_data)
        self.min_score = min_score
        self.log = log_fn or (lambda s: None)        # 진단 기록

    def _call(self, payload: bytes, method: str) -> bytes:
        t0 = time.monotonic()
        self._n_calls = getattr(self, "_n_calls", 0) + 1
        try:
            b = _post(payload, self.call_timeout(), method)
        except urllib.error.HTTPError as e:
            self._n_err = getattr(self, "_n_err", 0) + 1
            self.log(f"알송 {method}: HTTP {e.code} ({(time.monotonic() - t0) * 1000:.0f}ms)")
            raise NetError(f"HTTP {e.code}") from e
        except Exception as e:  # noqa
            self._n_err = getattr(self, "_n_err", 0) + 1
            self.log(f"알송 {method}: 연결 실패 {e} ({(time.monotonic() - t0) * 1000:.0f}ms)")
            raise NetError(str(e)) from e
        self.log(f"알송 {method}: HTTP 200 · {len(b)} 바이트 · 태그 {', '.join(item_tag_names(b)[:8])} "
                 f"({(time.monotonic() - t0) * 1000:.0f}ms)")
        return b

    def _md5_lyric(self, path: str) -> str | None:
        if not path.lower().endswith(".mp3") or "|cue:" in path:
            return None
        md5 = audio_md5(path)
        self.log(f"알송 MD5: {md5 or '(계산 못 함)'}")
        if not md5:
            return None
        for enc in ([self.enc_data, ""] if self.enc_data else [""]):
            m = "GetLyric7" if enc else "GetLyric5"
            txt = parse_lyric_response(self._call(build_lyric_request(md5, enc), m))
            if txt:
                return txt
        return None

    def candidates(self, q: Query, variants=None) -> list[dict]:
        """후보 목록 (점수 포함). 네트워크 오류만 있고 결과가 없으면 NetError"""
        out: list[dict] = []
        self._n_calls = self._n_err = 0
        try:
            txt = self._md5_lyric(q.path)
            if txt:
                out.append({"source": "alsong", "title": q.title, "artist": q.artist, "album": q.album,
                            "lyric": txt, "duration": 0.0, "score": 100, "via": "md5"})
                return out
        except NetError:
            pass
        for t, a in (variants or make_variants(q.title, q.artist)):
            if time.monotonic() > getattr(self, "deadline", float("inf")):      # 전체 제한 시간 넘김 → 그만
                break
            items = []
            try:
                items = parse_search_response(self._call(build_search_request(t, a, 0, self.enc_data),
                                                         "GetResembleLyric2"))
                if not items:
                    lst = parse_search_response(self._call(build_list_request(t, a, 1, self.enc_data),
                                                           "GetResembleLyricList2"))
                    lst.sort(key=lambda d: -score_of(q.title, q.artist, q.album, q.duration, d["title"],
                                                     d["artist"], d["album"], "", d["duration"]))
                    for d in lst[:2]:                       # 상위 2개만 본문 가져옴
                        d["lyric"] = parse_lyric_response(self._call(build_byid_request(d["id"], self.enc_data),
                                                                     "GetLyricByID2")) or ""
                    items = [d for d in lst[:2] if d["lyric"]]
            except NetError:
                pass
            for d in items:
                if not d.get("lyric"):
                    continue
                s = score_of(q.title, q.artist, q.album, q.duration, d["title"], d["artist"], d["album"],
                             d["lyric"], d.get("duration", 0))
                out.append(dict(d, source="alsong", score=s, synced="[" in d["lyric"][:12]))
            self.log(f"알송 검색 '{t}' / '{a}': {len(items)}건, 최고 {max([c['score'] for c in out] or [0])}점")
            if out and max(c["score"] for c in out) >= self.min_score:
                break
        if not out and self._n_err:                       # 일부라도 오류였으면 "못 찾음" 으로 기억하지 않게
            raise NetError("알송 서버에 연결하지 못함")
        return out

    def fetch(self, q: Query):
        try:
            cands = self.candidates(q)
        except NetError:
            return None
        best = max(cands, key=lambda c: c["score"], default=None)
        return best["lyric"] if best and best["score"] >= self.min_score else None


def search_candidates(title: str, artist: str, timeout: float = 5.0, enc_data: str = "", pages: int = 1,
                      album: str = "", duration: float = 0.0) -> list[dict]:
    """가사 후보 목록 ('다른 가사 찾기'). 네트워크 오류는 빈 목록"""
    p = AlsongProvider(timeout, enc_data, min_score=101)       # 101 = 끝까지 모든 변형 검색
    try:
        cands = p.candidates(Query("", title, artist, album, duration), make_variants(title, artist)[:2])
    except NetError as e:
        log.info("alsong candidates: %s", e)
        return []
    for c in cands:
        c.setdefault("synced", "[" in c["lyric"][:12])
    return cands
