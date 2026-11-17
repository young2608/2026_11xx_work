# -*- coding: utf-8 -*-
"""f38 (vr0.1.0.019): Qt 환경 점검 도구 — PE 가져오기 표 읽기 · 빠진 DLL 찾기 · 점검 실패 시 고치는 방법"""
import struct
import subprocess
import sys
from pathlib import Path

PC = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PC / "tools"))
import qt_doctor as Q  # noqa: E402


def make_pe(path: Path, dlls, delay=()):
    """가져오기(일반 · 지연) 표만 있는 최소 PE32+ 파일"""
    sec_va, sec_raw, sec_size = 0x1000, 0x200, 0x400
    data = bytearray(sec_raw + sec_size)
    data[0:2] = b"MZ"
    struct.pack_into("<I", data, 0x3C, 0x40)
    pe = 0x40
    data[pe:pe + 4] = b"PE\0\0"
    struct.pack_into("<HHIIIHH", data, pe + 4, 0x8664, 1, 0, 0, 0, 240, 0x2022)
    opt = pe + 24
    struct.pack_into("<H", data, opt, 0x20B)
    dd = opt + 112
    imp_rva, dly_rva, names_rva = sec_va, sec_va + 0x100, sec_va + 0x200
    struct.pack_into("<II", data, dd + 8 * 1, imp_rva, 20 * (len(dlls) + 1))
    if delay:
        struct.pack_into("<II", data, dd + 8 * 13, dly_rva, 32 * (len(delay) + 1))
    s = opt + 240
    data[s:s + 8] = b".idata\0\0"
    struct.pack_into("<IIII", data, s + 8, sec_size, sec_va, sec_size, sec_raw)
    off = lambda rva: rva - sec_va + sec_raw  # noqa: E731
    nr = names_rva
    for i, n in enumerate(dlls):
        struct.pack_into("<I", data, off(imp_rva) + 20 * i + 12, nr)
        data[off(nr):off(nr) + len(n)] = n.encode()
        nr += len(n) + 1
    for i, n in enumerate(delay):
        struct.pack_into("<I", data, off(dly_rva) + 32 * i + 4, nr)
        data[off(nr):off(nr) + len(n)] = n.encode()
        nr += len(n) + 1
    path.write_bytes(bytes(data))


def test_pe_imports_reads_normal_and_delay(tmp_path):
    p = tmp_path / "QtMultimedia.pyd"
    make_pe(p, ["Qt6Multimedia.dll", "Qt6Core.dll", "api-ms-win-crt-heap-l1-1-0.dll"], delay=["Qt6Network.dll"])
    assert Q.pe_imports(str(p)) == ["Qt6Multimedia.dll", "Qt6Core.dll", "api-ms-win-crt-heap-l1-1-0.dll", "Qt6Network.dll"]
    (tmp_path / "x.txt").write_text("not pe")
    assert Q.pe_imports(str(tmp_path / "x.txt")) == [] and Q.pe_imports(str(tmp_path / "없음.dll")) == []


def test_missing_deps_follows_chain(tmp_path):
    """pyd → Qt6Multimedia.dll(있음) → Qt6Network.dll(없음) 을 따라가서 이름과 부르는 파일을 알려 줌"""
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    make_pe(tmp_path / "QtMultimedia.pyd", ["Qt6Multimedia.dll", "api-ms-win-core-l1-1-0.dll"])
    make_pe(bin_ / "Qt6Multimedia.dll", ["Qt6Network.dll", "Qt6Core.dll"])
    make_pe(bin_ / "Qt6Core.dll", [])
    miss = Q.missing_deps(str(tmp_path / "QtMultimedia.pyd"), [str(bin_)])
    assert ("Qt6Network.dll", "Qt6Multimedia.dll") in miss
    assert not any(d in ("Qt6Multimedia.dll", "Qt6Core.dll") or d.startswith("api-ms-") for d, _ in miss)


def test_check_ok_and_failure_message(tmp_path):
    import os
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    r = subprocess.run([sys.executable, str(PC / "tools" / "qt_doctor.py")], capture_output=True, text=True,
                       encoding="utf-8", env=env, timeout=120)
    assert r.returncode == 0 and "Qt 환경 OK" in r.stdout
    block = tmp_path / "blk"
    block.mkdir()
    (block / "sitecustomize.py").write_text(
        "import sys\nclass B:\n    def find_spec(self, n, p=None, t=None):\n"
        "        if n == 'PyQt6.QtMultimedia':\n            raise ImportError('DLL load failed (모의)')\n"
        "sys.meta_path.insert(0, B())\n", encoding="utf-8")
    env["PYTHONPATH"] = str(block)
    r = subprocess.run([sys.executable, str(PC / "tools" / "qt_doctor.py")], capture_output=True, text=True,
                       encoding="utf-8", env=env, timeout=120)
    assert r.returncode == 1
    assert "실패    : PyQt6.QtMultimedia" in r.stdout and "pacman -Syu" in r.stdout


def test_visualizer_math_imports_without_qtmultimedia(tmp_path):
    """계산 함수(compute_bands 등)는 QtMultimedia 없이도 import (전에는 테스트 수집 자체가 멈춤)"""
    import os
    block = tmp_path / "blk2"
    block.mkdir()
    (block / "sitecustomize.py").write_text(
        "import sys\nclass B:\n    def find_spec(self, n, p=None, t=None):\n"
        "        if n == 'PyQt6.QtMultimedia':\n            raise ImportError('blocked')\n"
        "sys.meta_path.insert(0, B())\n", encoding="utf-8")
    code = ("import sys; sys.path.insert(0, r'%s'); import numpy as np\n"
            "from yamp.audio.visualizer import compute_bands, frame_stats\n"
            "from yamp.audio.waveform import reduce_peaks\n"
            "print(len(compute_bands(np.zeros(2048, np.float32), 44100)), len(reduce_peaks([0.1, 0.5])))" % PC)
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, encoding="utf-8",
                       env=dict(os.environ, PYTHONPATH=str(block), QT_QPA_PLATFORM="offscreen"), timeout=120)
    assert r.returncode == 0, r.stderr
    assert r.stdout.split() == ["24", "240"]          # v026: 24 밴드
