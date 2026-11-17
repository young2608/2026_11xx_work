# -*- coding: utf-8 -*-
"""vr0.1.0.016 (f29) — 선명한 GUI: 그림자 효과 없음 · 힌팅 자동 · 글꼴 엔진 인자 · 고해상도 그림 · 1px 정렬 · 글자 단계 · 글자 크기 메뉴 · 화면 정보"""
import math
import os
import re
import time
from pathlib import Path

import pytest

from yamp.domain import ticker as T

PC = Path(__file__).resolve().parents[1]


@pytest.fixture
def app():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _fake_fetch(markets, timeout=None):
    now = int(time.time() * 1000)
    return [T.Quote("KRW-XRP", 3512.0, "RISE", 43, 0.0124, 3540, 3455, 1.2e12, now)], now


def _win(tmp_path, monkeypatch):
    os.environ["YAMP_HOME"] = str(tmp_path)
    from yamp.core.config import Config
    from yamp.data import upbit
    from yamp.app.mainwindow import MainWindow
    monkeypatch.setattr(upbit, "fetch", _fake_fetch)
    c = Config(tmp_path)
    c["help_overlay_shown"] = True
    return MainWindow(c)


def _close(w):
    from yamp.ui import skin
    skin.set_font_size(10)
    w.topbar.shutdown()
    w.ctrl.shutdown()
    w.hide()
    w.deleteLater()


# ---------------------------------------------------------------- 순수 함수
def test_pick_hinting_and_engine_args():
    from yamp.ui.skin import pick_hinting, qt_platform_args
    assert pick_hinting("auto", 1.0) == "full"
    assert pick_hinting("auto", 1.25) == "full" and pick_hinting("auto", 1.5) == "full"      # v017: 분수 배율도 full
    assert pick_hinting("auto", 2.0) == "none" and pick_hinting("auto", 3.0) == "none"
    assert pick_hinting("vertical", 1.0) == "vertical" and pick_hinting("bogus", 1.0) == "full"
    assert qt_platform_args("auto", "win32") == []
    assert qt_platform_args("gdi", "win32") == ["-platform", "windows:fontengine=gdi"]
    assert qt_platform_args("directwrite", "win32") == ["-platform", "windows:fontengine=directwrite"]
    assert qt_platform_args("gdi", "linux") == []               # Windows 에서만 (테스트 · offscreen 영향 없음)
    assert qt_platform_args("evil;rm", "win32") == []


def test_type_scale_five_levels_and_font_size():
    from yamp.ui import skin
    try:
        skin.set_font_size(10)
        assert [skin.font_pt(r) for r in ("h1", "h2", "body", "cap", "tiny")] == [17.0, 13.0, 10.0, 9.0, 8.0]
        skin.set_font_size(12)
        assert skin.font_pt("body") == 12 and skin.font_pt("h1") == 20.5
        assert skin.set_font_size(99) == 14 and skin.set_font_size("x") == 10
        # 스타일시트의 글자 크기는 5단계 값만
        skin.set_font_size(10)
        qss = skin.stylesheet(skin.get("sunny"))
        sizes = set(re.findall(r"font-size:([0-9.]+)pt", qss))
        assert sizes <= {"17", "13", "10", "9", "8"}, sizes
        assert "Malgun Gothic','Segoe UI'" not in qss                # 목록이 영문까지 맑은 고딕으로 그리지 않게
    finally:
        skin.set_font_size(10)


def test_source_has_no_fixed_point_sizes():
    """직접 그리는 위젯의 고정 pt 금지 (가사 · 미니 가사 · LCD 는 설정 · 모양 때문에 예외)"""
    allow = {"ui/lyrics_view.py", "ui/mini_lyrics.py", "ui/widgets.py", "ui/skin.py"}
    bad = []
    for p in (PC / "yamp").rglob("*.py"):
        rel = p.relative_to(PC / "yamp").as_posix()
        if rel in allow:
            continue
        for i, ln in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if re.search(r"setPointSize(F)?\(\s*[0-9]", ln) or re.search(r"font-size:\s*[0-9]", ln):
                bad.append(f"{rel}:{i}: {ln.strip()}")
    assert not bad, "\n".join(bad)


def test_hi_pixmap_and_snap(app):
    from PyQt6.QtGui import QColor, QImage
    from yamp.ui.hidpi import hi_pixmap, snap
    img = QImage(1000, 600, QImage.Format.Format_RGB32)
    img.fill(QColor(200, 100, 50))
    for r in (1.0, 1.25, 1.5, 2.0, 3.0):
        pm = hi_pixmap(img, 160, 160, r, expand=True)
        assert (pm.width(), pm.height()) == (math.ceil(160 * r), math.ceil(160 * r))
        assert abs(pm.devicePixelRatio() - r) < 1e-6
        assert abs(pm.width() / pm.devicePixelRatio() - 160) < 1
    small = QImage(50, 50, QImage.Format.Format_RGB32)
    assert hi_pixmap(small, 160, 160, 2.0).width() == 320            # 작은 원본도 칸 크기로
    assert hi_pixmap(b"not an image", 10).isNull()
    assert snap(10.0) == 10.5 and snap(10.7) == 10.5 and snap(10.2, 2) == 10.0 and snap(10.6, 2) == 11.0


def test_placeholder_and_grid_use_device_pixels(app):
    from yamp.ui.album_grid import AlbumGrid, placeholder
    pm = placeholder("Ditto", 120, 1.5)
    assert pm.width() == 180 and abs(pm.devicePixelRatio() - 1.5) < 1e-6
    g = AlbumGrid()
    g.set_side(100)
    assert g.ratio >= 1.0
    g.ratio = 2.0
    assert g._ph("x").width() == 200
    g.shutdown()


# ---------------------------------------------------------------- 창
def test_window_font_menu_screen_info_covers(app, tmp_path, monkeypatch):
    from PyQt6.QtGui import QColor, QImage
    from PyQt6.QtWidgets import QApplication
    from yamp.ui import skin
    w = _win(tmp_path, monkeypatch)
    try:
        w.show()
        app.processEvents()
        assert all(c.graphicsEffect() is None for c in (w.sec_info, w.sec_vis, w.sec_next))   # G1 (f31: 전체 순회 금지)
        st = QApplication.instance()._yamp_font
        assert st[0] == 10 and st[1] in ("full", "vertical", "none")
        # 글자 크기 메뉴 → 바로 적용
        assert set(w.a_font_sizes) == {9, 10, 11, 12, 13, 14} and w.a_font_auto.isChecked()   # v023: 기본 = 자동 (화면 800×600 → 10pt)
        w.a_font_sizes[12].trigger()
        app.processEvents()
        assert w.cfg["font_size"] == 12 and skin.font_pt("body") == 12
        assert QApplication.instance().font().pointSizeF() == 12 and "font-size:12pt" in QApplication.instance().styleSheet()
        assert w.a_font_sizes[12].isChecked() and not w.a_font_sizes[10].isChecked()
        w.resize(1100, 700)
        app.processEvents()
        assert not w.grab().isNull()
        w.set_font_size(10)
        # 화면 정보
        info = w.screen_info()
        assert "Qt " in info and "배율" in info and "힌팅" in info and "글자 단계" in info
        # 표지: 화면 배율 픽셀
        img = QImage(900, 900, QImage.Format.Format_RGB32)
        img.fill(QColor(10, 120, 200))
        w._cover_src, w._cover_ph = img, "A"
        w.render_covers()
        pm = w.cover.pixmap()
        assert pm is not None and abs(pm.width() / pm.devicePixelRatio() - w.cover.width()) <= 1
        w._cover_src = None
        w.render_covers()
        assert not w.cover.pixmap().isNull()                              # 표지 없음 → 첫 글자 칸
        w._cover_dpr = 0.0
        w.on_dpr_changed()                                                # 배율 바뀜 처리 (예외 없음)
    finally:
        _close(w)


def test_config_defaults_text():
    from yamp.core import config as c
    t = c.DEFAULT_CONFIG_TEXT
    assert "font_size        = 10" in t and "font_hinting     = auto" in t and "font_engine      = auto" in t
