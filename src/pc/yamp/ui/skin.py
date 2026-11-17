"""테마 (vr0.1.0.011) — 색 '역할(토큰)' 표. 기본 = 써니 (흰색 · 노랑 · 주황)

  공용 표: testdata/themes.txt (PC · Android 같은 값, 테스트로 확인) / 대비 규칙: testdata/theme_contrast.txt
  토큰: bg surface surface2 nav line text dim fill1 fill1_soft fill2 accent_text on_fill lcd_bg lcd_fg
        wave_played wave_rest knob knob_rim graph_bg graph_grid tooltip_bg spectrum_lo spectrum_hi peak + bands[11]
  규칙: 흰 면 = bg/surface · 노랑(fill1)/주황(fill2) = '채움' 전용 (글자로 쓰지 않음)
        채움 위 글자·아이콘 = on_fill · 강조 글자 = accent_text · 선택 줄 = fill1_soft 바탕 + accent_text 글자
  앱 소스의 색은 모두 여기 토큰으로 (색 값 #rrggbb 는 themes.py 에만 — 테스트로 검사)
  v022 (N2): 색 표(Skin · SKINS)는 themes.py, 여기는 쓰는 법(현재 테마 · 글꼴 · 팔레트 · 스타일시트) — 이전 이름 그대로 다시 내보냄
"""
from PyQt6.QtGui import QColor, QPalette

from .themes import (BAND_COLORS, DEFAULT, LEGACY, LEVELS, NIGHT, SKINS, TASKBAR_ICON, TOKENS, Skin,  # noqa: F401
                     _mk)


def resolve(name: str) -> str:
    """config 값 → 실제 테마 키 (light → clean_blue, 모르는 값 → sunny)"""
    name = LEGACY.get(str(name or "").strip().lower(), str(name or "").strip().lower())
    return name if name in SKINS else DEFAULT


def get(name: str) -> Skin:
    return SKINS[resolve(name)]


# ---- 지금 적용된 테마 (아이콘 기본색 등이 따라감)
_current = SKINS[DEFAULT]


def current() -> Skin:
    return _current


def set_current(s: Skin):
    global _current
    _current = s


def color(c: str | None, s: Skin | None = None) -> str:
    """토큰 이름('text', 'accent_text' …) 또는 '#rrggbb' → '#rrggbb'. None = text"""
    s = s or _current
    if not c:
        return s.text
    if c.startswith("#"):
        return c
    return getattr(s, c)


def qcolor(c: str | None, alpha: int | None = None, s: Skin | None = None) -> QColor:
    q = QColor(color(c, s))
    if alpha is not None:
        q.setAlpha(alpha)
    return q


# ---- 시작 시 바꾸기 (D2) · 어두운 모드 따라가기 (D3) — 순수 함수 (테스트 대상)
MIGRATE_TOAST = "새 기본 테마 '써니' — 보기 → 테마에서 네온 다시 선택 가능"


def migrate_theme(theme: str, migrated: bool):
    """→ (새 테마, 알림 문구|None). 이 버전 첫 실행 1번만: 이전 기본 neon → sunny / light → clean_blue (항상)"""
    t = str(theme or "").strip().lower()
    if t in LEGACY:
        return LEGACY[t], None
    if t == "neon" and not migrated:
        return DEFAULT, MIGRATE_TOAST
    return (t if t in SKINS else DEFAULT), None


def step_theme(theme: str, delta: int) -> str:
    """v025: 단계 테마 한 칸 이동 (라이트 → … → 라이트++++ → 다크 → … → 다크++++, delta +1 = 어둡게 · -1 = 밝게).
    단계 테마가 아니면 첫 칸으로: 밝은 테마 → 라이트, 어두운 테마 → 다크 (끝에서는 그대로)"""
    t = resolve(theme)
    if t not in LEVELS:
        return "dark1" if SKINS[t].dark else "light1"
    i = LEVELS.index(t) + (1 if delta > 0 else -1)
    return LEVELS[max(0, min(len(LEVELS) - 1, i))]


def next_font_pt(cur: float, delta: int) -> int:
    """v025: 글자 크기 한 단계 (FONT_SIZES 안에서, 끝에서는 그대로)"""
    sizes = list(FONT_SIZES)
    c = int(round(float(cur)))
    if delta > 0:
        return next((p for p in sizes if p > c), sizes[-1])
    return next((p for p in reversed(sizes) if p < c), sizes[0])


def follow_dark(theme: str, follow: bool, light) -> str:
    """실제로 쓸 테마. follow 켜짐 + 시스템 어두움(light is False) → 밝은 테마의 짝 (sunny → night_sunny, lightN → darkN, 나머지 → dark)"""
    t = resolve(theme)
    if not follow or light is not False or SKINS[t].dark:
        return t
    return NIGHT.get(t, "dark")


# ---- 스타일시트 · 팔레트 (테마 이름 분기 없음, 모두 토큰)
FONT_FAMILIES = ["Segoe UI", "Segoe UI Variable Text", "Malgun Gothic", "맑은 고딕", "Noto Sans CJK KR", "Noto Sans KR", "sans-serif"]


# ---- v016 (f29 G2 · G7 · G9): 글자 크기 5단계 · 힌팅 자동 · 글꼴 엔진(진단용)
TYPE_SCALE = {"h1": 1.7, "h2": 1.3, "body": 1.0, "cap": 0.9, "tiny": 0.8}   # 큰 제목 · 제목 · 본문 · 보조 · 그래프 눈금
FONT_SIZES = (9, 10, 11, 12, 13, 14)                                       # 보기 → 글자 크기 (v023: 13 · 14 추가)
_BASE_PT = 10.0


def set_font_size(pt) -> float:
    global _BASE_PT
    try:
        _BASE_PT = max(8.0, min(14.0, float(pt)))
    except (TypeError, ValueError):
        _BASE_PT = 10.0
    return _BASE_PT


def font_pt(role: str = "body") -> float:
    """기준 글자 크기 × 단계 비율 (0.5pt 단위)"""
    return round(_BASE_PT * TYPE_SCALE.get(role, 1.0) * 2) / 2


def fs(role: str = "body") -> str:
    return f"{font_pt(role):g}pt"


def role_font(base, role: str = "body", bold: bool = False):
    """직접 그리는 위젯용: base 글꼴(가족 · 힌팅 유지)에 단계 크기만"""
    from PyQt6.QtGui import QFont
    f = QFont(base)
    f.setPointSizeF(font_pt(role))
    if bold:
        f.setBold(True)
    return f


def pick_hinting(mode: str, dpr: float) -> str:
    """auto: 200 % 미만(100 · 125 · 150 · 175 %) = full(획을 픽셀에 맞춤, 가장 또렷 — v017: 분수 배율도 full) ·
    200 % 이상 = none(픽셀이 충분해 원래 모양이 더 깔끔)"""
    mode = str(mode or "auto").lower()
    if mode in ("full", "vertical", "none"):
        return mode
    return "none" if dpr >= 2.0 - 1e-3 else "full"


def rounding_policy(mode: str):
    """ui_scale_rounding (v017): passthrough(기본) / round / floor → Qt 배율 반올림 정책"""
    from PyQt6.QtCore import Qt
    P = Qt.HighDpiScaleFactorRoundingPolicy
    return {"round": P.Round, "floor": P.RoundPreferFloor}.get(str(mode or "").lower(), P.PassThrough)


def qt_platform_args(engine: str, platform: str | None = None) -> list:
    """font_engine (Windows 전용): auto = Qt 기본(6.8+ DirectWrite) / directwrite / gdi / freetype → QApplication 인자"""
    import sys as _sys
    engine = str(engine or "auto").lower()
    if (platform or _sys.platform) != "win32" or engine not in ("directwrite", "gdi", "freetype"):
        return []
    return ["-platform", f"windows:fontengine={engine}"]


def apply_app_font(app, pt: float | None = None, hinting: str = "auto", dpr: float | None = None):
    """v014 → v016: 글꼴 = Segoe UI Variable/Segoe UI(영문) + 맑은 고딕(한글) · 크기 · 힌팅 자동 (다시 불러도 됨)"""
    if app is None:
        return None
    from PyQt6.QtGui import QFont
    if pt is not None:
        set_font_size(pt)
    if dpr is None:
        scr = app.primaryScreen() if hasattr(app, "primaryScreen") else None
        dpr = scr.devicePixelRatio() if scr is not None else 1.0
    h = pick_hinting(hinting, dpr)
    f = QFont()
    f.setFamilies(FONT_FAMILIES)
    f.setPointSizeF(font_pt("body"))
    f.setHintingPreference({"full": QFont.HintingPreference.PreferFullHinting,
                            "vertical": QFont.HintingPreference.PreferVerticalHinting,
                            "none": QFont.HintingPreference.PreferNoHinting}[h])
    f.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    app.setFont(f)
    app._yamp_font = (font_pt("body"), h, dpr)
    return h


def palette(s: Skin) -> QPalette:
    pal = QPalette()
    R = QPalette.ColorRole
    for role, tok in ((R.Window, "bg"), (R.WindowText, "text"), (R.Base, "surface"), (R.AlternateBase, "surface2"),
                      (R.Text, "text"), (R.Button, "surface2"), (R.ButtonText, "text"), (R.Highlight, "fill1_soft"),
                      (R.HighlightedText, "accent_text"), (R.ToolTipBase, "tooltip_bg"), (R.ToolTipText, "text"),
                      (R.PlaceholderText, "dim"), (R.Link, "accent_text"), (R.Mid, "line"), (R.Midlight, "line"),
                      (R.Light, "surface"), (R.Dark, "dim"), (R.Shadow, "line"), (R.BrightText, "accent_text")):
        pal.setColor(role, QColor(getattr(s, tok)))
    for role in (R.WindowText, R.Text, R.ButtonText):
        pal.setColor(QPalette.ColorGroup.Disabled, role, QColor(s.dim))
    return pal


def stylesheet(s: Skin) -> str:
    grad = f"qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {s.fill1}, stop:1 {s.fill2})"
    _t = QColor(s.text)                                # v016 G1: 카드 아래 선 = 글자색 18 % (그림자 효과 대신 — 글자 선명도 유지)
    deep = f"rgba({_t.red()},{_t.green()},{_t.blue()},0.18)"
    grad_r = f"qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {s.fill2}, stop:1 {s.fill1})"
    from .metrics import scale_css                     # v023: px 크기 × 글자 배율 (10pt = 그대로)
    return scale_css(f"""
QMainWindow, QWidget#root {{ background:{s.bg}; color:{s.text}; }}
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
QToolButton {{ background:{s.surface2}; color:{s.text}; border:1px solid {s.line}; border-radius:8px;
              min-width:30px; min-height:24px; font-size:{fs('h2')}; padding:1px 3px; }}
QToolButton:hover {{ border-color:{s.fill1}; }}
QToolButton:checked {{ background:{s.fill1}; color:{s.on_fill}; border-color:{s.fill1}; }}
QToolButton#round {{ border-radius:20px; min-width:40px; min-height:40px; }}
QToolButton#roundBig {{ border-radius:26px; min-width:52px; min-height:52px; background:{grad}; border:none; color:{s.on_fill}; }}
QToolButton#pill {{ background:{s.surface2}; color:{s.text}; border:1px solid {s.line}; border-radius:12px;
                   padding:3px 12px; min-height:22px; font-size:{fs('body')}; }}
QToolButton#pill:hover {{ border-color:{s.fill1}; }}
QToolButton#pill:checked {{ background:{s.fill1}; color:{s.on_fill}; border-color:{s.fill1}; font-weight:bold; }}
QSlider::groove:horizontal {{ height:6px; background:{s.wave_rest}; border:none; border-radius:3px; }}
QSlider::sub-page:horizontal {{ background:{s.fill1}; border-radius:3px; }}
QSlider::handle:horizontal {{ width:12px; height:12px; margin:-4px 0; background:{s.surface}; border:2px solid {s.fill2};
                             border-radius:7px; }}
QSlider::groove:vertical {{ width:6px; background:{s.wave_rest}; border:none; border-radius:3px; }}
QSlider::add-page:vertical {{ background:{s.fill1}; border-radius:3px; }}
QSlider::handle:vertical {{ width:12px; height:12px; margin:0 -4px; background:{s.surface}; border:2px solid {s.fill2};
                           border-radius:7px; }}
QProgressBar {{ background:{s.wave_rest}; border:none; border-radius:2px; }}
QProgressBar::chunk {{ background:{grad}; border-radius:2px; }}
QListView, QTreeWidget, QListWidget {{ background:{s.surface}; color:{s.text}; border:1px solid {s.line}; border-radius:10px;
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
QPushButton {{ background:{s.surface2}; color:{s.text}; border:1px solid {s.line}; border-radius:8px; padding:4px 12px; }}
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
QToolButton#iconBtn {{ background:transparent; border:none; border-radius:16px; min-width:30px; min-height:30px; padding:3px; }}
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
/* ---- v016 (f29 G8): 전체 다듬기 — 줄 높이 · 메뉴 · 초점 · 스크롤바 · 머리글 (간격 4 / 8 / 12px) */
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
""")
