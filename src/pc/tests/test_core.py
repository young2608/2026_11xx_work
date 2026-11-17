"""Qt 비의존 로직 테스트: LRC, 알송 MD5/SOAP, 플레이리스트, LRCLIB 선택, 가사 체인, 스펙트럼."""
import hashlib
import os
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("YAMP_HOME", str(Path(__file__).resolve().parent / "_home"))

from yamp.lyrics import lrc                                       # noqa: E402
from yamp.lyrics.providers import alsong                          # noqa: E402
from yamp.lyrics.providers.lrclib import pick                     # noqa: E402
from yamp.lyrics.providers.base import Provider, Query            # noqa: E402
from yamp.data.playlist import Playlist, Track, save_m3u, load_m3u, fmt_time   # noqa: E402
from yamp.data.tags import guess_from_name                       # noqa: E402
from yamp.audio.visualizer import compute_bands                   # noqa: E402
from yamp.core.version import version_label, VERSION              # noqa: E402

# ---------------------------------------------------------------- LRC (Android LrcTest 와 동일 케이스)
SAMPLE = """[ti:노래]
[ar:가수]
[offset:+200]
[00:01.00]첫 줄
[00:05.50][00:20.50]반복 줄
[00:10.123]세 번째
[00:10.123]third (번역)
[00:15]초만
[01:02:50]콜론 소수
"""


def test_lrc_parse_basic():
    ly = lrc.parse(SAMPLE, "t")
    assert ly.synced
    assert ly.meta["ti"] == "노래" and ly.meta["ar"] == "가수"
    # offset +200 → 200ms 빠르게
    assert [b.t_ms for b in ly.blocks] == [800, 5300, 9923, 14800, 20300, 62300]
    assert ly.blocks[2].lines == ["세 번째", "third (번역)"]
    assert ly.blocks[4].lines == ["반복 줄"]


def test_lrc_index_at():
    ly = lrc.parse("[00:01.00]a\n[00:02.00]b\n[00:03.00]c")
    assert ly.index_at(0) == -1
    assert ly.index_at(1000) == 0
    assert ly.index_at(2999) == 1
    assert ly.index_at(99999) == 2


def test_lrc_frac_variants():
    ly = lrc.parse("[00:01.5]a\n[00:02.50]b\n[00:03.500]c")
    assert [b.t_ms for b in ly.blocks] == [1500, 2500, 3500]


def test_lrc_plain_and_empty():
    ly = lrc.parse("\n\n가사 한 줄\n두 번째\n\n")
    assert not ly.synced and len(ly.blocks) == 2 and ly.index_at(5000) == -1
    assert lrc.is_empty(lrc.parse(""))
    assert lrc.is_empty(None)


def test_lrc_roundtrip():
    ly = lrc.parse("[00:01.00]a\n[00:01.00]b\n[00:02.30]c")
    ly2 = lrc.parse(ly.to_lrc())
    assert [(b.t_ms, b.lines) for b in ly2.blocks] == [(b.t_ms, b.lines) for b in ly.blocks]


# ---------------------------------------------------------------- 알송
def _fake_mp3(tmp_path, with_id3=True, junk=7):
    body = bytes([0xFF, 0xFB, 0x90, 0x64]) + bytes((i * 7) % 256 for i in range(200000))
    head = b""
    if with_id3:
        size = 300
        ss = bytes([(size >> 21) & 0x7F, (size >> 14) & 0x7F, (size >> 7) & 0x7F, size & 0x7F])
        head = b"ID3\x03\x00\x00" + ss + b"\x00" * size
    p = tmp_path / "a.mp3"
    p.write_bytes(head + b"\x00" * junk + body)
    return p, body


def test_alsong_md5_skips_id3(tmp_path):
    p, body = _fake_mp3(tmp_path)
    assert alsong.audio_md5(str(p)) == hashlib.md5(body[:alsong.MD5_LEN]).hexdigest()


def test_alsong_md5_no_id3(tmp_path):
    p, body = _fake_mp3(tmp_path, with_id3=False, junk=0)
    assert alsong.audio_md5(str(p)) == hashlib.md5(body[:alsong.MD5_LEN]).hexdigest()


def test_alsong_md5_known_vector():
    """Android AlsongTest 와 같은 벡터 (offset 계산)."""
    head = b"ID3\x04\x00\x00\x00\x00\x00\x0a" + b"\x00" * 10 + b"\x00\x00\xff\xfb"
    assert alsong.audio_start_offset(head) == 22


def test_alsong_request_xml():
    x5 = alsong.build_lyric_request("abc").decode()
    assert "<ns1:GetLyric5>" in x5 and "<ns1:strChecksum>abc</ns1:strChecksum>" in x5
    x7 = alsong.build_lyric_request("abc", "ENC").decode()
    assert "<ns1:GetLyric7><ns1:encData>ENC</ns1:encData>" in x7
    xs = alsong.build_search_request("제목 & <x>", "가수").decode()
    assert "제목 &amp; &lt;x&gt;" in xs and "<ns1:nCurPage>0</ns1:nCurPage>" in xs


RESP = """<?xml version="1.0" encoding="utf-8"?><soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">
<soap:Body><GetLyric5Response xmlns="ALSongWebServer"><GetLyric5Result>true</GetLyric5Result>
<output><strInfoID>1</strInfoID><strTitle>노래</strTitle>
<strLyric>[00:01.00]첫 줄&lt;br&gt;[00:02.00]둘째 줄&lt;br&gt;[00:02.00]second</strLyric></output>
</GetLyric5Response></soap:Body></soap:Envelope>"""

SEARCH = """<?xml version="1.0" encoding="utf-8"?><soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">
<soap:Body><GetResembleLyric2Response xmlns="ALSongWebServer"><GetResembleLyric2Result>
<ST_SEARCHLYRIC_LIST><strTitle>다른 노래</strTitle><strArtistName>누구</strArtistName><strAlbumName/>
<strLyric>[00:01.00]x</strLyric></ST_SEARCHLYRIC_LIST>
<ST_SEARCHLYRIC_LIST><strTitle>좋은 날</strTitle><strArtistName>아이유</strArtistName><strAlbumName>Real</strAlbumName>
<strLyric>[00:01.00]어쩜&lt;br&gt;[00:03.00]이렇게</strLyric></ST_SEARCHLYRIC_LIST>
</GetResembleLyric2Result></GetResembleLyric2Response></soap:Body></soap:Envelope>"""


def test_alsong_parse_lyric():
    txt = alsong.parse_lyric_response(RESP.encode())
    ly = lrc.parse(txt)
    assert ly.synced and ly.blocks[1].lines == ["둘째 줄", "second"]


def test_alsong_parse_search_pick():
    items = alsong.parse_search_response(SEARCH.encode())
    assert len(items) == 2
    best = alsong.pick_best(items, "좋은 날", "아이유")
    assert best["album"] == "Real" and "이렇게" in best["lyric"]
    assert alsong.pick_best(items, "없는 곡", "없는 가수") is None


def test_alsong_empty_response():
    assert alsong.parse_lyric_response(b"<a><strLyric></strLyric></a>") is None
    assert alsong.parse_lyric_response(b"not xml") is None


# ---------------------------------------------------------------- LRCLIB
def test_lrclib_pick_prefers_synced_and_duration():
    items = [{"duration": 200, "plainLyrics": "p"},
             {"duration": 201, "syncedLyrics": "[00:01.00]s"},
             {"duration": 300, "syncedLyrics": "[00:01.00]far"}]
    assert pick(items, 200) == "[00:01.00]s"
    assert pick([{"duration": 400, "syncedLyrics": "x"}], 200) is None


# ---------------------------------------------------------------- 가사 체인
class _P(Provider):
    def __init__(self, name, txt):
        self.name, self.txt, self.calls = name, txt, 0

    def fetch(self, q):
        self.calls += 1
        return self.txt


class _Boom(Provider):
    name = "boom"

    def fetch(self, q):
        raise RuntimeError("x")


def test_resolve_chain_and_cache(tmp_path):
    from yamp.lyrics.service import resolve, LyricsCache
    cache = LyricsCache(tmp_path / "c")
    q = Query(str(tmp_path / "s.mp3"), "제목", "가수")
    a, b = _P("local", None), _P("alsong", "[00:01.00]hi")
    ly = resolve(q, [_Boom(), a, b], cache)
    assert ly.source == "alsong" and a.calls == 1 and b.calls == 1
    ly2 = resolve(q, [b], cache)          # 캐시 적중 → 공급자 호출 없음
    assert ly2.source == "alsong" and b.calls == 1
    assert ly2.blocks[0].lines == ["hi"]
    ly3 = resolve(q, [b], cache, use_cache=False)
    assert b.calls == 2 and ly3 is not None


def test_local_lrc_provider(tmp_path):
    from yamp.lyrics.providers.local import LocalLrcProvider
    mp3 = tmp_path / "곡.mp3"
    mp3.write_bytes(b"x")
    (tmp_path / "곡.lrc").write_bytes("[00:01.00]로컬".encode("cp949"))
    assert "로컬" in LocalLrcProvider().fetch(Query(str(mp3)))


# ---------------------------------------------------------------- 플레이리스트
def _pl(n):
    p = Playlist()
    p.items = [Track(f"/m/{i}.mp3") for i in range(n)]
    return p


def test_next_prev_repeat():
    p = _pl(3)
    p.current = 2
    assert p.next_index("off") is None
    assert p.next_index("off", manual=True) == 0
    assert p.next_index("all") == 0
    assert p.next_index("one") == 2
    assert p.next_index("one", manual=True) == 0
    p.current = 0
    assert p.prev_index() == 2


def test_shuffle_visits_all():
    p = _pl(10)
    p.current = 3
    seen = {3}
    for _ in range(9):
        p.current = p.next_index("all", True)
        seen.add(p.current)
    assert seen == set(range(10))


def test_remove_move_keep_current():
    p = _pl(5)
    p.current = 3
    cur = p.items[3]
    p.remove([0, 1])
    assert p.items[p.current] is cur and p.current == 1
    p.move(1, 0)
    assert p.items[p.current] is cur and p.current == 0


def test_m3u_roundtrip(tmp_path):
    (tmp_path / "a.mp3").write_bytes(b"x")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.flac").write_bytes(b"x")
    (tmp_path / "c.txt").write_bytes(b"x")
    p = Playlist()
    assert p.add_paths([str(tmp_path)]) == 2
    m = tmp_path / "l.m3u8"
    save_m3u(str(m), p.items)
    assert load_m3u(str(m)) == [t.path for t in p.items]


def test_misc():
    assert fmt_time(65) == "1:05" and fmt_time(3725) == "1:02:05"
    assert guess_from_name("/x/01. 아이유 - 좋은 날.mp3") == ("아이유", "좋은 날")
    assert version_label().startswith(VERSION + "__")


# ---------------------------------------------------------------- 스펙트럼
def test_spectrum_peak_band():
    sr = 44100
    t = np.arange(4096) / sr
    lv = compute_bands((0.8 * np.sin(2 * np.pi * 1000 * t)).astype(np.float32), sr)
    assert len(lv) == 24                      # v026: 24 밴드
    k = int(np.argmax(lv))
    assert lv[k] > 0.7 and lv[0] < 0.3       # 1kHz 근처만 큼
    assert compute_bands(np.zeros(10, dtype=np.float32), sr) == [0.0] * 24
