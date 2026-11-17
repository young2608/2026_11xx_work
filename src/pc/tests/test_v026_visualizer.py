# -*- coding: utf-8 -*-
"""vr0.1.0.026 (f51 / f52) — 비주얼라이저 재구성: 24 밴드(낮은 밴드 보간) · 부드러운 움직임 · 웨이브 곡선 · 이름"""
from pathlib import Path

import numpy as np
import pytest

TD = Path(__file__).resolve().parents[2] / "testdata"


@pytest.fixture(scope="module")
def app():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _mags(form, bins):
    if form == "inv":
        return [1000.0 / (k + 1) for k in range(bins)]
    if form == "flat":
        return [50.0] * bins
    return [4000.0 if k == 1 else 2000.0 if k == 2 else 300.0 if k == 40 else 0.0 for k in range(bins)]


def _rows():
    return [ln.split("|") for ln in (TD / "vis_cases.txt").read_text(encoding="utf-8").splitlines()
            if ln.strip() and not ln.startswith("#")]


def test_shared_cases_bands_and_smoother():
    """testdata/vis_cases.txt — Android VisMathTest 도 같은 파일로 확인"""
    from yamp.domain.vis_math import BandSmoother, bands_from_mags
    rows = _rows()
    nb = ns = 0
    sm = BandSmoother(3)
    for r in rows:
        if r[0] == "bands":
            bins, hz, rng, ref, form, exp = int(r[1]), float(r[2]), float(r[3]), float(r[4]), r[5], r[6]
            got = bands_from_mags(_mags(form, bins), hz, 24, rng, ref)
            assert np.allclose(got, [float(x) for x in exp.split(",")], atol=2e-6), form
            nb += 1
        elif r[0] == "step":
            if r[2] != "-":
                sm.set_target([float(x) for x in r[2].split(",")])
            v, p = sm.step(float(r[1]))
            assert np.allclose(v, [float(x) for x in r[3].split(",")], atol=2e-6)
            assert np.allclose(p, [float(x) for x in r[4].split(",")], atol=2e-6)
            ns += 1
    assert nb == 4 and ns >= 18


def test_low_bands_not_identical():
    """전: 1024 FFT(43 Hz 간격)에서 40~100 Hz 밴드 3~4개가 같은 bin 하나를 읽어 똑같은 높이 → 지금은 보간으로 서로 다름"""
    from yamp.audio.visualizer import N_BANDS, compute_bands
    sr = 44100
    t = np.arange(4096) / sr
    x = sum(a * np.sin(2 * np.pi * f * t) for f, a in ((70, 0.3), (130, 0.2), (260, 0.1))).astype(np.float32)
    lv = compute_bands(x, sr)
    assert N_BANDS == 24 and len(lv) == 24
    low = [round(v, 4) for v in lv[:5]]
    assert len(set(low)) == 5, low


def test_smoother_motion_rules():
    from yamp.domain import vis_math as M
    sm = M.BandSmoother(4)
    sm.set_target([1, 1, 1, 1])
    v, _ = sm.step(0.05)
    assert 0.55 < v[1] < 0.7                        # 오를 때 τ 50 ms → 0.05초에 약 63 %
    for _ in range(10):
        sm.set_target([1, 1, 1, 1])
        sm.step(0.033)
    top = list(sm.v)
    sm.set_target([0, 0, 0, 0])
    v, p = sm.step(0.1)
    assert all(0.7 * a < b < a for a, b in zip(top, v))   # 내릴 때 τ 350 ms → 0.1초에 약 25 % 만 내려감 (천천히)
    assert p[1] >= top[1] - 1e-9                   # 꼭대기는 0.5초 머묾
    for _ in range(30):
        sm.step(0.033)
    assert sm.peaks[1] < top[1]                    # 그 뒤 떨어짐
    for _ in range(120):
        sm.step(0.033)
    assert sm.idle()
    sm.set_target([1, 1, 1, 1])                    # 새 값이 0.25초 넘게 안 오면 목표 = 0 (멈춤 · 엔진 바뀜)
    for _ in range(9):
        sm.step(0.033)
    assert sm.target == [0.0] * 4
    assert sm.step(5.0)[0][0] >= 0                 # 큰 dt 도 안전 (0.25초로 자름)


def test_smooth_curve_shape():
    from yamp.domain.vis_math import smooth_curve
    seg = smooth_curve([0.2, 0.8, 0.4], 0.0, 100.0)
    assert len(seg) == 4 and seg[-1][4] == 100.0 and seg[-1][5] == 0.0      # 양 끝 0 으로 모임
    assert all(c[1] >= 0 and c[3] >= 0 for c in seg)                      # 가운데 선 밖으로 넘지 않음
    assert smooth_curve([], 0, 10)[0][4] == 10


def test_vis_view_draws_all_modes(app):
    from yamp.ui.vis_block import VisView
    v = VisView()
    v.resize(520, 200)
    for _ in range(5):
        v.push_bands([0.1 * i % 1 for i in range(24)])
        v.tick(0.033)
    assert max(v.bands) > 0 and len(v.peak_hold) == 24
    for m in ("bars", "wave", "chart"):
        v.mode = m
        assert not v.grab().isNull()
    v.push_fallback([0.5] * 300, 5000, 30000)        # 파일 파형 기준 웨이브
    v.mode = "wave"
    assert v.fallback and not v.grab().isNull()
    v.clear()
    assert max(v.bands) == 0


def test_names_and_order(app, tmp_path):
    import os
    os.environ["YAMP_HOME"] = str(tmp_path)
    from yamp.core.config import Config
    from yamp.ui import tips
    from yamp.ui.vis_block import VisBlock
    assert (tips.name("vis_bars"), tips.name("vis_wave"), tips.name("vis_chart")) == ("스펙트럼", "웨이브", "레벨")
    vb = VisBlock(Config(tmp_path))
    assert list(vb.btns) == ["bars", "wave", "radial", "gram", "chart"]          # v027: 원형 · 스펙트로그램
