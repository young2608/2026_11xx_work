# -*- coding: utf-8 -*-
"""vr0.1.0.017 (f32) — 곡 파형 · 소리 파동 크게 + 선명 (픽셀 격자 막대 · 자동 키움 · 글꼴 · 배율 정책 · 아이콘 선 굵기)"""
import os
import time

import pytest



@pytest.fixture
def app():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_seek_bars_pixel_grid_and_shape(app):
    from yamp.ui.neon import WaveformSeek
    s = WaveformSeek()
    s.resize(600, 44)
    s.peaks = [0.0, 0.25, 1.0, 0.5] * 60
    for r in (1.0, 1.25, 1.5, 2.0):
        bars = s._bars(int(600 * r), r)
        step = max(3, round(3 * r))
        assert len(bars) == int(600 * r) // step
        assert max(bars) == 1.0 and min(bars) >= 0.0
    assert s._bars(600, 1.0) is s._bars(600, 1.0)                         # 캐시
    s.dur_ms, s.pos_ms = 1000, 500
    assert not s.grab().isNull()


def test_vis_wave_auto_gain(app):
    """v026 (f51): 오실로스코프(자동 키움)는 없어지고 웨이브 = 스펙트럼 곡선 — 자동 키움 계산(agc_step)만 남아 있는지"""
    from yamp.domain.vis_math import agc_step
    from yamp.ui.vis_block import VisView
    g = 1.0
    for _ in range(80):
        g = agc_step(g, 0.05)
    assert 7.0 < g <= 8.0
    v = VisView()
    v.resize(500, 200)
    v.mode = "wave"
    assert not v.grab().isNull() and v.minimumHeight() >= 180


def test_rounding_policy_fonts_icons():
    from PyQt6.QtCore import Qt
    from yamp.ui import skin
    P = Qt.HighDpiScaleFactorRoundingPolicy
    assert skin.rounding_policy("passthrough") == P.PassThrough and skin.rounding_policy("") == P.PassThrough
    assert skin.rounding_policy("round") == P.Round and skin.rounding_policy("floor") == P.RoundPreferFloor
    assert skin.FONT_FAMILIES[0] == "Segoe UI"                          # 힌팅 정보가 많은 고정 글꼴 먼저
    from yamp.core import config as c
    assert "ui_scale_rounding = passthrough" in c.DEFAULT_CONFIG_TEXT and "wave_height      = 44" in c.DEFAULT_CONFIG_TEXT


def test_icon_stroke_snapped_to_device_pixels(app):
    from PyQt6.QtCore import QSize
    from yamp.ui import icons
    for scale in (1.25, 1.5):
        pm = icons.icon("menu", "text").pixmap(QSize(20, 20), scale)
        img = pm.toImage()
        # 가로줄 3개(☰): 세로 단면에 반투명(번진) 픽셀이 없어야 함
        x = img.width() // 2
        alphas = [img.pixelColor(x, y).alpha() for y in range(img.height())]
        partial = sum(1 for a in alphas if 30 < a < 225)
        assert partial == 0, (scale, alphas)                                   # v017: 번진 픽셀 없음


def test_window_seek_height_from_config(app, tmp_path, monkeypatch):
    os.environ["YAMP_HOME"] = str(tmp_path)
    from yamp.core.config import Config
    from yamp.data import upbit
    from yamp.app.mainwindow import MainWindow
    monkeypatch.setattr(upbit, "fetch", lambda m, timeout=3.0: ([], int(time.time() * 1000)))
    c = Config(tmp_path)
    c["help_overlay_shown"] = True
    c["wave_height"] = 60
    w = MainWindow(c)
    try:
        assert w.seek.height() == 60 or w.seek.maximumHeight() == 60
    finally:
        w.topbar.shutdown()
        w.ctrl.shutdown()
        w.hide()
        w.deleteLater()
