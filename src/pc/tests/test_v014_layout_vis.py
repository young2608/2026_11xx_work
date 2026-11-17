# -*- coding: utf-8 -*-
"""vr0.1.0.014 (f26) — 제목 표시줄(버전 · XRP · KST) · 메뉴 막대 접기 · 소리 시각화 · 지금 재생 배치 · 선명한 아이콘"""
import math
import os
import time
import wave
from pathlib import Path

import pytest

from yamp.domain import ticker as T

PC = Path(__file__).resolve().parents[1]


@pytest.fixture
def app():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _fake_fetch(markets, timeout=None):
    now = int(time.time() * 1000)
    return [T.Quote("KRW-XRP", 3512.0, "RISE", 43, 0.0124, 3540, 3455, 1.2e12, now)], now


def _win(tmp_path, monkeypatch):
    os.environ["YAMP_HOME"] = str(tmp_path)
    from yamp.core.config import Config
    from yamp.data import upbit
    from yamp.app.mainwindow import MainWindow
    monkeypatch.setattr(upbit, "fetch", _fake_fetch)
    return MainWindow(Config(tmp_path))


def _close(w):
    w.topbar.shutdown()
    w.ctrl.shutdown()
    w.hide()
    w.deleteLater()


# ---------------------------------------------------------------- 순수 계산
def test_frame_stats_and_db():
    from yamp.audio.visualizer import WAVE_N, frame_stats
    from yamp.ui.vis_block import DB_FLOOR, db_y, peaks_window, to_db
    x = [0.5 * math.sin(2 * math.pi * 440 * i / 44100) for i in range(4096)]
    import numpy as np
    wv, rms, pk = frame_stats(np.array(x, dtype=np.float32))
    assert len(wv) == WAVE_N and abs(pk - 0.5) < 0.01 and abs(rms - 0.5 / math.sqrt(2)) < 0.01
    wv, rms, pk = frame_stats(np.zeros(100, dtype=np.float32))
    assert rms == 0 and pk == 0
    assert to_db(1.0) == 0 and abs(to_db(0.5) + 6.02) < 0.01 and to_db(0) == DB_FLOOR and to_db(1e-9) == DB_FLOOR
    assert db_y(0, 10, 100) == 10 and db_y(DB_FLOOR, 10, 100) == 110 and db_y(5, 0, 100) == 0     # 0 dB 위로 넘지 않음
    pw = peaks_window([0.1] * 100, 5000, 10000, 9)
    assert len(pw) == 9 and all(v == 0.1 for v in pw)
    assert peaks_window([], 0, 0, 4) == [0.0] * 4
    edge = peaks_window([1.0] * 100, 0, 10000, 11)               # 곡 시작: 왼쪽 반은 범위 밖 = 0
    assert edge[0] == 0.0 and edge[-1] == 1.0


def test_spectrum_emits_frame(app):
    import numpy as np
    from yamp.audio.visualizer import SpectrumAnalyzer
    sa = SpectrumAnalyzer()
    got = []
    sa.frame.connect(got.append)
    assert hasattr(sa, "frame")
    if hasattr(sa, "_acc"):
        sa._acc = np.full(4096, 0.25, dtype=np.float32)
    from yamp.audio import visualizer as V
    wv, rms, pk = V.frame_stats(np.full(4096, 0.25, dtype=np.float32))
    assert abs(rms - 0.25) < 1e-6 and abs(pk - 0.25) < 1e-6


# ---------------------------------------------------------------- 시각화 블럭
def test_vis_block_modes_fallback_timer(app, tmp_path):
    os.environ["YAMP_HOME"] = str(tmp_path)
    from yamp.core.config import Config
    from yamp.ui.vis_block import MODES, VisBlock
    cfg = Config(tmp_path)
    assert cfg["vis_mode"] == "chart"
    vb = VisBlock(cfg)
    vb.resize(500, 220)
    for m in MODES:
        vb.set_mode(m)
        assert cfg["vis_mode"] == m and vb.btns[m].isChecked() and sum(b.isChecked() for b in vb.btns.values()) == 1
        vb.on_frame(([0.1, -0.2] * 128, 0.3, 0.9))
        vb.on_levels([0.5] * 19)
        assert not vb.grab().isNull()
    vb.set_mode("nope")
    assert vb.view.mode == "chart"
    # PCM 이 안 오면 파일 파형으로 대신 (mpv · 스펙트럼 끔)
    vb.source = lambda: ([0.5] * 200, 3000, 20000, True)
    vb._got_pcm = 0
    vb.tick_fallback()
    assert vb.view.fallback and len(vb.view.hist) >= 1
    vb.on_frame(([0.0] * 256, 0.0, 0.0))
    assert not vb.view.fallback
    # 보일 때만 30fps
    assert not vb._timer.isActive()
    vb.set_active(True)
    assert vb._timer.isActive()
    vb.set_active(False)
    assert not vb._timer.isActive()
    vb.view.clear()
    assert not vb.view.hist
    # 히스토리는 10초 분량으로 제한 (장시간 운용)
    for _ in range(1000):
        vb.view.push_frame([0.0] * 4, 0.1, 0.2)
    assert len(vb.view.hist) == vb.view.hist.maxlen == 300


# ---------------------------------------------------------------- 아이콘 선명도 (벡터 엔진)
@pytest.mark.parametrize("scale", [1.0, 1.25, 1.5, 2.0])
def test_vector_icons_render_at_device_scale(app, scale):
    from PyQt6.QtCore import QSize
    from yamp.ui import icons
    for name in ("play", "wave", "chart", "menu", "folder"):
        ic = icons.icon(name, "text")
        pm = ic.pixmap(QSize(24, 24), scale)
        assert not pm.isNull()
        assert pm.width() == round(24 * scale) and abs(pm.devicePixelRatio() - scale) < 1e-6
        img = pm.toImage()
        assert any(img.pixelColor(x, y).alpha() > 0 for x in range(img.width()) for y in range(img.height()))


# ---------------------------------------------------------------- 창: 제목 · 메뉴 · 지금 재생
def test_title_bar_has_version_xrp_kst_and_no_corner(app, tmp_path, monkeypatch):
    from yamp.core.version import version_label
    w = _win(tmp_path, monkeypatch)
    try:
        w.topbar._render()
        title = w.windowTitle()
        assert version_label() in title and "KST" in title
        assert w.menuBar().cornerWidget() is None
        assert title.count(version_label()) == 1                 # 버전 표시는 한 곳 (제목 표시줄)
        assert w.topbar.isHidden()
    finally:
        _close(w)


def test_menu_bar_collapse_peek_and_shortcuts(app, tmp_path, monkeypatch):
    w = _win(tmp_path, monkeypatch)
    try:
        w.show()
        app.processEvents()
        assert w.menuBar().isVisible() and w.b_menu.isChecked()
        w.set_menu_bar(False)
        app.processEvents()
        assert not w.menuBar().isVisible() and w.cfg["menu_bar"] is False and not w.b_menu.isChecked()
        assert w.a_menubar.isChecked()
        # 숨겨도 단축키가 살아 있음: 메뉴 동작이 창에도 등록됨
        keys = {a.shortcut().toString() for a in w.actions() if not a.shortcut().isEmpty()}
        assert "Ctrl+O" in keys and "Ctrl+Shift+M" in keys
        w.peek_menu_bar()
        assert w.menuBar().isVisible() and w.cfg["menu_bar"] is False
        assert w._peek_timer.isActive()
        w.setFocus()
        w._hide_peek(force=True)                                 # (오프스크린에서는 초점 이동이 안 되어 강제)
        app.processEvents()
        assert not w._peek_timer.isActive()
        assert not w.menuBar().isVisible()
        w.b_menu.click()
        assert w.cfg["menu_bar"] is True and w.menuBar().isVisible()
    finally:
        _close(w)


def _wav(p: Path, sec=0.3):
    with wave.open(str(p), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(22050)
        f.writeframes(b"\x00\x00" * int(22050 * sec))


def test_now_page_up_next_empty_state(app, tmp_path, monkeypatch):
    w = _win(tmp_path, monkeypatch)
    try:
        w.show()
        app.processEvents()
        assert w.pages.currentWidget() is w.page_now or True
        w.go_page(w.page_now)
        assert w.empty_row.isVisible()                          # 빈 상태 안내
        assert not w.vis.active                                  # 재생 중이 아니면 그리지 않음
        m = tmp_path / "m"
        m.mkdir()
        for i in range(8):
            _wav(m / f"{i}.wav")
        w.ctrl.add_paths([str(m)])
        for _ in range(50):
            app.processEvents()
            if len(w.ctrl.pl) >= 8:
                break
            time.sleep(0.02)
        assert len(w.ctrl.pl) == 8
        w.ctrl.pl.current = 0
        w.cfg["shuffle"] = False
        w.cfg["repeat"] = "off"
        w.refresh_up_next()
        assert not w.empty_row.isVisible()
        assert w.up_next.count() == 5
        assert [d[1] for d in (w.up_next.item(i).data(0x0100) for i in range(5))] == [1, 2, 3, 4, 5]
        # 대기열이 먼저
        t = w.ctrl.pl.items[6]
        w.ctrl.queue.append(t)
        w.refresh_up_next()
        assert w.up_next.item(0).data(0x0100) == ("q", 0) and w.up_next.item(0).text().startswith("⏭")
        # 끝 근처 · 반복 없음 → 남은 곡만
        w.ctrl.queue.clear()
        w.ctrl.pl.current = 6
        w.refresh_up_next()
        assert w.up_next.count() == 1
        w.cfg["repeat"] = "all"
        w.refresh_up_next()
        assert w.up_next.count() == 5
        # 셔플: 순서 목록을 따름, 지금 곡 제외
        w.cfg["shuffle"] = True
        w.refresh_up_next()
        ids = [w.up_next.item(i).data(0x0100)[1] for i in range(w.up_next.count())]
        assert 6 not in ids and len(set(ids)) == len(ids)
        # 시각화 블럭 접으면 멈춤
        w.sec_vis.set_open(False)
        w._sync_vis()
        assert not w.vis.active
    finally:
        _close(w)


def test_layout_no_hardcoded_colors_and_tips():
    from yamp.ui import tips
    for key in ("menu_bar", "vis_wave", "vis_bars", "vis_chart", "open_folder"):
        assert key in tips.TIPS, key
    import re
    for f in ("yamp/ui/vis_block.py", "yamp/app/win_now.py", "yamp/app/win_layout.py"):
        src = (PC / f).read_text(encoding="utf-8")
        assert not re.search(r"#[0-9a-fA-F]{6}\b", src), f


def test_skin_has_new_styles_and_app_font(app):
    from yamp.ui import skin
    qss = skin.stylesheet(skin.get("sunny"))
    for sel in ("#nowTitle", "#nowSub", "#cardTitle", "#emptyHint", "QFrame#railSep", "QListWidget#upNext"):
        assert sel in qss, sel
    skin.apply_app_font(app)
    assert app.font().families()


def test_no_graphics_effects_cards_crisp(app, tmp_path, monkeypatch):
    """v016 (f29 G1): v014 카드 그림자(QGraphicsEffect)는 글자를 흐리게 해서 없앰
    f31: 모든 자식 위젯(findChildren)에 C++ 함수를 부르면 Windows 에서 access violation (Qt 내부 위젯) →
         소스 검사 + 알려진 카드만 확인"""
    import re
    for p in (PC / "yamp").rglob("*.py"):
        assert not re.search(r"QGraphics\w*Effect|setGraphicsEffect", p.read_text(encoding="utf-8")), p.name
    w = _win(tmp_path, monkeypatch)
    try:
        for name in ("sunny", "night_sunny"):
            w.apply_skin(name)
            assert all(c.graphicsEffect() is None for c in (w.sec_info, w.sec_vis, w.sec_next))
    finally:
        _close(w)
