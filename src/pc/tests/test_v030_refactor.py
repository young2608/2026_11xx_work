# -*- coding: utf-8 -*-
"""vr0.1.0.030 (f58) 기능별 모듈화 · 리팩토링 2차 — 구조 규칙 + 나눈 뒤에도 같은 동작

PC      : 긴 함수 나누기 (메뉴 · 스타일시트 · 단순 배치 · 사운드 화면 · 가사 찾기) + 함수 길이 규칙
Android : 설정 화면 → 카드마다 함수 (SettingsCards.kt)
iOS     : 기능별 폴더 (Player · Library · Visualizer · Settings · Theme) + 재생 엔진 3파일
"""
import ast
import re
from pathlib import Path

import pytest

PC = Path(__file__).resolve().parents[1]
PKG = PC / "yamp"
SRC = PC.parent
AND = SRC / "android/app/src/main/java/com/ascen/yamp"
IOS = SRC / "ios"

MAX_FUNC_LINES = 80
FUNC_ALLOW = {("ui/icon_paths.py", "path")}         # 아이콘 모양 표 (데이터) — 나누면 오히려 찾기 어려움


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    import os
    os.environ["YAMP_HOME"] = str(tmp_path_factory.mktemp("home"))
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


# ================================================================ PC 구조
def test_functions_stay_short():
    """함수 하나 80줄 미만 (v030 규칙 — 모듈 450줄 규칙(v019)과 함께)"""
    big = []
    for p in PKG.rglob("*.py"):
        rel = p.relative_to(PKG).as_posix()
        for n in ast.walk(ast.parse(p.read_text(encoding="utf-8"))):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                ln = n.end_lineno - n.lineno + 1
                if ln > MAX_FUNC_LINES and (rel, n.name) not in FUNC_ALLOW:
                    big.append(f"{rel}:{n.name} {ln}줄")
    assert not big, big


def test_menu_builders_split():
    from yamp.app import win_menus, win_menubar
    from yamp.app.mainwindow import MainWindow
    for name in ("_menu_file", "_menu_play", "_menu_lyrics", "_menu_view", "_menu_theme", "_menu_font",
                 "_menu_pages", "_menu_topbar", "_menu_tools", "_menu_help", "_check", "_radio"):
        assert hasattr(win_menus.MenuMixin, name), name
    for name in ("update_title", "set_menu_bar", "peek_menu_bar", "_hide_peek", "set_topbar_option",
                 "ask_ticker_market", "keyPressEvent", "keyReleaseEvent"):
        assert name in vars(win_menubar.MenuBarMixin), name
        assert name not in vars(win_menus.MenuMixin), name
    assert win_menubar.MenuBarMixin in MainWindow.__mro__


def test_menu_helpers_save_settings(app, tmp_path):
    """_check · _radio 로 바꾼 메뉴가 설정에 그대로 저장 (곡 전환 페이드 · ReplayGain · 가사 공급자 · 기록)"""
    from yamp.core.config import Config
    from yamp.app.mainwindow import MainWindow
    cfg = Config(tmp_path)
    w = MainWindow(cfg)

    def find(menu, text):
        for a in menu.actions():
            if a.text() == text:
                return a
            if a.menu():
                r = find(a.menu(), text)
                if r:
                    return r
        return None
    mb = w.menuBar()
    find(mb, "6초").trigger()
    assert cfg["crossfade_s"] == 6 and find(mb, "6초").isChecked() and not find(mb, "끔").isChecked()
    find(mb, "앨범 기준").trigger()
    assert cfg["replaygain"] == "album"
    a = find(mb, "LRCLIB")
    was = bool(cfg["lyrics_lrclib"])
    a.trigger()
    assert bool(cfg["lyrics_lrclib"]) is (not was)
    w.a_hist.setChecked(not w.a_hist.isChecked())
    assert bool(cfg["history_enabled"]) is w.a_hist.isChecked()
    w.topbar_actions["topbar_clock_seconds"].setChecked(True)
    assert cfg["topbar_clock_seconds"] is True
    w.close()


def test_stylesheet_parts_same_result(app):
    """스타일시트를 묶음 7개로 나눔 — 묶음 순서 그대로 · polish 가 마지막 · skin.stylesheet 그대로 사용 가능"""
    from yamp.ui import skin, skin_css
    assert skin.stylesheet is skin_css.stylesheet
    names = [p.__name__ for p in skin_css.PARTS]
    assert names == ["_css_window", "_css_buttons", "_css_inputs", "_css_lists", "_css_controls",
                     "_css_simple", "_css_polish"]
    q = skin.stylesheet(skin.get("sunny"))
    assert q.index("QMainWindow") < q.index("QToolButton {") < q.index("QSlider::groove") < q.index("QListView, QTreeWidget")
    assert q.rindex("QLabel#toast") > q.index("/* ---- v016")
    for name in skin.SKINS:
        assert skin.stylesheet(skin.get(name)).count("{") == q.count("{")


def test_resolve_steps_split():
    from yamp.lyrics import resolve as r
    for n in ("_from_cache", "_from_simple", "_gather_remote", "_cache_put", "_is_offline_error"):
        assert callable(getattr(r, n)), n
    assert r._is_offline_error("alsong: 시간 초과") and r._is_offline_error("x: [Errno 11001]")
    assert not r._is_offline_error("lrclib: HTTP 500")


def test_layout_and_sound_builders():
    from yamp.app.win_layout import LayoutMixin
    from yamp.ui.sound_view import SoundView
    for n in ("_build_pages", "_build_rail", "_build_side", "_hide_classic_only"):
        assert hasattr(LayoutMixin, n), n
    for n in ("_build_eq", "_build_tone", "_build_dyn"):
        assert hasattr(SoundView, n), n


# ================================================================ Android (이 환경에서 컴파일 불가 → 글자로 확인)
def _balanced(txt: str) -> bool:
    t = re.sub(r'"(?:\\.|[^"\\])*"', '""', txt)               # 문자열 안 괄호 무시
    t = re.sub(r"//[^\n]*", "", t)
    return all(t.count(a) == t.count(b) for a, b in ("{}", "()", "[]"))


def test_android_settings_cards():
    tab = (AND / "ui/SettingsTab.kt").read_text(encoding="utf-8")
    cards = (AND / "ui/SettingsCards.kt").read_text(encoding="utf-8")
    names = ("SettingsViewCard", "SettingsLyricsCard", "SettingsPlayCard", "SettingsHistoryCard", "SettingsAboutCard")
    for n in names:
        assert f"internal fun {n}(" in cards and f"{n}(vm, tick, bump" in tab, n
    assert "fun SettingToggle(" in cards and "fun SettingStepper(" in cards
    assert "tick++" not in cards and "val bump: () -> Unit = { tick++ }" in tab
    assert cards.count("if (tick < 0)") == len(names)                 # 카드마다 tick 을 읽어 다시 그림
    for key in ("set_view", "set_lyrics", "set_play", "set_history", "set_about"):   # 접힘 상태 키 그대로
        assert f'CollapsibleCard("{key}"' in cards
    assert _balanced(tab) and _balanced(cards)
    assert len(tab.splitlines()) < 60


# ================================================================ iOS
def test_ios_feature_folders():
    app_dir = IOS / "App"
    for f in ("Player/PlayerEngine.swift", "Player/PlayerEngine+System.swift", "Player/SpectrumTap.swift",
              "Player/NowPlayingView.swift", "Player/MiniBar.swift", "Library/Library.swift", "Library/TrackRow.swift",
              "Library/Cover.swift", "Library/EmptyHint.swift", "Visualizer/VisualizerView.swift",
              "Visualizer/VisState.swift", "Settings/AppSettings.swift", "Settings/SettingsView.swift",
              "Theme/Theme.swift", "ContentView.swift", "YampApp.swift", "BuildInfo.swift"):
        assert (app_dir / f).is_file(), f
    decl = re.compile(r"^(?:final\s+)?(?:struct|class|enum)\s+(\w+)", re.M)
    seen = {}
    for p in app_dir.rglob("*.swift"):
        txt = p.read_text(encoding="utf-8")
        assert _balanced(txt), p.name
        assert "import " in txt or p.name == "BuildInfo.swift", p.name
        for n in decl.findall(txt):
            assert n not in seen, f"{n}: {seen.get(n)} · {p.name}"
            seen[n] = p.name
        assert len(txt.splitlines()) < 250, p.name
    eng = (app_dir / "Player/PlayerEngine.swift").read_text(encoding="utf-8")
    assert "vDSP" not in eng and "SpectrumTap()" in eng and "spectrum.analyze(buf)" in eng
    tap = (app_dir / "Player/SpectrumTap.swift").read_text(encoding="utf-8")
    assert "VisMath.bandsFromMags" in tap and "1.0 / 30" in tap and "import Accelerate" in tap
    sysx = (app_dir / "Player/PlayerEngine+System.swift").read_text(encoding="utf-8")
    assert sysx.lstrip().startswith("//") and "extension PlayerEngine" in sysx and "private func" not in sysx
    for f in ("Settings/AppSettings.swift", "Visualizer/VisState.swift"):        # ObservableObject → Combine
        assert "import Combine" in (app_dir / f).read_text(encoding="utf-8"), f
    yml = (IOS / "project.yml").read_text(encoding="utf-8")
    assert "- path: App" in yml                                              # 하위 폴더까지 자동 포함 (XcodeGen)


# ================================================================ v031 (f59 재검) 보강
@pytest.mark.parametrize("mod", ["yamp.ui.skin_css", "yamp.ui.skin", "yamp.app.win_menubar", "yamp.app.win_menus",
                                 "yamp.lyrics.resolve", "yamp.ui.sound_view"])
def test_new_modules_import_alone(mod):
    """나눈 모듈을 '먼저' import 해도 순환 import 오류 없음 (재검: skin_css 를 먼저 부르면 실패하던 것 수정)"""
    import os
    import subprocess
    import sys
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    r = subprocess.run([sys.executable, "-c", f"import {mod}"], cwd=str(PC), env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-800:]


def test_android_cards_read_tick_inside_content():
    """재검: Kotlin 2.0 강한 건너뛰기(strong skipping) 에서도 스위치 · ± 값이 바로 보이게 — 카드 내용 안에서 tick 을 읽음"""
    cards = (AND / "ui/SettingsCards.kt").read_text(encoding="utf-8")
    for m in re.finditer(r'CollapsibleCard\("set_\w+", "[^"]*"\) \{\n(.*)\n', cards):
        assert m.group(1).strip().startswith("if (tick < 0) Text(\"\")"), m.group(0)
    assert len(re.findall(r'CollapsibleCard\("set_', cards)) == 5
