#!/usr/bin/env bash
# v020 이전 폴더 구조 → v021 구조 (src/ · scripts/ · docs/) 로 옮기기 — 00__build 에서 한 번 실행
#   bash docs/migrate_to_v021.sh   (MSYS2 UCRT64 터미널, 00__build 에서 · 이미 옮겼으면 아무것도 안 함)
#   그다음 f41 zip 을 00__build 에 덮어쓰기 (바뀐 파일)
set -e
cd "$(dirname "$0")/.." 2>/dev/null || true
[ -f build.sh ] || { echo "00__build 폴더에서 실행하세요"; exit 1; }
mkdir -p src scripts docs
for d in pc android testdata; do
    if [ -d "$d" ] && [ ! -e "src/$d" ]; then mv "$d" "src/$d" && echo "옮김: $d → src/$d"; fi
done
[ -f build_all.ps1 ] && [ ! -e scripts/build_all.ps1 ] && mv build_all.ps1 scripts/ && echo "옮김: build_all.ps1 → scripts/"
for f in DELETED_FILES_*.txt; do [ -f "$f" ] && mv "$f" docs/ && echo "옮김: $f → docs/"; done
echo "완료 — 이제 f41 zip 을 덮어쓰고 build_all.cmd (산출물은 그대로 dist/)"
