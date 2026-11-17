"""작업 표시줄 썸네일 버튼 + 진행률 막대 (vr0.1.0.009) — ITaskbarList3 를 ctypes COM vtable 로 직접 호출.

  썸네일 미리보기 아래 3 버튼 : [이전] [재생/일시정지] [다음]  (클릭 → WM_COMMAND, HIWORD(wParam)=THBN_CLICKED)
  작업 표시줄 버튼 진행률     : 재생=초록(NORMAL) 일시정지=노랑(PAUSED) 정지=없음 오류=빨강(ERROR)

흐름
  Explorer 가 작업 표시줄 버튼을 만들면 "TaskbarButtonCreated" 등록 메시지를 창에 보냄
   → (재)ThumbBarAddButtons + 마지막 진행률 다시 적용 (Explorer 재시작 시에도 복구)
  이미 버튼이 있는 상태(창 표시 후 생성)면 생성자에서 바로 추가 시도

규칙
  - 비Windows: available=False, 모든 메서드 no-op
  - COM/아이콘 실패: 로그("yamp.win") 후 그 기능만 끔. 예외는 절대 밖으로 나가지 않음
  - set_progress 는 progress_key() (천분율·상태) 가 바뀔 때만 COM 호출 (초당 수십 번 불러도 가벼움)
"""
import ctypes
import logging
import struct
import sys

from PyQt6.QtCore import QAbstractNativeEventFilter

log = logging.getLogger("yamp.win")

IS_WIN = sys.platform == "win32"
IS_64 = struct.calcsize("P") == 8

CLSID_TaskbarList = "{56FDF344-FD6D-11d0-958A-006097C9A090}"
IID_ITaskbarList3 = "{ea1afb91-9e28-4b86-90e9-9e9f8a5eee84}"

# vtable 순서 : IUnknown(3) + ITaskbarList(5) + ITaskbarList2(1) + ITaskbarList3(12)
VTBL = ("QueryInterface", "AddRef", "Release",
        "HrInit", "AddTab", "DeleteTab", "ActivateTab", "SetActiveAlt",
        "MarkFullscreenWindow",
        "SetProgressValue", "SetProgressState", "RegisterTab", "UnregisterTab", "SetTabOrder", "SetTabActive",
        "ThumbBarAddButtons", "ThumbBarUpdateButtons", "ThumbBarSetImageList", "SetOverlayIcon",
        "SetThumbnailTooltip", "SetThumbnailClip")
VT = {n: i for i, n in enumerate(VTBL)}

# TBPFLAG
TBPF_NOPROGRESS, TBPF_INDETERMINATE, TBPF_NORMAL, TBPF_ERROR, TBPF_PAUSED = 0x0, 0x1, 0x2, 0x4, 0x8
STATE_FLAGS = {"playing": TBPF_NORMAL, "paused": TBPF_PAUSED, "stopped": TBPF_NOPROGRESS, "error": TBPF_ERROR}
# THUMBBUTTONMASK / THUMBBUTTONFLAGS
THB_BITMAP, THB_ICON, THB_TOOLTIP, THB_FLAGS = 0x1, 0x2, 0x4, 0x8
THBF_ENABLED, THBF_DISABLED, THBF_DISMISSONCLICK, THBF_NOBACKGROUND = 0x0, 0x1, 0x2, 0x4
THBN_CLICKED = 0x1800
WM_COMMAND = 0x0111

BTN_PREV, BTN_TOGGLE, BTN_NEXT = 101, 102, 103
ICON_COLOR = None          # None = ui.skin.TASKBAR_ICON (작업 표시줄은 Windows 색 → 앱 테마와 무관)
TIP_PLAY, TIP_PAUSE, TIP_PREV, TIP_NEXT = "재생", "일시정지", "이전 곡", "다음 곡"


class THUMBBUTTON(ctypes.Structure):
    """shobjidl.h THUMBBUTTON — WCHAR 는 c_uint16 배열로 (Linux c_wchar 는 4바이트라 레이아웃이 달라짐).
    x64: 552 바이트, x86: 540 바이트"""
    _fields_ = [("dwMask", ctypes.c_uint32),
                ("iId", ctypes.c_uint32),
                ("iBitmap", ctypes.c_uint32),
                ("hIcon", ctypes.c_void_p),
                ("szTip", ctypes.c_uint16 * 260),
                ("dwFlags", ctypes.c_uint32)]


def set_tip(btn: THUMBBUTTON, text: str):
    """UTF-16-LE 로 szTip 채움 (최대 259자 + NUL)"""
    data = (text or "").encode("utf-16-le")[: 259 * 2]
    units = struct.unpack("<%dH" % (len(data) // 2), data)
    for i in range(260):
        btn.szTip[i] = units[i] if i < len(units) else 0


def get_tip(btn: THUMBBUTTON) -> str:
    units = []
    for u in btn.szTip:
        if u == 0:
            break
        units.append(u)
    return struct.pack("<%dH" % len(units), *units).decode("utf-16-le", "replace")


def make_button(bid: int, hicon, tip: str, flags: int = THBF_ENABLED) -> THUMBBUTTON:
    b = THUMBBUTTON()
    b.dwMask = THB_ICON | THB_TOOLTIP | THB_FLAGS
    b.iId = bid
    b.iBitmap = 0
    b.hIcon = hicon or None
    set_tip(b, tip)
    b.dwFlags = flags
    return b


def progress_key(pos_ms: int, dur_ms: int, state: str) -> tuple[str, int]:
    """(상태, 천분율 0~1000) — 이 값이 바뀔 때만 COM 호출.
    stopped → 0 / 알 수 없는 상태 → stopped / error 인데 길이 모름 → 1000 (빨간 막대가 보이게)"""
    st = state if state in STATE_FLAGS else "stopped"
    if st == "stopped":
        return st, 0
    try:
        d = int(dur_ms or 0)
        p = int(pos_ms or 0)
    except (TypeError, ValueError):
        d, p = 0, 0
    if d <= 0:
        return st, 1000 if st == "error" else 0
    return st, max(0, min(1000, p * 1000 // d))


# ====================================================================== Windows 전용 ctypes 도우미
class _GUID(ctypes.Structure):
    _fields_ = [("Data1", ctypes.c_uint32), ("Data2", ctypes.c_uint16), ("Data3", ctypes.c_uint16),
                ("Data4", ctypes.c_ubyte * 8)]


class _ICONINFO(ctypes.Structure):
    _fields_ = [("fIcon", ctypes.c_int), ("xHotspot", ctypes.c_uint32), ("yHotspot", ctypes.c_uint32),
                ("hbmMask", ctypes.c_void_p), ("hbmColor", ctypes.c_void_p)]


class _BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", ctypes.c_uint32), ("biWidth", ctypes.c_int32), ("biHeight", ctypes.c_int32),
                ("biPlanes", ctypes.c_uint16), ("biBitCount", ctypes.c_uint16), ("biCompression", ctypes.c_uint32),
                ("biSizeImage", ctypes.c_uint32), ("biXPelsPerMeter", ctypes.c_int32),
                ("biYPelsPerMeter", ctypes.c_int32), ("biClrUsed", ctypes.c_uint32), ("biClrImportant", ctypes.c_uint32)]


class _BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", _BITMAPINFOHEADER), ("bmiColors", ctypes.c_uint32 * 1)]


_api = None


def _win_api():
    """user32/gdi32/ole32 함수 원형 (별도 WinDLL 인스턴스 — 다른 모듈의 windll.* argtypes 와 섞이지 않게)"""
    global _api
    if _api is not None:
        return _api
    from ctypes import wintypes as w
    VP = ctypes.c_void_p
    u = ctypes.WinDLL("user32", use_last_error=True)
    g = ctypes.WinDLL("gdi32")
    o = ctypes.WinDLL("ole32")
    for fn, args, res in (
            (u.RegisterWindowMessageW, [w.LPCWSTR], w.UINT),
            (u.CreateIconIndirect, [ctypes.POINTER(_ICONINFO)], VP),
            (u.DestroyIcon, [VP], w.BOOL),
            (u.GetSystemMetrics, [ctypes.c_int], ctypes.c_int),
            (g.CreateDIBSection, [VP, ctypes.POINTER(_BITMAPINFO), w.UINT, ctypes.POINTER(VP), VP, w.DWORD], VP),
            (g.CreateBitmap, [ctypes.c_int, ctypes.c_int, w.UINT, w.UINT, VP], VP),
            (g.DeleteObject, [VP], w.BOOL),
            (o.CoInitializeEx, [VP, w.DWORD], ctypes.c_long),
            (o.CoUninitialize, [], None),
            (o.CLSIDFromString, [w.LPCWSTR, ctypes.POINTER(_GUID)], ctypes.c_long),
            (o.CoCreateInstance, [ctypes.POINTER(_GUID), VP, w.DWORD, ctypes.POINTER(_GUID), ctypes.POINTER(VP)],
             ctypes.c_long)):
        fn.argtypes = args
        fn.restype = res
    _api = {"user32": u, "gdi32": g, "ole32": o}
    return _api


def _guid(text: str) -> _GUID:
    g = _GUID()
    hr = _win_api()["ole32"].CLSIDFromString(text, ctypes.byref(g))
    if hr < 0:
        raise OSError("CLSIDFromString 0x%08x" % (hr & 0xFFFFFFFF))
    return g


def _qimage_to_hicon(img) -> int:
    """QImage → HICON. PyQt6 에 QImage.toHICON 이 있으면 사용 (Windows 빌드에만 존재), 없으면 32bpp DIB + CreateIconIndirect"""
    from PyQt6.QtGui import QImage
    fn = getattr(img, "toHICON", None)
    if callable(fn):
        try:
            h = int(fn())
            if h:
                return h
        except Exception as e:                  # noqa: BLE001
            log.debug("QImage.toHICON 실패 → ctypes 대체: %s", e)
    a = _win_api()
    im = img.convertToFormat(QImage.Format.Format_ARGB32)        # 메모리상 BGRA (비곱셈 알파) — 32bpp 아이콘 형식과 같음
    w_, h_ = im.width(), im.height()
    bpl = im.bytesPerLine()
    ptr = im.constBits()
    ptr.setsize(im.sizeInBytes())
    raw = bytes(ptr)
    bi = _BITMAPINFO()
    bi.bmiHeader.biSize = ctypes.sizeof(_BITMAPINFOHEADER)
    bi.bmiHeader.biWidth = w_
    bi.bmiHeader.biHeight = -h_                                   # top-down
    bi.bmiHeader.biPlanes = 1
    bi.bmiHeader.biBitCount = 32
    bi.bmiHeader.biCompression = 0                                # BI_RGB
    bits = ctypes.c_void_p()
    hbm_color = a["gdi32"].CreateDIBSection(None, ctypes.byref(bi), 0, ctypes.byref(bits), None, 0)
    if not hbm_color or not bits.value:
        raise OSError("CreateDIBSection 실패")
    hbm_mask = None
    try:
        for y in range(h_):                                       # DIB 줄 폭 = w*4 (32bpp 는 패딩 없음)
            ctypes.memmove(bits.value + y * w_ * 4, raw[y * bpl: y * bpl + w_ * 4], w_ * 4)
        mask_bytes = ((w_ + 15) // 16) * 2 * h_                    # 1bpp, WORD 정렬 — 전부 0 (알파 채널 사용)
        mask_buf = ctypes.create_string_buffer(mask_bytes)
        hbm_mask = a["gdi32"].CreateBitmap(w_, h_, 1, 1, mask_buf)
        ii = _ICONINFO(1, 0, 0, hbm_mask, hbm_color)
        hicon = a["user32"].CreateIconIndirect(ctypes.byref(ii))
        if not hicon:
            raise OSError("CreateIconIndirect 실패 (err %s)" % ctypes.get_last_error())
        return int(hicon)
    finally:
        a["gdi32"].DeleteObject(hbm_color)
        if hbm_mask:
            a["gdi32"].DeleteObject(hbm_mask)


def _make_hicon(name: str, size: int) -> int:
    from PyQt6.QtGui import QColor, QImage
    from ..ui import icons
    img = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(QColor(0, 0, 0, 0))
    from ..ui import skin
    icons.paint(img, name, ICON_COLOR or skin.TASKBAR_ICON, 2.2)
    return _qimage_to_hicon(img)


# ====================================================================== 본체
class TaskbarControl(QAbstractNativeEventFilter):
    def __init__(self, hwnd: int, on_prev, on_toggle, on_next):
        super().__init__()
        self.hwnd = int(hwnd or 0)
        self._cbs = {BTN_PREV: on_prev, BTN_TOGGLE: on_toggle, BTN_NEXT: on_next}
        self._ptr = None                # ITaskbarList3*
        self._fns = {}
        self._co_init = False
        self._icons = {}                # 이름 → HICON
        self._buttons_added = False
        self._playing = False
        self._key = None                # 마지막으로 적용한 progress_key
        self._last_args = (0, 0, "stopped")
        self._msg_created = 0
        self._thumbs_ok = True
        if not IS_WIN or not self.hwnd:
            return
        try:
            self._init_com()
        except Exception as e:          # noqa: BLE001
            log.warning("작업 표시줄 기능 사용 불가: %s", e)
            self._release()
            return
        try:
            self._msg_created = int(_win_api()["user32"].RegisterWindowMessageW("TaskbarButtonCreated"))
        except Exception as e:          # noqa: BLE001
            log.debug("RegisterWindowMessageW 실패: %s", e)
        self._add_buttons()             # 창이 이미 표시된 상태면 바로 성공 (아니면 TaskbarButtonCreated 때 재시도)

    # ------------------------------------------------------------ COM
    def _init_com(self):
        a = _win_api()
        hr = a["ole32"].CoInitializeEx(None, 0x2)                 # COINIT_APARTMENTTHREADED (Qt 가 이미 했으면 S_FALSE)
        self._co_init = hr >= 0                                  # RPC_E_CHANGED_MODE(음수) 면 짝 맞출 필요 없음
        clsid, iid = _guid(CLSID_TaskbarList), _guid(IID_ITaskbarList3)
        p = ctypes.c_void_p()
        hr = a["ole32"].CoCreateInstance(ctypes.byref(clsid), None, 0x1, ctypes.byref(iid), ctypes.byref(p))  # CLSCTX_INPROC_SERVER
        if hr < 0 or not p.value:
            raise OSError("CoCreateInstance(TaskbarList) 0x%08x" % (hr & 0xFFFFFFFF))
        self._ptr = p.value
        from ctypes import wintypes as w
        L, VP = ctypes.c_long, ctypes.c_void_p
        protos = {
            "Release": ctypes.WINFUNCTYPE(ctypes.c_ulong, VP),
            "HrInit": ctypes.WINFUNCTYPE(L, VP),
            "SetProgressValue": ctypes.WINFUNCTYPE(L, VP, w.HWND, ctypes.c_ulonglong, ctypes.c_ulonglong),
            "SetProgressState": ctypes.WINFUNCTYPE(L, VP, w.HWND, ctypes.c_int),
            "ThumbBarAddButtons": ctypes.WINFUNCTYPE(L, VP, w.HWND, w.UINT, ctypes.POINTER(THUMBBUTTON)),
            "ThumbBarUpdateButtons": ctypes.WINFUNCTYPE(L, VP, w.HWND, w.UINT, ctypes.POINTER(THUMBBUTTON)),
        }
        vtbl = ctypes.cast(ctypes.c_void_p(self._ptr), ctypes.POINTER(ctypes.c_void_p))[0]
        slots = ctypes.cast(ctypes.c_void_p(vtbl), ctypes.POINTER(ctypes.c_void_p))
        self._fns = {n: proto(slots[VT[n]]) for n, proto in protos.items()}
        hr = self._fns["HrInit"](self._ptr)
        if hr < 0:
            raise OSError("ITaskbarList3.HrInit 0x%08x" % (hr & 0xFFFFFFFF))

    def _call(self, name: str, *args) -> bool:
        if not self._ptr:
            return False
        try:
            hr = self._fns[name](self._ptr, self.hwnd, *args)
        except Exception as e:          # noqa: BLE001
            log.debug("%s 오류: %s", name, e)
            return False
        if hr < 0:
            log.debug("%s 실패 0x%08x", name, hr & 0xFFFFFFFF)
            return False
        return True

    def _release(self):
        if self._ptr and "Release" in self._fns:
            try:
                self._fns["Release"](self._ptr)
            except Exception:           # noqa: BLE001
                pass
        self._ptr = None
        self._fns = {}
        if self._co_init:
            try:
                _win_api()["ole32"].CoUninitialize()
            except Exception:           # noqa: BLE001
                pass
            self._co_init = False

    @property
    def available(self) -> bool:
        return bool(self._ptr)

    # ------------------------------------------------------------ 썸네일 버튼
    def _hicon(self, name: str):
        if name not in self._icons:
            try:
                size = max(16, int(_win_api()["user32"].GetSystemMetrics(49)))   # SM_CXSMICON (DPI 반영)
                self._icons[name] = _make_hicon(name, size)
            except Exception as e:      # noqa: BLE001
                log.debug("썸네일 아이콘 생성 실패 %s: %s", name, e)
                self._icons[name] = 0
        return self._icons[name] or None

    def _buttons(self):
        arr = (THUMBBUTTON * 3)()
        arr[0] = make_button(BTN_PREV, self._hicon("prev"), TIP_PREV)
        arr[1] = self._toggle_button()
        arr[2] = make_button(BTN_NEXT, self._hicon("next"), TIP_NEXT)
        return arr

    def _toggle_button(self) -> THUMBBUTTON:
        # 재생 중 → '일시정지' 버튼, 아니면 '재생' 버튼
        if self._playing:
            return make_button(BTN_TOGGLE, self._hicon("pause"), TIP_PAUSE)
        return make_button(BTN_TOGGLE, self._hicon("play"), TIP_PLAY)

    def _add_buttons(self):
        if not self._ptr or not self._thumbs_ok:
            return
        arr = self._buttons()
        if self._call("ThumbBarAddButtons", 3, arr):
            self._buttons_added = True
        elif self._call("ThumbBarUpdateButtons", 3, arr):         # 같은 버튼에 이미 추가됨
            self._buttons_added = True

    def set_playing(self, playing: bool):
        playing = bool(playing)
        if playing == self._playing:
            return
        self._playing = playing
        if self._ptr and self._buttons_added:
            b = (THUMBBUTTON * 1)(self._toggle_button())
            self._call("ThumbBarUpdateButtons", 1, b)

    # ------------------------------------------------------------ 진행률
    def set_progress(self, pos_ms: int, dur_ms: int, state: str):
        self._last_args = (pos_ms, dur_ms, state)
        if not self._ptr:
            return
        key = progress_key(pos_ms, dur_ms, state)
        if key == self._key:
            return
        st, permille = key
        ok = True
        if st != "stopped":
            ok = self._call("SetProgressValue", permille, 1000)
        ok = self._call("SetProgressState", STATE_FLAGS[st]) and ok
        self._key = key if ok else None                           # 실패(버튼 생성 전 등) → 다음에 재시도

    # ------------------------------------------------------------ 이벤트
    def nativeEventFilter(self, event_type, message):
        # 모든 메시지가 지나감 → 빠르게 거르고, 예외는 절대 PyQt 밖으로 내보내지 않음 (앱 abort 방지)
        if not self._ptr or event_type not in (b"windows_generic_MSG", "windows_generic_MSG"):
            return False, 0
        try:
            from ctypes import wintypes
            msg = wintypes.MSG.from_address(int(message))
            m = msg.message
            if m == WM_COMMAND:
                wp = int(msg.wParam)
                if (wp >> 16) & 0xFFFF == THBN_CLICKED and int(msg.hWnd or 0) == self.hwnd:
                    cb = self._cbs.get(wp & 0xFFFF)
                    if cb is not None:
                        try:
                            cb()
                        except Exception:       # noqa: BLE001
                            log.exception("썸네일 버튼 콜백 오류")
                        return True, 0
            elif self._msg_created and m == self._msg_created and int(msg.hWnd or 0) == self.hwnd:
                # 작업 표시줄 버튼 (재)생성 — Explorer 재시작 포함
                self._buttons_added = False
                self._add_buttons()
                self._key = None
                self.set_progress(*self._last_args)
        except Exception:                       # noqa: BLE001
            log.exception("작업 표시줄 이벤트 처리 오류")
        return False, 0

    # ------------------------------------------------------------ 정리
    def close(self):
        if self._ptr:
            self._call("SetProgressState", TBPF_NOPROGRESS)
        self._release()
        if IS_WIN and self._icons:
            try:
                u = _win_api()["user32"]
                for h in self._icons.values():
                    if h:
                        u.DestroyIcon(h)
            except Exception:                   # noqa: BLE001
                pass
        self._icons = {}
        self._buttons_added = False
        self._key = None
