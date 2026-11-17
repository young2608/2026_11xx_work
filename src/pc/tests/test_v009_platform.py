"""vr0.1.0.009: Windows 통합 — 작업 표시줄 썸네일 버튼·진행률 · 전역 단축키 · 시스템 테마 · SMTC · 절전/종료
(Linux CI 에서는 순수 함수 + 비Windows no-op 만 검증, COM/winrt 경로는 Windows 에서 수동 확인)"""
import ctypes
import os
import struct
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
if sys.platform.startswith("linux"):
    os.environ.setdefault("QT_AUDIO_BACKEND", "alsa")
PC = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PC))

NOT_WIN = sys.platform != "win32"


@pytest.fixture
def app():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


# ---------------------------------------------------------------- 전역 단축키
def test_parse_hotkey_defaults():
    from yamp.winplat.win_hotkeys import (DEFAULT_BINDINGS, MOD_ALT, MOD_CONTROL, MOD_NOREPEAT, parse_hotkey)
    ca = MOD_CONTROL | MOD_ALT | MOD_NOREPEAT
    assert parse_hotkey("Ctrl+Alt+Space") == (ca, 0x20)
    assert parse_hotkey("Ctrl+Alt+Right") == (ca, 0x27)
    assert parse_hotkey("Ctrl+Alt+Left") == (ca, 0x25)
    assert parse_hotkey("Ctrl+Alt+Up") == (ca, 0x26)
    assert parse_hotkey("Ctrl+Alt+Down") == (ca, 0x28)
    assert parse_hotkey("Ctrl+Alt+P") == (ca, ord("P"))
    assert set(DEFAULT_BINDINGS) == {"toggle", "next", "prev", "vol_up", "vol_down", "show"}
    assert all(parse_hotkey(v) for v in DEFAULT_BINDINGS.values())


def test_parse_hotkey_keys_and_mods():
    from yamp.winplat.win_hotkeys import (MOD_ALT, MOD_CONTROL, MOD_NOREPEAT, MOD_SHIFT, MOD_WIN, parse_hotkey)
    R = MOD_NOREPEAT
    assert parse_hotkey("ctrl+shift+a") == (MOD_CONTROL | MOD_SHIFT | R, 0x41)
    assert parse_hotkey(" Win + Alt + 7 ") == (MOD_WIN | MOD_ALT | R, 0x37)
    assert parse_hotkey("Meta+Z") == (MOD_WIN | R, 0x5A)
    assert parse_hotkey("Ctrl+F1") == (MOD_CONTROL | R, 0x70)
    assert parse_hotkey("Alt+F24") == (MOD_ALT | R, 0x87)
    assert parse_hotkey("F13") == (R, 0x7C)                       # F 키는 수정키 없이 허용
    assert parse_hotkey("Ctrl+Home")[1] == 0x24
    assert parse_hotkey("Ctrl+End")[1] == 0x23
    assert parse_hotkey("Ctrl+PageUp")[1] == 0x21
    assert parse_hotkey("Ctrl+PgDown")[1] == 0x22
    assert parse_hotkey("Ctrl+Insert")[1] == 0x2D
    assert parse_hotkey("Ctrl+Del")[1] == 0x2E
    assert parse_hotkey("Ctrl+Alt+Plus")[1] == 0xBB
    assert parse_hotkey("Ctrl++") == (MOD_CONTROL | R, 0xBB)       # Qt 표기 'Ctrl++'
    assert parse_hotkey("Ctrl+Alt+Minus")[1] == 0xBD
    assert parse_hotkey("Ctrl+-")[1] == 0xBD


@pytest.mark.parametrize("bad", ["", "   ", None, "Space", "A", "Ctrl+", "Ctrl+Alt", "Hyper+A", "Ctrl+F25",
                                 "Ctrl+F0", "Ctrl+AB", "Ctrl+Alt+Foo", 123])
def test_parse_hotkey_invalid(bad):
    from yamp.winplat.win_hotkeys import parse_hotkey
    assert parse_hotkey(bad) is None


@pytest.mark.skipif(not NOT_WIN, reason="비Windows no-op 확인")
def test_global_hotkeys_noop(app):
    from yamp.winplat.win_hotkeys import DEFAULT_BINDINGS, GlobalHotkeys
    got = []
    hk = GlobalHotkeys(1234, DEFAULT_BINDINGS, got.append)
    assert hk.registered == {} and hk.failed == [] and hk.invalid == []
    assert hk.nativeEventFilter(b"windows_generic_MSG", 0) == (False, 0)
    assert hk.nativeEventFilter(b"xcb_generic_event_t", 0) == (False, 0)
    hk.rebind({"toggle": "Ctrl+Alt+Space"})
    hk.unregister()
    hk.unregister()
    app.installNativeEventFilter(hk)
    app.removeNativeEventFilter(hk)
    assert got == []


# ---------------------------------------------------------------- 시스템 테마
def test_color_conversions():
    from yamp.winplat.win_theme import abgr_to_hex, argb_to_hex
    assert abgr_to_hex(0xFFD77800) == "#0078d7"                  # Windows 기본 파랑 (ABGR)
    assert abgr_to_hex(0x00332211) == "#112233"
    assert argb_to_hex(0xC40078D7) == "#0078d7"                  # ColorizationColor (ARGB)
    assert argb_to_hex(0x00112233) == "#112233"
    assert abgr_to_hex(-1) == "#ffffff"                           # 부호 있는 DWORD 도 안전
    assert argb_to_hex(0x1FFFFFFFF) == "#ffffff"


@pytest.mark.skipif(not NOT_WIN, reason="비Windows no-op 확인")
def test_system_theme_noop(app):
    from yamp.winplat.win_theme import ThemeWatcher, system_theme
    assert system_theme() == {"light": None, "accent": None}
    w = ThemeWatcher()
    assert w.start() == {"light": None, "accent": None}
    assert not w.is_active()                                      # 비Windows 기본 reader → 폴링 안 함
    w.stop()


def test_theme_watcher_emits_only_on_change(app):
    from yamp.winplat.win_theme import ThemeWatcher
    vals = [{"light": True, "accent": "#0078d7"}]
    w = ThemeWatcher(interval_ms=5000, reader=lambda: dict(vals[0]))
    got = []
    w.changed.connect(got.append)
    assert w.start() == vals[0] and w.is_active()
    w._poll()
    assert got == []                                              # 같으면 발생 안 함
    vals[0] = {"light": False, "accent": "#0078d7"}
    w._poll()
    w._poll()
    assert got == [{"light": False, "accent": "#0078d7"}]
    w.stop()
    assert not w.is_active()


def test_theme_watcher_reader_error(app):
    from yamp.winplat.win_theme import ThemeWatcher

    def boom():
        raise OSError("x")
    w = ThemeWatcher(reader=boom)
    assert w.start() == {"light": None, "accent": None}
    w._poll()
    w.stop()


# ---------------------------------------------------------------- 작업 표시줄
def test_thumbbutton_layout():
    from yamp.winplat.win_taskbar import THUMBBUTTON
    if struct.calcsize("P") == 8:
        assert ctypes.sizeof(THUMBBUTTON) == 552                  # x64 shobjidl.h 와 동일
        assert THUMBBUTTON.hIcon.offset == 16 and THUMBBUTTON.szTip.offset == 24 and THUMBBUTTON.dwFlags.offset == 544
    else:
        assert ctypes.sizeof(THUMBBUTTON) == 540
    assert THUMBBUTTON.szTip.size == 520                          # WCHAR[260] = 2바이트 × 260 (플랫폼 무관)


def test_thumbbutton_tip_utf16():
    from yamp.winplat.win_taskbar import (BTN_TOGGLE, THB_FLAGS, THB_ICON, THB_TOOLTIP, get_tip, make_button, set_tip)
    b = make_button(BTN_TOGGLE, None, "일시정지")
    assert b.dwMask == THB_ICON | THB_TOOLTIP | THB_FLAGS and b.iId == BTN_TOGGLE
    assert get_tip(b) == "일시정지"
    assert list(b.szTip[:4]) == [ord(c) for c in "일시정지"]      # BMP 문자 = 1 UTF-16 단위
    set_tip(b, "재생")
    assert get_tip(b) == "재생" and b.szTip[2] == 0
    set_tip(b, "가" * 400)                                        # 259자 + NUL 로 잘림
    assert len(get_tip(b)) == 259 and b.szTip[259] == 0
    set_tip(b, "🎵 a")                                            # 서로게이트 쌍
    assert get_tip(b) == "🎵 a"


def test_progress_key():
    from yamp.winplat.win_taskbar import progress_key
    assert progress_key(0, 200000, "playing") == ("playing", 0)
    assert progress_key(100000, 200000, "playing") == ("playing", 500)
    assert progress_key(100199, 200000, "playing") == ("playing", 500)   # 같은 천분율 → 같은 키 (COM 생략)
    assert progress_key(100200, 200000, "playing") == ("playing", 501)
    assert progress_key(100000, 200000, "paused") == ("paused", 500)
    assert progress_key(999999, 200000, "playing") == ("playing", 1000)  # 넘쳐도 1000
    assert progress_key(-5, 200000, "playing") == ("playing", 0)
    assert progress_key(5000, 0, "playing") == ("playing", 0)
    assert progress_key(5000, 0, "error") == ("error", 1000)
    assert progress_key(5000, 200000, "stopped") == ("stopped", 0)
    assert progress_key(5000, 200000, "weird") == ("stopped", 0)
    assert progress_key(None, None, "playing") == ("playing", 0)


def test_progress_throttle_counts_calls(app):
    """COM 호출 대신 _call 을 바꿔 끼워 '바뀔 때만 호출' 확인"""
    from yamp.winplat.win_taskbar import TBPF_NORMAL, TBPF_PAUSED, TaskbarControl
    t = TaskbarControl(0, lambda: None, lambda: None, lambda: None)
    calls = []
    t._ptr = 1                                                    # 가짜 '사용 가능'
    t._call = lambda name, *a: calls.append((name, a)) or True
    dur = 240000
    for ms in range(0, 2400, 10):                                # 10ms 간격 240번 → 천분율 0..9 → 10번 변화
        t.set_progress(ms, dur, "playing")
    assert len([c for c in calls if c[0] == "SetProgressValue"]) == 10
    assert calls[1] == ("SetProgressState", (TBPF_NORMAL,))
    n = len(calls)
    t.set_progress(2390, dur, "playing")
    assert len(calls) == n                                        # 변화 없음 → 호출 없음
    t.set_progress(2390, dur, "paused")
    assert calls[-1] == ("SetProgressState", (TBPF_PAUSED,))
    n = len(calls)
    t.set_progress(0, dur, "stopped")
    assert calls[n:] == [("SetProgressState", (0,))]              # 정지 → 값 설정 없이 NOPROGRESS 만
    t._call = lambda name, *a: False                              # 실패 (버튼 생성 전 등) → 키 기억 안 함 → 다음에 재시도
    t.set_progress(1000, dur, "playing")
    assert t._key is None
    t._ptr = None
    t._call = lambda *a: True


@pytest.mark.skipif(not NOT_WIN, reason="비Windows no-op 확인")
def test_taskbar_noop(app):
    from yamp.winplat.win_taskbar import TaskbarControl
    hits = []
    t = TaskbarControl(1234, lambda: hits.append("p"), lambda: hits.append("t"), lambda: hits.append("n"))
    assert t.available is False
    t.set_playing(True)
    t.set_playing(False)
    t.set_progress(1000, 2000, "playing")
    t.set_progress(1000, 2000, "error")
    assert t.nativeEventFilter(b"windows_generic_MSG", 0) == (False, 0)
    app.installNativeEventFilter(t)
    app.removeNativeEventFilter(t)
    t.close()
    t.close()
    assert hits == []


def test_thumb_icons_paint_on_qimage(app):
    """HICON 변환 직전 단계 (QImage 에 아이콘 그리기) 는 어디서나 동작해야 함"""
    from PyQt6.QtGui import QColor, QImage
    from yamp.ui import icons
    for name in ("prev", "play", "pause", "next"):
        img = QImage(32, 32, QImage.Format.Format_ARGB32_Premultiplied)
        img.fill(QColor(0, 0, 0, 0))
        icons.paint(img, name, "#f2f4f8", 2.2)
        assert any(img.pixelColor(x, y).alpha() > 0 for x in range(32) for y in range(32)), name


def test_vtable_order():
    from yamp.winplat.win_taskbar import VT, VTBL
    assert len(VTBL) == 21
    assert VT["HrInit"] == 3 and VT["MarkFullscreenWindow"] == 8
    assert VT["SetProgressValue"] == 9 and VT["SetProgressState"] == 10
    assert VT["ThumbBarAddButtons"] == 15 and VT["ThumbBarUpdateButtons"] == 16 and VT["SetThumbnailClip"] == 20


# ---------------------------------------------------------------- SMTC / 전원
@pytest.mark.skipif(not NOT_WIN, reason="비Windows no-op 확인")
def test_smtc_noop(app):
    from yamp.winplat.win_smtc import Smtc
    s = Smtc()
    assert s.available is False
    got = []
    s.command.connect(got.append)
    s.set_metadata("제목", "가수", "앨범", b"\x89PNG")
    s.set_state("playing")
    s.set_timeline(1000, 2000)
    s.close()
    assert got == []
    Smtc().close()                                                # 두 번째 생성도 안전 (로그는 한 번만)


def test_smtc_signal_queued_to_qt_thread(app):
    """내부 _raw → command 는 QueuedConnection (WinRT 스레드 → Qt 스레드)"""
    from yamp.winplat.win_smtc import Smtc
    s = Smtc()
    got = []
    s.command.connect(got.append)
    s._raw.emit("next")
    assert got == []                                              # 큐 처리 전
    app.processEvents()
    assert got == ["next"]
    s.close()


@pytest.mark.skipif(not NOT_WIN, reason="비Windows no-op 확인")
def test_power_noop():
    from yamp.winplat import power
    assert power.sleep_pc() is False
    assert power.shutdown_pc(60) is False
    assert power.cancel_shutdown() is False


def test_package_imports():
    import importlib
    import yamp.winplat as p
    for m in ("power", "win_hotkeys", "win_smtc", "win_taskbar", "win_theme"):
        assert importlib.import_module("yamp.winplat." + m)
    assert p.IS_WIN == (sys.platform == "win32")
