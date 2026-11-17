# -*- coding: utf-8 -*-
"""vr0.1.0.022 (f43 · f44) 남은 추천 모아서 진행 — N1~N7"""
import os
import time
from pathlib import Path

import numpy as np
import pytest


@pytest.fixture(scope="module")
def app():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _wait(app, cond, ms=3000):
    t = time.monotonic() + ms / 1000
    while time.monotonic() < t:
        app.processEvents()
        if cond():
            return True
        time.sleep(0.01)
    return cond()


def _png(color=0xFF3366AA, w=40, h=30) -> bytes:
    from PyQt6.QtCore import QBuffer, QByteArray, QIODevice
    from PyQt6.QtGui import QImage
    img = QImage(w, h, QImage.Format.Format_ARGB32)
    img.fill(color)
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    img.save(buf, "PNG")
    return bytes(ba)


# ---------------------------------------------------------------- N1 표지 디코드 백그라운드
def test_cover_decoded_in_background_latest_wins(tmp_path, app):
    os.environ["YAMP_HOME"] = str(tmp_path)
    from yamp.app.mainwindow import MainWindow
    from yamp.app.win_now import decode_cover
    from yamp.core.config import Config
    from yamp.data.tags import TagInfo
    from yamp.data.track import Track
    cfg = Config(tmp_path)
    cfg["topbar_ticker"] = False
    w = MainWindow(cfg)
    try:
        big = decode_cover(_png(w=1600, h=900))
        assert big is not None and max(big.width(), big.height()) == 800          # 800px 까지만
        assert decode_cover(b"not an image") is None and decode_cover(b"") is None
        t = Track("/m/a.mp3", "A")
        w.load_cover(t, TagInfo(album="X", cover=_png(0xFFFF0000)))
        w.load_cover(t, TagInfo(album="Y", cover=_png(0xFF00FF00)))             # 빨리 넘김 → 마지막 곡 표지만
        assert _wait(app, lambda: getattr(w, "_cover_src", None) is not None and w._cover_pool.activeThreadCount() == 0)
        app.processEvents()
        assert w._cover_src.pixelColor(1, 1).green() == 255 and w._cover_ph == "Y"
        w.load_cover(t, TagInfo(album="Z"))                                         # 표지 없는 곡 → 바로 비움
        assert w._cover_src is None and not w.cover.pixmap().isNull()             # 단순 배치: 첫 글자 칸
    finally:
        w.ctrl.shutdown()
        w.close()


# ---------------------------------------------------------------- N2 테마 표 분리
def test_themes_split_compat():
    from yamp.ui import skin, themes
    assert skin.SKINS is themes.SKINS and skin.Skin is themes.Skin and skin.DEFAULT == themes.DEFAULT
    src = (Path(skin.__file__)).read_text(encoding="utf-8")
    import re
    assert not re.search(r"#[0-9a-fA-F]{6}\b", src)            # 색 값은 themes.py 에만


# ---------------------------------------------------------------- N3 자동 가사 캐시 정리
def test_lyrics_cache_trim_keeps_user_and_recent(tmp_path):
    from yamp.core.keys import cache_key
    from yamp.lyrics.cache import LyricsCache, source_of
    from yamp.lyrics.providers.base import Query
    c = LyricsCache(tmp_path)
    qs = [Query(f"/m/{i}.mp3", f"t{i}", "a", "", 100, "") for i in range(12)]
    for i, q in enumerate(qs):
        c.put(q, f"[00:01.00]{i}", "user" if i in (0, 1) else "alsong")
        os.utime(c.path_for(q), (1_000_000 + i, 1_000_000 + i))                  # 0 이 가장 오래됨
    assert source_of(c.path_for(qs[0])) == "user" and source_of(c.path_for(qs[5])) == "alsong"
    c.get(qs[2])                                                                  # 최근 사용 → 남아야 함
    assert c.trim(0) == 0                                                         # 0 = 제한 없음
    assert c.trim(8) == 4
    left = {p.stem.rsplit("__", 1)[-1] for p in tmp_path.glob("*.lrc")}
    keep = {cache_key(qs[i].path) for i in (0, 1, 2, 7, 8, 9, 10, 11)}
    assert left == keep                                                           # 직접 편집 2 + 최근 사용 1 + 최신 5
    assert c.get(qs[3]) is None and c.get(qs[0]) is not None                     # 색인도 맞음
    assert c.trim(8) == 0


def test_config_has_lyrics_cache_max():
    from yamp.core.config_schema import DEFAULT_CONFIG_TEXT, FILE_DEFAULTS, LIMITS
    assert FILE_DEFAULTS["lyrics_cache_max"] == 5000 and LIMITS["lyrics_cache_max"] == (0, 1_000_000)
    assert "lyrics_cache_max = 5000" in DEFAULT_CONFIG_TEXT


# ---------------------------------------------------------------- N4 재생 목록 검색: 큰 목록만 입력이 멈춘 뒤
def test_playlist_filter_debounced_only_for_big_lists(app):
    from yamp.data.playlist import Playlist
    from yamp.data.track import Track
    from yamp.ui.playlist_view import PlaylistModel
    pl = Playlist()
    pl.items = [Track(f"/m/{i}.mp3", f"song{i}") for i in range(50)]
    m = PlaylistModel(pl)
    m.request_filter("song1")
    assert m.rowCount() == 11                                                    # 작은 목록: 바로 (전과 같음)
    pl.items = [Track(f"/m/{i}.mp3", f"song{i}") for i in range(3000)]
    m.request_filter("")
    m.request_filter("song29")
    assert m.rowCount() == 11                                                    # 큰 목록: 아직 그대로
    assert _wait(app, lambda: m.rowCount() == 111, 1500)
    assert m.filter == "song29" and m.rowCount() == 111                          # song29, song290~299, song2900~2999


# ---------------------------------------------------------------- N5 앨범 격자: 보이는 칸만 찾기
def test_album_visible_rows_same_as_full_scan(app):
    from yamp.ui.album_grid import AlbumGrid
    g = AlbumGrid()
    g.resize(700, 500)
    g.show()
    g.set_side(90)
    g.set_rows([{"key": f"k{i}", "album": f"A{i:04d}", "artist": "", "path": "", "cue_no": 0} for i in range(600)])
    app.processEvents()
    sb = g.verticalScrollBar()
    for v in (0, sb.maximum() // 3, sb.maximum() // 2, sb.maximum()):
        sb.setValue(v)
        app.processEvents()
        vp = g.viewport().rect()
        full = [i for i in range(g.count()) if g.visualItemRect(g.item(i)).intersects(vp)]
        assert g.visible_rows() == full and full
    g.close()


# ---------------------------------------------------------------- N6 Qt 엔진 스펙트럼: 버퍼 끝만 변환
def test_buffer_to_mono_tail_same(app):
    from PyQt6.QtCore import QByteArray
    from PyQt6.QtMultimedia import QAudioBuffer, QAudioFormat
    from yamp.audio.visualizer import buffer_to_mono
    rng = np.random.default_rng(0)
    F = QAudioFormat.SampleFormat
    for sf, dt, ch in ((F.Int16, np.int16, 2), (F.Float, np.float32, 1), (F.Int32, np.int32, 2), (F.UInt8, np.uint8, 2)):
        f = QAudioFormat()
        f.setSampleFormat(sf)
        f.setChannelCount(ch)
        f.setSampleRate(44100)
        for frames in (100, 1024, 1500, 9000):
            data = (rng.random(frames * ch) - 0.5).astype(dt) if dt == np.float32 else \
                rng.integers(np.iinfo(dt).min, np.iinfo(dt).max, frames * ch, dtype=dt)
            b = QAudioBuffer(QByteArray(data.tobytes()), f)
            full, sr = buffer_to_mono(b)
            tail, _ = buffer_to_mono(b, 1024)
            assert sr == 44100 and np.array_equal(full[-1024:], tail), (sf, frames)


# ---------------------------------------------------------------- N7 시세 · 앨범 표지 작업 = core/bg
def test_ticker_error_path_via_bgtask(app, tmp_path):
    from yamp.app.ticker_service import TickerService
    from yamp.core.config import Config
    cfg = Config(tmp_path)
    cfg["topbar_ticker"] = True

    def boom(markets, timeout):
        raise OSError("getaddrinfo failed")
    s = TickerService(cfg, fetch=boom)
    s.refresh()
    s._pool.waitForDone(3000)
    assert _wait(app, lambda: not s._busy)
    assert s.fails == 1 and s.error == "인터넷 연결 없음"


def test_album_cover_job_via_bgtask(app, tmp_path):
    from yamp.ui import album_grid as AG
    g = AG.AlbumGrid()
    got = []
    g._on_cover = lambda alb, img: got.append((alb, img.width()))
    g._gen = 5
    assert g._cover_work("A", str(tmp_path / "x.mp3"), 64, 4) is None            # 옛 세대 → 건너뜀
    g._on_cover_bg(None)
    g._on_cover_bg(("B", AG.QImage(64, 64, AG.QImage.Format.Format_ARGB32)))
    assert got == [("B", 64)]
