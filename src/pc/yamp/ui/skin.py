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
FONT_SIZES = (9, 10, 11, 12, 13, 14, 15, 16)                               # 보기 → 글자 크기 (v023: 13 · 14 · v033: 15 · 16 — 4K 100 %)
FONT_MAX = FONT_SIZES[-1]
_BASE_PT = 10.0


def set_font_size(pt) -> float:
    global _BASE_PT
    try:
        _BASE_PT = max(8.0, min(float(FONT_MAX), float(pt)))
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
    if not hasattr(app, "_yamp_mb_font"):                  # v033: 처음 한 번 — 플랫폼 메뉴 막대 글꼴(Windows = Segoe UI 9pt) 기억
        try:
            app._yamp_mb_font = QFont(app.font("QMenuBar"))
        except (TypeError, AttributeError):
            app._yamp_mb_font = QFont(f)
    app.setFont(f)
    # v033 (f61 H2): 메뉴 막대는 플랫폼 기본 글꼴(Windows Segoe UI 9pt)이 따로 정해져 글자 크기를 바꿔도 그대로였음
    #   (4K 에서 16pt 를 골라도 메뉴 막대만 9pt) → 크기만 보조 글자(cap, 10pt 기준 9pt = Windows 기본과 같음)로 같이 따라감
    for w in (app.topLevelWidgets() if hasattr(app, "topLevelWidgets") else ()):
        sync_menubar_font(w)                               # 이미 만든 메뉴 막대
    app._yamp_font = (font_pt("body"), h, dpr)
    return h


def menubar_font():
    """메뉴 막대 글꼴 = 플랫폼 메뉴 막대 글꼴 모양 그대로 + 크기만 보조 글자(cap) (10pt 기준 9pt = Windows 기본과 같음)"""
    from PyQt6.QtGui import QFont
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance()
    base = getattr(app, "_yamp_mb_font", None)
    fm = QFont(base) if base is not None else QFont()
    fm.setPointSizeF(font_pt("cap"))
    return fm


def sync_menubar_font(win) -> bool:
    """v033 (f61 H2): 창의 메뉴 막대 글꼴을 지금 글자 크기로 (QMainWindow 가 아니거나 메뉴 막대가 없으면 False).
    앱 전체 'QMenuBar' 글꼴(app.setFont(f, 'QMenuBar'))은 쓰지 않음 — 다른 위젯 배치가 1px 달라져 10pt 화면이 바뀌었음"""
    from PyQt6.QtWidgets import QMainWindow
    if not isinstance(win, QMainWindow) or win.menuWidget() is None:
        return False
    fm = menubar_font()
    if win.menuWidget().font() != fm:
        win.menuWidget().setFont(fm)
    return True


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


from .skin_css import stylesheet  # noqa: E402,F401  (vr0.1.0.030: 스타일시트는 skin_css.py)
