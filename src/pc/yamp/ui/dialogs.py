# -*- coding: utf-8 -*-
"""대화상자: 속도·음정(A6) · 이퀄라이저(D1) · 태그 편집(C5)   (가사 편집기 A1 · 다른 가사 찾기 A2 → lyrics_dialogs.py, v019)"""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QGridLayout, QHBoxLayout,
                             QLabel, QLineEdit, QSlider, QVBoxLayout)

from ..audio.mpv_engine import EQ_FREQS, EQ_PRESETS, parse_eq_bands
# v019 (R8): 가사 대화상자는 lyrics_dialogs.py 로 나눔 — dialogs.LyricsEditorDialog 처럼 이전 이름 그대로 쓰게 다시 내보냄
from . import metrics
from .lyrics_dialogs import LyricsEditorDialog, LyricsPickDialog  # noqa: F401


class SpeedDialog(QDialog):
    def __init__(self, ctrl, parent=None):
        super().__init__(parent)
        self.ctrl = ctrl
        self.setWindowTitle("재생 속도 · 음정")
        f = QFormLayout(self)
        self.sp = QSlider(Qt.Orientation.Horizontal)
        self.sp.setRange(50, 200)
        self.sp.setSingleStep(5)
        self.sp.setValue(int(round(float(ctrl.cfg["speed"] or 1.0) * 100)))
        self.sp_lbl = QLabel()
        self.pi = QSlider(Qt.Orientation.Horizontal)
        self.pi.setRange(-6, 6)
        self.pi.setValue(int(ctrl.cfg["pitch_st"] or 0))
        self.pi_lbl = QLabel()
        ok_pitch = getattr(ctrl.engine, "supports_pitch", False)
        self.pi.setEnabled(ok_pitch)
        f.addRow("속도", self.sp)
        f.addRow("", self.sp_lbl)
        f.addRow("음정(키)", self.pi)
        f.addRow("", self.pi_lbl)
        if not ok_pitch:
            f.addRow(QLabel("음정 조절은 mpv 엔진에서 사용 가능 (config.txt audio_backend = mpv)"))
        bb = QDialogButtonBox()
        reset = bb.addButton("초기화", QDialogButtonBox.ButtonRole.ResetRole)
        bb.addButton(QDialogButtonBox.StandardButton.Close)
        reset.clicked.connect(lambda: (self.sp.setValue(100), self.pi.setValue(0)))
        bb.rejected.connect(self.close)
        f.addRow(bb)
        self.sp.valueChanged.connect(self._sp)
        self.pi.valueChanged.connect(self._pi)
        self._sp(self.sp.value(), apply=False)
        self._pi(self.pi.value(), apply=False)

    def _sp(self, v, apply=True):
        v = round(v / 5) * 5
        self.sp_lbl.setText(f"{v / 100:.2f}배")
        if apply:
            self.ctrl.set_speed(v / 100)

    def _pi(self, v, apply=True):
        self.pi_lbl.setText(f"{v:+d} 반음")
        if apply:
            self.ctrl.set_pitch(v)


class EqDialog(QDialog):
    def __init__(self, ctrl, parent=None):
        super().__init__(parent)
        self.ctrl = ctrl
        self.setWindowTitle("이퀄라이저 (10밴드)")
        v = QVBoxLayout(self)
        ok = getattr(ctrl.engine, "supports_eq", False)
        if not ok:
            v.addWidget(QLabel("현재 Qt 엔진 — EQ 는 mpv 엔진에서 적용됩니다.\n"
                               "config.txt 의 audio_backend = mpv 로 바꾸고 다시 시작하세요 (mpv-2.dll 필요).\n"
                               "지금 설정한 값은 저장되어 mpv 엔진에서 적용됩니다."))
        top = QHBoxLayout()
        self.on = QCheckBox("사용")
        self.on.setChecked(bool(ctrl.cfg["eq_enabled"]))
        self.preset = QComboBox()
        self.preset.addItem("프리셋…")
        self.preset.addItems(list(EQ_PRESETS))
        top.addWidget(self.on)
        top.addStretch(1)
        top.addWidget(self.preset)
        v.addLayout(top)
        g = QGridLayout()
        self.sl = []
        self.vals = []
        bands = parse_eq_bands(ctrl.cfg["eq_bands"])
        for i, fq in enumerate(EQ_FREQS):
            s = QSlider(Qt.Orientation.Vertical)
            s.setRange(-12, 12)
            s.setValue(int(round(bands[i])))
            metrics.fix(s, min_h=140)  # v033 (f61 H5): 글자 배율
            lv = QLabel()
            lv.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lf = QLabel(f"{fq // 1000}k" if fq >= 1000 else str(fq))
            lf.setAlignment(Qt.AlignmentFlag.AlignCenter)
            g.addWidget(lv, 0, i)
            g.addWidget(s, 1, i, alignment=Qt.AlignmentFlag.AlignHCenter)
            g.addWidget(lf, 2, i)
            s.valueChanged.connect(self._changed)
            self.sl.append(s)
            self.vals.append(lv)
        v.addLayout(g)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        bb.rejected.connect(self.close)
        v.addWidget(bb)
        self.on.toggled.connect(self._changed)
        self.preset.activated.connect(self._preset)
        self._labels()

    def _labels(self):
        for s, l in zip(self.sl, self.vals):
            l.setText(f"{s.value():+d}")

    def _preset(self, i):
        if i <= 0:
            return
        for s, g in zip(self.sl, EQ_PRESETS[self.preset.itemText(i)]):
            s.blockSignals(True)
            s.setValue(g)
            s.blockSignals(False)
        self.on.setChecked(True)
        self._changed()

    def _changed(self, *_):
        self._labels()
        self.ctrl.set_eq(self.on.isChecked(), [s.value() for s in self.sl])


class TagEditDialog(QDialog):
    def __init__(self, path, info, parent=None):
        super().__init__(parent)
        self.setWindowTitle("곡 정보 편집")
        f = QFormLayout(self)
        f.addRow("파일", QLabel(path))
        self.ed = {}
        for k, label, val in (("title", "제목", info.title), ("artist", "가수", info.artist),
                              ("album", "앨범", info.album), ("genre", "장르", info.genre), ("date", "연도", info.year)):
            e = QLineEdit(val or "")
            self.ed[k] = e
            f.addRow(label, e)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        f.addRow(bb)

    def values(self) -> dict:
        return {k: e.text() for k, e in self.ed.items()}
