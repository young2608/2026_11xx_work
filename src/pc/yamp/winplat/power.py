"""재생 목록이 끝나면: 정지 / PC 절전 / PC 종료 (vr0.1.0.009)

  sleep_pc()            powrprof.dll SetSuspendState(절전) — 최대 절전(hibernate) 이 켜진 PC 는 OS 설정에 따라 최대 절전으로 갈 수 있음
  shutdown_pc(60)       shutdown.exe /s /t 60  (콘솔 창 없이 실행 — CREATE_NO_WINDOW)
  cancel_shutdown()     shutdown.exe /a        (예약된 종료 취소)
모두 성공 True / 실패·비Windows False. 예외는 던지지 않음."""
import logging
import os
import subprocess
import sys

log = logging.getLogger("yamp.win")

CREATE_NO_WINDOW = 0x08000000
SHUTDOWN_COMMENT = "yMp3Player: 재생 목록이 끝나 PC 를 종료합니다"


def _shutdown_exe() -> str:
    # MSYS2 셸 PATH 에서는 다른 'shutdown' 이 잡힐 수 있어 System32 경로를 직접 사용
    root = os.environ.get("SystemRoot") or os.environ.get("WINDIR") or r"C:\Windows"
    exe = os.path.join(root, "System32", "shutdown.exe")
    return exe if os.path.isfile(exe) else "shutdown.exe"


def _run(args: list[str]) -> bool:
    try:
        r = subprocess.run([_shutdown_exe(), *args], creationflags=CREATE_NO_WINDOW,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
        if r.returncode != 0:
            log.warning("shutdown %s 실패 (code %s)", " ".join(args), r.returncode)
        return r.returncode == 0
    except Exception as e:                                  # noqa: BLE001 — 절대 밖으로 던지지 않음
        log.warning("shutdown %s 실행 오류: %s", " ".join(args), e)
        return False


def sleep_pc() -> bool:
    """PC 절전 (S3/모던 대기). 성공 True"""
    if sys.platform != "win32":
        log.info("sleep_pc: Windows 아님 — 무시")
        return False
    try:
        import ctypes
        from ctypes import wintypes
        powrprof = ctypes.WinDLL("powrprof", use_last_error=True)
        fn = powrprof.SetSuspendState
        fn.argtypes = [wintypes.BOOLEAN, wintypes.BOOLEAN, wintypes.BOOLEAN]
        fn.restype = wintypes.BOOLEAN
        ok = bool(fn(False, False, False))                  # (hibernate=False, force=False, wakeupEventsDisabled=False)
        if not ok:
            log.warning("SetSuspendState 실패 (err %s)", ctypes.get_last_error())
        return ok
    except Exception as e:                                  # noqa: BLE001
        log.warning("sleep_pc 오류: %s", e)
        return False


def shutdown_pc(delay_s: int = 60) -> bool:
    """delay_s 초 뒤 PC 종료 예약 (그동안 cancel_shutdown() 으로 취소 가능). 성공 True"""
    if sys.platform != "win32":
        log.info("shutdown_pc: Windows 아님 — 무시")
        return False
    try:
        n = max(0, min(int(delay_s), 315360000))            # shutdown.exe /t 최대값
    except (TypeError, ValueError):
        n = 60
    return _run(["/s", "/t", str(n), "/c", SHUTDOWN_COMMENT])


def cancel_shutdown() -> bool:
    """예약된 종료 취소. 예약이 없으면 shutdown.exe 가 실패 코드 → False"""
    if sys.platform != "win32":
        log.info("cancel_shutdown: Windows 아님 — 무시")
        return False
    return _run(["/a"])
