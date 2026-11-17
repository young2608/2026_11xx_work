#!/usr/bin/env bash
# =====================================================================
#  yMp3Player build script  (MSYS2 UCRT64 terminal)
#
#   ./build.sh help                 도움말
#   ./build.sh deps [mpv]           빌드 의존성 설치 (pacman) + Android 환경 점검  (mpv: libmpv 도 설치 → EQ·음정)
#   ./build.sh exe  [onefile]       PC  : dist/yMp3Player_<ver>/yMp3Player_<ver>.exe  + dist/yMp3Player_<ver>_win64.zip
#                                         (onefile: dist/yMp3Player_<ver>.exe 파일 하나)
#   ./build.sh apk  [debug]         Android : dist/yMp3Player_<ver>.apk
#   ./build.sh ios                  iPhone : GitHub Actions(macOS)에서 서명 없는 ipa → dist/yMp3Player_<ver>_ios_unsigned.ipa
#                                         (ios.cfg 의 GH_REPO 필요 · gh 로그인 — docs/ios_setup.md, v028)
#   ./build.sh all                  clean + exe + apk (+ ios: ios.cfg 설정 시) + dist/yMp3Player_<ver>_release.zip
#   ./build.sh clean [dist]         빌드 중간물 + 현재 버전 산출물 삭제  (dist: dist 폴더 전체)
#   ./build.sh test                 PC pytest + Android 단위 테스트
#   ./build.sh doctor               Qt 환경 점검 (PyQt6 · QtMultimedia DLL — 빠진 DLL · 패키지 버전 · 고치는 명령)
#   ./build.sh ver                  현재 버전 출력          (vr0.1.0.003)
#   ./build.sh bump [build|patch|minor|major]   버전 +1  (src/pc/yamp/version.py)
#   ./build.sh run                  PC 소스 실행
#
#  버전 단일 소스 : src/pc/yamp/version.py   형식 v<r|d|p|t><major>.<minor>.<patch>.<build3>[+|++]
#  빌드 시각      : 한 번 정해 exe·apk 같은 값 → 메뉴바 '버전__빌드날짜 시간'
#  로그           : dist/build_<명령>_<시각>.log  (최근 30개 유지)
#                   각 줄 [시:분:초], 시작 시 환경 정보, 30초 동안 출력이 없으면 '진행 중' 줄,
#                   끝에 단계별 소요 시간 · 결과 코드.  BUILD_LOG=경로 로 파일 지정 가능
#                   BUILD_QUIET=1 이면 화면 출력 없이 로그 파일에만 (build_all.ps1 이 로그를 읽어 화면에 표시)
# =====================================================================
set -u
set -o pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
PC="$ROOT/src/pc"          # v021: 소스는 src/ 아래 (src/pc · src/android · src/testdata)
AND="$ROOT/src/android"
IOSD="$ROOT/src/ios"       # v028: iOS (Swift · XcodeGen) — 빌드는 GitHub Actions macOS
DIST="$ROOT/dist"
PY="${PYTHON:-python}"
command -v "$PY" >/dev/null 2>&1 || PY=python3
export PYTHONUTF8=1 PYTHONIOENCODING=utf-8
APP="yMp3Player"

IS_WIN=0
case "$(uname -s)" in MINGW*|MSYS*|CYGWIN*|UCRT*|CLANG*|*_NT-*) IS_WIN=1 ;; esac
winpath()  { if [ $IS_WIN = 1 ]; then cygpath -m "$1"; else echo "$1"; fi; }
unixpath() { if [ $IS_WIN = 1 ]; then cygpath -u "$1"; else echo "$1"; fi; }

c_ok()   { printf '\033[32m%s\033[0m\n' "$*"; }
c_info() { printf '\n\033[36m==== %s ====\033[0m\n' "$*"; }
c_err()  { printf '\033[31m%s\033[0m\n' "$*" >&2; }

ver()   { timeout 60 "$PY" "$PC/yamp/version.py"; }
usage() { sed -n '3,25p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; }

VER_ERR=""
VER="$(ver 2>/dev/null | tr -d '\r\n')"
[ -n "$VER" ] || { VER_ERR="버전을 읽을 수 없음: src/pc/yamp/version.py (python: $(command -v "$PY" || echo 없음) → ./build.sh deps)"; VER="vt0.0.0.000"; }
BASE="${APP}_${VER}"
export YAMP_BUILD_TIME="${YAMP_BUILD_TIME:-$(date '+%Y-%m-%d %H:%M')}"

# ---------------------------------------------------------------------
deps() {
    c_info "MSYS2 패키지 설치"
    if command -v pacman >/dev/null 2>&1; then
        pacman -S --needed --noconfirm \
            mingw-w64-ucrt-x86_64-python mingw-w64-ucrt-x86_64-python-pyqt6 \
            mingw-w64-ucrt-x86_64-qt6-multimedia mingw-w64-ucrt-x86_64-python-numpy \
            mingw-w64-ucrt-x86_64-python-mutagen mingw-w64-ucrt-x86_64-python-pytest \
            mingw-w64-ucrt-x86_64-pyinstaller zip unzip || return 1
        if [ "${1:-}" = "mpv" ]; then
            pacman -S --needed --noconfirm mingw-w64-ucrt-x86_64-mpv || c_err "mpv 설치 실패 (Qt 엔진은 그대로 사용 가능)"
        fi
    else
        c_err "pacman 없음 (MSYS2 UCRT64 터미널에서 실행하세요)"
    fi
    "$PY" -c "import numpy, mutagen; print('numpy/mutagen OK')" || return 1
    qt_doctor || return 1
    c_info "Android 환경"
    find_jdk && echo "JDK : $JAVA_HOME" || echo "JDK 없음 (Android Studio 설치 → jbr 자동 탐지)"
    find_sdk && echo "SDK : $SDK" || echo "Android SDK 없음 (ANDROID_HOME 또는 %LOCALAPPDATA%\\Android\\Sdk)"
    return 0
}

find_jdk() {
    local c
    for c in "${JAVA_HOME:-}" "/c/Program Files/Android/Android Studio/jbr" "/c/Program Files/Android/Android Studio/jre" \
             "${LOCALAPPDATA:+$(unixpath "$LOCALAPPDATA")/Programs/Android Studio/jbr}"; do
        [ -n "$c" ] || continue
        c="$(unixpath "$c")"
        if [ -x "$c/bin/java" ] || [ -x "$c/bin/java.exe" ]; then export JAVA_HOME="$(winpath "$c")"; return 0; fi
    done
    return 1
}

find_sdk() {
    local c
    for c in "${ANDROID_HOME:-}" "${ANDROID_SDK_ROOT:-}" \
             "${LOCALAPPDATA:+$(unixpath "$LOCALAPPDATA")/Android/Sdk}" \
             "${USERPROFILE:+$(unixpath "$USERPROFILE")/AppData/Local/Android/Sdk}" \
             "$HOME/Android/Sdk" /c/Android/Sdk /d/Android/Sdk; do
        [ -n "$c" ] || continue
        c="$(unixpath "$c")"
        if [ -d "$c/platforms" ] || [ -d "$c/build-tools" ]; then SDK="$c"; return 0; fi
    done
    return 1
}

# ---------------------------------------------------------------------
qt_doctor() {
    # v019 f38: PyQt6 · Qt DLL 점검 — 'DLL load failed while importing QtMultimedia' 처럼 원인 없이 실패하는 경우
    #           빠진 DLL 이름 · 설치된 패키지 버전 · 고치는 명령을 로그에 남김 (src/pc/tools/qt_doctor.py)
    c_info "Qt 환경 점검"
    (cd "$PC" && QT_QPA_PLATFORM=offscreen "$PY" tools/qt_doctor.py)
}

pc_test() {
    qt_doctor || { c_err "Qt 환경 문제 → 테스트 · exe 빌드 중단 (위 '고치는 방법' 실행 후 다시 빌드, 소스 문제 아님)"; return 1; }
    c_info "PC 테스트 (pytest)"
    # v011b: -v = 테스트마다 한 줄 (진행이 보임) · 느린 테스트 10개 · 한 테스트가 120초 넘으면 스레드 상태를 로그에 남김
    #        테스트 중 인터넷은 tests/conftest.py 가 막음 (가사 서버 접속 대기로 수십 분 걸리던 문제)
    (cd "$PC" && QT_QPA_PLATFORM=offscreen "$PY" -m pytest -v -p no:cacheprovider --durations=10 \
        -o faulthandler_timeout=120 -o console_output_style=classic tests)
}

exe() {
    local mode="${1:-onedir}"
    c_info "PC exe  $VER  ($YAMP_BUILD_TIME)"
    pc_test || { c_err "테스트 실패 → exe 빌드 중단"; return 1; }
    local BI="$PC/yamp/core/build_info.py"
    cp -f "$BI" "$BI.bak"
    printf '# build.sh 가 exe 빌드 중에만 채움 (빌드 후 원복)\nBUILD_TIME = "%s"\n' "$YAMP_BUILD_TIME" > "$BI"
    local rc=0
    rm -rf "$PC/build/pyi"
    mkdir -p "$DIST"
    # libmpv (audio_backend = mpv 용, 있을 때만 동봉)
    local MPV_ARGS=()
    local mpvdll
    for mpvdll in /ucrt64/bin/libmpv-2.dll /ucrt64/bin/mpv-2.dll; do
        if [ -f "$mpvdll" ]; then MPV_ARGS=(--add-binary "$(winpath "$mpvdll");."); echo "libmpv 동봉: $mpvdll"; break; fi
    done
    [ ${#MPV_ARGS[@]} -eq 0 ] && echo "libmpv 없음 → Qt 엔진만 (EQ·음정 쓰려면: ./build.sh deps mpv)"
    c_info "PyInstaller (exe 만들기)"
    if [ "$mode" = "onefile" ]; then
        (cd "$PC" && "$PY" -m PyInstaller --noconfirm --clean --windowed --onefile --name "$BASE" \
            --distpath "$(winpath "$DIST")" --workpath build/pyi --specpath build \
            --hidden-import PyQt6.QtMultimedia "${MPV_ARGS[@]}" main.py) || rc=1
    else
        rm -rf "${DIST:?}/$BASE"
        (cd "$PC" && "$PY" -m PyInstaller --noconfirm --clean --windowed --name "$BASE" \
            --distpath "$(winpath "$DIST")" --workpath build/pyi --specpath build \
            --hidden-import PyQt6.QtMultimedia "${MPV_ARGS[@]}" main.py) || rc=1
    fi
    mv -f "$BI.bak" "$BI"
    [ $rc = 0 ] || { c_err "PyInstaller 실패"; return 1; }
    if [ "$mode" = "onefile" ]; then
        ls "$DIST/$BASE"* >/dev/null 2>&1 || { c_err "exe 없음"; return 1; }
        c_ok "OK  dist/$BASE.exe  (config.txt·log/ 는 첫 실행 때 exe 옆에 생성)"
        return 0
    fi
    # 배포 폴더: exe + _internal + config.txt + log/ + README
    c_info "배포 폴더 · win64.zip"
    cp -f "$PC/config.txt" "$DIST/$BASE/config.txt"
    mkdir -p "$DIST/$BASE/log"
    cat > "$DIST/$BASE/README_run.txt" <<EOF
$APP $VER  (빌드 $YAMP_BUILD_TIME)

실행     : $BASE.exe
설정     : config.txt  (메모장으로 수정 후 다시 실행하면 적용)
로그     : log\\NN__YYYY__MMDD.txt  (최대 크기·개수는 config.txt [log])
데이터   : data\\  (플레이리스트, 가사 캐시, 창 위치)
업데이트 : 새 폴더의 파일로 덮어쓰되 config.txt / data / log 는 그대로 두세요.
EOF
    (cd "$DIST" && rm -f "${BASE}_win64.zip" && zip -qr "${BASE}_win64.zip" "$BASE")
    c_ok "OK  dist/$BASE/$BASE.exe"
    c_ok "OK  dist/${BASE}_win64.zip"
}

apk() {
    local kind="${1:-release}"
    c_info "Android apk  $VER  ($YAMP_BUILD_TIME)"
    find_jdk || { c_err "JDK 없음 — Android Studio 설치 필요"; return 1; }
    find_sdk || { c_err "Android SDK 없음 — ANDROID_HOME 설정 필요"; return 1; }
    echo "JDK : $JAVA_HOME"
    echo "SDK : $SDK"
    echo "sdk.dir=$(winpath "$SDK")" > "$AND/local.properties"
    chmod +x "$AND/gradlew" 2>/dev/null
    local task="assembleRelease" sub="release" suffix=""
    [ "$kind" = "debug" ] && { task="assembleDebug"; sub="debug"; suffix="_debug"; }
    echo "Gradle 시작 (첫 빌드는 라이브러리 다운로드로 몇 분 걸릴 수 있음)"
    (cd "$AND" && ./gradlew --no-daemon --console=plain testDebugUnitTest "$task") || { c_err "Gradle 실패 (위 로그 확인)"; return 1; }
    local out="$AND/app/build/outputs/apk/$sub/${BASE}${suffix}.apk"
    [ -f "$out" ] || out="$(ls "$AND/app/build/outputs/apk/$sub/"*.apk 2>/dev/null | head -1)"
    [ -f "$out" ] || { c_err "apk 없음"; return 1; }
    mkdir -p "$DIST"
    cp -f "$out" "$DIST/${BASE}${suffix}.apk"
    c_ok "OK  dist/${BASE}${suffix}.apk"
}

android_test() {
    c_info "Android 단위 테스트"
    find_jdk && find_sdk || { c_err "JDK/SDK 없음 — 건너뜀"; return 0; }
    echo "sdk.dir=$(winpath "$SDK")" > "$AND/local.properties"
    (cd "$AND" && ./gradlew --no-daemon --console=plain testDebugUnitTest)
}

clean() {
    c_info "clean"
    rm -rf "$PC/build" "$PC/.pytest_cache" "$PC/tests/_home" "$AND/app/build" "$AND/build" "$AND/.gradle" "$AND/.kotlin"
    find "$ROOT" -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null
    if [ "${1:-}" = "dist" ]; then
        rm -rf "$DIST"; echo "dist 전체 삭제"
    else
        rm -rf "${DIST:?}/$BASE" "$DIST/$BASE.exe" "$DIST/${BASE}_win64.zip" "$DIST/$BASE.apk" \
               "$DIST/${BASE}_debug.apk" "$DIST/${BASE}_release.zip" "$DIST/${BASE}_ios_unsigned.ipa"
        echo "중간물 + 현재 버전($VER) 산출물 삭제 (다른 버전 산출물은 유지)"
    fi
}

# ---------------------------------------------------------------------
#  iOS (v028, f55): Windows 에서는 iOS 바이너리를 만들 수 없음 (Xcode = macOS 전용)
#    → 소스를 GitHub 에 올리고 GitHub Actions(macOS) 에 빌드 요청 → 끝나면 ipa 를 dist/ 로 받음
#    설정: ios.cfg (ios.cfg.example 복사) · gh 설치 + gh auth login   — docs/ios_setup.md
# ---------------------------------------------------------------------
ios_cfg() {
    GH_REPO="" GH_BRANCH="ymp3player" IOS_PUSH=1 IOS_IN_ALL=1
    # shellcheck disable=SC1091
    [ -f "$ROOT/ios.cfg" ] && . "$ROOT/ios.cfg"
    GH_REPO="${GH_REPO//[[:space:]]/}"
    GH_BRANCH="${GH_BRANCH//[[:space:]]/}"; IOS_PUSH="${IOS_PUSH//[[:space:]]/}"; IOS_IN_ALL="${IOS_IN_ALL//[[:space:]]/}"   # 메모장 CRLF 대비
    GH_BRANCH="${GH_BRANCH:-ymp3player}"
}

ios() {
    c_info "iOS (GitHub Actions → 서명 없는 ipa)"
    ios_cfg
    "$PY" "$IOSD/tools/gen_ios.py" --build-time "$YAMP_BUILD_TIME" || return 1     # 빌드 시각 = exe · apk 와 같은 값 (커밋에 들어감)
    if [ -z "$GH_REPO" ]; then
        echo "ios.cfg 의 GH_REPO 가 비어 있음 → iOS 건너뜀  (ios.cfg.example 을 ios.cfg 로 복사해 GitHub 저장소 입력 — docs/ios_setup.md)"
        return 0
    fi
    command -v gh >/dev/null 2>&1 || { c_err "gh(GitHub CLI) 없음 → pacman -S mingw-w64-ucrt-x86_64-github-cli  (또는 winget install GitHub.cli)"; return 1; }
    command -v git >/dev/null 2>&1 || { c_err "git 없음 → pacman -S git"; return 1; }
    gh auth status -h github.com >/dev/null 2>&1 || { c_err "GitHub 로그인 필요 → gh auth login  (한 번만)"; return 1; }
    gh auth setup-git >/dev/null 2>&1 || true
    local url="https://github.com/$GH_REPO.git"
    if [ "$IOS_PUSH" = 1 ]; then
        echo "소스 올리기 → $url ($GH_BRANCH)"
        if [ ! -d "$ROOT/.git" ]; then
            git -C "$ROOT" init -q && git -C "$ROOT" checkout -q -b "$GH_BRANCH" || return 1
        fi
        git -C "$ROOT" remote get-url origin >/dev/null 2>&1 || git -C "$ROOT" remote add origin "$url"
        git -C "$ROOT" config user.name >/dev/null 2>&1 || git -C "$ROOT" config user.name "yMp3Player build"
        git -C "$ROOT" config user.email >/dev/null 2>&1 || git -C "$ROOT" config user.email "build@localhost"
        git -C "$ROOT" add -A || return 1
        git -C "$ROOT" commit -q -m "build $VER $YAMP_BUILD_TIME" >/dev/null 2>&1 || echo "(바뀐 파일 없음 — 커밋 생략)"
        if ! git -C "$ROOT" push -q origin "HEAD:$GH_BRANCH"; then
            c_err "push 실패: $url ($GH_BRANCH) — 저장소 이름 · 권한(gh auth login) 확인."
            c_err "  같은 이름 브랜치에 다른 기록이 있으면 ios.cfg 의 GH_BRANCH 를 새 이름으로 (워크플로 push 브랜치도 같이)"
            return 1
        fi
    fi
    local sha t0 id="" i
    sha="$(git -C "$ROOT" rev-parse HEAD 2>/dev/null || true)"
    t0="$(date -u -d '-3 min' '+%Y-%m-%dT%H:%M:%SZ' 2>/dev/null || date -u '+%Y-%m-%dT%H:%M:%SZ')"   # PC 시계 차이 여유 3분
    local ev=push
    if [ "$IOS_PUSH" = 1 ]; then
        echo "빌드 시작 — push 로 자동 (ios.yml, 브랜치 $GH_BRANCH, 빌드 시각 $YAMP_BUILD_TIME)"
    else
        ev=workflow_dispatch                       # 이미 올린 소스로: 직접 요청 (워크플로 파일이 기본 브랜치에도 있어야 함)
        echo "빌드 요청 (ios.yml, 빌드 시각 $YAMP_BUILD_TIME)"
        gh workflow run ios.yml -R "$GH_REPO" --ref "$GH_BRANCH" -f build_time="$YAMP_BUILD_TIME" || { c_err "빌드 요청 실패 (.github/workflows/ios.yml 이 기본 브랜치에 있는지)"; return 1; }
    fi
    for i in $(seq 1 40); do                         # 방금 시작한 실행 찾기 (같은 커밋 · 요청 시각 이후)
        sleep 3
        id="$(gh run list -R "$GH_REPO" -w ios.yml -e "$ev" -L 5 \
              --json databaseId,headSha,createdAt -q ".[] | select(.createdAt >= \"$t0\") | select(\"$sha\" == \"\" or .headSha == \"$sha\") | .databaseId" 2>/dev/null | head -1)"
        [ -n "$id" ] && break
    done
    [ -n "$id" ] || { c_err "빌드 실행을 찾지 못함 → https://github.com/$GH_REPO/actions 에서 확인"; return 1; }
    echo "빌드 중 (macOS 약 5~10분): https://github.com/$GH_REPO/actions/runs/$id"
    if ! gh run watch "$id" -R "$GH_REPO" --interval 30 --exit-status >/dev/null; then
        c_err "iOS 빌드 실패 — 실패 단계 로그 끝부분:"
        gh run view "$id" -R "$GH_REPO" --log-failed 2>/dev/null | tail -60
        return 1
    fi
    rm -f "$DIST/${BASE}_ios_unsigned.ipa"
    gh run download "$id" -R "$GH_REPO" -n ipa -D "$DIST" || { c_err "ipa 받기 실패"; return 1; }
    [ -f "$DIST/${BASE}_ios_unsigned.ipa" ] || { c_err "받은 파일 이름이 다름 → dist/ 확인"; ls -l "$DIST"/*.ipa 2>/dev/null; return 1; }
    c_ok "OK  dist/${BASE}_ios_unsigned.ipa  ($(du -h "$DIST/${BASE}_ios_unsigned.ipa" | cut -f1))"
    echo "설치: Sideloadly 에 끌어다 놓고 Apple ID 로 Start (무료 계정 = 7일마다 다시) — docs/ios_setup.md"
}

pack_release() {
    c_info "release zip"
    local files=()
    [ -f "$DIST/${BASE}_win64.zip" ] && files+=("${BASE}_win64.zip")
    [ -f "$DIST/$BASE.apk" ] && files+=("$BASE.apk")
    [ -f "$DIST/${BASE}_ios_unsigned.ipa" ] && files+=("${BASE}_ios_unsigned.ipa")
    [ ${#files[@]} -gt 0 ] || { echo "산출물 없음"; return 1; }
    (cd "$DIST" && rm -f "${BASE}_release.zip" && zip -q "${BASE}_release.zip" "${files[@]}")
    c_ok "OK  dist/${BASE}_release.zip  (${files[*]})"
}

all() {
    local r_exe=0 r_apk=0 r_ios=0 ios_msg="건너뜀 (ios.cfg 의 GH_REPO 없음)"
    clean
    exe || r_exe=1
    apk || r_apk=1
    ios_cfg
    if [ -n "$GH_REPO" ] && [ "$IOS_IN_ALL" = 1 ]; then
        if ios; then ios_msg="OK  dist/${BASE}_ios_unsigned.ipa"; else r_ios=1; ios_msg="실패"; fi
    fi
    pack_release
    c_info "결과  ${VER}__${YAMP_BUILD_TIME}"
    echo "PC exe  : $([ $r_exe = 0 ] && echo "OK  dist/$BASE/$BASE.exe" || echo 실패)"
    echo "Android : $([ $r_apk = 0 ] && echo "OK  dist/$BASE.apk" || echo 실패)"
    echo "iPhone  : $ios_msg"
    return $(( r_exe || r_apk || r_ios ))
}

# ---------------------------------------------------------------------
#  빌드 로그
#    화면: 원래 출력 (색) / 파일: 색 코드 없이 각 줄 앞에 [시:분:초]
#    30초 동안 출력이 없으면 '… 진행 중: 단계 (경과)' 줄 → 멈춘 것인지 구분
#    '==== 단계 ====' 줄마다 단계 시작으로 보고 끝에 단계별 소요 시간 표
# ---------------------------------------------------------------------
shopt -s extglob
fmt_t() { printf '%d:%02d' $(( $1 / 60 )) $(( $1 % 60 )); }

log_pump() {
    local line buf="" plain ts st step="준비" step_t0=$SECONDS t0=$SECONDS
    local -a s_name=() s_sec=()
    exec 3>>"$LOG"
    _emit() {   # $1 = 원래 줄
        plain="${1//$'\e['*([0-9;])m/}"
        plain="${plain%$'\r'}"
        printf -v ts '%(%H:%M:%S)T' -1
        [ -n "${BUILD_QUIET:-}" ] || printf '%s\n' "$1"
        printf '[%s] %s\n' "$ts" "$plain" >&3
        if [[ "$plain" == "==== "*" ====" ]]; then
            s_name+=("$step"); s_sec+=($((SECONDS - step_t0)))
            step="${plain#==== }"; step="${step% ====}"; step_t0=$SECONDS
        fi
    }
    while :; do
        if IFS= read -r -t "${BUILD_HEARTBEAT_S:-30}" line; then
            _emit "$buf$line"; buf=""
        else
            st=$?
            if [ $st -gt 128 ]; then
                buf+="$line"
                _emit "  … 진행 중: $step (단계 $(fmt_t $((SECONDS - step_t0))), 전체 $(fmt_t $((SECONDS - t0))))"
                continue
            fi
            [ -n "$buf$line" ] && _emit "$buf$line"
            break
        fi
    done
    s_name+=("$step"); s_sec+=($((SECONDS - step_t0)))
    _emit ""
    _emit "---- 단계별 소요 시간 ----"
    local i
    for i in "${!s_name[@]}"; do
        [ "${s_sec[$i]}" -gt 0 ] || [ "${s_name[$i]}" != "준비" ] || continue
        _emit "$(printf '  %6s  %s' "$(fmt_t "${s_sec[$i]}")" "${s_name[$i]}")"
    done
    _emit "$(printf '  %6s  %s' "$(fmt_t $((SECONDS - t0)))" "전체")"
    exec 3>&-
}

env_info() {
    c_info "환경"
    echo "시작     : $(date '+%Y-%m-%d %H:%M:%S')"
    echo "명령     : ./build.sh $cmd ${ARGS_STR}"
    echo "폴더     : $(winpath "$ROOT")"
    echo "로그     : $(winpath "$LOG")"
    echo "버전     : ${VER}__${YAMP_BUILD_TIME}"
    [ -n "$VER_ERR" ] && c_err "$VER_ERR"
    echo "OS       : $(uname -sr)  MSYSTEM=${MSYSTEM:-없음}"
    echo "python   : $(command -v "$PY" || echo 없음)  $(timeout 30 "$PY" --version 2>&1 | head -1)"
    case "$cmd" in exe|all)
        echo "PyInstaller: $(timeout 60 "$PY" -m PyInstaller --version 2>&1 | tail -1)" ;;
    esac
    case "$cmd" in apk|all|test|deps)
        if find_jdk; then echo "JDK      : $JAVA_HOME  ($(timeout 30 "$(unixpath "$JAVA_HOME")/bin/java" -version 2>&1 | head -1))"
        else echo "JDK      : 없음"; fi
        if find_sdk; then echo "SDK      : $(winpath "$SDK")"; else echo "SDK      : 없음"; fi ;;
    esac
    case "$cmd" in ios|all)
        ios_cfg
        echo "iOS      : 저장소=${GH_REPO:-없음(ios.cfg)}  gh=$(command -v gh >/dev/null 2>&1 && gh --version | head -1 || echo 없음)  git=$(git --version 2>/dev/null || echo 없음)" ;;
    esac
    echo "디스크   : $(df -h "$ROOT" 2>/dev/null | awk 'NR==2{print $4" 남음 ("$6")"}')"
}

run_cmd() {
    env_info
    case "$cmd" in
        deps)  deps "$@" ;;
        exe)   exe "$@" ;;
        apk)   apk "$@" ;;
        all)   all ;;
        clean) clean "$@" ;;
        test)  local r=0; pc_test || r=1; android_test || r=1; return $r ;;
        doctor) qt_doctor ;;
        ios)   ios "$@" ;;
        *) c_err "알 수 없는 명령: $cmd"; usage; return 2 ;;
    esac
}

# ---------------------------------------------------------------------
cmd="${1:-help}"
[ $# -gt 0 ] && shift
case "$cmd" in
    help|-h|--help) usage; exit 0 ;;
    ver) echo "$VER"; exit 0 ;;
    bump) "$PY" "$PC/yamp/version.py" --bump "${1:-build}"; exit $? ;;
    run) cd "$PC" && exec "$PY" main.py "$@" ;;
esac
mkdir -p "$DIST"
ARGS_STR="$*"
if [ -n "${BUILD_LOG:-}" ]; then
    LOG="$(unixpath "$BUILD_LOG")"
else
    LOG="$DIST/build_${cmd}_$(date '+%Y%m%d_%H%M%S').log"
fi
# 오래된 빌드 로그 정리 (최근 30개 유지)
ls -1t "$DIST"/build_*.log 2>/dev/null | tail -n +30 | while IFS= read -r f; do rm -f "$f"; done
[ -n "${BUILD_QUIET:-}" ] || echo "로그: $(winpath "$LOG")"
{
    echo "# $APP build.sh $cmd $*   $VER   $YAMP_BUILD_TIME"
    run_cmd "$@"
    r=$?
    echo
    if [ $r = 0 ]; then echo "BUILD_RESULT 성공 (rc=0)"; else echo "BUILD_RESULT 실패 (rc=$r)"; fi
    exit $r
} 2>&1 | log_pump
rc=${PIPESTATUS[0]}
[ -n "${BUILD_QUIET:-}" ] || echo "log: $(winpath "$LOG")"
exit $rc
