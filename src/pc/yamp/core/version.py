"""호환용: 버전 단일 소스는 yamp/version.py (규칙: v<type>major.minor.patch.build<+>)."""
from ..version import APP_NAME, VERSION, VERSION_CODE, EXE_BASENAME, build_time, full  # noqa: F401

BUILD_TIME = build_time()


def version_label() -> str:
    """메뉴바 표시 (규칙 9): vr0.1.0.003__2026-11-02 21:50"""
    return full()


def title_label() -> str:
    return f"{APP_NAME} {full()}"
