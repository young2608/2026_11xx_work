# -*- coding: utf-8 -*-
"""vr0.1.0.028 (f55 / f56) — iPhone(iOS) 소스 · 빌드 환경: 생성 파일이 공용 표와 같은지 · 빌드 설정 · build.sh ios
(Swift 컴파일 · 실행은 GitHub Actions macOS 의 swift test / xcodebuild 가 확인 — 여기서는 Windows/Linux 에서 확인할 수 있는 것)"""
import importlib.util
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "src"
IOS = SRC / "ios"


def _gen():
    spec = importlib.util.spec_from_file_location("gen_ios", IOS / "tools" / "gen_ios.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_generated_files_up_to_date():
    """ThemeTable.swift · project.yml 버전이 공용 표 · version.py 와 같음 (gen_ios.py 를 다시 돌려도 바뀌지 않음)"""
    g = _gen()
    assert (IOS / "YampCore/Sources/YampCore/ThemeTable.swift").read_text(encoding="utf-8") == g.gen_theme_swift()
    V = g.load_version()
    y = (IOS / "project.yml").read_text(encoding="utf-8")
    assert f'MARKETING_VERSION: "{V.VER_MAJOR}.{V.VER_MINOR}.{V.VER_PATCH}"' in y
    assert f'CURRENT_PROJECT_VERSION: "{V.VERSION_CODE}"' in y
    assert f'static let version = "{V.VERSION}"' in (IOS / "App/BuildInfo.swift").read_text(encoding="utf-8")


def test_theme_swift_has_every_theme_and_token():
    from yamp.ui import skin
    sw = (IOS / "YampCore/Sources/YampCore/ThemeTable.swift").read_text(encoding="utf-8")
    names = re.findall(r'ThemeDef\(name: "(\w+)"', sw)
    assert names == list(skin.SKINS)
    for name, s in skin.SKINS.items():
        block = sw.split(f'ThemeDef(name: "{name}"', 1)[1].split("ThemeDef(name:", 1)[0]
        for tok in skin.TOKENS:
            assert f'"{tok}": "{getattr(s, tok)}"' in block, (name, tok)


def test_swift_vis_constants_match_pc():
    from yamp.domain import vis_math as M
    sw = (IOS / "YampCore/Sources/YampCore/VisMath.swift").read_text(encoding="utf-8")
    assert f"bands = {M.VIS_BANDS}" in sw and f"fLo = {M.VIS_F_LO}" in sw and f"fHi = {M.VIS_F_HI}" in sw
    assert f"attack = {M.VIS_ATTACK_S}, release = {M.VIS_RELEASE_S}, holdS = {M.VIS_PEAK_HOLD_S}, gravity = {M.VIS_PEAK_GRAVITY}" in sw
    assert f"staleS = {M.VIS_STALE_S}" in sw and f"gramCols = {M.GRAM_COLS}" in sw
    assert '"bars", "wave", "radial", "gram", "chart"' in sw and '"round", "led", "mirror", "reflex"' in sw
    t = (IOS / "YampCore/Tests/YampCoreTests/VisMathTests.swift").read_text(encoding="utf-8")
    assert "testdata/vis_cases.txt" in t                      # 같은 공용 값 파일


def test_project_and_workflow_settings():
    import yaml
    p = yaml.safe_load((IOS / "project.yml").read_text(encoding="utf-8"))
    t = p["targets"]["yMp3Player"]
    assert p["options"]["deploymentTarget"]["iOS"] == "16.0" and t["platform"] == "iOS"
    assert t["settings"]["base"]["PRODUCT_BUNDLE_IDENTIFIER"] == "com.ascen.yamp"
    props = t["info"]["properties"]
    assert props["UIBackgroundModes"] == ["audio"] and props["UIFileSharingEnabled"] is True
    assert props["LSSupportsOpeningDocumentsInPlace"] is True and "UILaunchScreen" in props
    w = yaml.safe_load((ROOT / ".github/workflows/ios.yml").read_text(encoding="utf-8"))
    steps = w["jobs"]["ios"]["steps"]
    runs = " ".join(s.get("run", "") for s in steps)
    assert w["jobs"]["ios"]["runs-on"].startswith("macos")
    assert "gen_ios.py" in runs and "swift test" in runs and "xcodegen generate" in runs
    assert "CODE_SIGNING_ALLOWED=NO" in runs and "_ios_unsigned.ipa" in runs
    assert any(s.get("with", {}).get("name") == "ipa" for s in steps)


def test_app_icon_and_sources():
    from PIL import Image
    im = Image.open(IOS / "App/Assets.xcassets/AppIcon.appiconset/AppIcon.png")
    assert im.size == (1024, 1024) and im.mode == "RGB"           # 투명 없음 (App Store 규칙)
    for f in ("YampApp.swift", "PlayerEngine.swift", "Library.swift", "ContentView.swift", "NowPlayingView.swift",
              "VisualizerView.swift", "Theme.swift", "BuildInfo.swift"):
        assert (IOS / "App" / f).is_file(), f
    eng = (IOS / "App/PlayerEngine.swift").read_text(encoding="utf-8")
    assert "VisMath.bandsFromMags" in eng and "MPRemoteCommandCenter" in eng and ".playback" in eng


def test_build_sh_ios_and_ignore():
    sh = (ROOT / "build.sh").read_text(encoding="utf-8")
    assert "ios()" in sh and "ios)   ios" in sh and "gh workflow run ios.yml" in sh and "gh run download" in sh
    if sys.platform != "win32":
        assert subprocess.run(["bash", "-n", str(ROOT / "build.sh")]).returncode == 0
    gi = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "/ios.cfg" in gi and "src/ios/yMp3Player.xcodeproj/" in gi
    ex = (ROOT / "ios.cfg.example").read_text(encoding="utf-8")
    assert "GH_REPO=" in ex and "IOS_PUSH=1" in ex and "GH_BRANCH=ymp3player" in ex       # v029: 전용 브랜치
    import yaml
    w = yaml.safe_load((ROOT / ".github/workflows/ios.yml").read_text(encoding="utf-8"))
    assert w[True]["push"]["branches"] == ["ymp3player"]                                  # 올리면 자동 빌드
    assert 'GH_BRANCH="ymp3player"' in sh and "--keep-build-time" in (ROOT / ".github/workflows/ios.yml").read_text(encoding="utf-8")


def test_gen_keep_build_time(tmp_path):
    """v029: push 로 시작한 CI 는 PC 가 커밋 전에 넣은 빌드 시각을 그대로 (exe · apk 와 같은 값)"""
    g = _gen()
    bi = IOS / "App/BuildInfo.swift"
    old = bi.read_text(encoding="utf-8")
    try:
        g.main(["--build-time", "2026-01-02 03:04"])
        g.main(["--keep-build-time"])
        assert 'buildTime = "2026-01-02 03:04"' in bi.read_text(encoding="utf-8")
        g.main([])
        assert 'buildTime = "2026-01-02 03:04"' in bi.read_text(encoding="utf-8")
    finally:
        bi.write_text(old, encoding="utf-8", newline="\n")
