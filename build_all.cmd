@echo off
setlocal
rem =====================================================================
rem  yMp3Player release build (double-click in Explorer or run in cmd)
rem    build_all.cmd            clean + exe + apk + zip  (= build.sh all)
rem    build_all.cmd exe | apk | deps | clean | test | doctor | help
rem
rem  Screen : scripts\build_all.ps1 shows the log file live
rem           (MSYS2 bash output is not visible in Windows Terminal)
rem  Log    : dist\build_<cmd>_<date_time>.log  (time per line, env info, progress, step times)
rem  Old way: set BUILD_VIEW=direct  (show bash output directly)
rem  MSYS2 in another folder: set MSYS2_ROOT=D:\msys64
rem
rem  vr0.1.0.011b: this file is ASCII only on purpose.
rem    With UTF-8 Korean text + "chcp 65001", cmd.exe reads lines at wrong
rem    byte offsets and ran a piece of a comment as a command
rem    ("sh: ...: No such file or directory"). Korean messages are printed
rem    by build_all.ps1 / build.sh instead.
rem  Keep CRLF line endings.
rem =====================================================================
if "%MSYS2_ROOT%"=="" set "MSYS2_ROOT=C:\msys64"
cd /d "%~dp0"
echo.
echo [build_all] %date% %time%
echo [build_all] folder: %CD%
if not exist "%MSYS2_ROOT%\usr\bin\bash.exe" goto nomsys
set "ARGS=%*"
if "%ARGS%"=="" set "ARGS=all"
if /i "%BUILD_VIEW%"=="direct" goto direct
where powershell >nul 2>nul
if errorlevel 1 goto direct
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\build_all.ps1" %ARGS%
set "RC=%ERRORLEVEL%"
goto done

:direct
chcp 65001 >nul
echo [build_all] direct mode - bash output on screen, log in dist\build_*.log
set MSYSTEM=UCRT64
set CHERE_INVOKING=1
set MSYS2_PATH_TYPE=inherit
"%MSYS2_ROOT%\usr\bin\bash.exe" -lc "./build.sh %ARGS%"
set "RC=%ERRORLEVEL%"
goto done

:nomsys
echo [ERROR] MSYS2 not found: %MSYS2_ROOT%
echo         Install from https://www.msys2.org or set MSYS2_ROOT, then run again.
set "RC=1"

:done
echo.
if "%RC%"=="0" (echo [build_all] BUILD OK) else (echo [build_all] BUILD FAILED rc=%RC% - see dist\build_*.log)
pause
exit /b %RC%
