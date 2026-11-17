"""사용자 지정 전역 단축키 (vr0.1.0.009) — 창이 비활성/최소화여도 동작.

mediakeys.py 와 같은 RegisterHotKey + QAbstractNativeEventFilter 방식.
  - id 는 100 부터 (mediakeys 가 1~4 사용)
  - 다른 앱이 이미 잡은 조합은 등록 실패 → failed 에 기록 (설정 화면에서 안내용)
  - 글자 해석 실패 → invalid 에 기록
  - parse_hotkey() 는 순수 함수 (Linux 테스트 가능)

사용
  hk = GlobalHotkeys(int(win.winId()), cfg_bindings or DEFAULT_BINDINGS, on_action)
  QApplication.instance().installNativeEventFilter(hk)
  ...  종료 시  hk.unregister(); app.removeNativeEventFilter(hk)
"""
import logging
import sys

from PyQt6.QtCore import QAbstractNativeEventFilter

log = logging.getLogger("yamp.win")

WM_HOTKEY = 0x0312
MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN, MOD_NOREPEAT = 0x1, 0x2, 0x4, 0x8, 0x4000
ID_BASE = 100
ERROR_HOTKEY_ALREADY_REGISTERED = 1409

DEFAULT_BINDINGS = {
    "toggle": "Ctrl+Alt+Space",
    "next": "Ctrl+Alt+Right",
    "prev": "Ctrl+Alt+Left",
    "vol_up": "Ctrl+Alt+Up",
    "vol_down": "Ctrl+Alt+Down",
    "show": "Ctrl+Alt+P",
}

_MODS = {"ctrl": MOD_CONTROL, "control": MOD_CONTROL, "alt": MOD_ALT, "shift": MOD_SHIFT,
         "win": MOD_WIN, "meta": MOD_WIN, "super": MOD_WIN}

# 이름 → 가상 키 코드 (소문자 비교)
_VK = {
    "space": 0x20, "left": 0x25, "up": 0x26, "right": 0x27, "down": 0x28,
    "home": 0x24, "end": 0x23,
    "pageup": 0x21, "pgup": 0x21, "pagedown": 0x22, "pgdown": 0x22, "pgdn": 0x22,
    "insert": 0x2D, "ins": 0x2D, "delete": 0x2E, "del": 0x2E,
    "plus": 0xBB, "=": 0xBB, "minus": 0xBD, "-": 0xBD,      # VK_OEM_PLUS / VK_OEM_MINUS (메인 키보드)
    "esc": 0x1B, "escape": 0x1B, "tab": 0x09, "backspace": 0x08, "enter": 0x0D, "return": 0x0D,
}


def parse_hotkey(text: str):
    """"Ctrl+Alt+Space" → (mods | MOD_NOREPEAT, vk), 해석 불가 → None.

    - 대소문자 무시, 공백 무시, 'Ctrl++' 처럼 끝의 '+' 는 Plus 키
    - 수정키 없는 조합은 F1~F24 만 허용 (일반 글자 키를 시스템 전체에서 뺏지 않도록)"""
    if not isinstance(text, str):
        return None
    s = text.replace(" ", "").strip()
    if not s:
        return None
    if s == "+" or s.endswith("++"):
        rest, key = s[:-2] if len(s) > 1 else "", "plus"
    else:
        rest, _, key = s.rpartition("+")
    mods = 0
    for tok in (t for t in rest.split("+") if t):
        m = _MODS.get(tok.lower())
        if m is None:
            return None
        mods |= m
    k = key.lower()
    if not k:
        return None
    is_fkey = False
    if len(k) == 1 and ("a" <= k <= "z" or "0" <= k <= "9"):
        vk = ord(k.upper())
    elif k[0] == "f" and k[1:].isdigit() and 1 <= int(k[1:]) <= 24:
        vk = 0x70 + int(k[1:]) - 1
        is_fkey = True
    elif k in _VK:
        vk = _VK[k]
    else:
        return None
    if not mods and not is_fkey:
        return None
    return mods | MOD_NOREPEAT, vk


class GlobalHotkeys(QAbstractNativeEventFilter):
    def __init__(self, hwnd: int, bindings: dict, callback):
        super().__init__()
        self.hwnd = int(hwnd or 0)
        self.cb = callback
        self.registered: dict[str, str] = {}    # action → 등록된 키 글자
        self.failed: list[str] = []             # 다른 앱이 사용 중 (등록 실패) action
        self.invalid: list[str] = []            # 글자 해석 실패 action
        self._ids: dict[int, str] = {}          # hotkey id → action
        self._user32 = None
        if sys.platform != "win32":
            return
        try:
            import ctypes
            from ctypes import wintypes
            u = ctypes.WinDLL("user32", use_last_error=True)   # 별도 인스턴스 (mediakeys 의 windll.user32 argtypes 와 분리)
            u.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
            u.RegisterHotKey.restype = wintypes.BOOL
            u.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
            u.UnregisterHotKey.restype = wintypes.BOOL
            self._user32 = u
            self._ctypes = ctypes
        except Exception as e:                  # noqa: BLE001
            log.warning("전역 단축키 사용 불가: %s", e)
            self._user32 = None
            return
        self._register(bindings or {})

    # ------------------------------------------------------------ 등록
    def _register(self, bindings: dict):
        if self._user32 is None:
            return
        hid = ID_BASE
        for action, text in bindings.items():
            if not text:                        # 빈 값 = 사용 안 함
                continue
            pk = parse_hotkey(text)
            if pk is None:
                self.invalid.append(action)
                log.info("전역 단축키 해석 실패: %s=%r", action, text)
                continue
            try:
                ok = self._user32.RegisterHotKey(self.hwnd, hid, pk[0], pk[1])
            except Exception as e:              # noqa: BLE001
                log.warning("RegisterHotKey 오류 %s: %s", action, e)
                ok = False
            if ok:
                self._ids[hid] = action
                self.registered[action] = text
            else:
                self.failed.append(action)
                err = self._ctypes.get_last_error()
                log.info("전역 단축키 등록 실패 %s=%s (err %s%s)", action, text, err,
                         " — 다른 앱이 사용 중" if err == ERROR_HOTKEY_ALREADY_REGISTERED else "")
            hid += 1

    def rebind(self, bindings: dict):
        """설정 변경 시 — 모두 해제 후 다시 등록"""
        self.unregister()
        self._register(bindings or {})

    def unregister(self):
        if self._user32 is not None:
            for hid in self._ids:
                try:
                    self._user32.UnregisterHotKey(self.hwnd, hid)
                except Exception:               # noqa: BLE001
                    pass
        self._ids = {}
        self.registered = {}
        self.failed = []
        self.invalid = []

    # ------------------------------------------------------------ 이벤트
    def nativeEventFilter(self, event_type, message):
        # 모든 Windows 메시지가 지나가므로 짧게. 예외가 PyQt 가상함수 밖으로 나가면 앱이 죽을 수 있어 전부 잡음
        if not self._ids or event_type not in (b"windows_generic_MSG", "windows_generic_MSG"):
            return False, 0
        try:
            from ctypes import wintypes
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == WM_HOTKEY:
                action = self._ids.get(int(msg.wParam))
                if action is not None:
                    try:
                        self.cb(action)
                    except Exception:           # noqa: BLE001
                        log.exception("전역 단축키 콜백 오류: %s", action)
                    return True, 0
        except Exception:                       # noqa: BLE001
            log.exception("전역 단축키 이벤트 처리 오류")
        return False, 0
