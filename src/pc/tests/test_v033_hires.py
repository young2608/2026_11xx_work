# -*- coding: utf-8 -*-
"""vr0.1.0.033 (f61) 화면 최대 해상도 반영 — 글자 · 틀 · 아이콘

H1 글자 크기 자동 + 실제 밀도(dpi) · 15 · 16pt   H2 메뉴 막대 글자   H3 스타일 기본 크기(px) 배율
H4 레이아웃 여백 · 간격 배율   H5 최소 크기 · 대화상자 배율   H6 직접 그리는 글자 칸   H7 앱 아이콘 · .ico   H8 메뉴 색 견본
"""
import struct
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def app():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture
def font_pt(app):
    """글자 크기를 바꿔 보고 끝나면 10pt 로 되돌림"""
    from yamp.ui import skin

    def set_pt(pt):
        skin.apply_app_font(app, pt)
    yield set_pt
    skin.apply_app_font(app, 10)


# ---------------------------------------------------------------- H1
def test_auto_font_dpi():
    from yamp.ui.metrics import auto_font_pt, dpi_font_pt
    # (사용 가능 높이, 물리 dpi, 배율) → pt
    cases = [((1040, 92, 1.0), 10),        # 24" 1080p
             ((1400, 109, 1.0), 11),       # 27" 1440p (높이 단계 그대로)
             ((2110, 163, 1.0), 14),       # 27" 4K 100 %  (전: 13)
             ((2110, 184, 1.0), 15),       # 24" 4K 100 %
             ((2830, 218, 1.0), 16),       # 27" 5K 100 %  (최대 16)
             ((2110, 138, 1.0), 13),       # 32" 4K 100 % (밀도 단계 12 < 높이 단계 13)
             ((1400, 163, 1.5), 11),       # 27" 4K 150 % (권장 배율 = 전과 같음)
             ((860, 242, 2.0), 10),        # 14" 노트북 200 %
             ((2110, 0, 1.0), 13), ((2110, 1000, 1.0), 13), ((2110, None, 1.0), 13), ((2110, "x", 1.0), 13)]  # 모르는 값 무시
    for args, pt in cases:
        assert auto_font_pt(*args) == pt, args
    assert [auto_font_pt(h) for h in (600, 1299, 1300, 1700, 2050, 4000)] == [10, 10, 11, 12, 13, 13]   # 높이만 = v023 그대로
    assert dpi_font_pt(120) == 10 and dpi_font_pt(400) == 16 and dpi_font_pt(144) == 12


def test_font_sizes_up_to_16(app):
    from yamp.ui import skin
    from yamp.app.win_menus import FONT_LABELS
    assert skin.FONT_SIZES[-1] == 16 == skin.FONT_MAX and len(FONT_LABELS) == len(skin.FONT_SIZES)
    assert skin.set_font_size(16) == 16 and skin.next_font_pt(14, 1) == 15
    skin.set_font_size(10)


def test_config_font_auto_dpi():
    from yamp.core.config_schema import FILE_DEFAULTS
    assert FILE_DEFAULTS["font_auto_dpi"] is True
    txt = (ROOT / "src" / "pc" / "config.txt").read_text("utf-8")
    assert "font_auto_dpi    = 1" in txt and "9~16" in txt


# ---------------------------------------------------------------- H2 메뉴 막대
def test_menubar_font_follows(app, font_pt):
    from PyQt6.QtWidgets import QMainWindow
    from yamp.ui import skin
    w = QMainWindow()
    mb = w.menuBar()
    font_pt(16)                                               # 이미 만든 메뉴 막대도 따라감
    assert mb.font().pointSizeF() == 14.5 and skin.menubar_font().pointSizeF() == 14.5
    font_pt(10)
    assert mb.font().pointSizeF() == 9.0                      # 10pt = 9pt (Windows 기본 메뉴 글자 크기와 같음)
    w.close()


# ---------------------------------------------------------------- H3 스타일 기본 크기
def test_style_metrics_scaled(app, font_pt):
    from PyQt6.QtWidgets import QSlider, QStyle
    from yamp.ui.iconbutton import TipStyle, scaled_metric
    assert scaled_metric(15, 1.0) == 15 and scaled_metric(15, 0.9) == 15 and scaled_metric(15, 1.6) == 24
    st = TipStyle(None)                                       # 앱 스타일은 스타일시트가 감싸므로 직접 만들어 확인
    font_pt(10)
    base = st.pixelMetric(QStyle.PixelMetric.PM_SmallIconSize)
    sl = QSlider()
    font_pt(16)
    assert st.pixelMetric(QStyle.PixelMetric.PM_SmallIconSize) == round(base * 1.6)
    assert st.pixelMetric(QStyle.PixelMetric.PM_SliderThickness) >= 20
    sl.close()


# ---------------------------------------------------------------- H4 · H5 여백 · 간격 · 최소 크기
def test_layout_margins_spacing_follow(app, font_pt):
    from PyQt6.QtWidgets import QHBoxLayout, QWidget
    from yamp.ui import metrics
    font_pt(10)
    w = QWidget()
    lay = QHBoxLayout(w)
    metrics.margins(lay, 12, 6, 2, 0)
    metrics.spacing(lay, 10)
    c = QWidget(w)
    lay.addWidget(c)
    metrics.fix(c, min_w=80, min_h=60)
    m = lay.contentsMargins()
    assert (m.left(), m.top(), m.right(), m.bottom(), lay.spacing()) == (12, 6, 2, 0, 10)   # 10pt = 그대로
    assert (c.minimumWidth(), c.minimumHeight()) == (80, 60)
    font_pt(16)
    assert metrics.reapply(w) >= 2
    m = lay.contentsMargins()
    assert (m.left(), m.top(), m.right(), lay.spacing()) == (19, 10, 2, 16)                  # 2px 이하는 그대로
    assert (c.minimumWidth(), c.minimumHeight()) == (128, 96)
    font_pt(10)
    metrics.reapply(w)
    assert lay.contentsMargins().left() == 12 and c.minimumHeight() == 60
    w.close()


def test_no_raw_margins_in_main_layout():
    """주 화면 파일에는 고정 px 여백 · 간격이 남아 있지 않음 (0 은 예외)"""
    import re
    pat = re.compile(r"\.(setContentsMargins\((?!0, 0, 0, 0)(?!m, 0, m, 0)|setSpacing\((?!0\)))")
    for f in ("app/win_layout.py", "app/win_now.py", "app/win_classic.py", "ui/section.py", "ui/sound_view.py",
              "ui/folder_view.py", "ui/vis_block.py", "ui/mini_player.py", "ui/quick_find.py"):
        src = (ROOT / "src" / "pc" / "yamp" / f).read_text("utf-8")
        bad = [ln for ln in src.splitlines() if pat.search(ln) and "self.setSpacing" not in ln]
        assert not bad, (f, bad)


# ---------------------------------------------------------------- H6 직접 그리는 글자 칸
def test_vis_chart_columns_fit_text(app, font_pt):
    from PyQt6.QtGui import QFontMetrics
    from yamp.ui import skin
    from yamp.ui.vis_block import VisView
    for pt in (10, 13, 16):
        font_pt(pt)
        v = VisView()
        lab_w, db_w, db_h = v._chart_cols()
        fb = QFontMetrics(skin.role_font(v.font(), "body", bold=True))
        assert db_w >= fb.horizontalAdvance("-60 dB") and db_h >= fb.height() and lab_w >= 28 and db_w >= 44
        if pt == 16:
            assert db_w > 44 and db_h > 18                    # 전: 44 × 18 고정 → '-12 dB' 가 잘림
        v.close()


def test_neon_text_rows(app, font_pt):
    from PyQt6.QtWidgets import QWidget
    from yamp.ui import neon
    font_pt(16)
    w = QWidget()
    assert neon._line_h(w.font()) > 14
    k = neon.Knob("베이스", -12, 12, 0)
    k.resize(k.minimumSize())
    k.grab()                                                   # 그리기 오류 없음
    w.close()
    k.close()


# ---------------------------------------------------------------- H7 앱 아이콘
def test_app_icon_and_ico(app, tmp_path):
    from PyQt6.QtCore import QSize
    from yamp.ui import app_icon as A
    ic = A.app_icon()
    assert not ic.isNull() and A.app_icon() is ic
    for n, scale in ((16, 1.0), (32, 1.5), (48, 2.0)):
        pm = ic.pixmap(QSize(n, n), scale)
        assert pm.width() == round(n * scale)                 # 배율마다 실제 픽셀로 그림
    img = A.render(64)
    assert img.pixelColor(32, 32).name() == A.BG.lower() or img.pixelColor(32, 40).isValid()
    data = A.ico_bytes()
    zero, typ, cnt = struct.unpack("<HHH", data[:6])
    assert (zero, typ, cnt) == (0, 1, len(A.ICO_SIZES))
    sizes = []
    for i in range(cnt):
        w, h, _c, _r, _p, bpp, ln, off = struct.unpack("<BBBBHHII", data[6 + 16 * i: 22 + 16 * i])
        assert data[off:off + 8] == b"\x89PNG\r\n\x1a\n" and bpp == 32 and off + ln <= len(data)
        sizes.append(w or 256)
    assert sizes == list(A.ICO_SIZES)
    p = tmp_path / "a.ico"
    assert A.write_ico(p) == len(data) and p.read_bytes() == data


def test_mainwindow_and_build_use_icon():
    mw = (ROOT / "src" / "pc" / "yamp" / "app" / "mainwindow.py").read_text("utf-8")
    assert "setWindowIcon(app_icon())" in mw
    b = (ROOT / "build.sh").read_text("utf-8")
    assert "tools/make_icon.py build/yMp3Player.ico" in b and b.count('"${ICON_ARGS[@]}"') == 2
    assert (ROOT / "src" / "pc" / "tools" / "make_icon.py").exists()


# ---------------------------------------------------------------- H8 메뉴 색 견본 · 켜기 표시
def test_swatch_vector(app):
    from PyQt6.QtCore import QSize
    from PyQt6.QtGui import QIcon
    from yamp.ui import icons
    ic = icons.swatch(("#FFFFFF", "#FFC72C", "#FF8A00"))
    for n, scale in ((16, 1.0), (25, 2.0), (24, 3.0)):
        pm = ic.pixmap(QSize(n, n), scale, QIcon.Mode.Normal, QIcon.State.Off)
        assert pm.width() == round(n * scale)                 # 전: 36px 그림 1장을 늘려 씀
    off = ic.pixmap(QSize(18, 18), 2.0, QIcon.Mode.Normal, QIcon.State.Off).toImage()
    on = ic.pixmap(QSize(18, 18), 2.0, QIcon.Mode.Normal, QIcon.State.On).toImage()
    assert off != on
    assert not icons.toggle().isNull() and icons._swatch_pm(("#000000",), True, 18).width() == 36
