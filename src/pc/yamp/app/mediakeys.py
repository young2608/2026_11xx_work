"""Windows 전역 미디어 키 (창이 비활성이어도 동작). RegisterHotKey + 네이티브 이벤트 필터.
다른 앱이 이미 키를 잡고 있으면 등록 실패 → 조용히 무시 (창 활성 시 Qt 키 처리로 동작)."""
import sys

from PyQt6.QtCore import QAbstractNativeEventFilter

WM_HOTKEY = 0x0312
KEYS = {1: 0xB3, 2: 0xB0, 3: 0xB1, 4: 0xB2}   # play/pause, next, prev, stop
NAMES = {1: "toggle", 2: "next", 3: "prev", 4: "stop"}


class WinMediaKeys(QAbstractNativeEventFilter):
    def __init__(self, hwnd: int, callback):
        super().__init__()
        self.hwnd = hwnd
        self.cb = callback
        self.ok = []
        if sys.platform != "win32":
            return
        import ctypes
        self.user32 = ctypes.windll.user32
        for hid, vk in KEYS.items():
            if self.user32.RegisterHotKey(hwnd, hid, 0x4000, vk):   # MOD_NOREPEAT
                self.ok.append(hid)

    def nativeEventFilter(self, event_type, message):
        if sys.platform == "win32" and self.ok and event_type in (b"windows_generic_MSG", "windows_generic_MSG"):
            import ctypes.wintypes
            msg = ctypes.wintypes.MSG.from_address(int(message))
            if msg.message == WM_HOTKEY and msg.wParam in NAMES:
                self.cb(NAMES[msg.wParam])
                return True, 0
        return False, 0

    def unregister(self):
        if sys.platform == "win32":
            for hid in self.ok:
                self.user32.UnregisterHotKey(self.hwnd, hid)
        self.ok = []
