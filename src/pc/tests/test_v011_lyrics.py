# -*- coding: utf-8 -*-
"""vr0.1.0.011 — 가사 (f18): 알송 프로토콜 수정 · 검색어 변형 · 점수 · LRCLIB · 동시 조회 · 실패 기억 · 이유 · 진단 · NetEase"""
import time
import urllib.error
from pathlib import Path

import pytest

from yamp.lyrics import lrc, query as Q, score as S
from yamp.lyrics.providers import alsong as A, lrclib as LB, netease as NE
from yamp.lyrics.providers.base import NetError, Query
from yamp.lyrics.service import LyricsCache, NotFoundStore, Result, resolve_full

TD = Path(__file__).resolve().parents[2] / "testdata"


# ---------------------------------------------------------------- 공용 벡터
def test_query_cases_shared():
    n = 0
    for line in (TD / "lyrics_query_cases.txt").read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        f = line.split("|")
        i = f.index("=>")
        t, a, rest = f[0], f[1], f[i + 1:]
        want = [(rest[k], rest[k + 1]) for k in range(0, len(rest), 2)]
        assert Q.variants(t, a) == want, line
        n += 1
    assert n >= 20


def test_score_cases_shared():
    n = 0
    for line in (TD / "lyrics_score_cases.txt").read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        f = line.split("|")
        got = S.score(f[0], f[1], f[2], float(f[3]), f[4], f[5], f[6], f[7].replace("\\n", "\n"), float(f[8]))
        assert got == int(f[9]), line
        n += 1
    assert n >= 12


# ---------------------------------------------------------------- 알송 (C1·C2)
def test_alsong_resemble2_real_tag_parsed():
    items = A.parse_search_response((TD / "alsong_resemble2.xml").read_bytes())
    assert [d["id"] for d in items] == ["111", "222"]
    assert items[1]["lyric"] == "[00:01.00]어쩜\n[00:01.00]eojjeom\n[00:03.00]이렇게"
    best = A.pick_best(items, "좋은 날", "아이유", "Real", 233)
    assert best["id"] == "222" and best["score"] >= 55
    assert A.parse_search_response((TD / "alsong_empty.xml").read_bytes()) == []
    lst = A.parse_search_response((TD / "alsong_list2.xml").read_bytes())
    assert lst[1]["id"] == "9002" and lst[1]["duration"] == 233.0 and lst[1]["lyric"] == ""
    for f in ("alsong_byid2.xml", "alsong_lyric7.xml"):
        assert A.parse_lyric_response((TD / f).read_bytes()) == "[00:01.00]어쩜\n[00:03.00]이렇게"


def test_alsong_requests_have_encdata_and_new_methods():
    assert A.enc_value("") == A.BUILTIN_ENC and A.enc_value("off") == "" and A.enc_value(" X ") == "X"
    x7 = A.build_lyric_request("abc", A.BUILTIN_ENC).decode()
    assert "<ns1:GetLyric7><ns1:encData>7c2d15b8" in x7 and "<ns1:strChecksum>abc</ns1:strChecksum>" in x7
    xs = A.build_search_request("제목 & <x>", "가수", 0, "E").decode()
    assert "<ns1:GetResembleLyric2><ns1:encData>E</ns1:encData><ns1:stQuery><ns1:strTitle>제목 &amp; &lt;x&gt;" in xs
    xl = A.build_list_request("t", "a", 1, "E").decode()
    assert "<ns1:GetResembleLyricList2><ns1:encData>E</ns1:encData><ns1:title>t</ns1:title><ns1:artist>a</ns1:artist>" \
           "<ns1:pageNo>1</ns1:pageNo>" in xl
    assert "<ns1:GetLyricByID2><ns1:encData>E</ns1:encData><ns1:lyricID>9002</ns1:lyricID>" in \
           A.build_byid_request(9002, "E").decode()


def _fake_alsong(monkeypatch, routes, calls):
    def post(payload, timeout, method=""):
        calls.append(method)
        r = routes.get(method)
        if isinstance(r, Exception):
            raise r
        return (TD / r).read_bytes() if r else (TD / "alsong_empty.xml").read_bytes()
    monkeypatch.setattr(A, "_post", post)


def test_alsong_provider_resemble2(monkeypatch):
    calls = []
    _fake_alsong(monkeypatch, {"GetResembleLyric2": "alsong_resemble2.xml"}, calls)
    p = A.AlsongProvider(1, "")
    c = p.candidates(Query("/x/a.flac", "좋은 날 (Good Day) [MV]", "아이유 (IU)", "Real", 233))
    assert calls[0] == "GetResembleLyric2"                    # flac → MD5 안 함
    best = max(c, key=lambda d: d["score"])
    assert best["title"] == "좋은 날" and best["score"] >= 55 and best["source"] == "alsong"
    assert "이렇게" in p.fetch(Query("/x/a.flac", "좋은 날", "아이유", "Real", 233))


def test_alsong_provider_list2_byid2_fallback(monkeypatch):
    calls = []
    _fake_alsong(monkeypatch, {"GetResembleLyricList2": "alsong_list2.xml", "GetLyricByID2": "alsong_byid2.xml"}, calls)
    c = A.AlsongProvider(1, "").candidates(Query("/x/a.flac", "좋은 날", "아이유", "Real", 233))
    assert calls[:3] == ["GetResembleLyric2", "GetResembleLyricList2", "GetLyricByID2"]
    assert c and c[0]["id"] == "9002" and c[0]["score"] >= 55


def test_alsong_md5_lyric7_then_5(monkeypatch, tmp_path):
    mp3 = tmp_path / "a.mp3"
    mp3.write_bytes(b"\xff\xfb" + bytes(range(256)) * 700)
    calls = []
    _fake_alsong(monkeypatch, {"GetLyric5": "alsong_lyric7.xml"}, calls)
    c = A.AlsongProvider(1, "").candidates(Query(str(mp3), "x", "y"))
    assert calls[:2] == ["GetLyric7", "GetLyric5"] and c[0]["via"] == "md5" and c[0]["score"] == 100


def test_alsong_all_network_errors_raise(monkeypatch):
    calls = []
    err = urllib.error.URLError("down")
    _fake_alsong(monkeypatch, {m: err for m in ("GetResembleLyric2", "GetResembleLyricList2")}, calls)

    def post(payload, timeout, method=""):
        raise err
    monkeypatch.setattr(A, "_post", post)
    with pytest.raises(NetError):
        A.AlsongProvider(1, "").candidates(Query("/x/a.flac", "좋은 날", "아이유"))


# ---------------------------------------------------------------- LRCLIB (C4)
def test_lrclib_no_album_and_q_fallback(monkeypatch):
    seen = []

    def get(self, path, params):
        seen.append((path, dict(params)))
        if path == "get":
            return None                                         # 404
        if "q" in params:
            return [{"id": 7, "trackName": "좋은 날", "artistName": "IU", "albumName": "Real", "duration": 234,
                     "syncedLyrics": "[00:01.00]어쩜"}]
        return []
    monkeypatch.setattr(LB.LrclibProvider, "_get", get)
    c = LB.LrclibProvider(1).candidates(Query("", "좋은 날", "아이유 (IU)", "Real 앨범", 233))
    assert all("album_name" not in p for _, p in seen)
    assert seen[0] == ("get", {"track_name": "좋은 날", "artist_name": "아이유 (IU)", "duration": 233})
    assert any("q" in p for _, p in seen) and c[0]["score"] >= 55


# ---------------------------------------------------------------- NetEase (L10)
def test_netease_parse_and_translation_merge():
    songs = NE.parse_search({"result": {"songs": [{"id": 5, "name": "Ditto", "artists": [{"name": "NewJeans"}],
                                                   "album": {"name": "OMG"}, "duration": 185000}]}})
    assert songs == [{"id": 5, "title": "Ditto", "artist": "NewJeans", "album": "OMG", "duration": 185.0}]
    txt = NE.parse_lyric({"lrc": {"lyric": "[00:01.00]Stay in the middle\n[00:03.50]Like you a little"},
                          "tlyric": {"lyric": "[00:01.00]가운데 있어\n[00:03.50]조금 좋아"}})
    ly = lrc.parse(txt)
    assert ly.blocks[0].lines == ["Stay in the middle", "가운데 있어"] and ly.blocks[1].t_ms == 3500


# ---------------------------------------------------------------- 단어 시각 (C9)
def test_word_timing_stripped():
    ly = lrc.parse("[00:01.00]<00:01.00>안녕 <00:01.50>하세요\n[00:02.00]<00:02.00>Hi")
    assert ly.blocks[0].lines == ["안녕 하세요"] and ly.blocks[1].lines == ["Hi"]


# ---------------------------------------------------------------- 동시 조회 · 이유 · 실패 기억 (L5~L7)
class _R:
    remote = True

    def __init__(self, name, cands=None, err=None, delay=0.0):
        self.name, self.cands, self.err, self.delay, self.calls = name, cands or [], err, delay, 0

    def candidates(self, q, variants=None):
        self.calls += 1
        if self.delay:
            time.sleep(self.delay)
        if self.err:
            raise self.err
        return [dict(c) for c in self.cands]

    def fetch(self, q):
        return None


def _c(src, score, lyric="[00:01.00]가사"):
    return {"source": src, "title": "t", "artist": "a", "album": "", "lyric": lyric, "score": score, "synced": True}


def test_resolve_full_picks_best_concurrently(tmp_path):
    cache = LyricsCache(tmp_path / "c")
    q = Query(str(tmp_path / "s.flac"), "제목", "가수", "", 200)
    a, b = _R("alsong", [_c("alsong", 70, "[00:01.00]알송")]), _R("lrclib", [_c("lrclib", 90, "[00:01.00]립")])
    t0 = time.monotonic()
    slow = _R("netease", [_c("netease", 99)], delay=3.0)
    res = resolve_full(q, [a, b, slow], cache, timeout_s=1.0)
    assert time.monotonic() - t0 < 2.5                      # 느린 공급자를 기다리지 않음
    assert res.lyrics is not None and res.source == "lrclib" and res.score == 90
    assert "netease: 시간 초과" in res.errors
    assert cache.get(q)[1] == "lrclib"
    assert res.status_text() == "가사: LRCLIB · 90점"


def test_resolve_full_reasons_and_notfound(tmp_path):
    q = Query(str(tmp_path / "s.flac"), "제목", "가수", "", 200)
    nf = NotFoundStore(tmp_path / "nf.json", 7)
    off = resolve_full(q, [_R("alsong", err=NetError("연결 실패")), _R("lrclib", err=NetError("연결 실패"))], None,
                       notfound=nf, timeout_s=1)
    assert off.reason == "offline" and nf.age_days(__import__("yamp.lyrics.service", fromlist=["x"]).cache_key(q.path)) is None
    low = resolve_full(q, [_R("alsong", [_c("alsong", 40)])], None, notfound=nf, timeout_s=1)
    assert low.reason == "low_score" and low.lyrics is None and len(low.candidates) == 1
    again = resolve_full(q, [_R("alsong", [_c("alsong", 99)])], None, notfound=nf, timeout_s=1)
    assert again.reason == "remembered" and "0일 전 확인" in again.status_text()
    forced = resolve_full(q, [_R("alsong", [_c("alsong", 99)])], None, use_cache=False, notfound=nf, timeout_s=1)
    assert forced.lyrics is not None                         # 다시 찾기는 기억 무시 · 찾으면 기억 지움
    assert resolve_full(q, [_R("alsong", [_c("alsong", 99)])], None, notfound=nf, timeout_s=1).lyrics is not None
    srv = resolve_full(q, [_R("alsong", err=NetError("HTTP 500"))], None, timeout_s=1)
    assert srv.reason == "server" and "진단" in srv.status_text()
    assert resolve_full(q, [], None).reason == "disabled"
    assert Result(None, "not_found").status_text() == "맞는 가사를 못 찾음"


def test_notfound_store_expiry(tmp_path):
    nf = NotFoundStore(tmp_path / "nf.json", 7)
    nf.add("k", now=1000.0)
    assert nf.age_days("k", now=1000.0 + 2 * 86400) == 2
    assert nf.age_days("k", now=1000.0 + 8 * 86400) is None
    assert NotFoundStore(tmp_path / "nf.json", 7).age_days("k", now=1000.0) == 0        # 파일에서 다시 읽음
    nf0 = NotFoundStore(tmp_path / "nf0.json", 0)
    nf0.add("k")
    assert nf0.age_days("k") is None


def test_cache_backs_up_user_lyrics_and_save_beside(tmp_path):
    cache = LyricsCache(tmp_path / "c")
    song = tmp_path / "m" / "곡.flac"
    song.parent.mkdir()
    song.write_bytes(b"x")
    q = Query(str(song), "제목", "가수", "", 200)
    cache.put(q, "[00:01.00]내가 고친 가사", "user")
    res = resolve_full(q, [_R("lrclib", [_c("lrclib", 90, "[00:01.00]새 가사")])], cache, use_cache=False,
                       timeout_s=1, save_beside=True)
    assert res.lyrics.blocks[0].lines == ["새 가사"]
    bak = list((tmp_path / "c").glob("*.user.bak"))
    assert bak and "내가 고친 가사" in bak[0].read_text(encoding="utf-8")
    assert (tmp_path / "m" / "곡.lrc").read_text(encoding="utf-8").startswith("[00:01.00]새 가사")


def test_diag_report(tmp_path, monkeypatch):
    from yamp.core.config import Config
    from yamp.lyrics import diag, service
    cfg = Config(tmp_path)
    monkeypatch.setattr(service, "build_providers", lambda c, log_fn=None: [_R("alsong", [_c("alsong", 88)])])
    monkeypatch.setattr(diag, "build_providers", lambda c, log_fn=None: [_R("alsong", [_c("alsong", 88)])])
    text, saved = diag.run(cfg, Query(str(tmp_path / "s.mp3"), "좋은 날 [MV]", "아이유"), tmp_path / "log")
    assert "검색어 : 좋은 날 [MV] / 아이유 | 좋은 날 / 아이유" in text and "88점" in text and "결과: 찾음" in text
    assert saved and Path(saved).read_text(encoding="utf-8") == text


def test_config_lyrics_keys(tmp_path):
    from yamp.core.config import Config
    c = Config(tmp_path)
    assert c["lyrics_timeout_s"] == 6 and c["lyrics_min_score"] == 55 and c["lyrics_notfound_days"] == 7
    assert c["lyrics_netease"] is False and c["lyrics_save_beside"] is False and c["alsong_enc_data"] == ""


@pytest.fixture
def app():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_diag_dialog_and_menu(app, tmp_path, monkeypatch):
    import os
    os.environ["YAMP_HOME"] = str(tmp_path)
    from yamp.core.config import Config
    from yamp.app.controller import Controller
    from yamp.lyrics import diag
    from yamp.ui.lyrics_diag import LyricsDiagDialog
    monkeypatch.setattr(diag, "run", lambda cfg, q, d=None, cache=None: ("보고서 내용", str(tmp_path / "x.txt")))
    c = Controller(Config(tmp_path))
    try:
        c.lyrics.last_query = Query(str(tmp_path / "a.mp3"), "t", "a")
        d = LyricsDiagDialog(c)
        d._pool.waitForDone(3000)
        app.processEvents()
        assert d.text.toPlainText() == "보고서 내용" and "x.txt" in d.status.text()
        d.done(0)
    finally:
        c.shutdown()


def test_request_timeouts_bounded_by_deadline(monkeypatch, tmp_path):
    """v011b: 요청 1건 제한 시간이 전체 마감을 넘지 않음 (느린 인터넷에서 곡 넘김·종료가 오래 걸리지 않게)"""
    import urllib.request
    seen = []

    def slow(req, data=None, timeout=None, **k):
        seen.append(timeout)
        time.sleep(min(timeout, 0.4))
        raise urllib.error.URLError("느린 인터넷 흉내")
    monkeypatch.setattr(urllib.request, "urlopen", slow)
    q = Query(str(tmp_path / "a.flac"), "좋은 날 (Good Day)", "아이유 (IU)", "", 233)
    t0 = time.monotonic()
    res = resolve_full(q, [A.AlsongProvider(6, ""), LB.LrclibProvider(6), NE.NeteaseProvider(6)], None, timeout_s=1.0)
    assert time.monotonic() - t0 < 2.0 and res.lyrics is None and res.reason in ("offline", "server")
    time.sleep(1.2)                                      # 남은 요청이 마감 뒤 곧 끝남
    assert seen and max(seen) <= 1.05


def test_tests_have_no_network():
    """conftest 가 테스트 중 인터넷을 막음 (Windows 빌드에서 테스트가 수십 분 걸리던 원인)"""
    import urllib.request
    with pytest.raises(urllib.error.URLError):
        urllib.request.urlopen("http://lyrics.alsong.co.kr/", timeout=1)
