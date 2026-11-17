"""vr0.1.0.002: 버전 체계 / config.txt / 로그 rotation"""
import datetime
import logging
import os
import subprocess
import sys
from pathlib import Path

import pytest

PC = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PC))

from yamp import version as V                                    # noqa: E402
from yamp.core import config as C                                # noqa: E402
from yamp.core.logger import RingFileHandler                     # noqa: E402


# ---------------------------------------------------------------- 버전
def test_version_format():
    assert V.parse("vt0.0.0.001") == ("t", 0, 0, 0, 1, "")
    assert V.parse("vr0.1.2.345+") == ("r", 0, 1, 2, 345, "+")
    assert V.parse("vd1.2.3.004++")[5] == "++"
    for bad in ("v0.1.2.3", "vx0.1.2.345", "vr0.1.2.3456", "vr0.1.2.345+++", "r0.1.2.345"):
        with pytest.raises(ValueError):
            V.parse(bad)
    assert V.make("r", 0, 1, 2, 5, "+") == "vr0.1.2.005+"
    assert V.VERSION == V.make() and V._RE.match(V.VERSION)
    assert V.code(0, 1, 2, 345) == 102345
    assert V.EXE_BASENAME == f"yMp3Player_{V.VERSION}"
    assert V.full().startswith(V.VERSION + "__")


def test_version_cli_bump(tmp_path):
    p = tmp_path / "version.py"
    p.write_text((PC / "yamp" / "version.py").read_text(encoding="utf-8"), encoding="utf-8")

    def run(*a):
        return subprocess.run([sys.executable, str(p), *a], capture_output=True, text=True).stdout.strip()
    run("--set", "vt0.0.0.998")
    assert run("--bump", "build") == "vt0.0.0.999"
    assert run("--bump", "build") == "vt0.0.1.001"          # 999 다음 → patch +1
    assert run("--type", "r") == "vr0.0.1.001"
    assert run("--upgrade", "++") == "vr0.0.1.001++"
    assert run("--bump", "minor") == "vr0.1.0.001++"
    assert run("--upgrade", "none") == "vr0.1.0.001"
    assert run() == "vr0.1.0.001"
    assert run("--code") == "100001"


def test_gradle_reads_same_version():
    g = (PC.parent / "android" / "app" / "build.gradle.kts").read_text(encoding="utf-8")
    assert "pc/yamp/version.py" in g and "VER_BUILD" in g


# ---------------------------------------------------------------- config.txt
def test_config_parse_types_and_warnings():
    vals, warns = C.parse_config_text(
        "# c\n[log]\nlog_level = debug\nlog_max_size_kb = 2048\nlog_max_files=99999\n"
        "shuffle = yes\nmini_opacity = 0.5\ntheme = DARK\nunknown_key = 1\nrepeat = sometimes\nbroken line\n")
    assert vals["log_level"] == "DEBUG" and vals["log_max_size_kb"] == 2048
    assert vals["log_max_files"] == 100                     # 범위 제한
    assert vals["shuffle"] is True and vals["mini_opacity"] == 0.5 and vals["theme"] == "dark"
    assert "repeat" not in vals
    assert len(warns) == 3 and any("unknown_key" in w for w in warns)


def test_config_default_file_and_update(tmp_path):
    cfg = C.Config(tmp_path)
    assert (tmp_path / "config.txt").read_text(encoding="utf-8") == C.DEFAULT_CONFIG_TEXT
    assert cfg["log_max_files"] == 8 and cfg["log_dir"] == "log" and cfg.data_dir == tmp_path / "data"
    # 기본 config.txt 의 모든 키가 FILE_DEFAULTS 와 일치 (오타 방지)
    vals, warns = C.parse_config_text(C.DEFAULT_CONFIG_TEXT)
    assert not warns and set(vals) == set(C.FILE_DEFAULTS)
    cfg["theme"] = "dark"
    cfg["volume"] = 33                     # state.json
    cfg.save()
    txt = (tmp_path / "config.txt").read_text(encoding="utf-8")
    assert "theme            = dark" in txt and "sunny (기본: 흰색·노랑·주황) / clean_blue" in txt     # v011: 기본 써니
    assert txt.count("\n") == C.DEFAULT_CONFIG_TEXT.count("\n")      # 줄 수 유지
    cfg2 = C.Config(tmp_path)
    assert cfg2["theme"] == "dark" and cfg2["volume"] == 33


def test_config_user_edit_applied(tmp_path):
    (tmp_path / "config.txt").write_text("log_max_size_kb = 64\nlog_dir = mylog\nlyrics_alsong = 0\n", encoding="utf-8")
    cfg = C.Config(tmp_path)
    assert cfg["log_max_size_kb"] == 64 and cfg["lyrics_alsong"] is False
    assert cfg.path_of("log_dir") == tmp_path / "mylog"
    assert cfg["lyrics_lrclib"] is True     # 없는 키 = 기본값


# ---------------------------------------------------------------- 로그
class _Day:
    def __init__(self, d):
        self.d = d

    def __call__(self):
        return self.d


def _emit(h, text):
    h.emit(logging.LogRecord("t", logging.INFO, __file__, 1, text, None, None))


def test_log_name_and_size_rotation(tmp_path):
    day = _Day(datetime.date(2026, 7, 16))
    h = RingFileHandler(tmp_path, max_bytes=4096, max_files=8, today=day)
    h.setFormatter(logging.Formatter("%(message)s"))
    assert os.path.basename(h.current_path) == "00__2026__0716.txt"
    for i in range(400):                    # 약 40KB → 여러 번 rotation
        _emit(h, f"line {i:04d} " + "x" * 90)
    h.close()
    names = sorted(os.listdir(tmp_path))
    assert len(names) == 8                  # 최대 8개 유지
    assert all(n.endswith("__2026__0716.txt") for n in names)
    assert all(os.path.getsize(tmp_path / n) <= 4096 for n in names)
    assert {n[:2] for n in names} == {f"{i:02d}" for i in range(8)}
    last = max(names, key=lambda n: os.path.getmtime(tmp_path / n))
    assert "line 0399" in (tmp_path / last).read_text(encoding="utf-8")
    assert "line 0000" not in "".join((tmp_path / n).read_text(encoding="utf-8") for n in names)  # 오래된 것 삭제


def test_log_day_rotation_and_resume(tmp_path):
    day = _Day(datetime.date(2026, 7, 16))
    h = RingFileHandler(tmp_path, max_bytes=1 << 20, max_files=8, today=day)
    _emit(h, "a")
    day.d = datetime.date(2026, 7, 17)
    _emit(h, "b")
    assert os.path.basename(h.current_path) == "01__2026__0717.txt"
    h.close()
    h2 = RingFileHandler(tmp_path, max_bytes=1 << 20, max_files=8, today=day)   # 재시작 → 이어서
    assert os.path.basename(h2.current_path) == "01__2026__0717.txt"
    h2.close()
    day.d = datetime.date(2026, 7, 18)
    h3 = RingFileHandler(tmp_path, max_bytes=1 << 20, max_files=8, today=day)   # 날짜 바뀜 → 다음 번호
    assert os.path.basename(h3.current_path) == "02__2026__0718.txt"
    h3.close()


def test_logger_setup_writes_file(tmp_path):
    from yamp.core import logger
    cfg = C.Config(tmp_path)
    h = logger.setup(cfg)
    logging.getLogger("yamp.test").warning("hello-log")
    logger.shutdown()
    files = os.listdir(tmp_path / "log")
    assert len(files) == 1 and C.re.match(r"^00__\d{4}__\d{4}\.txt$", files[0])
    txt = (tmp_path / "log" / files[0]).read_text(encoding="utf-8")
    assert "hello-log" in txt and V.VERSION in txt
