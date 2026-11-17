# -*- coding: utf-8 -*-
"""vr0.1.0.023 (f45 / f46) — 고해상도 · 큰 화면: 글자 크기를 따르는 틀 크기 · 글자 자동 · 넓은 창 가운데 · 빈 표지 ♪"""
import os

import pytest

from test_v016_crisp import _close, _win  # noqa: F401  (같은 창 도우미)


@pytest.fixture(scope="module")
def app():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_scale_css_keeps_default_and_thin_lines():
    from yamp.ui.metrics import scale_css
    css = "a { border:1px solid x; border:2px; min-height:24px; margin:-4px 0; radius:10px; w:3px }"
    assert scale_css(css, 1.0) == css                                   # 10pt = v022 와 글자 하나까지 같음
    out = scale_css(css, 1.3)
    assert "border:1px" in out and "border:2px" in out                   # 가는 선은 그대로 (흐려지지 않게)
    assert "min-height:31px" in out and "margin:-5px 0" in out and "radius:13px" in out and "w:4px" in out


def test_auto_font_steps():
    from yamp.ui.metrics import auto_font_pt
    assert [auto_font_pt(h) for h in (600, 1040, 1299, 1300, 1400, 1700, 2050, 2110, 4000)] == \
        [10, 10, 10, 11, 11, 12, 13, 13, 13]
    assert auto_font_pt(None) == 10 and auto_font_pt("x") == 10


def test_k_dp_follow_font_size():
    from yamp.ui import metrics, skin
    try:
        skin.set_font_size(10)
        assert metrics.k() == 1.0 and metrics.dp(56) == 56
        skin.set_font_size(13)
        assert abs(metrics.k() - 1.3) < 1e-9 and metrics.dp(56) == 73 and metrics.dp(84) == 109
        css = skin.stylesheet(skin.get("sunny"))
        assert "min-width:39px" in css and "border:1px" in css           # 30px → 39px · 선은 1px
    finally:
        skin.set_font_size(10)


def test_center_box_and_fix_reapply(app):
    from PyQt6.QtWidgets import QLabel, QWidget
    from yamp.ui import metrics, skin
    try:
        skin.set_font_size(10)
        box = metrics.CenterBox(QLabel("x"), 1000)
        assert box.side_margin(800) == 0 and box.side_margin(1400) == 200
        root = QWidget()
        lab = metrics.fix(QLabel("y", root), 50, 20)
        assert (lab.width(), lab.height()) == (50, 20)
        skin.set_font_size(12)
        assert metrics.reapply(root) >= 1 and (lab.width(), lab.height()) == (60, 24)
        assert box.side_margin(1400) == 100                               # 최대 폭도 글자 배율을 따라감
    finally:
        skin.set_font_size(10)


def test_window_scales_frames_with_font(app, tmp_path, monkeypatch):
    from PyQt6.QtWidgets import QFrame
    from yamp.ui import skin
    from yamp.ui.metrics import CenterBox
    w = _win(tmp_path, monkeypatch)
    try:
        w.show()
        app.processEvents()
        assert w.cfg["font_auto"] and w.a_font_auto.isChecked() and skin.font_pt("body") == 10
        rail = w.findChild(QFrame, "rail")
        bar = w.findChild(QFrame, "playerBar")
        assert rail.width() == 56 and bar.height() == 84 and w.bar_cover.width() == 52
        assert isinstance(w.page_now, CenterBox) and w.pages.indexOf(w.page_now) >= 0
        assert w.cover.pixmap() is not None and not w.cover.pixmap().isNull()      # 곡 없음 → ♪ 칸 (빈 칸 아님)
        w.set_font_size(13)
        app.processEvents()
        assert not w.cfg["font_auto"] and w.cfg["font_size"] == 13
        assert rail.width() == 73 and bar.height() == 109 and w.bar_cover.width() == 68 and w.cover.width() == 208
        assert w.b_play.iconSize().width() == round(22 * 1.3) and w.a_font_sizes[13].isChecked()
        assert w.side.maximumWidth() == round(720 * 1.3)
        assert "틀 배율 1.30" in w.screen_info()
        w.a_font_auto.trigger()                                          # 자동으로 되돌리기 → 10pt (화면 800×600)
        app.processEvents()
        assert w.cfg["font_auto"] and rail.width() == 56 and not w.a_font_sizes[13].isChecked()
    finally:
        _close(w)


def test_keep_on_screen(app, tmp_path, monkeypatch):
    from PyQt6.QtWidgets import QApplication
    from yamp.ui.metrics import keep_on_screen
    w = _win(tmp_path, monkeypatch)
    try:
        w.move(-20000, -20000)
        assert keep_on_screen(w)
        av = QApplication.primaryScreen().availableGeometry()
        assert av.intersects(w.frameGeometry())
        assert not keep_on_screen(w)                                     # 이미 화면 안 → 그대로
    finally:
        _close(w)


def test_config_font_auto_default():
    from yamp.core import config as c
    assert c.FILE_DEFAULTS["font_auto"] is True
    assert "font_auto        = 1" in c.DEFAULT_CONFIG_TEXT
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(here, "config.txt"), encoding="utf-8") as f:
        assert "font_auto        = 1" in f.read()
