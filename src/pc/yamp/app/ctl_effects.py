"""Controller 기능 묶음 — 효과: ReplayGain · 전환 페이드 · 구간 반복 A-B · 속도/음정 · 사운드(EQ·톤·다이내믹) · 슬립 타이머

Controller(QObject) 가 이 믹스인을 상속. 상태·시그널은 Controller.__init__ 에 있음."""
import logging
import time

from PyQt6.QtCore import QTimer

from ..audio.mpv_engine import parse_eq_bands
from ..domain import recommend as R

log = logging.getLogger("yamp.ctrl")


class EffectsMixin:
    def _rg_factor(self, info) -> float:
        mode = str(self.cfg["replaygain"])
        if mode == "off" or not info.rg:
            return 1.0
        g = R.parse_gain(info.rg.get("replaygain_album_gain")) if mode == "album" else None
        pk = R.parse_gain(info.rg.get("replaygain_album_peak")) if g is not None else None
        if g is None:
            g = R.parse_gain(info.rg.get("replaygain_track_gain"))
            pk = R.parse_gain(info.rg.get("replaygain_track_peak"))
        if g is None:                         # 트랙 값이 없으면 앨범 값 (CUE 앨범 등, vr0.1.0.010)
            g = R.parse_gain(info.rg.get("replaygain_album_gain"))
            pk = R.parse_gain(info.rg.get("replaygain_album_peak"))
        return R.gain_factor(g, pk, float(self.cfg["preamp_db"] or 0))

    def _fade_factor(self, pos, dur) -> float:
        f = 1.0
        cf = int(self.cfg["crossfade_s"] or 0) * 1000
        if cf > 0:
            f = min(f, pos / cf if pos < cf else 1.0)
            if dur > cf:
                f = min(f, max(0.0, (dur - pos) / cf))
        fade_s = max(1, int(self.cfg["sleep_fade_s"] or 0)) * 1000
        if self._sleep_end:
            rem = (self._sleep_end - time.monotonic()) * 1000
            if rem <= 0:
                self.engine.pause()
                self.sleep_cancel()
                self.message.emit("슬립 타이머: 일시정지")
                QTimer.singleShot(200, lambda: self.engine.set_fade(1.0))
                return f
            f = min(f, rem / fade_s if rem < fade_s else 1.0)
        elif self._sleep_track and dur > 0:
            rem = dur - pos
            f = min(f, rem / fade_s if rem < fade_s else 1.0)
        ramp = getattr(self, "_alarm_ramp", None)
        if ramp is not None:                      # 알람: 30초에 걸쳐 볼륨을 올림 (50ms 틱 → 600틱)
            ramp = min(1.0, ramp + 1 / 600)
            self._alarm_ramp = None if ramp >= 1.0 else ramp
            f = min(f, ramp)
        return max(0.0, min(1.0, f))

    # ---- 구간 반복 (A5)
    def cycle_ab(self):
        pos = self.rel_pos()
        if self.ab:
            self.ab = None
            self._ab_a = None
            self.message.emit("구간 반복 해제")
        elif self._ab_a is None:
            self._ab_a = pos
            self.message.emit(f"구간 반복 A = {pos / 1000:.1f}s (한 번 더 누르면 B)")
        else:
            a, b = sorted((self._ab_a, pos))
            if b - a < 500:
                b = a + 500
            self.ab = (a, b)
            self._ab_a = None
            self.message.emit(f"구간 반복 {a / 1000:.1f}s ~ {b / 1000:.1f}s")
        self.abChanged.emit(self.ab if self.ab else ("A", self._ab_a) if self._ab_a is not None else None)

    def repeat_range(self, a_ms, b_ms):
        """가사 줄 반복 등 (offset 은 호출 쪽에서 반영)"""
        a, b = max(0, int(a_ms)), int(b_ms)
        if b <= a:
            b = a + 3000
        self.ab = (a, b)
        self._ab_a = None
        self.engine.seek(a + self._off())
        self.abChanged.emit(self.ab)
        self.message.emit(f"구간 반복 {a / 1000:.1f}s ~ {b / 1000:.1f}s")

    # ---- 속도 · 음정 · EQ (A6, D1)
    def set_speed(self, rate: float):
        rate = round(max(0.5, min(2.0, float(rate))), 2)
        self.cfg["speed"] = rate
        self.engine.set_rate(rate)
        self.modesChanged.emit()

    def set_skip_silence(self, on: bool):
        """무음 건너뛰기 (V1, vr0.1.0.010) — mpv 엔진에서만"""
        self.cfg["skip_silence"] = bool(on)
        self.engine.set_skip_silence(bool(on))
        if on and not getattr(self.engine, "supports_skip_silence", False):
            self.message.emit("무음 건너뛰기는 mpv 엔진에서 동작 (config.txt audio_backend = mpv)")
        else:
            self.message.emit("무음 건너뛰기 " + ("켬" if on else "끔"))
        self.modesChanged.emit()

    def set_pitch(self, st: int):
        self.cfg["pitch_st"] = int(st)
        self.engine.set_pitch(int(st))
        self.modesChanged.emit()

    def set_eq(self, enabled: bool, bands):
        """이전 EQ 대화상자 호환 — 사운드 설정의 EQ 부분만 바꿈"""
        self.cfg["eq_enabled"] = bool(enabled)
        self.cfg["eq_bands"] = ",".join(f"{b:g}" for b in bands)
        self.sound.enabled = bool(enabled)
        self.sound.bands = [float(b) for b in list(bands)[:10]]
        self.set_sound(self.sound)

    # ---- 사운드 탭 (vr0.1.0.006): EQ·프리앰프·톤·밸런스·컴프레서·리미터
    def _load_sound(self):
        from ..domain.dsp import SoundSettings
        txt = str(self.cfg["sound"] or "").strip()
        if txt:
            return SoundSettings.from_text(txt)
        s = SoundSettings()                       # 이전 버전 설정 이전 (eq_enabled / eq_bands)
        s.enabled = bool(self.cfg["eq_enabled"])
        s.bands = parse_eq_bands(self.cfg["eq_bands"])
        return s.clamp()

    def set_sound(self, settings=None):
        if settings is not None:
            self.sound = settings
        self.sound.clamp()
        self.cfg["sound"] = self.sound.to_text()
        self.cfg["eq_enabled"] = bool(self.sound.enabled)
        self.cfg["eq_bands"] = ",".join(f"{b:g}" for b in self.sound.bands)
        self.engine.set_sound(self.sound)
        self.soundChanged.emit()

    def apply_preset(self, name: str):
        """사운드 프리셋 적용 (메뉴 '음성 또렷하게' 등, vr0.1.0.010)"""
        from ..domain.dsp import PRESETS
        if name not in PRESETS:
            return
        self.sound.enabled = True
        self.sound.bands = [float(b) for b in PRESETS[name]]
        self.set_sound(self.sound)
        self.message.emit(f"사운드 프리셋: {name}" + ("" if self.sound_supported() else " (적용은 mpv 엔진)"))

    def sound_supported(self) -> bool:
        return bool(getattr(self.engine, "supports_eq", False))

    # ---- 슬립 타이머 (A7)
    def sleep_start(self, minutes):
        """minutes: 분 (int) 또는 'track' (곡 끝날 때)"""
        self.engine.set_fade(1.0)
        if minutes == "track":
            self._sleep_end, self._sleep_track = 0.0, True
            self.sleepChanged.emit("곡 끝날 때")
        else:
            self._sleep_end, self._sleep_track = time.monotonic() + int(minutes) * 60, False
            self.sleepChanged.emit(f"{int(minutes)}분")
        log.info("sleep timer %s", minutes)

    def sleep_cancel(self):
        self._sleep_end, self._sleep_track = 0.0, False
        self.sleepChanged.emit("")

    def sleep_remaining(self) -> str:
        if self._sleep_track:
            return "곡 끝날 때"
        if self._sleep_end:
            m = max(0, int((self._sleep_end - time.monotonic() + 59) // 60))
            return f"{m}분 남음"
        return ""

    # ---- 재생 목록 끝 동작 · 알람 (W8, vr0.1.0.009)
    END_ACTIONS = {"stop": "정지", "sleep": "PC 절전", "shutdown": "PC 종료 (60초 뒤)"}

    def set_end_action(self, act: str):
        self.cfg["end_action"] = act if act in self.END_ACTIONS else "stop"
        self.message.emit(f"재생 목록이 끝나면: {self.END_ACTIONS[self.cfg['end_action']]}")

    def on_list_end(self):
        act = str(self.cfg["end_action"] or "stop")
        log.info("list end action=%s", act)
        if act == "stop":
            return
        from ..winplat import power
        if act == "sleep":
            self.message.emit("재생 목록 끝 — PC 절전")
            QTimer.singleShot(3000, power.sleep_pc)
        elif act == "shutdown":
            self.message.emit("재생 목록 끝 — 60초 뒤 PC 종료 (취소: 슬립 메뉴 → 종료 취소)")
            power.shutdown_pc(60)

    def cancel_shutdown(self):
        from ..winplat import power
        power.cancel_shutdown()
        self.message.emit("PC 종료 취소")

    def set_alarm(self, hhmm: str):
        """'HH:MM' (빈 값 = 끔). 그 시각에 마지막 폴더(없으면 재생 목록)를 볼륨을 서서히 올리며 재생"""
        self.cfg["alarm_time"] = hhmm or ""
        self._alarm_fired_day = ""
        self.message.emit(f"알람: {hhmm}" if hhmm else "알람 끔")

    def check_alarm(self, now_struct=None):
        """30초마다 호출. 반환: 울렸으면 True"""
        hhmm = str(self.cfg["alarm_time"] or "").strip()
        if not hhmm:
            return False
        t = now_struct or time.localtime()
        today = time.strftime("%Y%m%d", t)
        if time.strftime("%H:%M", t) != hhmm or getattr(self, "_alarm_fired_day", "") == today:
            return False
        self._alarm_fired_day = today
        lf = self.cfg["last_folder"]
        log.info("alarm %s folder=%s", hhmm, lf)
        import os
        if lf and os.path.isdir(lf):
            self.play_folder(lf, bool(self.cfg["folder_include_sub"]), bool(self.cfg["shuffle"]), str(self.cfg["folder_sort"]))
        elif len(self.pl):
            self.play_index(max(0, self.pl.current))
        else:
            return False
        self._alarm_ramp = 0.0                     # 30초 동안 볼륨 0 → 1
        self.engine.set_fade(0.0)
        self.message.emit(f"알람 {hhmm} — 재생 시작")
        return True
