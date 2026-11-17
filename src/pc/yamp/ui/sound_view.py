# -*- coding: utf-8 -*-
"""
사운드 탭 (vr0.1.0.006) — 참고 EQ 앱 스타일 카드 4개, 모두 접기/펼치기
  ① 이퀄라이저: 켜기 · 프리셋 칩 · 응답 곡선 · 프리앰프+10밴드 빛 슬라이더
  ② 톤: 베이스 · 트레블 · 밸런스 노브
  ③ 다이내믹: 컴프레서(문턱·비율·어택·릴리스·메이크업) · 리미터(−1 dBFS)
엔진: mpv 백엔드에서만 소리에 적용 (Qt 백엔드는 안내 문구)
"""
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QScrollArea, QToolButton, QVBoxLayout, QWidget

from ..domain import dsp
from .iconbutton import IconButton
from .neon import EqSliders, Knob, ResponseCurve
from .section import Section


class SoundView(QScrollArea):
    def __init__(self, ctrl, parent=None):
        super().__init__(parent)
        self.ctrl = ctrl
        self.cfg = ctrl.cfg
        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.Shape.NoFrame)
        inner = QWidget(objectName="scrollInner")
        v = QVBoxLayout(inner)
        v.setContentsMargins(4, 4, 4, 4)
        v.setSpacing(8)
        self._freqs = dsp.log_freqs(96)
        self._apply_timer = QTimer(self, singleShot=True, interval=120, timeout=self._apply)

        if not ctrl.sound_supported():
            note = QLabel("ⓘ 현재 Qt 오디오 백엔드는 사운드 효과를 지원하지 않습니다. config.txt 에서 "
                          "audio_backend = mpv 로 바꾸고 다시 시작하세요 (설정은 저장됩니다).")
            note.setWordWrap(True)
            note.setObjectName("noteLabel")
            v.addWidget(note)

        # ① EQ
        eqb = QWidget()
        ev = QVBoxLayout(eqb)
        ev.setContentsMargins(0, 0, 0, 0)
        chips = QHBoxLayout()
        chips.setSpacing(4)
        self.preset_btns = {}
        for name in dsp.PRESETS:
            b = QToolButton(objectName="pill")
            b.setText(name)
            b.setCheckable(True)
            b.clicked.connect(lambda _=False, n=name: self.set_preset(n))
            chips.addWidget(b)
            self.preset_btns[name] = b
        chips.addStretch(1)
        ev.addLayout(chips)
        self.curve = ResponseCurve()
        ev.addWidget(self.curve)
        self.sliders = EqSliders()
        self.sliders.changed.connect(self._on_band)
        ev.addWidget(self.sliders, 1)
        self.sec_eq = Section("이퀄라이저", "sound.eq", self.cfg, eqb)
        self.eq_on = IconButton("power", "eq_on", checkable=True)
        self.eq_on.toggled.connect(self._on_eq_on)
        self.sec_eq.add_action(self.eq_on)
        reset = IconButton("undo", "eq_reset", self.reset)
        self.sec_eq.add_action(reset)
        v.addWidget(self.sec_eq)

        # ② 톤
        tb = QWidget()
        th = QHBoxLayout(tb)
        # 노브 색 = 테마 밴드 색 번호 (네온: 주황·하늘·보라 … 예전과 같은 색)
        self.k_bass = Knob("베이스", -12, 12, 0, 0, 1, lambda x: f"{x:+.1f} dB", 0.5)
        self.k_treble = Knob("트레블", -12, 12, 0, 0, 7, lambda x: f"{x:+.1f} dB", 0.5)
        self.k_bal = Knob("밸런스", -1, 1, 0, 0, 9, self._bal_txt, 0.05)
        for k in (self.k_bass, self.k_treble, self.k_bal):
            k.valueChanged.connect(self._on_knob)
            th.addWidget(k)
        th.addStretch(1)
        self.sec_tone = Section("톤 · 밸런스", "sound.tone", self.cfg, tb)
        v.addWidget(self.sec_tone)

        # ③ 다이내믹
        db = QWidget()
        dv = QVBoxLayout(db)
        row = QHBoxLayout()
        self.comp_on = IconButton("comp", "comp", checkable=True)
        self.lim_on = IconButton("limit", "limiter", checkable=True)
        self.comp_on.toggled.connect(self._on_dyn)
        self.lim_on.toggled.connect(self._on_dyn)
        row.addWidget(self.comp_on)
        row.addWidget(self.lim_on)
        row.addStretch(1)
        dv.addLayout(row)
        kh = QHBoxLayout()
        self.k_th = Knob("문턱", -60, 0, -18, -18, 4, lambda x: f"{x:.0f} dB", 1)
        self.k_ratio = Knob("비율", 1, 20, 3, 3, 5, lambda x: f"{x:.1f}:1", 0.5)
        self.k_att = Knob("어택", 0.5, 200, 10, 10, 6, lambda x: f"{x:.0f} ms", 0.5)
        self.k_rel = Knob("릴리스", 5, 1000, 120, 120, 8, lambda x: f"{x:.0f} ms", 5)
        self.k_mk = Knob("메이크업", 0, 24, 0, 0, 10, lambda x: f"+{x:.1f} dB", 0.5)
        for k in (self.k_th, self.k_ratio, self.k_att, self.k_rel, self.k_mk):
            k.valueChanged.connect(self._on_knob)
            kh.addWidget(k)
        kh.addStretch(1)
        dv.addLayout(kh)
        self.sec_dyn = Section("다이내믹 (컴프레서 · 리미터)", "sound.dyn", self.cfg, db)
        v.addWidget(self.sec_dyn)
        v.addStretch(1)
        self.setWidget(inner)

        self._loading = False
        self.load(ctrl.sound)
        ctrl.levels.connect(self._on_levels)
        self._own = False
        ctrl.soundChanged.connect(lambda: None if self._own else self.load(ctrl.sound))   # 다른 곳(EQ 대화상자)에서 바뀜

    @staticmethod
    def _bal_txt(x):
        if abs(x) < 0.01:
            return "가운데"
        return f"L {abs(x) * 100:.0f}%" if x < 0 else f"R {x * 100:.0f}%"

    # ---- 화면 ← 설정
    def load(self, s: dsp.SoundSettings):
        self._loading = True
        self.eq_on.setChecked(s.enabled)
        self.sliders.set_values(s.preamp_db, s.bands)
        self.sliders.enabled_look = s.enabled
        for k, val in ((self.k_bass, s.bass_db), (self.k_treble, s.treble_db), (self.k_bal, s.balance),
                       (self.k_th, s.comp_threshold_db), (self.k_ratio, s.comp_ratio), (self.k_att, s.comp_attack_ms),
                       (self.k_rel, s.comp_release_ms), (self.k_mk, s.comp_makeup_db)):
            k.setValue(val)
        self.comp_on.setChecked(s.comp)
        self.lim_on.setChecked(s.limiter)
        self._loading = False
        self._refresh_curve()
        self._mark_preset()

    # ---- 설정 ← 화면
    def _collect(self) -> dsp.SoundSettings:
        s = self.ctrl.sound
        s.enabled = self.eq_on.isChecked()
        s.preamp_db = self.sliders.vals[0]
        s.bands = list(self.sliders.vals[1:])
        s.bass_db, s.treble_db, s.balance = self.k_bass.value(), self.k_treble.value(), self.k_bal.value()
        s.comp, s.limiter = self.comp_on.isChecked(), self.lim_on.isChecked()
        s.comp_threshold_db, s.comp_ratio = self.k_th.value(), self.k_ratio.value()
        s.comp_attack_ms, s.comp_release_ms, s.comp_makeup_db = self.k_att.value(), self.k_rel.value(), self.k_mk.value()
        return s

    def _changed(self):
        if self._loading:
            return
        self._collect()
        self._refresh_curve()
        self._mark_preset()
        self._apply_timer.start()            # 드래그 중 mpv af 를 너무 자주 바꾸지 않게 120ms 모아서

    def _apply(self):
        self._own = True
        try:
            self.ctrl.set_sound(self._collect())
        finally:
            self._own = False

    def _on_band(self, i, v):
        if i > 0 and not self.eq_on.isChecked():
            self.eq_on.setChecked(True)      # 밴드를 움직이면 자동으로 켬
        self._changed()

    def _on_eq_on(self, on):
        self.sliders.enabled_look = on
        self.sliders.update()
        self._changed()

    def _on_knob(self, _v):
        if self.sender() in (self.k_bass, self.k_treble) and not self.eq_on.isChecked():
            self.eq_on.setChecked(True)      # 톤도 EQ 단계에 포함 (dsp.chain 과 같음)
        self._changed()

    def _on_dyn(self, _on):
        self._changed()

    def set_preset(self, name):
        bands = dsp.PRESETS.get(name)
        if bands is None:
            return
        self.sliders.set_values(self.sliders.vals[0], bands)
        self.eq_on.setChecked(True)
        self._changed()

    def reset(self):
        self.sliders.set_values(0, [0] * 10)
        for k in (self.k_bass, self.k_treble, self.k_bal):
            k.setValue(0)
        self._changed()

    def _mark_preset(self):
        cur = [round(x, 1) for x in self.sliders.vals[1:]]
        for name, b in self.preset_btns.items():
            b.setChecked([float(x) for x in dsp.PRESETS[name]] == cur)

    def _refresh_curve(self):
        s = self._collect() if not self._loading else self.ctrl.sound
        self.curve.set_curve(dsp.response_db(s, self._freqs))

    def _on_levels(self, lv):
        if self.isVisible() and self.sec_eq.is_open():
            self.curve.set_levels(lv)
