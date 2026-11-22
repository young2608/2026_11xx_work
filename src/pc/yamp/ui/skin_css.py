# -*- coding: utf-8 -*-
"""앱 전체 Qt 스타일시트 (vr0.1.0.030 f58 — skin.py 에서 나눔, 133줄 함수 → 묶음 7개)

색은 모두 테마 토큰(s.*) · 글자 크기는 fs(역할) · px 는 metrics.scale_css 가 글자 배율만큼 키움.
묶음 순서 = 적용 순서 (뒤에 있는 규칙이 앞 규칙을 덮음 — polish 는 항상 마지막)."""
from PyQt6.QtGui import QColor

from .themes import Skin


def fs(role: str = "body") -> str:
    """글자 크기 (skin.fs) — skin 은 부를 때 가져옴: skin.py 가 이 파일을 맨 끝에서 import 하므로
    이 파일을 먼저 import 해도 순환 import 오류가 나지 않게 (v030 재검)"""
    from .skin import fs as _fs
    return _fs(role)


def _css_window(s: Skin, grad: str, grad_r: str, deep: str) -> str:
    """창 · 메뉴 · 카드 · 상단 글자"""
    return f"""QMainWindow, QWidget#root {{ background:{s.bg}; color:{s.text}; }}
QMenuBar {{ background:{s.bg}; color:{s.text}; border-bottom:1px solid {s.line}; }}
QMenuBar::item {{ background:transparent; padding:4px 10px; }}
QMenuBar::item:selected {{ background:{s.fill1_soft}; color:{s.accent_text}; border-radius:6px; }}
QMenu {{ background:{s.surface}; color:{s.text}; border:1px solid {s.line}; padding:4px; }}
QMenu::item:selected {{ background:{s.fill1_soft}; color:{s.accent_text}; }}
QMenu::item:disabled {{ color:{s.dim}; }}
QMenu::separator {{ height:1px; background:{s.line}; margin:4px 8px; }}
QFrame#topPanel {{ background:{s.surface}; border:1px solid {s.line}; border-radius:14px; }}
QFrame#card {{ background:{s.surface}; border:1px solid {s.line}; border-bottom:1px solid {deep}; border-radius:14px; }}
QToolButton#secHeader {{ background:transparent; border:none; color:{s.dim}; font-weight:bold; text-align:left;
                        padding:2px 4px; min-height:18px; font-size:{fs('body')}; }}
QToolButton#secHeader:hover {{ color:{s.text}; }}
QFrame#lcd {{ background:{s.lcd_bg}; border:1px solid {s.line}; border-radius:10px; }}
QLabel {{ color:{s.text}; background:transparent; }}
QLabel#info {{ color:{s.accent_text}; font-family:Consolas,'DejaVu Sans Mono',monospace; font-size:{fs('cap')}; }}
QLabel#verLabel {{ color:{s.dim}; padding:0 8px; font-size:{fs('cap')}; }}
QLabel#clockLabel {{ color:{s.text}; padding:0 6px; font-size:{fs('cap')}; }}
QLabel#topSep {{ color:{s.line}; padding:0 2px; font-size:{fs('cap')}; }}
"""


def _css_buttons(s: Skin, grad: str, grad_r: str, deep: str) -> str:
    """도구 버튼 · 알약 버튼"""
    return f"""QToolButton {{ background:{s.surface2}; color:{s.text}; border:1px solid {s.line}; border-radius:8px;
              min-width:30px; min-height:24px; font-size:{fs('h2')}; padding:1px 3px; }}
QToolButton:hover {{ border-color:{s.fill1}; }}
QToolButton:checked {{ background:{s.fill1}; color:{s.on_fill}; border-color:{s.fill1}; }}
QToolButton#round {{ border-radius:20px; min-width:40px; min-height:40px; }}
QToolButton#roundBig {{ border-radius:26px; min-width:52px; min-height:52px; background:{grad}; border:none; color:{s.on_fill}; }}
QToolButton#pill {{ background:{s.surface2}; color:{s.text}; border:1px solid {s.line}; border-radius:12px;
                   padding:3px 12px; min-height:22px; font-size:{fs('body')}; }}
QToolButton#pill:hover {{ border-color:{s.fill1}; }}
QToolButton#pill:checked {{ background:{s.fill1}; color:{s.on_fill}; border-color:{s.fill1}; font-weight:bold; }}
"""


def _css_inputs(s: Skin, grad: str, grad_r: str, deep: str) -> str:
    """슬라이더 · 진행 막대"""
    return f"""QSlider::groove:horizontal {{ height:6px; background:{s.wave_rest}; border:none; border-radius:3px; }}
QSlider::sub-page:horizontal {{ background:{s.fill1}; border-radius:3px; }}
QSlider::handle:horizontal {{ width:12px; height:12px; margin:-4px 0; background:{s.surface}; border:2px solid {s.fill2};
                             border-radius:7px; }}
QSlider::groove:vertical {{ width:6px; background:{s.wave_rest}; border:none; border-radius:3px; }}
QSlider::add-page:vertical {{ background:{s.fill1}; border-radius:3px; }}
QSlider::handle:vertical {{ width:12px; height:12px; margin:0 -4px; background:{s.surface}; border:2px solid {s.fill2};
                           border-radius:7px; }}
QProgressBar {{ background:{s.wave_rest}; border:none; border-radius:2px; }}
QProgressBar::chunk {{ background:{grad}; border-radius:2px; }}
"""


def _css_lists(s: Skin, grad: str, grad_r: str, deep: str) -> str:
    """목록 · 머리글 · 탭 · 스크롤"""
    return f"""QListView, QTreeWidget, QListWidget {{ background:{s.surface}; color:{s.text}; border:1px solid {s.line}; border-radius:10px;
            font-size:{fs('body')}; outline:none; }}
QListView::item:hover, QTreeWidget::item:hover, QListWidget::item:hover {{ background:{s.surface2}; }}
QListView::item:selected, QTreeWidget::item:selected, QListWidget::item:selected {{ background:{s.fill1_soft};
            color:{s.accent_text}; }}
QHeaderView::section {{ background:{s.surface2}; color:{s.dim}; border:none; border-bottom:1px solid {s.line}; padding:4px 6px; }}
QTabWidget::pane {{ border:1px solid {s.line}; border-radius:10px; background:{s.surface}; top:-1px; }}
QTabBar::tab {{ background:{s.surface2}; color:{s.text}; padding:4px 12px; border:1px solid {s.line}; margin-right:2px;
               border-top-left-radius:8px; border-top-right-radius:8px; }}
QTabBar::tab:hover {{ border-color:{s.fill1}; }}
QTabBar::tab:selected {{ background:{s.fill1}; color:{s.on_fill}; border-color:{s.fill1}; }}
QScrollArea {{ background:{s.bg}; border:none; }}
QWidget#scrollInner {{ background:{s.bg}; }}
QScrollBar:vertical {{ background:transparent; width:10px; margin:0; }}
QScrollBar:horizontal {{ background:transparent; height:10px; margin:0; }}
QScrollBar::handle:vertical {{ background:{s.line}; border-radius:4px; min-height:24px; margin:1px; }}
QScrollBar::handle:horizontal {{ background:{s.line}; border-radius:4px; min-width:24px; margin:1px; }}
QScrollBar::handle:hover {{ background:{s.dim}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width:0; height:0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background:transparent; }}
"""


def _css_controls(s: Skin, grad: str, grad_r: str, deep: str) -> str:
    """버튼 · 콤보 · 대화상자 · 입력칸 · 풍선 도움말"""
    return f"""QPushButton {{ background:{s.surface2}; color:{s.text}; border:1px solid {s.line}; border-radius:8px; padding:4px 12px; }}
QPushButton:hover {{ border-color:{s.fill1}; }}
QPushButton:pressed, QPushButton:checked {{ background:{s.fill1}; color:{s.on_fill}; border-color:{s.fill1}; }}
QPushButton:default {{ border-color:{s.fill2}; }}
QComboBox {{ background:{s.surface2}; color:{s.text}; border:1px solid {s.line}; border-radius:8px; padding:3px 8px; }}
QComboBox:hover {{ border-color:{s.fill1}; }}
QComboBox QAbstractItemView {{ background:{s.surface}; color:{s.text}; border:1px solid {s.line};
            selection-background-color:{s.fill1_soft}; selection-color:{s.accent_text}; }}
QDialog, QMessageBox, QInputDialog {{ background:{s.bg}; color:{s.text}; }}
QPlainTextEdit, QTextEdit, QTextBrowser {{ background:{s.surface}; color:{s.text}; border:1px solid {s.line}; border-radius:8px;
            selection-background-color:{s.fill1_soft}; selection-color:{s.accent_text}; }}
QCheckBox, QRadioButton {{ color:{s.text}; background:transparent; }}
QSpinBox, QDoubleSpinBox {{ background:{s.surface2}; color:{s.text}; border:1px solid {s.line}; border-radius:6px; padding:2px 4px; }}
QStatusBar {{ background:{s.nav}; color:{s.dim}; border-top:1px solid {s.line}; }}
QStatusBar QLabel {{ color:{s.dim}; }}
QSplitter::handle {{ background:{s.bg}; }}
QSplitter::handle:hover {{ background:{s.fill1_soft}; }}
QSplitter#foldSplit::handle {{ background:transparent; margin:3px 40%; border-radius:3px; }}
QSplitter#foldSplit::handle:hover {{ background:{s.fill1}; }}
QLineEdit {{ background:{s.surface2}; color:{s.text}; border:1px solid {s.line}; border-radius:12px; padding:3px 8px;
            selection-background-color:{s.fill1_soft}; selection-color:{s.accent_text}; }}
QLineEdit:focus {{ border-color:{s.fill1}; }}
QLineEdit QToolButton {{ background:transparent; border:none; min-width:0px; min-height:0px; padding:0px; margin:0px; }}
QToolTip {{ background:{s.tooltip_bg}; color:{s.text}; border:1px solid {s.line}; border-radius:6px; padding:6px 8px; font-size:{fs('cap')}; }}
"""


def _css_simple(s: Skin, grad: str, grad_r: str, deep: str) -> str:
    """단순 배치 (아이콘 버튼 · 레일 · 재생 막대 · 제목 글자)"""
    return f"""QToolButton#iconBtn {{ background:transparent; border:none; border-radius:16px; min-width:30px; min-height:30px; padding:3px; }}
QToolButton#iconBtn:hover {{ background:{s.surface2}; }}
QToolButton#iconBtn:checked {{ background:{s.fill1_soft}; }}
QToolButton#iconBtn:disabled {{ background:transparent; }}
QToolButton#playBig {{ background:{grad}; border:none; border-radius:23px; min-width:46px; min-height:46px; }}
QToolButton#playBig:hover {{ background:{grad_r}; }}
QToolButton#railBtn {{ background:transparent; border:none; border-radius:10px; min-width:38px; min-height:38px; }}
QToolButton#railBtn:hover {{ background:{s.surface2}; }}
QToolButton#railBtn:checked {{ background:{s.fill1_soft}; border-left:3px solid {s.fill2}; }}
QFrame#rail {{ background:{s.nav}; border:none; border-right:1px solid {s.line}; }}
QFrame#playerBar {{ background:{s.nav}; border:none; border-top:1px solid {s.line}; }}
QFrame#sidePanel {{ background:{s.surface}; border:none; border-left:1px solid {s.line}; }}
QLabel#barTitle {{ font-weight:bold; font-size:{fs('body')}; }}
QLabel#barSub, QLabel#barTime {{ color:{s.dim}; font-size:{fs('cap')}; }}
QLabel#pageTitle {{ font-size:{fs('h2')}; font-weight:bold; }}
QLabel#nowTitle {{ font-size:{fs('h1')}; font-weight:bold; color:{s.text}; }}
QLabel#nowSub {{ font-size:{fs('body')}; color:{s.dim}; }}
QLabel#cardTitle {{ font-size:{fs('body')}; font-weight:bold; color:{s.dim}; }}
QLabel#emptyHint {{ font-size:{fs('body')}; color:{s.dim}; }}
QFrame#railSep, QFrame#barSep {{ background:{s.line}; border:none; }}
QListWidget#upNext {{ background:transparent; border:none; }}
QListWidget#upNext::item {{ padding:5px 6px; border-radius:6px; }}
QListWidget#upNext::item:hover {{ background:{s.fill1_soft}; }}
"""


def _css_polish(s: Skin, grad: str, grad_r: str, deep: str) -> str:
    """v016 (f29 G8) 다듬기 — 줄 높이 · 메뉴 · 초점 · 스크롤바 · 머리글"""
    return f"""/* ---- v016 (f29 G8): 전체 다듬기 — 줄 높이 · 메뉴 · 초점 · 스크롤바 · 머리글 (간격 4 / 8 / 12px) */
QListView::item, QTreeWidget::item, QListWidget::item {{ padding:4px 8px; border-radius:6px; }}
QListWidget#upNext::item {{ padding:6px 8px; }}
QMenu {{ padding:6px; border-radius:10px; }}
QMenu::item {{ padding:6px 28px 6px 12px; border-radius:6px; }}
QMenu::icon {{ padding-left:8px; }}
QToolButton#iconBtn:focus {{ border:1px solid {s.fill1}; }}
QToolButton#iconBtn:pressed {{ background:{s.fill1_soft}; }}
QPushButton:focus, QComboBox:focus, QSpinBox:focus {{ border-color:{s.fill1}; }}
QScrollBar:vertical {{ width:8px; }}
QScrollBar:horizontal {{ height:8px; }}
QScrollBar::handle:vertical, QScrollBar::handle:horizontal {{ border-radius:3px; }}
QScrollBar:vertical:hover {{ width:10px; }}
QHeaderView::section {{ padding:6px 8px; font-weight:bold; }}
QToolTip {{ padding:6px 10px; }}
QStatusBar {{ font-size:{fs('cap')}; }}
QLabel#dimLabel {{ color:{s.dim}; }}
QLabel#noteLabel {{ color:{s.accent_text}; padding:4px; }}
QLabel#toast {{ background:{s.tooltip_bg}; color:{s.text}; border:1px solid {s.line}; border-radius:10px; padding:6px 12px; }}
"""


PARTS = (_css_window, _css_buttons, _css_inputs, _css_lists, _css_controls, _css_simple, _css_polish)


def stylesheet(s: Skin) -> str:
    grad = f"qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {s.fill1}, stop:1 {s.fill2})"
    grad_r = f"qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {s.fill2}, stop:1 {s.fill1})"
    _t = QColor(s.text)                                # v016 G1: 카드 아래 선 = 글자색 18 % (그림자 효과 대신)
    deep = f"rgba({_t.red()},{_t.green()},{_t.blue()},0.18)"
    from .metrics import scale_css                     # v023: px 크기 × 글자 배율 (10pt = 그대로)
    return scale_css("\n" + "".join(p(s, grad, grad_r, deep) for p in PARTS))
