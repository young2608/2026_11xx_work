# -*- coding: utf-8 -*-
"""iOS 소스 생성 (vr0.1.0.028, f55) — PC · Android 와 같은 값을 iOS 로 (손으로 두 번 쓰지 않게)

  python src/ios/tools/gen_ios.py [--build-time "YYYY-MM-DD HH:MM" | --keep-build-time]   (둘 다 없으면 지금 값 유지)
    1) YampCore/Sources/YampCore/ThemeTable.swift   ← src/testdata/themes.txt (18 테마)
    2) App/BuildInfo.swift                         ← src/pc/yamp/version.py (버전) + 빌드 시각 (규칙 9: 버전__빌드날짜 시간)
    3) project.yml 의 MARKETING_VERSION · CURRENT_PROJECT_VERSION ← version.py (0.1.0 · versionCode)
  build.sh ios 와 GitHub Actions(.github/workflows/ios.yml) 가 빌드 전에 부름. 결과는 늘 같은 내용 (다시 실행해도 안전)
"""
import argparse
import importlib.util
import re
import sys
from pathlib import Path

IOS = Path(__file__).resolve().parents[1]
SRC = IOS.parent
THEMES = SRC / "testdata" / "themes.txt"
VERSION_PY = SRC / "pc" / "yamp" / "version.py"
TOKENS_ORDER = None


def load_version():
    spec = importlib.util.spec_from_file_location("yamp_version", VERSION_PY)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def themes():
    out = {}
    for ln in THEMES.read_text(encoding="utf-8").splitlines():
        if not ln.strip() or ln.startswith("#"):
            continue
        t, k, v = ln.split("|")
        out.setdefault(t, {})[k] = v
    return out


def swift_str(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def gen_theme_swift() -> str:
    tab = themes()
    lines = [
        "// 자동 생성 — 손으로 고치지 마세요 (src/ios/tools/gen_ios.py ← src/testdata/themes.txt)",
        "// 테마 색 표: PC ui/themes.py · Android ThemeTable.kt 와 같은 값 (PC 테스트 test_v028_ios.py 가 확인)",
        "",
        "public struct ThemeDef {",
        "    public let name: String",
        "    public let label: String",
        "    public let dark: Bool",
        "    public let tokens: [String: String]",
        "    public let bands: [String]",
        "    /// 토큰 → 0xRRGGBB (없으면 0)",
        "    public func rgb(_ token: String) -> UInt32 {",
        "        guard let h = tokens[token], h.count == 7 else { return 0 }",
        "        return UInt32(h.dropFirst(), radix: 16) ?? 0",
        "    }",
        "}",
        "",
        "public enum ThemeTable {",
        '    public static let defaultName = "sunny"',
        "    /// 어두운 모드 짝 (써니 → 나이트 써니, 라이트 n → 다크 n, 나머지 밝은 테마 → 다크 블루)",
        '    public static let night: [String: String] = ["sunny": "night_sunny", "light1": "dark1", "light2": "dark2", '
        '"light3": "dark3", "light4": "dark4", "light5": "dark5"]',
        "    public static let all: [ThemeDef] = [",
    ]
    for name, d in tab.items():
        toks = [(k, v) for k, v in d.items() if k not in ("label", "dark", "bands")]
        lines.append(f"        ThemeDef(name: {swift_str(name)}, label: {swift_str(d['label'])}, dark: {'true' if d['dark'] == '1' else 'false'},")
        lines.append("                 tokens: [" + ", ".join(f"{swift_str(k)}: {swift_str(v)}" for k, v in toks) + "],")
        lines.append("                 bands: [" + ", ".join(swift_str(b) for b in d["bands"].split(",")) + "]),")
    lines += [
        "    ]",
        "",
        "    public static func named(_ n: String) -> ThemeDef {",
        '        let key = n == "light" ? "clean_blue" : n',
        "        return all.first { $0.name == key } ?? all.first { $0.name == defaultName }!",
        "    }",
        "",
        "    /// 실제로 쓸 테마: 어두운 모드 따라가기 + 시스템 어두움이면 짝 테마",
        "    public static func effective(_ n: String, follow: Bool, systemDark: Bool) -> String {",
        "        let t = named(n)",
        "        if !follow || !systemDark || t.dark { return t.name }",
        '        return night[t.name] ?? "dark"',
        "    }",
        "}",
        "",
    ]
    return "\n".join(lines)


def gen_build_info(V, build_time: str) -> str:
    return "\n".join([
        "// 자동 생성 — src/ios/tools/gen_ios.py (버전 = src/pc/yamp/version.py, 빌드 시각 = build.sh / GitHub Actions)",
        "enum BuildInfo {",
        f"    static let version = {swift_str(V.VERSION)}",
        f"    static let buildTime = {swift_str(build_time)}",
        "    /// 화면 표시 (규칙 9): 버전__빌드날짜 시간",
        '    static var full: String { "\\(version)__\\(buildTime)" }',
        "}",
        "",
    ])


def patch_project_yml(V) -> bool:
    p = IOS / "project.yml"
    s = p.read_text(encoding="utf-8")
    new = re.sub(r'MARKETING_VERSION: "[^"]*"', f'MARKETING_VERSION: "{V.VER_MAJOR}.{V.VER_MINOR}.{V.VER_PATCH}"', s)
    new = re.sub(r'CURRENT_PROJECT_VERSION: "[^"]*"', f'CURRENT_PROJECT_VERSION: "{V.VERSION_CODE}"', new)
    if new != s:
        p.write_text(new, encoding="utf-8", newline="\n")
    return new != s


def write_if_changed(p: Path, text: str) -> bool:
    if p.exists() and p.read_text(encoding="utf-8") == text:
        return False
    p.write_text(text, encoding="utf-8", newline="\n")
    return True


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--build-time", default="")
    ap.add_argument("--keep-build-time", action="store_true",
                    help="BuildInfo.swift 의 빌드 시각 그대로 (push 로 시작한 CI — PC 가 커밋 전에 넣은 값, v029)")
    a = ap.parse_args(argv)
    V = load_version()
    if a.keep_build_time or not a.build_time:
        old = (IOS / "App" / "BuildInfo.swift")
        m = re.search(r'buildTime = "([^"]*)"', old.read_text(encoding="utf-8")) if old.exists() else None
        a.build_time = (m.group(1) if m else "") or a.build_time or "dev"
    ch = []
    if write_if_changed(IOS / "YampCore" / "Sources" / "YampCore" / "ThemeTable.swift", gen_theme_swift()):
        ch.append("ThemeTable.swift")
    if write_if_changed(IOS / "App" / "BuildInfo.swift", gen_build_info(V, a.build_time)):
        ch.append("BuildInfo.swift")
    if patch_project_yml(V):
        ch.append("project.yml")
    print(f"gen_ios: {V.VERSION}__{a.build_time}  바뀜: {', '.join(ch) or '없음'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
