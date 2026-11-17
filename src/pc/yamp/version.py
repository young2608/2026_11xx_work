# -*- coding: utf-8 -*-
"""
yMp3Player 버전 (단일 소스 — PC / Android 공용)

형식 : v<type><major>.<minor>.<patch>.<build3><upgrade>
  예)  vt0.0.0.001     vr0.1.2.345+
  v       : version
  type    : r=release  d=debug  p=patch  t=test
  major   : 0
  minor   : 1
  patch   : 2
  build   : 345  (minor / bug patch update, 3자리)
  upgrade : ''  / '+'  / '++'   (업그레이드 표시 버젼)

CLI  (00__build/src/pc/yamp 에서, 또는 ./build.sh ver / bump)
  python version.py                  현재 버전            -> vr0.1.0.003
  python version.py --bump build     build +1   (major | minor | patch | build)
  python version.py --type r         type 변경  (r | d | p | t)
  python version.py --upgrade +      업그레이드 표시 ('none' | '+' | '++')
  python version.py --set vr0.1.2.345+
  python version.py --code           Android versionCode 정수
  python version.py --exe            exe/apk 기본 이름  -> yMp3Player_vr0.1.0.003

src/android/app/build.gradle.kts 가 아래 VER_* 6개 값을 정규식으로 읽음 (형식 유지).
"""
import os
import re
import sys

APP_NAME = "yMp3Player"

VER_TYPE = "r"
VER_MAJOR = 0
VER_MINOR = 1
VER_PATCH = 0
VER_BUILD = 29
VER_UPGRADE = ""

VER_TYPES = {"r": "release", "d": "debug", "p": "patch", "t": "test"}
_RE = re.compile(r"^v([rdpt])(\d+)\.(\d+)\.(\d+)\.(\d{1,3})(\+{0,2})$")


def make(t=None, ma=None, mi=None, pa=None, bu=None, up=None) -> str:
    t = VER_TYPE if t is None else t
    ma = VER_MAJOR if ma is None else ma
    mi = VER_MINOR if mi is None else mi
    pa = VER_PATCH if pa is None else pa
    bu = VER_BUILD if bu is None else bu
    up = VER_UPGRADE if up is None else up
    return f"v{t}{ma}.{mi}.{pa}.{bu:03d}{up}"


def parse(s: str):
    """'vr0.1.2.345+' -> ('r', 0, 1, 2, 345, '+')   형식 오류 시 ValueError"""
    m = _RE.match((s or "").strip())
    if not m:
        raise ValueError(f"bad version string: {s!r}")
    t, a, b, c, d, u = m.groups()
    return t, int(a), int(b), int(c), int(d), u


def code(ma=None, mi=None, pa=None, bu=None) -> int:
    """Android versionCode: major*10^7 + minor*10^5 + patch*10^3 + build"""
    ma = VER_MAJOR if ma is None else ma
    mi = VER_MINOR if mi is None else mi
    pa = VER_PATCH if pa is None else pa
    bu = VER_BUILD if bu is None else bu
    return ma * 10_000_000 + mi * 100_000 + pa * 1_000 + bu


VERSION = make()
VERSION_TYPE_NAME = VER_TYPES.get(VER_TYPE, "?")
VERSION_CODE = code()
EXE_BASENAME = f"{APP_NAME}_{VERSION}"


def build_time() -> str:
    """빌드 날짜·시간 'YYYY-MM-DD HH:MM' (build.sh 가 core/build_info.py 에 기록). 소스 실행 = 'dev'"""
    try:
        from .core import build_info
        return build_info.BUILD_TIME or "dev"
    except Exception:  # noqa  (python version.py 로 직접 실행할 때)
        return "dev"


def full() -> str:
    """화면 표시용 (규칙 9): vr0.1.0.003__2026-11-02 21:50"""
    return f"{VERSION}__{build_time()}"


def _rewrite(t, ma, mi, pa, bu, up) -> str:
    path = os.path.abspath(__file__)
    with open(path, "r", encoding="utf-8") as f:
        src = f.read()
    rep = {"VER_TYPE": f'"{t}"', "VER_MAJOR": str(ma), "VER_MINOR": str(mi),
           "VER_PATCH": str(pa), "VER_BUILD": str(bu), "VER_UPGRADE": f'"{up}"'}
    for k, v in rep.items():
        src = re.sub(rf"^{k} = .*$", f"{k} = {v}", src, count=1, flags=re.M)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(src)
    return make(t, ma, mi, pa, bu, up)


def _cli(argv) -> int:
    t, ma, mi, pa, bu, up = VER_TYPE, VER_MAJOR, VER_MINOR, VER_PATCH, VER_BUILD, VER_UPGRADE
    if not argv:
        print(VERSION)
        return 0
    changed = False
    i = 0
    while i < len(argv):
        a = argv[i]
        v = argv[i + 1] if i + 1 < len(argv) else ""
        if a == "--bump":
            if v == "major":
                ma, mi, pa, bu = ma + 1, 0, 0, 1
            elif v == "minor":
                mi, pa, bu = mi + 1, 0, 1
            elif v == "patch":
                pa, bu = pa + 1, 1
            elif v in ("build", ""):
                bu += 1
                if bu > 999:
                    bu, pa = 1, pa + 1
            else:
                print("bump: major | minor | patch | build", file=sys.stderr)
                return 2
            changed = True
        elif a == "--type":
            if v not in VER_TYPES:
                print("type: r | d | p | t", file=sys.stderr)
                return 2
            t = v
            changed = True
        elif a == "--upgrade":
            v = "" if v in ("none", "-", "0") else v
            if v not in ("", "+", "++"):
                print("upgrade: none | + | ++", file=sys.stderr)
                return 2
            up = v
            changed = True
        elif a == "--set":
            try:
                t, ma, mi, pa, bu, up = parse(v)
            except ValueError as e:
                print(e, file=sys.stderr)
                return 2
            changed = True
        elif a == "--code":
            print(VERSION_CODE)
            return 0
        elif a == "--exe":
            print(EXE_BASENAME)
            return 0
        else:
            print(__doc__)
            return 2
        i += 2
    print(_rewrite(t, ma, mi, pa, bu, up) if changed else VERSION)
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
