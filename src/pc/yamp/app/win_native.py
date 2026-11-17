"""MainWindow Windows 연동 (vr0.1.0.009) — winplat 패키지를 창에 연결

  W1 작업 표시줄 미리보기 버튼(이전·재생·다음) + 진행 표시   (config: taskbar_buttons)
  W5 전역 단축키 (다른 프로그램 사용 중에도)                  (config: global_hotkeys, hotkeys)
  W6 Windows 강조색 따라가기                                  (config: follow_system_accent)
  D3 Windows 어두운 모드 따라가기 (vr0.1.0.011)                 (config: follow_system_dark — sunny ↔ night_sunny)
  W2 Windows 미디어 제어 (볼륨 팝업·잠금 화면)                (config: smtc — winrt 패키지 있을 때만)
Windows 가 아니거나 기능이 실패하면 조용히 꺼짐 (재생에는 영향 없음).
"""
import logging
import sys

from PyQt6.QtWidgets import QApplication

log = logging.getLogger("yamp.win")
VOL_STEP = 5


def parse_bindings(text: str) -> dict:
    """'toggle=Ctrl+Alt+Space;next=...' → {동작: 키}"""
    out = {}
    for part in str(text or "").split(";"):
        k, _, v = part.partition("=")
        if k.strip():
            out[k.strip()] = v.strip()
    return out


class NativeMixin:
    _native = None
    _theme_watcher = None
    _theme_accent = None

    def native_start(self):
        """창이 처음 보인 뒤 한 번"""
        if self._native is not None:
            return
        self._native = {}
        app = QApplication.instance()
        if self.cfg["follow_system_accent"] or self.cfg["follow_system_dark"]:
            self.ensure_theme_watcher()
        if sys.platform != "win32":
            return
        hwnd = int(self.winId())
        c = self.ctrl
        if self.cfg["taskbar_buttons"]:
            try:
                from ..winplat.win_taskbar import TaskbarControl
                tb = TaskbarControl(hwnd, c.prev, c.toggle, c.next)
                app.installNativeEventFilter(tb)
                self._native["taskbar"] = tb
                tb.set_playing(c.engine.is_playing())
            except Exception as e:  # noqa
                log.warning("taskbar: %s", e)
        if self.cfg["global_hotkeys"]:
            try:
                from ..winplat.win_hotkeys import GlobalHotkeys
                hk = GlobalHotkeys(hwnd, parse_bindings(self.cfg["hotkeys"]), self._on_hotkey)
                app.installNativeEventFilter(hk)
                self._native["hotkeys"] = hk
                if hk.failed:
                    self._on_message("전역 단축키 사용 중(다른 프로그램): " + ", ".join(hk.failed))
            except Exception as e:  # noqa
                log.warning("hotkeys: %s", e)
        if self.cfg["smtc"]:
            try:
                from ..winplat.win_smtc import Smtc
                sm = Smtc(self)
                if sm.available:
                    sm.command.connect(self._on_mediakey)
                    self._native["smtc"] = sm
            except Exception as e:  # noqa
                log.info("smtc: %s", e)

    def native_stop(self):
        n = self._native or {}
        app = QApplication.instance()
        for k in ("taskbar", "hotkeys"):
            obj = n.get(k)
            if obj is not None:
                try:
                    app.removeNativeEventFilter(obj)
                    (obj.close if k == "taskbar" else obj.unregister)()
                except Exception as e:  # noqa
                    log.info("%s close: %s", k, e)
        if n.get("smtc") is not None:
            n["smtc"].close()
        if self._theme_watcher is not None:
            self._theme_watcher.stop()
            self._theme_watcher = None
        self._native = {}

    # ---- 재생 상태 → Windows
    def native_track(self, t, info):
        sm = (self._native or {}).get("smtc")
        if sm is not None:
            sm.set_metadata(info.title or t.display, info.artist or t.artist, info.album or t.album, info.cover)

    def native_pos(self, pos, dur):
        n = self._native or {}
        tb = n.get("taskbar")
        st = "playing" if self.ctrl.engine.is_playing() else ("paused" if dur > 0 else "stopped")
        if tb is not None:
            tb.set_progress(pos, dur, st)
        if n.get("smtc") is not None:
            n["smtc"].set_timeline(pos, dur)

    def native_state(self, st):
        n = self._native or {}
        if n.get("taskbar") is not None:
            n["taskbar"].set_playing(st == "playing")
            if st == "stopped":
                n["taskbar"].set_progress(0, 0, "stopped")
        if n.get("smtc") is not None:
            n["smtc"].set_state(st)

    # ---- Windows → 앱
    def _on_hotkey(self, action):
        c = self.ctrl
        if action == "vol_up":
            self.vol.setValue(min(100, self.vol.value() + VOL_STEP))
        elif action == "vol_down":
            self.vol.setValue(max(0, self.vol.value() - VOL_STEP))
        elif action == "show":
            self._show_from_tray()
        elif action in ("toggle", "next", "prev", "stop"):
            getattr(c, action)()

    def ensure_theme_watcher(self):
        """Windows 밝게/어둡게 · 강조색 5초 감시 시작 (이미 있으면 그대로) — 메뉴에서 켤 때도 부름"""
        if self._theme_watcher is not None:
            return
        try:
            from ..winplat.win_theme import ThemeWatcher
            w = ThemeWatcher(self)
            th = w.start() or {}
            w.changed.connect(self._on_system_theme)
            self._theme_watcher = w
            self._theme_accent = th.get("accent")
            old = (self.native_accent(), self.effective_theme())
            self._sys_light = th.get("light")
            if old != (self.native_accent(), self.effective_theme()) or self._theme_accent:
                self.apply_skin()
        except Exception as e:  # noqa
            log.info("theme watcher: %s", e)

    def _on_system_theme(self, th):
        self._theme_accent = th.get("accent")
        self._sys_light = th.get("light")
        self.apply_skin()

    def native_accent(self):
        return getattr(self, "_theme_accent", None) if self.cfg["follow_system_accent"] else None
