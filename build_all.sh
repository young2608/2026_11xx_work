#!/usr/bin/env bash
# 릴리즈 빌드 (규칙 8): clean + exe + apk + 버전별 zip  →  ./build.sh all
#   다른 명령은 ./build.sh help
cd "$(dirname "$0")" && exec ./build.sh "${@:-all}"
