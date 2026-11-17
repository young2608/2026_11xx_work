# -*- coding: utf-8 -*-
"""vr0.1.0.015 (f28) — 지금 재생 블럭 크기 조절 · 접기/펼치기 · 도움말(F1) 이름표 겹침 없앰"""
import os
import random
import time

import pytest
from PyQt6.QtCore import QRect

from yamp.domain import ticker as T


@pytest.fixture
def app():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _fake_fetch(markets, timeout=None):
    now = int(time.time() * 1000)
    return [T.Quote("KRW-XRP", 3512.0, "RISE", 43, 0.0124, 3540, 3455, 1.2e12, now)], now


def _win(tmp_path, monkeypatch, cfg=None):
    os.environ["YAMP_HOME"] = str(tmp_path)
    from yamp.core.config import Config
    from yamp.data import upbit
    from yamp.app.mainwindow import MainWindow
    monkeypatch.setattr(upbit, "fetch", _fake_fetch)
    c = cfg or Config(tmp_path)
    c["help_overlay_shown"] = True
    return MainWindow(c)


def _close(w):
    w.topbar.shutdown()
    w.ctrl.shutdown()
    w.hide()
    w.deleteLater()


def _pump(app, n=15):
    for _ in range(n):
        app.processEvents()
        time.sleep(0.01)


# ---------------------------------------------------------------- 순수 계산
def test_share_keeps_total_and_floor():
    from yamp.ui.fold_split import share
    s = share([100, 50, 300], [0, 2], 150)
    assert sum(s) == 600 and s[1] == 50 and s[0] > 100 and s[2] > 300
    s = share([200, 50, 300], [0, 2], -400, floor=80)
    assert s == [80, 50, 80]                                       # 덜 수 있는 340 만 (각 80 남김)
    s = share([100, 100], [0, 1], -1000, floor=80)                # 덜어 올 수 있는 만큼만
    assert s == [80, 80]


def test_place_labels_never_overlap():
    from yamp.ui.help_overlay import place_labels
    rnd = random.Random(7)
    W, H = 1280, 800
    for _ in range(30):
        rects = []
        while len(rects) < 40:                                     # 버튼끼리는 겹치지 않게 (실제 화면과 같음)
            r = QRect(rnd.randrange(0, W - 40), rnd.randrange(0, H - 40), 32, 32)
            if not any(r.adjusted(-4, -4, 4, 4).intersects(o) for o in rects):
                rects.append(r)
        sizes = [(rnd.randrange(30, 150), 18) for _ in rects]
        hint = QRect(300, 6, 600, 30)
        boxes = place_labels(rects, sizes, W, H, [hint])
        assert len(boxes) == len(rects)
        for i, b in enumerate(boxes):
            assert b.left() >= 0 and b.top() >= 0 and b.right() < W and b.bottom() < H
            assert not b.intersects(hint) or b.bottom() >= H - 20     # (마지막 수단으로 밀린 경우만)
    # 세로 메뉴(왼쪽 끝 줄): 이름표는 오른쪽에 → 아래 버튼을 가리지 않음
    col = [QRect(8, 40 + 50 * k, 44, 44) for k in range(8)]
    boxes = place_labels(col, [(110, 18)] * 8, W, H, [])
    for r, b in zip(col, boxes):
        assert b.left() > r.right()
        assert not any(b.intersects(o) for o in col)
    assert not any(a.intersects(b) for i, a in enumerate(boxes) for b in boxes[i + 1:])


def test_help_overlay_in_window_no_overlap(app, tmp_path, monkeypatch):
    from PyQt6.QtGui import QFontMetrics
    from yamp.ui.help_overlay import hint_box, place_labels
    w = _win(tmp_path, monkeypatch)
    try:
        for size in ((1280, 800), (960, 640)):
            w.resize(*size)
            w.show()
            _pump(app)
            ov = w.show_help_overlay()
            f, fh = ov.fonts()
            fm = QFontMetrics(f)
            hint = hint_box(QFontMetrics(fh), ov.HINT, ov.width(), ov.height())
            boxes = place_labels([r for r, _ in ov.items], [(fm.horizontalAdvance(n) + 12, fm.height() + 4) for _, n in ov.items],
                                 ov.width(), ov.height(), [hint])
            assert len(ov.items) >= 15
            for i, a in enumerate(boxes):
                assert not a.intersects(hint)
                assert not any(a.intersects(b) for b in boxes[i + 1:]), ov.items[i][1]
            assert not ov.grab().isNull()
            ov.close()
    finally:
        _close(w)


# ---------------------------------------------------------------- 창: 블럭
def _assert_default(sp):
    sz = sp.sizes()
    info = sp.secs[0]
    assert abs(sz[0] - max(info.minimumSizeHint().height(), info.sizeHint().height())) <= 4   # 곡 정보 = 내용 높이
    assert abs(sz[1] - sz[2] * 2) <= 12                                                      # 시각화 : 다음 곡 = 2 : 1 (v017)

def test_now_blocks_fold_resize_persist(app, tmp_path, monkeypatch):
    from yamp.core.config import Config
    w = _win(tmp_path, monkeypatch)
    try:
        w.resize(1280, 800)
        w.show()
        _pump(app)
        sp = w.now_split
        assert [s.btn.text() for s in sp.secs] == ["곡 정보", "비주얼라이저", "다음 곡"]   # v026 이름
        assert w.sec_next.body is w.up_next                         # 빈 QListWidget 도 본문 (len()=0 거짓 회귀 방지)
        assert sp._restored and len(sp.sizes()) == 3
        total = sum(sp.sizes())
        # 접기 → 제목 줄 높이만, 남는 높이는 펼친 블럭으로 (합계 그대로)
        w.sec_vis.set_open(False)
        _pump(app)
        sz = sp.sizes()
        assert sz[1] == sp.head_h(w.sec_vis) and abs(sum(sz) - total) <= 2
        assert w.cfg["folds"].get("main.vis") is True
        assert not w.vis.active
        # 펼치기 → 접기 전 높이 근처로
        before = sp._open_size[1]
        w.sec_vis.set_open(True)
        _pump(app)
        assert abs(sp.sizes()[1] - before) <= 40 and abs(sum(sp.sizes()) - total) <= 2
        # 곡 정보 접으면 제목 줄에 곡 이름
        w.sec_info.set_open(False)
        w._info_head()
        assert w.sec_info.btn.text() == "곡 정보"                   # 곡 없음
        w.sec_info.set_open(True)
        # 끌어서 조절한 크기 저장 → 다음 실행 때 복원
        mins = [x.minimumSizeHint().height() for x in sp.secs]
        want = [mins[0] + 20, 0, mins[2] + 10]
        want[1] = sum(sp.sizes()) - want[0] - want[2]
        sp.setSizes(want)
        sp._save()
        saved = list(w.cfg["now_split"])
        assert saved == want
        # 기본 크기 (보기 메뉴 · 손잡이 더블클릭)
        w.sec_next.set_open(False)
        w.reset_now_blocks()
        _pump(app)
        assert all(s.is_open() for s in sp.secs)
        _assert_default(sp)
        sp.setSizes(saved)
        sp._save()
        cfg = w.cfg
        cfg.save()
    finally:
        _close(w)
    w2 = _win(tmp_path, monkeypatch, Config(tmp_path))
    try:
        w2.resize(1280, 800)
        w2.show()
        _pump(app)
        assert w2.now_split.sizes()[0] == saved[0]
    finally:
        _close(w2)


def test_handle_double_click_resets(app, tmp_path, monkeypatch):
    from yamp.ui.fold_split import _Handle
    w = _win(tmp_path, monkeypatch)
    try:
        w.resize(1280, 800)
        w.show()
        _pump(app)
        sp = w.now_split
        sp.setSizes([60, 400, sum(sp.sizes()) - 460])
        h = sp.handle(1)
        assert isinstance(h, _Handle)
        h.mouseDoubleClickEvent(None)
        _assert_default(sp)
    finally:
        _close(w)
