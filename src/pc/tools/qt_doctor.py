# -*- coding: utf-8 -*-
"""
Qt 실행 환경 점검 (vr0.1.0.019 f38) — build.sh 가 PC 테스트 전에 부름 (./build.sh doctor 로 따로 실행 가능)

  python tools/qt_doctor.py            점검 → 문제가 있으면 원인 · 고치는 명령 출력, 종료 코드 1
  python tools/qt_doctor.py --deps X   X(.pyd/.dll) 가 부르는 DLL 중 못 찾는 것 (진단용)

왜: MSYS2 패키지를 일부만 업데이트하면(pacman -S 로 하나만 · 업데이트 중단 등) PyQt6 와 Qt DLL 버전이 어긋나
    "DLL load failed while importing QtMultimedia: 지정된 모듈을 찾을 수 없습니다." 처럼 '어떤 DLL 인지' 없이 실패함.
    → .pyd 의 PE 가져오기 표를 직접 읽어 **빠진 DLL 이름**을 찾아 줌 (ntldd 같은 추가 패키지 없이, 표준 라이브러리만).
"""
import os
import struct
import subprocess
import sys

MODULES = ("PyQt6.QtCore", "PyQt6.QtGui", "PyQt6.QtWidgets", "PyQt6.QtMultimedia")
PACKAGES = ("mingw-w64-ucrt-x86_64-python", "mingw-w64-ucrt-x86_64-python-pyqt6", "mingw-w64-ucrt-x86_64-qt6-base",
            "mingw-w64-ucrt-x86_64-qt6-multimedia", "mingw-w64-ucrt-x86_64-ffmpeg")
FIX = ("고치는 방법 (MSYS2 UCRT64 터미널):\n"
       "  1) pacman -Syu            ← 전체 업데이트 (창이 닫히면 터미널을 다시 열고 한 번 더)\n"
       "  2) pacman -S --needed mingw-w64-ucrt-x86_64-python-pyqt6 mingw-w64-ucrt-x86_64-qt6-multimedia\n"
       "  3) ./build.sh doctor      ← 다시 점검 → OK 면 build_all.cmd")


# ---------------------------------------------------------------- PE 가져오기 표 (표준 라이브러리만)
def pe_imports(path: str) -> list[str]:
    """PE(.exe/.dll/.pyd) 가 부르는 DLL 이름 목록 (일반 + 지연 로드). 읽기 실패 시 []"""
    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError:
        return []
    try:
        if data[:2] != b"MZ":
            return []
        pe = struct.unpack_from("<I", data, 0x3C)[0]
        if data[pe:pe + 4] != b"PE\0\0":
            return []
        n_sec = struct.unpack_from("<H", data, pe + 6)[0]
        opt_size = struct.unpack_from("<H", data, pe + 20)[0]
        opt = pe + 24
        magic = struct.unpack_from("<H", data, opt)[0]
        dd = opt + (112 if magic == 0x20B else 96)                 # 데이터 디렉터리 (PE32+ / PE32)
        secs = []
        for i in range(n_sec):
            s = opt + opt_size + 40 * i
            vsize, va, rsize, raw = struct.unpack_from("<IIII", data, s + 8)
            secs.append((va, max(vsize, rsize), raw))

        def off(rva):
            for va, size, raw in secs:
                if va <= rva < va + size:
                    return rva - va + raw
            return None

        def cstr(rva):
            o = off(rva)
            if o is None:
                return ""
            e = data.index(b"\0", o)
            return data[o:e].decode("ascii", "replace")

        names = []
        for idx, size in ((1, 20), (13, 32)):                      # 1 = 가져오기, 13 = 지연 로드
            rva = struct.unpack_from("<I", data, dd + 8 * idx)[0]
            o = off(rva) if rva else None
            while o is not None and o + size <= len(data):
                name_rva = struct.unpack_from("<I", data, o + (12 if idx == 1 else 4))[0]
                if not name_rva:
                    break
                n = cstr(name_rva)
                if n:
                    names.append(n)
                o += size
        return names
    except (struct.error, ValueError):
        return []


def _system_dirs():
    root = os.environ.get("SystemRoot", r"C:\Windows")
    return [os.path.join(root, "System32"), root]


def find_dll(name: str, extra_dirs) -> str | None:
    low = name.lower()
    if low.startswith(("api-ms-win-", "ext-ms-")):              # Windows 가상 DLL (항상 있음)
        return "<system>"
    for d in list(extra_dirs) + _system_dirs():
        p = os.path.join(d, name)
        if os.path.isfile(p):
            return p
    return None


def missing_deps(path: str, extra_dirs, limit: int = 400) -> list[tuple[str, str]]:
    """[(빠진 DLL, 그것을 부르는 파일)] — 찾은 DLL 은 그 DLL 의 가져오기까지 따라감"""
    seen, out, todo = set(), [], [path]
    while todo and len(seen) < limit:
        cur = todo.pop()
        for dep in pe_imports(cur):
            key = dep.lower()
            if key in seen:
                continue
            seen.add(key)
            hit = find_dll(dep, [os.path.dirname(cur)] + list(extra_dirs))
            if hit is None:
                out.append((dep, os.path.basename(cur)))
            elif hit != "<system>" and not hit.lower().startswith(tuple(d.lower() for d in _system_dirs())):
                todo.append(hit)
    return out


# ---------------------------------------------------------------- 점검
def _pacman_versions() -> str:
    try:
        r = subprocess.run(["pacman", "-Q", *PACKAGES], capture_output=True, text=True, timeout=30)
        return (r.stdout + r.stderr).strip()
    except (OSError, subprocess.SubprocessError):
        return "(pacman 없음 — MSYS2 UCRT64 터미널에서 실행하세요)"


def _pyd_path(mod: str) -> str | None:
    try:
        import importlib.util
        pkg = importlib.util.find_spec("PyQt6")
    except Exception:  # noqa
        return None
    if not pkg or not pkg.submodule_search_locations:
        return None
    base = list(pkg.submodule_search_locations)[0]
    short = mod.split(".")[-1]
    for f in os.listdir(base):
        if f.startswith(short + ".") and f.endswith((".pyd", ".so")):
            return os.path.join(base, f)
    return None


def check() -> int:
    print(f"python  : {sys.executable}  {sys.version.split()[0]}")
    bad = []
    for m in MODULES:
        try:
            __import__(m)
            print(f"OK      : {m}")
        except Exception as e:  # noqa
            print(f"실패    : {m}  — {e}")
            bad.append(m)
    try:
        from PyQt6 import QtCore
        print(f"Qt      : PyQt6 {QtCore.PYQT_VERSION_STR} (빌드 기준 Qt {QtCore.QT_VERSION_STR}) · 실행 Qt DLL {QtCore.qVersion()}")
        if QtCore.qVersion().split(".")[:2] != QtCore.QT_VERSION_STR.split(".")[:2]:
            print("주의    : PyQt6 와 Qt DLL 의 버전이 다름 → 패키지 일부만 업데이트된 상태")
    except Exception:  # noqa
        pass
    if not bad:
        print("결과    : Qt 환경 OK")
        return 0
    print("\n---- 원인 찾기 ----")
    print("설치된 패키지:\n  " + _pacman_versions().replace("\n", "\n  "))
    dirs = [os.path.join(sys.prefix, "bin"), os.path.dirname(sys.executable)]
    for m in bad:
        pyd = _pyd_path(m)
        if not pyd:
            print(f"{m}: 모듈 파일 없음 → python-pyqt6 패키지가 깨졌거나 없음")
            continue
        miss = missing_deps(pyd, dirs + [os.path.dirname(pyd)])
        if miss:
            print(f"{m}: 못 찾는 DLL " + ", ".join(f"{d} (← {who})" for d, who in miss))
        else:
            print(f"{m}: DLL 파일은 모두 있음 → 버전이 서로 맞지 않음 (함수 이름 불일치) — 부분 업데이트가 원인")
    print("\n" + FIX)
    return 1


def main(argv) -> int:
    if len(argv) >= 2 and argv[0] == "--deps":
        extra = [os.path.join(sys.prefix, "bin"), os.path.dirname(sys.executable)]
        print("부르는 DLL:", ", ".join(pe_imports(argv[1])) or "(없음/읽기 실패)")
        miss = missing_deps(argv[1], extra)
        print("못 찾음  :", ", ".join(f"{d} (← {w})" for d, w in miss) or "없음")
        return 1 if miss else 0
    return check()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
