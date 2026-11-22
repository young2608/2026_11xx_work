# -*- coding: utf-8 -*-
"""vr0.1.0.032 (f60) 성능 병목 2차 — 결과(그림 · 값 · 목록)가 전과 같은지 + 반복 작업이 줄었는지

P1 레벨 차트 dB 를 넣을 때 한 번 · P2 LED 칸 drawRects · P3 밴드 계획 캐시 · P4 스펙트럼 버퍼 변환 미루기
P5 Path 없는 곡 이름 · P6 목록 빼기 한 번에 · P7 라이브러리 스캔 따로 + 종료 시 멈춤 · A1~A4 Android 소스
"""
import math
import os
import random
from pathlib import Path, PurePosixPath, PureWindowsPath

import numpy as np
import pytest

ANDROID = Path(__file__).resolve().parents[2] / "android" / "app" / "src" / "main" / "java" / "com" / "ascen" / "yamp"


@pytest.fixture(scope="module")
def app():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _render(widget, w, h, dpr):
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QImage, QPainter
    img = QImage(int(w * dpr), int(h * dpr), QImage.Format.Format_ARGB32_Premultiplied)
    img.setDevicePixelRatio(dpr)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    widget.render(p)
    p.end()
    return img


# ---------------------------------------------------------------- P1 레벨 차트
def test_chart_db_cached_same_picture(app):
    from yamp.ui.vis_block import VisView
    from yamp.domain.vis_math import to_db
    v = VisView()
    v.resize(500, 200)
    v.mode = "chart"
    for i in range(400):                                     # maxlen(300) 넘게 → 앞이 밀려나도 짝이 맞음
        v.push_frame([0.0] * 8, abs(math.sin(i / 9)) * 0.5, abs(math.sin(i / 7)))
    assert len(v._hist_db) == len(v.hist) == v.hist.maxlen
    assert list(v._hist_db) == [(to_db(r), to_db(p)) for r, p in v.hist]
    a = _render(v, 500, 200, 1.25)
    v._hist_db.clear()                                       # 밖에서 hist 만 바뀐 경우 → 다시 계산해 같은 그림
    b = _render(v, 500, 200, 1.25)
    assert a == b
    v.clear()
    assert not v.hist and not v._hist_db


# ---------------------------------------------------------------- P2 LED 칸 = 예전 fillRect 그림과 픽셀까지 같음
def _old_led(p, r, s, v, pk):
    from PyQt6.QtCore import QRectF
    from PyQt6.QtGui import QColor
    from yamp.ui import metrics
    from yamp.ui.vis_draw import _grad
    from yamp.domain.vis_math import LED_CELL, led_cells
    n = len(v)
    slot = r.width() / n
    gap = max(2.0, slot * 0.28)
    w = slot - gap
    peak = QColor(s.peak)
    hmax = r.height() - 4
    g = _grad(r, s)
    cell = max(3.0, LED_CELL * metrics.k())
    total = max(1, int((hmax + 2) // (cell + 2)))
    dim = QColor(s.graph_grid)
    for i in range(n):
        x = r.left() + i * slot + gap / 2
        on = led_cells(v[i], hmax, cell)
        top_on = led_cells(max(v[i], pk[i]), hmax, cell)
        for c in range(total):
            y = r.bottom() - (c + 1) * (cell + 2) + 2
            if c < on:
                p.fillRect(QRectF(x, y, w, cell), g)
            elif c == top_on - 1 and top_on > on:
                p.fillRect(QRectF(x, y, w, cell), peak)
            else:
                p.fillRect(QRectF(x, y, w, cell), dim)


def test_led_bars_same_pixels(app):
    from PyQt6.QtCore import QRectF, Qt
    from PyQt6.QtGui import QImage, QPainter
    from yamp.ui import skin, vis_draw
    rng = random.Random(60)
    for theme in ("sunny", "neon", "dark5"):
        s = skin.get(theme)
        for (w, h, dpr) in ((600, 240, 1.0), (333, 181, 1.25), (1201, 402, 2.0)):
            v = [rng.random() for _ in range(24)]
            pk = [min(1.0, x + rng.random() * 0.3) for x in v]
            imgs = []
            for fn in ("new", "old"):
                img = QImage(int(w * dpr), int(h * dpr), QImage.Format.Format_ARGB32_Premultiplied)
                img.setDevicePixelRatio(dpr)
                img.fill(Qt.GlobalColor.transparent)
                p = QPainter(img)
                p.setRenderHint(QPainter.RenderHint.Antialiasing)
                r = QRectF(10.5, 8.5, w - 21, h - 17)
                if fn == "new":
                    vis_draw.draw_bars(p, r, s, v, pk, "led")
                else:
                    _old_led(p, r, s, v, pk)
                p.end()
                imgs.append(img)
            assert imgs[0] == imgs[1], (theme, w, h, dpr)


# ---------------------------------------------------------------- P3 밴드 계획 캐시 = 예전 계산과 비트까지 같음
def _old_bands(mags, bin_hz, n=24, range_db=60.0, ref=1.0):
    from yamp.domain.vis_math import VIS_TILT_DB_OCT, band_freqs
    m = len(mags)
    out = []
    if m < 2 or bin_hz <= 0:
        return [0.0] * n
    for f0, f1, fc in band_freqs(n):
        if f1 - f0 < 2 * bin_hz:
            x = min(m - 1.0, max(1.0, fc / bin_hz))
            k = int(x)
            fr = x - k
            a = float(mags[k])
            b = float(mags[min(m - 1, k + 1)])
            v = a + (b - a) * fr
        else:
            k0 = max(1, int(f0 / bin_hz))
            k1 = min(m, max(k0 + 1, int(f1 / bin_hz)))
            s = 0.0
            for k in range(k0, k1):
                s += float(mags[k]) ** 2
            v = math.sqrt(s / (k1 - k0)) if k1 > k0 else 0.0
        db = 20.0 * math.log10(max(v, 1e-9) / ref) + VIS_TILT_DB_OCT * math.log2(fc / 1000.0)
        out.append(min(1.0, max(0.0, (db + range_db) / range_db)))
    return out


def test_band_plan_bit_identical():
    from yamp.domain.vis_math import bands_from_mags
    rng = np.random.default_rng(32)
    for m in (2, 64, 513, 1025):
        for hz in (10.7, 43.066, 46.875, 300.0, 4000.0):
            for n in (8, 24):
                mg = (rng.random(m) * rng.random() * 2).tolist()
                assert bands_from_mags(mg, hz, n) == _old_bands(mg, hz, n)
                assert bands_from_mags(mg, hz, n, 45.0, 128.0) == _old_bands(mg, hz, n, 45.0, 128.0)
    assert bands_from_mags([0.5], 43.0) == [0.0] * 24 and bands_from_mags([0.5, 0.5], 0) == [0.0] * 24


# ---------------------------------------------------------------- P4 스펙트럼: 버퍼 변환을 미뤄도 내보내는 값은 같음
class _OldAnalyzer:
    """vr0.1.0.031 까지의 feed (버퍼마다 변환)"""

    def __init__(self, clock):
        from yamp.audio import visualizer as V
        self.V, self.clock, self.min_dt, self._last = V, clock, 1.0 / 30, 0.0
        self._acc = np.zeros(0, dtype=np.float32)
        self.out = []

    def feed(self, buf):
        V = self.V
        r = V.buffer_to_mono(buf, V.FFT_N)
        if r is None:
            return
        a, sr = r
        self._acc = a[-V.FFT_N:] if a.size >= V.FFT_N else np.concatenate([self._acc, a])[-V.FFT_N:]
        now = self.clock[0]
        if now - self._last < self.min_dt:
            return
        self._last = now
        self.out.append((V.compute_bands(self._acc, sr), V.frame_stats(self._acc)))


def test_spectrum_feed_deferred_same(app, monkeypatch):
    from PyQt6.QtCore import QByteArray
    from PyQt6.QtMultimedia import QAudioBuffer, QAudioFormat
    from yamp.audio import visualizer as V
    clock = [100.0]
    monkeypatch.setattr(V.time, "monotonic", lambda: clock[0])
    f = QAudioFormat()
    f.setSampleFormat(QAudioFormat.SampleFormat.Int16)
    f.setChannelCount(2)
    f.setSampleRate(44100)
    rng = np.random.default_rng(4)
    new = V.SpectrumAnalyzer()
    got = []
    new.levels.connect(lambda lv: got.append(lv))
    frames = []
    new.frame.connect(lambda fr: frames.append(fr))
    old = _OldAnalyzer(clock)
    converted = [0]
    real = V.buffer_to_mono

    def counting(buf, max_frames=None):
        converted[0] += 1
        return real(buf, max_frames)
    for k in range(300):
        n = int(rng.choice([200, 700, 1024, 2048, 4096]))       # 작은 버퍼(이어 붙임) · 큰 버퍼 섞음
        data = rng.integers(-20000, 20000, n * 2, dtype=np.int16)
        b = QAudioBuffer(QByteArray(data.tobytes()), f)
        clock[0] += n / 44100
        old.feed(b)
        monkeypatch.setattr(V, "buffer_to_mono", counting)
        new.feed(b)
        monkeypatch.setattr(V, "buffer_to_mono", real)
    assert len(got) == len(old.out) > 20
    for (lv, fr), g, f2 in zip(old.out, got, frames):
        assert g == lv and f2 == fr
    assert converted[0] < 300                                  # 그리지 않을 큰 버퍼는 변환하지 않음


# ---------------------------------------------------------------- P5 Path 없는 곡 이름 = Path 와 같음
def test_path_name_stem_same_as_pathlib():
    import ntpath
    from yamp.data.track import Track, path_name, path_stem
    from yamp.data.scan import sort_tracks
    posix = ["/m/a.mp3", "/m/.h", "/m/a.", "rel/b.c.ogg", "/m/x/", "트랙 01.m4a", "/m/01 - t (live).flac"]
    for c in posix if os.sep == "/" else []:
        assert path_name(c) == PurePosixPath(c).name and path_stem(c) == PurePosixPath(c).stem, c
    win = ["C:\\Music\\a.mp3", "C:/Music/b.c.flac", "D:\\x\\.hidden", "\\\\srv\\share\\01 - t.mp3", "C:song.mp3",
           "D:\\x\\a.", "D:\\x\\y\\", "D:/x/트랙 01.m4a"]
    for c in win:                                            # Windows 규칙: ntpath + 두 구분자 (track.path_name 과 같은 식)
        n = ntpath.basename(c.rstrip("/\\"))
        i = n.rfind(".")
        st = n[:i] if 0 < i < len(n) - 1 else n
        assert n == PureWindowsPath(c).name and st == PureWindowsPath(c).stem, c
    ts = [Track(f"/Music/A{i % 7}/{random.Random(i).randint(0, 999):03d} song.{['mp3', 'flac'][i % 2]}", cue_no=i % 3)
          for i in range(300)]
    assert [t.display for t in ts] == [Path(t.path).stem for t in ts]
    old_name = sorted(ts, key=lambda t: (os.path.dirname(t.path).lower(), Path(t.path).name.lower(), t.cue_no))
    old_title = sorted(ts, key=lambda t: ((t.title or Path(t.path).stem).lower(), t.cue_no))
    assert sort_tracks(ts) == old_name and sort_tracks(ts, "title") == old_title


# ---------------------------------------------------------------- P6 목록에서 빼기
def test_playlist_remove_same_as_before():
    from yamp.data.playlist import Playlist, Track
    rnd = random.Random(6)
    for _ in range(30):
        items = [Track(f"/m/{i}.mp3") for i in range(rnd.randint(0, 200))]
        idx = [rnd.randint(-3, len(items) + 3) for _ in range(rnd.randint(0, 60))]
        cur = rnd.randint(-1, len(items) - 1) if items else -1
        exp = list(items)
        for i in sorted(set(idx), reverse=True):
            if 0 <= i < len(exp):
                del exp[i]
        cur_t = items[cur] if cur >= 0 else None
        pl = Playlist()
        pl.items = list(items)
        pl.current = cur
        same_list = pl.items
        pl.remove(idx)
        assert pl.items == exp and pl.items is same_list
        assert pl.current == (next((k for k, t in enumerate(exp) if t is cur_t), -1) if cur_t else -1)


# ---------------------------------------------------------------- P7 라이브러리 스캔: 따로 작업 줄 · 종료하면 멈춤
def test_scan_on_own_pool_and_stops(tmp_path, app):
    from yamp.data.library import Library
    from yamp.data.tags import TagInfo
    lib = Library(tmp_path / "lib.db")
    d = tmp_path / "music"
    d.mkdir()
    for i in range(30):
        (d / f"{i:02d}.mp3").write_bytes(b"\0" * 10)
    calls = []

    def read(p):
        calls.append(p)
        return TagInfo(title=os.path.basename(p))
    n = lib.scan([str(d)], read, stop=lambda: len(calls) >= 5)
    assert n == 5 and len(calls) == 5                         # 곡 사이에서 멈춤
    assert lib.remove_missing(stop=lambda: True) == 0         # 멈추면 아무것도 지우지 않음
    os.remove(d / "00.mp3")
    assert lib.remove_missing() == 1
    lib.close()
    import inspect
    from yamp.app import controller, ctl_library
    assert "_scan_jobs" in inspect.getsource(controller.Controller.__init__)
    src = inspect.getsource(ctl_library.LibraryMixin.scan_library)
    assert "_scan_jobs" in src and "stop=stop" in src and "self._closed" in src
    assert "_scan_jobs.waitForDone" in inspect.getsource(controller.Controller.shutdown)


# ---------------------------------------------------------------- A1~A4 Android 소스 (컴파일 · 단위 테스트는 ./build.sh apk)
def test_android_perf_sources():
    sp = (ANDROID / "playback" / "SoundProcessor.kt").read_text("utf-8")
    assert "asShortBuffer().get(" in sp and "asFloatBuffer().get(" in sp and "asShortBuffer().put(" in sp
    assert "inputBuffer.getShort()" not in sp and "out.putShort(" not in sp
    dsp = (ANDROID / "domain" / "Dsp.kt").read_text("utf-8")
    assert "cThrSafe" in dsp and "envC <= cThrSafe" in dsp
    fx = (ANDROID / "playback" / "Fx.kt").read_text("utf-8")
    assert "= hypot(" not in fx and "import kotlin.math.hypot" not in fx and "sqrt(re * re + im * im)" in fx
    pp = (ANDROID / "ui" / "PlayerParts.kt").read_text("utf-8")
    assert "delay(SPECTRUM_GAP_MS)" in pp and "SPECTRUM_GAP_MS = 12L" in pp
    t = (ANDROID.parents[4] / "test" / "java" / "com" / "ascen" / "yamp" / "domain" / "DspTest.kt").read_text("utf-8")
    assert "compressorFastPathBitIdentical" in t
