# -*- coding: utf-8 -*-
"""vr0.1.0.024 (f47 / f48) — 라이트 · 다크 5단계 테마 (라이트 … 라이트++++ / 다크 … 다크++++)"""
import os

import pytest

from test_v011_theme import _lum, contrast

LIGHT = [f"light{i}" for i in range(1, 6)]
DARK = [f"dark{i}" for i in range(1, 6)]


@pytest.fixture
def app():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_levels_names_labels_order():
    from yamp.ui import skin
    assert skin.LEVELS == tuple(LIGHT + DARK)
    assert list(skin.SKINS)[-10:] == LIGHT + DARK                           # 메뉴 맨 아래 두 묶음
    assert [skin.SKINS[k].label for k in LIGHT] == ["라이트", "라이트+", "라이트++", "라이트+++", "라이트++++"]
    assert [skin.SKINS[k].label for k in DARK] == ["다크", "다크+", "다크++", "다크+++", "다크++++"]
    assert not any(skin.SKINS[k].dark for k in LIGHT) and all(skin.SKINS[k].dark for k in DARK)
    assert skin.get("light").name == "clean_blue"                          # 옛 이름 'light' 는 그대로 클린 블루


def test_each_plus_is_one_step_further():
    """'+' 한 칸 = 그 방향으로 한 단계: 라이트는 배경이 점점 덜 밝게, 다크는 점점 더 어둡게 (다크++++ = 검정)"""
    from yamp.ui import skin
    for group in (LIGHT, DARK):
        lums = [_lum(skin.SKINS[k].bg) for k in group]
        assert all(a > b for a, b in zip(lums, lums[1:])), group
    assert skin.SKINS["light1"].bg == "#FFFFFF" and skin.SKINS["dark5"].bg == "#000000"
    assert _lum(skin.SKINS["light5"].bg) > _lum(skin.SKINS["dark1"].bg) * 3     # 가장 어두운 라이트도 다크보다 확실히 밝음
    for k in LIGHT + DARK:
        s = skin.SKINS[k]
        assert contrast(s.text, s.bg) >= 7.0 and contrast(s.text, s.surface) >= 7.0, k   # 본문 글자 AAA


def test_follow_dark_pairs_levels():
    from yamp.ui import skin
    for i in range(1, 6):
        assert skin.follow_dark(f"light{i}", True, False) == f"dark{i}"
        assert skin.follow_dark(f"light{i}", True, True) == f"light{i}"
        assert skin.follow_dark(f"dark{i}", True, False) == f"dark{i}"
    assert skin.follow_dark("sunny", True, False) == "night_sunny" and skin.follow_dark("mint", True, False) == "dark"


def test_config_accepts_level_names(tmp_path):
    from yamp.core.config import CHOICES, DEFAULT_CONFIG_TEXT, Config
    assert set(LIGHT + DARK) <= set(CHOICES["theme"])
    assert "light1~light5" in DEFAULT_CONFIG_TEXT and "dark1~dark5" in DEFAULT_CONFIG_TEXT
    (tmp_path / "config.txt").write_text(DEFAULT_CONFIG_TEXT.replace("theme            = sunny", "theme            = dark4"),
                                         encoding="utf-8")
    assert Config(tmp_path)["theme"] == "dark4"


def test_menu_sections_and_live_switch(app, tmp_path):
    os.environ["YAMP_HOME"] = str(tmp_path)
    from yamp.core.config import Config
    from yamp.app.mainwindow import MainWindow
    from yamp.ui import skin
    cfg = Config(tmp_path)
    cfg["topbar_ticker"] = False
    w = MainWindow(cfg)
    try:
        assert set(w.theme_actions) == set(skin.SKINS) and len(w.theme_actions) == 18
        heads = [a.text() for a in w.menu_view.actions()[0].menu().actions() if a.isSeparator() and a.text()]
        assert any("라이트 5단계" in h for h in heads) and any("다크 5단계" in h for h in heads), heads
        w.theme_actions["dark5"].trigger()
        assert cfg["theme"] == "dark5" and w.skin.name == "dark5" and skin.current().bg == "#000000"
        assert w.theme_actions["dark5"].isChecked() and not w.theme_actions["sunny"].isChecked()
        w.apply_skin("light3")
        assert w.skin.name == "light3" and "#E8EAEE" in app.styleSheet()
    finally:
        w.apply_skin("sunny")
        w.ctrl.shutdown()
        w.close()
        w.deleteLater()
