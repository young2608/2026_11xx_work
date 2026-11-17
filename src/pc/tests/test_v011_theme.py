# -*- coding: utf-8 -*-
"""vr0.1.0.011 — f19 테마 (써니 기본 · 토큰 표 · 고정 색 0 · 바로 적용 · D2 바꾸기 · D3 어두운 모드 따라가기)"""
import os
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TD = ROOT / "testdata"
PC = Path(__file__).resolve().parents[1]
THEMES = ("sunny", "clean_blue", "mint", "cherry", "night_sunny", "neon", "dark", "classic",
          "light1", "light2", "light3", "light4", "light5", "dark1", "dark2", "dark3", "dark4", "dark5")   # v024 단계


@pytest.fixture
def app():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _table():
    out = {}
    for ln in (TD / "themes.txt").read_text(encoding="utf-8").splitlines():
        if not ln.strip() or ln.startswith("#"):
            continue
        t, k, v = ln.split("|")
        out.setdefault(t, {})[k] = v
    return out


def _lum(h):
    def ch(c):
        c = c / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (int(h[i:i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def contrast(a, b):
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


# ---------------------------------------------------------------- 표
def test_skin_table_matches_shared_file():
    from yamp.ui import skin
    tab = _table()
    assert tuple(tab) == THEMES == tuple(skin.SKINS)
    for name, s in skin.SKINS.items():
        assert s.as_dict() == tab[name], name
        assert len(s.bands) == 11
    assert skin.DEFAULT == "sunny" and skin.get("").name == "sunny" and skin.get("모름").name == "sunny"
    assert skin.get("light").name == "clean_blue" and skin.get("NEON").name == "neon"
    s = skin.get("sunny")                      # 옛 이름 → 토큰
    assert (s.panel, s.accent, s.list_cur, s.lyric_cur, s.list_bg, s.list_fg, s.lcd_dim) == \
        (s.surface, s.fill1, s.accent_text, s.accent_text, s.surface, s.text, s.wave_rest)
    assert (s.bg, s.fill1, s.fill2, s.accent_text) == ("#FFFFFF", "#FFC72C", "#FF8A00", "#C2410C")


def test_every_theme_passes_contrast_rules():
    from yamp.ui import skin
    rules = [ln.split("|") for ln in (TD / "theme_contrast.txt").read_text(encoding="utf-8").splitlines()
             if ln.strip() and not ln.startswith("#")]
    assert len(rules) >= 10
    bad = []
    for name, s in skin.SKINS.items():
        for a, b, mn in rules:
            c = contrast(getattr(s, a), getattr(s, b))
            if c + 1e-9 < float(mn):
                bad.append(f"{name}: {a}/{b} = {c:.2f} < {mn}")
    assert not bad, bad


def test_no_hardcoded_colors_in_source():
    """앱 소스에 #rrggbb 금지 (themes.py 만 색 표, v022). 테마 이름 분기 금지 (스타일시트)"""
    pat = re.compile(r"#[0-9a-fA-F]{6}\b")
    bad = []
    for p in (PC / "yamp").rglob("*.py"):
        rel = p.relative_to(PC / "yamp").as_posix()
        if rel in ("ui/themes.py", "version.py", "core/version.py"):     # v022: 색 표는 themes.py (skin.py 도 이제 검사 대상)
            continue
        for i, ln in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if pat.search(ln):
                bad.append(f"{rel}:{i}: {ln.strip()}")
    assert not bad, "\n".join(bad)
    import inspect
    from yamp.ui import skin
    src = inspect.getsource(skin.stylesheet)
    assert "s.name" not in src and not pat.search(src)
    for name, s in skin.SKINS.items():                  # 스타일시트의 색은 모두 그 테마 토큰
        used = set(pat.findall(skin.stylesheet(s)))
        assert used <= set(s.as_dict().values()), (name, used - set(s.as_dict().values()))


def test_follow_dark_and_migration_rules():
    from yamp.ui import skin
    f = skin.follow_dark
    assert f("sunny", True, False) == "night_sunny"
    assert f("sunny", True, True) == "sunny" and f("sunny", True, None) == "sunny"   # 밝음 / 모름 → 그대로
    assert f("sunny", False, False) == "sunny"                                       # 꺼짐
    assert f("clean_blue", True, False) == "dark" and f("mint", True, False) == "dark"
    assert f("cherry", True, False) == "dark" and f("light", True, False) == "dark"
    assert f("neon", True, False) == "neon" and f("classic", True, False) == "classic"   # 이미 어두운 테마
    m = skin.migrate_theme
    assert m("neon", False) == ("sunny", skin.MIGRATE_TOAST)
    assert m("neon", True) == ("neon", None)                  # 바꾼 뒤 다시 고른 네온은 유지
    assert m("light", False) == ("clean_blue", None) and m("light", True) == ("clean_blue", None)
    assert m("dark", False) == ("dark", None) and m("sunny", False) == ("sunny", None)
    assert m("zzz", False) == ("sunny", None)
    assert "보기 → 테마" in skin.MIGRATE_TOAST and "네온" in skin.MIGRATE_TOAST


# ---------------------------------------------------------------- 창
def _win(tmp_path, **kv):
    os.environ["YAMP_HOME"] = str(tmp_path)
    from yamp.core.config import Config
    from yamp.app.mainwindow import MainWindow
    cfg = Config(tmp_path)
    for k, v in kv.items():
        cfg[k] = v
    return cfg, MainWindow(cfg)


def _icon_color(btn):
    """아이콘 픽스맵에서 가장 진한(불투명) 픽셀 색"""
    img = btn.icon().pixmap(24, 24).toImage()
    best = None
    for y in range(img.height()):
        for x in range(img.width()):
            c = img.pixelColor(x, y)
            if c.alpha() == 255:
                return c.name().upper()
            if c.alpha() > 0 and (best is None or c.alpha() > best.alpha()):
                best = c
    return best.name().upper() if best else None


def test_mainwindow_all_themes_live_switch(app, tmp_path):
    from PyQt6.QtWidgets import QApplication
    from yamp.ui import skin
    cfg, w = _win(tmp_path)
    w.show()
    app.processEvents()
    assert cfg["theme"] == "sunny" and cfg["theme_migrated"] is True and w._theme_notice is None   # 새로 설치: 알림 없음
    assert skin.current().name == "sunny" and "#FFC72C" in QApplication.instance().styleSheet()
    assert set(w.theme_actions) == set(THEMES) and w.theme_actions["sunny"].isChecked()
    assert not w.theme_actions["sunny"].icon().isNull()                    # 색 견본
    for name in THEMES:
        w.apply_skin(name)
        app.processEvents()
        s = skin.get(name)
        assert cfg["theme"] == name and w.skin is s and skin.current() is s
        assert w.theme_actions[name].isChecked()
        assert QApplication.instance().styleSheet() == skin.stylesheet(s)
        assert w.model.cur_color.name().upper() == s.accent_text
        assert w.lcd.skin is s and w.lyv.skin is s and w.spec.skin is s
        assert _icon_color(w.b_prev) == s.text                             # 기본 아이콘 = text (다시 칠함)
        assert _icon_color(w.b_play) == s.on_fill                          # 채움 버튼 위 = on_fill
        w.b_shuf.setChecked(True)
        assert _icon_color(w.b_shuf) == s.accent_text                      # 켜짐 = accent_text
        w.b_shuf.setChecked(False)
        assert w.seek.accent.name().upper() == s.wave_played
        assert not w.grab().isNull()
    w.apply_skin("light")                                                  # 옛 이름도 동작
    assert w.skin.name == "clean_blue"
    w.apply_skin("sunny")
    w.grab().save(str(tmp_path / "sunny.png"))
    w.quit_app()


def test_mini_windows_follow_theme(app, tmp_path):
    from yamp.ui import skin
    cfg, w = _win(tmp_path)
    w.show()
    w.toggle_mini_player()
    w.toggle_mini()
    app.processEvents()
    assert w.mini_player is not None and w.mini is not None
    w.apply_skin("night_sunny")
    s = skin.get("night_sunny")
    assert _icon_color(w.mini_player.b_prev) == s.text
    assert not w.mini.grab().isNull() and not w.mini_player.grab().isNull()
    w.quit_app()


def test_classic_layout_follows_theme(app, tmp_path):
    from yamp.ui import skin
    cfg, w = _win(tmp_path, layout="classic")
    w.show()
    app.processEvents()
    for name in THEMES:
        w.apply_skin(name)
        app.processEvents()
        assert _icon_color(w.b_prev) == skin.get(name).text
        img = w.grab().toImage()
        assert not img.isNull()
    w.apply_skin("sunny")                       # D5: 써니면 흰 Winamp — 창 배경이 흰색
    app.processEvents()
    img = w.grab().toImage()
    assert img.pixelColor(img.width() - 3, img.height() // 2).name().upper() in ("#FFFFFF", skin.get("sunny").line)
    w.quit_app()


def test_migration_at_startup(app, tmp_path):
    (tmp_path / "config.txt").write_text("theme = neon\n", encoding="utf-8")
    cfg, w = _win(tmp_path)
    assert cfg["theme"] == "sunny" and cfg["theme_migrated"] is True
    assert w._theme_notice and "네온" in w._theme_notice
    w.quit_app()
    from yamp.core.config import Config
    cfg2 = Config(tmp_path)
    assert cfg2["theme_migrated"] is True
    cfg2["theme"] = "neon"                     # 바꾼 뒤 사용자가 다시 네온 → 유지
    cfg2.save()
    from yamp.app.mainwindow import MainWindow
    w2 = MainWindow(Config(tmp_path))
    assert w2.cfg["theme"] == "neon" and w2._theme_notice is None and w2.skin.name == "neon"
    w2.quit_app()
    (tmp_path / "config.txt").write_text("theme = light\n", encoding="utf-8")
    w3 = MainWindow(Config(tmp_path))
    assert w3.cfg["theme"] == "clean_blue" and w3.skin.name == "clean_blue"
    w3.quit_app()


def test_follow_system_dark_in_window(app, tmp_path, monkeypatch):
    from yamp.winplat import win_theme
    monkeypatch.setattr(win_theme, "system_theme", lambda: {"light": False, "accent": None})   # Windows 어두운 모드 흉내
    cfg, w = _win(tmp_path)
    w.a_follow_dark.setChecked(True)
    assert cfg["follow_system_dark"] is True and w.skin.name == "night_sunny"
    assert cfg["theme"] == "sunny"             # 설정 테마는 그대로
    w._on_system_theme({"light": True, "accent": None})
    assert w.skin.name == "sunny"
    w._on_system_theme({"light": False, "accent": None})
    w.apply_skin("mint")
    assert w.skin.name == "dark" and cfg["theme"] == "mint"
    w.a_follow_dark.setChecked(False)
    assert w.skin.name == "mint"
    w.quit_app()


def test_bound_icons_dropped_when_window_deleted(app, tmp_path):
    """v011b: 앞 창이 지워진 뒤 새 창의 테마 적용이 지워진 위젯을 부르지 않음
    (Windows: test_mainwindow_v006 에서 icons.refresh_bound access violation)"""
    import os
    from PyQt6 import sip
    from PyQt6.QtCore import QCoreApplication, QEvent
    from yamp.core.config import Config
    from yamp.app.mainwindow import MainWindow
    from yamp.ui import icons
    os.environ["YAMP_HOME"] = str(tmp_path)
    for layout in ("simple", "classic"):
        cfg = Config(tmp_path)
        cfg["layout"] = layout
        before = {id(e) for e in icons._bound}
        w = MainWindow(cfg)
        owners = [e[0] for e in icons._bound if id(e) not in before]
        assert owners
        w.ctrl.shutdown()
        w.deleteLater()
        for _ in range(3):
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete.value)
            app.processEvents()
        assert all(sip.isdeleted(o) for o in owners)
        assert not any(e[0] is o for e in icons._bound for o in owners)  # destroyed 시그널로 이미 빠짐
        icons.refresh_bound()                                          # 지워진 것을 부르지 않음
    w2 = MainWindow(Config(tmp_path))
    w2.apply_skin("mint")
    w2.ctrl.shutdown()
    w2.deleteLater()
