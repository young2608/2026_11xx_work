# -*- coding: utf-8 -*-
"""vr0.1.0.025 (f49 / f50) — 추천 모음: 입력칸 아이콘 · 가사 글자 배율 · 글자 단축키 · 테마 단계 단축키 · 시세 칸 배율"""
import pytest

from test_v016_crisp import _close, _win  # noqa: F401


@pytest.fixture(scope="module")
def app():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_step_theme_ladder():
    from yamp.ui.skin import step_theme
    assert step_theme("light1", 1) == "light2" and step_theme("light5", 1) == "dark1"     # 라이트++++ 다음 = 다크
    assert step_theme("dark1", -1) == "light5" and step_theme("dark3", -1) == "dark2"
    assert step_theme("light1", -1) == "light1" and step_theme("dark5", 1) == "dark5"     # 끝에서는 그대로
    assert step_theme("sunny", 1) == "light1" and step_theme("mint", -1) == "light1"      # 밝은 테마 → 라이트부터
    assert step_theme("neon", 1) == "dark1" and step_theme("night_sunny", -1) == "dark1"  # 어두운 테마 → 다크부터
    assert step_theme("모름", 1) == "light1"                                              # 모르는 값 = 써니 취급


def test_next_font_pt():
    from yamp.ui.skin import next_font_pt
    assert next_font_pt(10, 1) == 11 and next_font_pt(10, -1) == 9
    assert next_font_pt(14, 1) == 14 and next_font_pt(9, -1) == 9
    assert next_font_pt(12.4, 1) == 13 and next_font_pt(8, 1) == 9


def test_lyrics_font_follows_scale(app):
    from yamp.ui import metrics, skin
    from yamp.ui.lyrics_view import LyricsView
    try:
        skin.set_font_size(10)
        v = LyricsView(skin.get("sunny"), 13)
        assert v.font_n.pointSize() == 13 and v.font_c.pointSize() == 16          # 10pt = 이전과 같음
        skin.set_font_size(13)
        assert metrics.reapply(v) >= 1
        assert v.font_n.pointSize() == 17 and v.font_c.pointSize() == 21          # 13 × 1.3 · +3 × 1.3
        v.set_font_pt(20)                                                          # 가사 크게 (설정 값)
        assert v._base_pt == 20 and v.font_n.pointSize() == 26
    finally:
        skin.set_font_size(10)


def test_search_icon_inside_box(app, tmp_path, monkeypatch):
    from PyQt6.QtWidgets import QStyle, QToolButton
    from yamp.ui import metrics
    w = _win(tmp_path, monkeypatch)
    try:
        w.show()
        w.go_page(w.page_list)
        app.processEvents()
        assert app.style().pixelMetric(QStyle.PixelMetric.PM_LineEditIconSize) == metrics.dp(18)
        btns = [b for b in w.search.findChildren(QToolButton)]
        assert btns
        for b in btns:                                # 돋보기 · 지우기 버튼이 입력칸 높이 안에 (전: 28px > 칸 25px → 아래로 처짐)
            assert b.geometry().top() >= 0 and b.geometry().bottom() < w.search.height(), (b.geometry(), w.search.height())
    finally:
        _close(w)


def test_font_and_theme_shortcuts(app, tmp_path, monkeypatch):
    from PyQt6.QtGui import QAction
    from yamp.ui import skin
    w = _win(tmp_path, monkeypatch)
    try:
        keys = {a.shortcut().toString() for a in w.findChildren(QAction) if not a.shortcut().isEmpty()}
        assert {"Ctrl+=", "Ctrl+-", "Ctrl+0", "Ctrl+Shift+PgUp", "Ctrl+Shift+PgDown"} <= keys
        w.step_font(1)
        assert not w.cfg["font_auto"] and w.cfg["font_size"] == 11 and skin.font_pt("body") == 11
        w.step_font(-1)
        w.step_font(-1)
        assert w.cfg["font_size"] == 9
        w.set_font_size(None)
        assert w.cfg["font_auto"] and skin.font_pt("body") == 10
        w.step_theme(1)                                # 써니 → 라이트
        assert w.cfg["theme"] == "light1" and w.skin.name == "light1"
        for _ in range(5):
            w.step_theme(1)
        assert w.cfg["theme"] == "dark1"
        w.step_theme(-1)
        assert w.cfg["theme"] == "light5" and w.theme_actions["light5"].isChecked()
    finally:
        w.apply_skin("sunny")
        _close(w)
