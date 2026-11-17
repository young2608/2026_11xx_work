# -*- coding: utf-8 -*-
"""vr0.1.0.018 (f33 · f34) 성능 최적화 — 결과가 전과 같은지 + 반복 작업이 줄었는지"""
import os
import random
from collections import Counter

import numpy as np
import pytest


@pytest.fixture(scope="module")
def app():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


# ---------------------------------------------------------------- P6 파형 (전 구현과 같은 값)
def _old_chunks(bufs, per):
    chunks, acc, acc_n = [], 0.0, 0
    for a in bufs:
        i = 0
        while i < a.size:
            take = min(per - acc_n, a.size - i)
            acc = max(acc, float(a[i:i + take].max()))
            acc_n += take
            i += take
            if acc_n >= per:
                chunks.append(acc)
                acc, acc_n = 0.0, 0
    return chunks, acc, acc_n


def test_chunk_peaks_same_as_loop():
    from yamp.audio.waveform import chunk_peaks
    rng = np.random.default_rng(1)
    for per in (1, 7, 2205):
        bufs = [np.abs(rng.standard_normal(int(n))).astype(np.float32)
                for n in rng.integers(1, 9000, 25)]
        want = _old_chunks(bufs, per)
        acc, acc_n, got = 0.0, 0, []
        for a in bufs:
            acc, acc_n, done = chunk_peaks(a, per, acc, acc_n)
            got.extend(done)
        assert got == want[0] and acc == want[1] and acc_n == want[2]


def test_reduce_peaks_same_as_loop():
    from yamp.audio.waveform import reduce_peaks

    def old(chunks, n_bars=240):
        a = np.asarray(chunks, dtype=np.float32)
        edges = np.linspace(0, a.size, n_bars + 1).astype(int)
        out = np.array([a[edges[i]:max(edges[i + 1], edges[i] + 1)].max() for i in range(n_bars)], dtype=np.float32)
        top = float(out.max())
        if top <= 1e-6:
            return [0.0] * n_bars
        return [round(float(x), 3) for x in np.sqrt(out / top)]
    rng = np.random.default_rng(2)
    for n in (1, 5, 239, 240, 241, 999, 6000):
        ch = rng.random(n).tolist()
        assert reduce_peaks(ch) == old(ch)
    assert reduce_peaks([]) == []


# ---------------------------------------------------------------- P8 스펙트럼 (전 구현과 같은 값)
def test_compute_bands_same_as_before():
    """v026 (f51): 밴드 규칙이 바뀜 (낮은 밴드 보간 · RMS · +3 dB/옥타브) → compute_bands = FFT 크기 + vis_math.bands_from_mags"""
    from yamp.audio import visualizer as V
    from yamp.domain.vis_math import bands_from_mags

    def ref(mono, sr):
        x = mono[-V.FFT_N:]
        if x.size < V.FFT_N:
            x = np.pad(x, (V.FFT_N - x.size, 0))
        spec = np.abs(np.fft.rfft(x * np.hanning(V.FFT_N))) / (V.FFT_N / 4)
        return bands_from_mags(spec.tolist(), sr / V.FFT_N, V.N_BANDS, 60.0, 1.0)
    rng = np.random.default_rng(3)
    for sr in (8000, 22050, 44100, 48000, 96000):
        for n in (100, 700, 1024, 5000):
            x = (rng.random(n).astype(np.float32) - 0.5) * rng.random()
            assert np.allclose(V.compute_bands(x, sr), ref(x, sr), atol=1e-12)
    assert V.compute_bands(np.zeros(10, np.float32), 44100) == [0.0] * V.N_BANDS
    w, rms, pk = V.frame_stats(np.linspace(-1, 1, 2048).astype(np.float32))
    assert len(w) == V.WAVE_N and all(isinstance(v, float) for v in w)


# ---------------------------------------------------------------- P7 재생 막대 파형 (그림 같음 · 캐시)
def test_bars_played_rule():
    from yamp.ui.neon import bars_played
    rnd = random.Random(4)
    for _ in range(20000):
        n = rnd.randint(0, 700)
        f = rnd.choice([rnd.random(), rnd.randint(0, 2 * max(1, n)) / (2 * max(1, n)), 0.0, 1.0, 1.5, -0.2])
        assert bars_played(n, f) == sum(1 for k in range(n) if (k + 0.5) / n <= f)


def _old_paint_bars(ws, img):
    """v017 막대 그리기 (비교용 — 재생 위치선 · 구간 없이 막대만)"""
    from PyQt6.QtCore import QRectF
    from PyQt6.QtGui import QPainter
    p = QPainter(img)
    w, h = ws.width(), ws.height()
    frac = ws.pos_ms / ws.dur_ms
    r = 1.0
    bars = ws._bars(int(w * r), r)
    step = max(3, round(3 * r))
    bar_px = max(2, step - max(1, round(r)))
    mid_px = round(h * r / 2)
    maxh = max(2.0, (h - 4) * r)
    n = len(bars)
    for k, v in enumerate(bars):
        bh = max(2, int(round(v * maxh / 2)) * 2)
        p.fillRect(QRectF(k * step / r, (mid_px - bh // 2) / r, bar_px / r, bh / r),
                   ws.accent if (k + 0.5) / n <= frac else ws.rest)
    p.end()


def test_waveform_seek_same_pixels_and_cached(app):
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QImage
    from yamp.ui.neon import WaveformSeek
    ws = WaveformSeek()
    ws.resize(997, 44)
    ws.set_peaks([abs(np.sin(i / 7.0)) for i in range(240)])
    ws.dur_ms = 180_000
    for pos in (0, 1, 61_234, 90_000, 179_999, 180_000):
        ws.pos_ms = pos
        new = QImage(997, 44, QImage.Format.Format_ARGB32_Premultiplied)
        new.fill(Qt.GlobalColor.transparent)
        dur = ws.dur_ms                              # 위치선 · 구간은 전과 같은 코드 → 막대 부분만 비교
        p_sheets = ws._bar_sheets(997, 44, 1.0, ws.accent, ws.rest)
        from PyQt6.QtGui import QPainter
        from PyQt6.QtCore import QRectF
        from yamp.ui.neon import bars_played
        pm_play, pm_rest, n, step = p_sheets
        cut = min(pm_play.width(), bars_played(n, pos / dur) * step)
        q = QPainter(new)
        if cut:
            q.drawPixmap(QRectF(0, 0, cut, 44), pm_play, QRectF(0, 0, cut, 44))
        q.drawPixmap(QRectF(cut, 0, 997 - cut, 44), pm_rest, QRectF(cut, 0, 997 - cut, 44))
        q.end()
        old = QImage(997, 44, QImage.Format.Format_ARGB32_Premultiplied)
        old.fill(Qt.GlobalColor.transparent)
        _old_paint_bars(ws, old)
        assert new == old, pos
    # 캐시: 같은 크기 · 곡 · 색이면 그림을 다시 만들지 않음, 곡이 바뀌면 다시
    a = ws._bar_sheets(997, 44, 1.0, ws.accent, ws.rest)
    assert ws._bar_sheets(997, 44, 1.0, ws.accent, ws.rest) is a
    ws.set_peaks([0.5] * 100)
    assert ws._bar_sheets(997, 44, 1.0, ws.accent, ws.rest) is not a
    img = QImage(997, 44, QImage.Format.Format_ARGB32_Premultiplied)
    ws.render(img)                                   # 실제 paintEvent 도 오류 없이


# ---------------------------------------------------------------- P2 · P3 라이브러리 DB
def test_library_wal_and_rescan_skips_known(tmp_path):
    from yamp.data.library import Library
    from yamp.data.tags import TagInfo
    music = tmp_path / "m"
    (music / "a").mkdir(parents=True)
    for k in range(30):
        (music / "a" / f"{k:02d}.mp3").write_bytes(b"")
    lib = Library(tmp_path / "lib.db")
    assert lib.journal in ("wal", "delete", "memory", "truncate", "persist")   # 파일 시스템이 지원하면 wal
    calls = []

    def rt(p):
        calls.append(p)
        return TagInfo(title=os.path.basename(p))
    assert lib.scan([str(music)], rt) == 30 and len(calls) == 30
    calls.clear()
    assert lib.scan([str(music)], rt) == 0 and calls == []          # 이미 있는 곡은 태그를 읽지 않음
    assert len(lib.known_keys()) == 30
    (music / "a" / "new.mp3").write_bytes(b"")                        # 겹치는 폴더 두 개 → 새 곡은 한 번만
    assert lib.scan([str(music), str(music / "a")], rt) == 1 and len(calls) == 1
    os.remove(music / "a" / "new.mp3")
    assert lib.remove_missing() == 1
    for k in range(10):
        os.remove(music / "a" / f"{k:02d}.mp3")
    assert lib.remove_missing() == 10 and len(lib.known_keys()) == 20
    assert lib.remove_missing() == 0
    lib.close()
    from yamp.data.library import apply_pragmas, is_network_path
    assert is_network_path("//server/share/library.db") and not is_network_path(str(tmp_path / "x.db"))
    import sqlite3
    db = sqlite3.connect(str(tmp_path / "lib.db"))
    assert apply_pragmas(db, wal=False) == "delete"                     # 네트워크 위치 → WAL 끔
    db.close()


# ---------------------------------------------------------------- P4 · P5 폴더 스캔 (한 번에 형식 개수)
def test_scan_tracks_counts_match_folder_summary(tmp_path):
    from yamp.data.playlist import scan_tracks
    from yamp.ui.folder_view import folder_summary
    root = tmp_path / "r"
    (root / "sub").mkdir(parents=True)
    for n in ("a.mp3", "b.FLAC", "c.txt", ".mp3", "d.wav"):
        (root / n).write_bytes(b"")
    for n in ("x.ogg", "y.mp3"):
        (root / "sub" / n).write_bytes(b"")
    (root / "sub" / "album.cue").write_text('FILE "y.mp3" WAVE\n  TRACK 01 AUDIO\n    TITLE "t1"\n    INDEX 01 00:00:00\n'
                                             '  TRACK 02 AUDIO\n    TITLE "t2"\n    INDEX 01 01:00:00\n', encoding="utf-8")
    for rec in (False, True):
        c = Counter()
        ts = scan_tracks(str(root), rec, counts=c)
        n, want = folder_summary(str(root), recursive=rec)
        assert c == want
        assert [t.uid for t in ts] == [t.uid for t in scan_tracks(str(root), rec)]
    ts = scan_tracks(str(root), True)
    assert sum(1 for t in ts if t.cue_no) == 2 and not any(t.path.endswith("y.mp3") and not t.cue_no for t in ts)


def test_add_paths_files_first_same(tmp_path):
    from yamp.data.playlist import Playlist
    fs = []
    for n in ("1.mp3", "2.flac", "3.m4a"):
        (tmp_path / n).write_bytes(b"")
        fs.append(str(tmp_path / n))
    a, b = Playlist(), Playlist()
    assert a.add_paths(fs) == b.add_paths(fs, files_first=True) == 3
    assert [t.path for t in a.items] == [t.path for t in b.items]


def test_play_folder_uses_given_tracks(tmp_path, app):
    from yamp.app import ctl_library
    from yamp.data.playlist import Track

    class C(ctl_library.LibraryMixin):
        pass
    c = C()
    c.folder_tracks = lambda *a, **k: pytest.fail("폴더를 다시 돌면 안 됨")
    c._finish_record = lambda *_a: (_ for _ in ()).throw(StopIteration)
    with pytest.raises(StopIteration):
        c.play_folder(str(tmp_path), tracks=[Track(str(tmp_path / "a.mp3"))])


# ---------------------------------------------------------------- P1 라이브러리 탭 (지연 · 검색 디바운스)
def test_library_view_lazy_and_debounced(tmp_path, app):
    from pathlib import Path
    from PyQt6.QtCore import QObject, pyqtSignal
    from PyQt6.QtWidgets import QStackedWidget
    from yamp.core.config import Config
    from yamp.data.library import Library
    from yamp.ui.library_views import LibraryView

    base = tmp_path / "cfg"
    base.mkdir()
    cfg = Config(Path(base))

    class Ctl(QObject):
        libraryChanged = pyqtSignal()
        homeReady = pyqtSignal(object)

        def __init__(s):
            super().__init__()
            s.cfg = cfg
            s.library = Library(tmp_path / "l.db")
            for i in range(50):
                s.library.upsert(f"/m/a{i % 5}/s{i}.mp3", f"t{i}", f"artist{i % 5}", f"alb{i % 7}")
            s.queries = 0
            orig = s.library.all_tracks

            def counted():
                s.queries += 1
                return orig()
            s.library.all_tracks = counted

        def scan_library(s):
            pass

    ctl = Ctl()
    stack = QStackedWidget()
    other = QStackedWidget()
    lv = LibraryView(ctl)
    stack.addWidget(other)
    stack.addWidget(lv)
    stack.setCurrentWidget(other)                   # 라이브러리 탭이 안 보임
    stack.show()
    app.processEvents()
    q0 = ctl.queries
    ctl.libraryChanged.emit()
    ctl.libraryChanged.emit()
    assert ctl.queries == q0 and lv._dirty          # 안 보이면 DB 를 읽지 않음
    stack.setCurrentWidget(lv)                       # 탭을 열면 한 번
    app.processEvents()
    assert ctl.queries == q0 + 1 and not lv._dirty
    assert lv.tree.topLevelItemCount() == 5
    q1 = ctl.queries
    for ch in "artist3":                             # 글자마다 다시 만들지 않음
        lv.search.setText(lv.search.text() + ch)
    assert lv._search_t.isActive() and lv.tree.topLevelItemCount() == 5
    lv.reload()                                      # (타이머 대신 바로) — 캐시 사용, DB 다시 안 읽음
    assert ctl.queries == q1
    assert lv.tree.topLevelItemCount() == 1 and lv.tree.topLevelItem(0).childCount() == 10
    ctl.libraryChanged.emit()                        # 보이는 중 → 바로 새로
    assert ctl.queries == q1 + 1
    ctl.library.close()


# ---------------------------------------------------------------- P10 가사 블록 높이 (같은 값)
def test_lyrics_block_height_same(app):
    from PyQt6.QtGui import QFontMetrics
    from yamp.lyrics.lrc import parse as parse_lrc
    from yamp.ui import skin as skinmod
    from yamp.ui.lyrics_view import LyricsView
    v = LyricsView(skinmod.current(), 13)
    v.set_lyrics(parse_lrc("[00:01.00]가\n[00:02.00]나\n[00:03.00]다"))
    v.set_position(2100)
    for k in range(3):
        fm = QFontMetrics(v.font_c if k == v.cur else v.font_n)
        assert v._block_h(k) == max(1, len(v._lines(k))) * fm.lineSpacing() + 10


def test_cache_key_cached():
    from yamp.lyrics.service import cache_key
    import hashlib
    assert cache_key("C:/A/b.mp3") == hashlib.md5("c:/a/b.mp3".encode()).hexdigest()[:12]
    assert cache_key.cache_info().hits >= 0
