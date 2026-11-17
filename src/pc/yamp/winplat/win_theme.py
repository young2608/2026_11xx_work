"""Windows 밝게/어둡게 모드 · 강조색 (vr0.1.0.009)

  system_theme() -> {"light": bool|None, "accent": "#rrggbb"|None}
    light  : HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize  AppsUseLightTheme (1=밝게)
    accent : HKCU\\Software\\Microsoft\\Windows\\DWM  AccentColor (DWORD ABGR)
             없으면 ColorizationColor (DWORD ARGB)
  비Windows / 값 없음 → None

  ThemeWatcher : start() 했을 때만 5초마다 레지스트리 읽기, 바뀌었을 때만 changed(dict) 발생.
  stop() 하면 타이머 정지 (폴링 0).

레지스트리 읽기는 winreg (MSYS2 mingw Python 에도 포함) → 없으면 ctypes RegGetValueW 로 대체.
"""
import logging
import sys

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

log = logging.getLogger("yamp.win")

KEY_PERSONALIZE = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
KEY_DWM = r"Software\Microsoft\Windows\DWM"
EMPTY = {"light": None, "accent": None}


def abgr_to_hex(dword: int) -> str:
    """0xAABBGGRR → '#rrggbb' (DWM AccentColor)"""
    d = int(dword) & 0xFFFFFFFF
    return "#%02x%02x%02x" % (d & 0xFF, (d >> 8) & 0xFF, (d >> 16) & 0xFF)


def argb_to_hex(dword: int) -> str:
    """0xAARRGGBB → '#rrggbb' (DWM ColorizationColor)"""
    d = int(dword) & 0xFFFFFFFF
    return "#%02x%02x%02x" % ((d >> 16) & 0xFF, (d >> 8) & 0xFF, d & 0xFF)


def _read_dword_winreg(subkey: str, name: str):
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, subkey) as k:
            v, t = winreg.QueryValueEx(k, name)
        return int(v) & 0xFFFFFFFF if t == winreg.REG_DWORD else None
    except OSError:
        return None


_RegGetValueW = None


def _read_dword_ctypes(subkey: str, name: str):
    global _RegGetValueW
    import ctypes
    from ctypes import wintypes
    if _RegGetValueW is None:
        fn = ctypes.WinDLL("advapi32").RegGetValueW
        fn.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
                       ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p, ctypes.POINTER(wintypes.DWORD)]
        fn.restype = ctypes.c_long
        _RegGetValueW = fn
    HKCU = ctypes.c_void_p(0x80000001)
    RRF_RT_REG_DWORD = 0x10
    val = wintypes.DWORD(0)
    size = wintypes.DWORD(4)
    rc = _RegGetValueW(HKCU, subkey, name, RRF_RT_REG_DWORD, None, ctypes.byref(val), ctypes.byref(size))
    return int(val.value) if rc == 0 else None


def _has_winreg() -> bool:
    import importlib.util
    return importlib.util.find_spec("winreg") is not None


def _read_dword(subkey: str, name: str):
    if _has_winreg():
        return _read_dword_winreg(subkey, name)
    return _read_dword_ctypes(subkey, name)


def system_theme() -> dict:
    if sys.platform != "win32":
        return dict(EMPTY)
    try:
        lt = _read_dword(KEY_PERSONALIZE, "AppsUseLightTheme")
        acc = _read_dword(KEY_DWM, "AccentColor")
        if acc is not None:
            accent = abgr_to_hex(acc)
        else:
            col = _read_dword(KEY_DWM, "ColorizationColor")
            accent = argb_to_hex(col) if col is not None else None
        return {"light": None if lt is None else bool(lt), "accent": accent}
    except Exception as e:                      # noqa: BLE001
        log.warning("시스템 테마 읽기 실패: %s", e)
        return dict(EMPTY)


class ThemeWatcher(QObject):
    """시스템 테마 변경 감시 — start() 동안만 폴링, 바뀔 때만 changed 발생"""
    changed = pyqtSignal(dict)

    def __init__(self, parent=None, interval_ms: int = 5000, reader=None):
        super().__init__(parent)
        self._reader = reader or system_theme
        self._custom = reader is not None
        self._last = None
        self._timer = QTimer(self)
        self._timer.setInterval(max(500, int(interval_ms)))
        self._timer.timeout.connect(self._poll)

    @property
    def current(self) -> dict:
        return dict(self._last) if self._last is not None else self._read()

    def _read(self) -> dict:
        try:
            r = self._reader()
            return dict(r) if isinstance(r, dict) else dict(EMPTY)
        except Exception as e:                  # noqa: BLE001
            log.warning("테마 감시 읽기 오류: %s", e)
            return dict(EMPTY)

    def start(self) -> dict:
        """기준값을 읽고 (발생 없음) 폴링 시작. 현재 테마 반환. 비Windows(기본 reader) 는 타이머를 켜지 않음"""
        self._last = self._read()
        if (sys.platform == "win32" or self._custom) and not self._timer.isActive():
            self._timer.start()
        return dict(self._last)

    def stop(self):
        self._timer.stop()

    def is_active(self) -> bool:
        return self._timer.isActive()

    def _poll(self):
        now = self._read()
        if now != self._last:
            self._last = now
            self.changed.emit(dict(now))
