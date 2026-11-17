# -*- coding: utf-8 -*-
"""vr0.1.0.027 (f53 / f54) — 다른 앱 표현 방식: 막대 모양(둥근 · LED · 미러 · 반사) · 원형 · 스펙트로그램"""
from pathlib import Path

import pytest

TD = Path(__file__).resolve().parents[2] / "testdata"


@pytest.fixture(scope="module")
def app():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _rows(kind):
    return [ln.split("|") for ln in (TD / "vis_cases.txt").read_text(encoding="utf-8").splitlines()
            if ln.startswith(kind + "|")]


def test_shared_cases_heat_led_style_mirror():
    """testdata/vis_cases.txt (Android VisMathTest 도 같은 값)"""
    from yamp.domain.vis_math import heat_rgb, led_cells, mirror_order, next_bar_style
    hs = _rows("heat")
    assert len(hs) >= 8
    for _k, v, stops, exp in hs:
        assert heat_rgb(float(v), stops.split(",")) == tuple(int(x) for x in exp.split(",")), v
    for _k, v, h, c, exp in _rows("led"):
        assert led_cells(float(v), float(h), float(c)) == int(exp)
    for _k, cur, nxt in _rows("style"):
        assert next_bar_style(cur) == nxt
    for _k, n, exp in _rows("mirror"):
        assert mirror_order(int(n)) == [int(x) for x in exp.split(",")]


def test_gram_history_ring():
    from yamp.domain.vis_math import GramHistory
    g = GramHistory(3, 4)
    for k in range(6):
        g.push([k, k + 0.5, k + 0.25])
    assert g.size == 4 and g.col(0) == [2, 2.5, 2.25] and g.col(3) == [5, 5.5, 5.25]
    g.push([1.0])                                   # 짧은 값 → 나머지 0
    assert g.col(3) == [1.0, 0.0, 0.0]
    g.clear()
    assert g.size == 0


def test_modes_and_parse():
    from yamp.domain.vis_math import BAR_STYLES, VIS_MODES, parse_mode
    assert VIS_MODES == ("bars", "wave", "radial", "gram", "chart")
    assert BAR_STYLES == ("round", "led", "mirror", "reflex")
    assert parse_mode("gram") == "gram" and parse_mode("x") == "chart"


def test_view_draws_every_mode_and_style(app):
    from yamp.ui import skin
    from yamp.ui.vis_block import VisView
    from yamp.ui.vis_draw import gram_image, gram_stops
    v = VisView()
    v.resize(520, 200)
    v.mode = "gram"
    for k in range(40):
        v.push_bands([(i * 7 + k) % 10 / 10 for i in range(24)])
        v.tick(0.033)
    assert v.gram.size == 40
    img = gram_image(v.gram, skin.current())
    assert (img.width(), img.height()) == (150, 24)
    for name in ("sunny", "dark5"):                      # 바탕 → 진한(밝은 테마) / 밝은(어두운 테마) 순서
        s = skin.get(name)
        st = gram_stops(s)
        assert st[0] == s.graph_bg and st[-1] == s.peak
    for st in ("round", "led", "mirror", "reflex"):
        v.mode, v.bar_style = "bars", st
        assert not v.grab().isNull()
    for m in ("wave", "radial", "gram", "chart"):
        v.mode = m
        assert not v.grab().isNull()
    v.mode = "wave"
    n = v.gram.size
    v.tick(0.033)
    assert v.gram.size == n                              # 스펙트로그램이 아닐 때는 쌓지 않음


def test_block_bar_style_cycle_and_state(app, tmp_path):
    import os
    os.environ["YAMP_HOME"] = str(tmp_path)
    from yamp.core.config import Config
    from yamp.ui import tips
    from yamp.ui.vis_block import VisBlock
    cfg = Config(tmp_path)
    assert cfg["vis_bar_style"] == "round"
    vb = VisBlock(cfg)
    vb.set_mode("wave")
    vb.set_mode("bars")                                  # 다른 모드에서 오면 모양 그대로
    assert vb.view.bar_style == "round"
    vb.set_mode("bars")                                  # 스펙트럼에서 또 누르면 다음 모양
    assert vb.view.bar_style == "led" and cfg["vis_bar_style"] == "led"
    for _ in range(3):
        vb.set_mode("bars")
    assert vb.view.bar_style == "round"
    assert "막대 모양" in vb.btns["bars"].toolTip()
    cfg["vis_bar_style"] = "mirror"
    assert VisBlock(cfg).view.bar_style == "mirror"
    cfg["vis_bar_style"] = "zzz"
    assert VisBlock(cfg).view.bar_style == "round"
    assert tips.name("vis_radial") == "원형" and tips.name("vis_gram") == "스펙트로그램"
    for b in vb.btns.values():
        assert not b.icon().isNull()
