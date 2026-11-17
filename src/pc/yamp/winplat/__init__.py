"""Windows 통합 기능 묶음 (vr0.1.0.009)

  win_taskbar  작업 표시줄 썸네일 버튼(이전/재생·일시정지/다음) + 진행률 막대 (ITaskbarList3, ctypes COM)
  win_hotkeys  사용자 지정 전역 단축키 (RegisterHotKey, id 100~ — mediakeys 는 1~4 사용)
  win_theme    Windows 밝게/어둡게 모드 · 강조색 읽기 + 변경 감시 (5초 폴링, 시작했을 때만)
  win_smtc     시스템 미디어 전송 컨트롤 (pyWinRT 있을 때만, 없으면 no-op) — best-effort
  power        재생 목록이 끝나면: PC 절전 / PC 종료 (+ 종료 취소)

공통 규칙
  - sys.platform != "win32" 에서도 import 가능, 모든 기능은 조용히 no-op
  - Windows 에서 API 실패 시 예외를 밖으로 던지지 않음 → logging "yamp.win" 에 기록하고 그 기능만 끔
  - 하위 모듈은 필요할 때 개별 import (이 __init__ 은 가볍게 유지)
"""
import logging
import sys

IS_WIN = sys.platform == "win32"
log = logging.getLogger("yamp.win")

__all__ = ["IS_WIN", "log"]
