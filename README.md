# yMp3Player — Winamp 컨셉 음악 플레이어 + 싱크 가사 (PC / Android)

## 1. 버전 (단일 소스: `src/pc/yamp/version.py`)

형식 `v<type><major>.<minor>.<patch>.<build3><upgrade>` — 예) `vt0.0.0.001`, `vr0.1.2.345+`

| 자리 | 뜻 |
|---|---|
| v | version |
| type | r = release, d = debug, p = patch, t = test |
| major . minor . patch | 0 . 1 . 2 |
| build (3자리) | 345 — minor / 버그 패치 업데이트 |
| upgrade | 없음 / `+` / `++` — 업그레이드 표시 버전 |

```bash
./build.sh ver                 # vr0.1.0.003
./build.sh bump                # build +1   (bump patch / minor / major)
python src/pc/yamp/version.py --type t | --upgrade + | --set vr0.1.2.345+
```
Android(`build.gradle.kts`)도 같은 파일을 읽어 versionName / versionCode 를 만듭니다.
실행 화면 메뉴바 오른쪽: `vr0.1.0.003__2026-11-02 21:50` (버전__빌드날짜 시간, 소스 실행은 `__dev`).

## 2. 빌드 (Windows, MSYS2 UCRT64)

| 명령 | 결과 |
|---|---|
| `build_all.cmd` (더블클릭) | = `build.sh all` |
| `./build.sh help` | 도움말 |
| `./build.sh deps` | MSYS2 패키지 설치 + JDK/SDK 확인 (최초 1회) |
| `./build.sh exe` | `dist/yMp3Player_<ver>/yMp3Player_<ver>.exe` (+ config.txt, log/, README_run.txt) + `dist/yMp3Player_<ver>_win64.zip` |
| `./build.sh exe onefile` | `dist/yMp3Player_<ver>.exe` 파일 하나 |
| `./build.sh apk` | `dist/yMp3Player_<ver>.apk`  (`apk debug` → `_debug.apk`) |
| `./build.sh all` | clean + exe + apk + `dist/yMp3Player_<ver>_release.zip` |
| `./build.sh clean` | 빌드 중간물 + 현재 버전 산출물 삭제 (`clean dist` = dist 전체) |
| `./build.sh test` | PC pytest + Android 단위 테스트 |
| `./build.sh doctor` | Qt 환경 점검 — PyQt6 · QtMultimedia 를 불러 보고, 실패하면 **빠진 DLL 이름 · 설치된 패키지 버전 · 고치는 명령** (vr0.1.0.019 f38, exe · test 전에 자동으로도 실행) |

### 빌드 로그 (vr0.1.0.005~)
- `build_all.cmd` 를 실행하면 창 맨 위에 **로그 파일 경로**가 먼저 나오고, 진행 내용이 실시간으로 표시됩니다
  (bash 는 로그 파일에만 쓰고 `scripts/build_all.ps1` 이 그 파일을 읽어 보여 줌 — MSYS2 출력이 창에 안 보이던 문제 대응)
- 로그: `dist\build_<명령>_<날짜_시각>.log` — 최근 30개 유지
  - 각 줄 앞에 `[시:분:초]`
  - 맨 앞 **환경 정보**: 폴더·버전·python·PyInstaller·JDK·SDK·디스크 남은 공간
  - 30초 동안 출력이 없으면 `… 진행 중: 단계 (경과)` 줄 → 멈춘 것인지 구분 (Gradle 첫 빌드는 몇 분 걸림)
  - 끝에 `BUILD_RESULT 성공/실패 (rc=…)` 와 **단계별 소요 시간** 표
- 오류가 나면 이 로그 파일 하나만 보내 주세요
- **`DLL load failed while importing QtMultimedia`** 로 PC 테스트가 멈추면 소스가 아니라 MSYS2 패키지 문제입니다 (일부만 업데이트된 상태):
  UCRT64 터미널에서 `pacman -Syu` (창이 닫히면 다시 열고 한 번 더) → `pacman -S --needed mingw-w64-ucrt-x86_64-python-pyqt6 mingw-w64-ucrt-x86_64-qt6-multimedia` → `./build.sh doctor` 가 OK 면 다시 빌드
- 예전처럼 bash 출력을 직접 보려면: `set BUILD_VIEW=direct` 후 `build_all.cmd`, 또는 UCRT64 터미널에서 `./build.sh all`

## 3. 설정 `config.txt`

- PC: exe 와 같은 폴더 (소스 실행은 `src/pc/config.txt`). Android: `내장 저장소/Android/data/com.ascen.yamp/files/config.txt`
- 형식 `key = value`, `#` 주석. **시작할 때 읽어서 적용** — 고친 뒤 다시 실행
- 메뉴(설정 화면)에서 바꾼 값은 주석·순서를 그대로 두고 그 줄만 갱신
- 잘못된 값 / 모르는 키는 기본값을 쓰고 로그에 경고
- 주요 항목 (v004 추가: `audio_backend`, `replaygain`, `preamp_db`, `crossfade_s`, `sleep_fade_s`, `eq_enabled`, `eq_bands`, `lyric_show_pron/trans`, `mini_font_pt`, `mini_click_through`, `library_folders`, `history_enabled`, `close_to_tray`): `log_level`, `log_dir`, `log_max_size_kb`, `log_max_files`, `data_dir`, `start_folder`, `resume_on_start`, `repeat`, `shuffle`, `theme`, `always_on_top`, `spectrum`, `lyrics_font_pt`, `lyrics_local/embedded/alsong/lrclib`, `lyrics_timeout_s`, `lyrics_offset_ms`, `alsong_enc_data`
- 창 위치·볼륨·마지막 곡 같은 실행 상태는 `data/state.json` (PC)

## 4. 로그

- 파일: `log/NN__YYYY__MMDD.txt` — 예) `log/00__2026__0716.txt` (NN = 순환 번호, 날짜 = 그 파일을 연 날)
- `log_max_size_kb` 를 넘거나 날짜가 바뀌면 다음 번호 파일로 → `log_max_files`(기본 8개: 00~07) 넘으면 가장 오래된 파일을 지우고 재사용
- 재시작 시 오늘 날짜 파일에 여유가 있으면 이어서 기록
- 각 줄: `2026-07-16 21:50:01.123 [INFO ] yamp.ctrl: play 3 ...`, 시작 줄에 버전__빌드시각·config/data/log 경로
- 파일 쓰기는 백그라운드 스레드 (재생·UI 끊김 없음), 경고 이상은 즉시 기록, 예외로 종료되면 원인도 기록
- PC 메뉴: 파일 → config.txt 열기 / 로그 폴더 열기. Android: 설정 탭 아래에 경로 표시

## 5. 소스 실행 · 진단

```bash
./build.sh run                          # = cd src/pc && python main.py
cd src/pc && python main.py --alsong-test "곡.mp3"
cd src/pc && python main.py --lrclib-test "아이유" "좋은 날"
```

## 6. 기능 요약

| 기능 | PC | Android |
|---|---|---|
| 재생·시크·볼륨·반복(끔/전체/1곡)·셔플 | ○ | ○ |
| 플레이리스트: 드래그&드롭, 폴더, M3U, 검색 | ○ | 음악 스캔·파일 추가·검색 |
| LCD 시간, 흐르는 제목, 앨범아트, 19밴드 스펙트럼 | ○ | ○ (스펙트럼: 마이크 권한) |
| 싱크 가사 (강조·자동 스크롤·줄 이동·±0.5초) | ○ | ○ |
| 가사: 캐시 → .lrc → 태그 내장(PC) → **알송 · LRCLIB (· NetEase) 동시 조회 → 점수 최고** (v011) | ○ | ○ |
| **가사 진단** (못 찾는 이유 단계별 기록) · 못 찾은 이유 표시 · 못 찾은 곡 7일 기억 (v011) | ○ | ○ |
| **가사 편집기** (재생하며 F9/버튼으로 싱크 찍기) | ○ (.lrc 저장 선택) | ○ (앱 캐시에 저장) |
| **다른 가사 찾기** (알송·LRCLIB·NetEase 후보, 점수순) | ○ | ○ |
| **3단 가사** 발음·번역 줄 켜기/끄기 | ○ | ○ |
| **플로팅 가사** | 미니 가사창 + 잠금(클릭 통과)·글자 크기 | 다른 앱 위 오버레이 + 잠금 |
| **추천 홈**: 오늘의 믹스·자주 듣는 곡·다시 발견·최근 추가·상황 믹스 | ○ (추천 탭) | ○ (첫 탭) |
| **비슷한 곡 라디오**, 좋아요 ♥, 별점 | ○ | ○ |
| 상황 태그 직접 지정 (공부·운동·드라이브·수면) | ○ (우클릭 메뉴) | — (장르로 자동 분류) |
| **재생 대기열** (다음에 재생 / 끝에 추가) | ○ (대기열 탭) | ○ |
| **라이브러리** 가수·앨범·장르·폴더 | ○ | ○ |
| **구간 반복 A-B** · 가사 줄 반복 | ○ | ○ |
| **재생 속도** 0.5~2.0 / **음정** ±6 | 속도 ○ / 음정 mpv 엔진 | ○ / ○ |
| **슬립 타이머** (분 / 곡 끝날 때, 끝에 볼륨 줄임) | ○ | ○ (앱 닫아도 동작) |
| **음량 맞춤 ReplayGain** (곡/앨범) | ○ | ○ (줄이는 쪽만, ExoPlayer 한계 / mp3 ID3·FLAC 태그만) |
| **곡 전환 페이드** (끝 줄이고 시작 올림, 겹침 아님) | ○ | ○ |
| **사운드 탭** (v006): 프리앰프+10밴드 EQ·응답 곡선·프리셋·베이스/트레블/밸런스 노브·컴프레서·리미터 | ○ (mpv 엔진에서 소리 적용) | ○ (앱 자체 처리, 모든 기기 같은 소리) |
| **폴더 재생** (v006): 폴더 탭·이 폴더 재생·하위 포함·셔플·정렬·고정·마지막 폴더·변경 감지 | ○ | ○ (폴더 추가 = 저장소 접근 허용) |
| **여러 음원 형식** (v006, v010 확장): FLAC·WAV·AIFF·ALAC·APE·WV·DSD·OPUS… + **CUE 시트** · 녹음(AMR·3GP·QCP·GSM…) · 오디오북 M4B · 영화 음성(AC3·E-AC3·DTS·TrueHD) · 트래커 | ○ (FFmpeg, 형식 표 `src/testdata/formats.txt`) | 기기 기본 형식 (+ AMR·3GP·M4B·WEBM…) + CUE |
| **재생목록 파일** (v010): M3U·M3U8·**PLS·XSPF·WPL** 읽기 | ○ | ○ |
| **녹음·강의 듣기** (v010): 무음 건너뛰기 · 30분 넘는 파일 이어 듣기 · 사운드 프리셋 '음성' | ○ (무음 건너뛰기는 mpv 엔진) | ○ |
| **형식 표시** `FLAC 24bit/96kHz` · Hi-Res | ○ | ○ |
| **파형 시크바** · 블럭 접기/펼치기 (상태 기억) · **테마 8종** (기본 '써니' 흰색·노랑·주황, v011) · 벡터 아이콘 | ○ | ○ |
| 태그 편집 | ○ | — |
| 트레이 / 홈 화면 위젯 | 트레이 ○ | 위젯 4×1 ○ |
| 백그라운드·미디어 키 | 전역 미디어 키 | 알림·잠금화면·블루투스 |

### 추천은 어떻게 만드나
- 모든 데이터는 기기 안 (`data/library.db`) — 외부 서버·AI 없음. 도구 → 재생 기록 끄기/지우기
- 곡 길이 50% 이상(또는 4분) 들으면 "완청", 30초 안에 넘기면 "건너뜀"
- 선호 점수 = 3×좋아요 + 별점 + ln(1+완청) − 1.5×ln(1+건너뜀)
- 비슷한 곡 = 같은 가수·앨범·장르·폴더 + 같이 들은 곡
- PC·Android 가 같은 규칙 (`src/testdata/recommend_cases.txt` 공용 테스트)

### PC 엔진 (config.txt `audio_backend`)
- `qt` (기본): 추가 설치 없음, 스펙트럼 ○, 사운드 효과·음정 ✕ (사운드 탭에 안내, 설정은 저장됨)
- `mpv`: `./build.sh deps mpv` 후 빌드하면 `libmpv-2.dll` 동봉 → 사운드 탭 전체(EQ·톤·밸런스·컴프레서·리미터)·음정·갭리스. dll 이 없으면 자동으로 qt 로 실행 (상태줄 안내)

### 사운드 처리 (PC·Android 같은 식, `src/testdata/dsp_cases.txt` 공용 테스트)
프리앰프 → 10밴드 피킹(Q 1.41) → 베이스 로우셸프 100Hz / 트레블 하이셸프 8kHz → 밸런스 → 컴프레서(하드 니) → 리미터(−1 dBFS, 1ms/80ms).
PC 는 같은 값을 mpv `af` 필터(lavfi equalizer/bass/treble/pan/acompressor/alimiter)로, Android 는 앱 안 AudioProcessor 로 처리.

### 블럭 접기/펼치기
카드 제목(▾/▸)을 누르면 접힘. 상태는 config.txt `[state]` 아래 `folds` 에 저장되어 다음 실행에도 유지. 보기 메뉴 → 모든 블럭 펼치기/접기.

### 단순 화면 (vr0.1.0.009 기본)
- 왼쪽 **아이콘 레일**(지금 재생 · 목록 · 라이브러리 · 폴더 · 추천 · 사운드 / 도움말 · 설정), 아래 **고정 재생 막대**, 오른쪽 **가사 · 대기열 패널**
- 명령 버튼은 **아이콘만** — 마우스를 0.5초 올리면 이름 · 단축키 · 설명 · 현재 상태 팝업 (`config.txt tooltip_delay_ms`)
- **F1** = 모든 버튼 이름표 보기 (처음 실행 때 한 번 자동) · 켜짐은 노란색
- 보기 → 화면 배치 → 클래식(Winamp 모양) 선택 가능 (다시 시작하면 적용, `layout = simple | classic`)
- 추가 기능: **Ctrl+K 빠른 찾기**(곡·폴더·명령) · **Ctrl+M 미니 플레이어** · **Ctrl+Z 되돌리기** · **스마트 재생목록** 7종 ·
  **앨범 격자**(크기 슬라이더) · **재생 목록이 끝나면** 정지/PC 절전/PC 종료 · **알람 재생** (슬립 메뉴)
- Windows 연동: **작업 표시줄 미리보기 버튼 + 진행 표시** · **전역 단축키** (Ctrl+Alt+Space/←/→/↑/↓/P, `hotkeys`) ·
  **강조색 따라가기** (`follow_system_accent`) · **미디어 제어(SMTC)** — winrt 파이썬 패키지가 있을 때만 (MSYS2 기본 빌드에는 없음)
- 단축키 바뀜: 가사 편집기 **Ctrl+Shift+K** (Ctrl+K 는 빠른 찾기), 화면 이동 Ctrl+1~6, 가사 패널 Ctrl+Shift+L, 대기열 패널 Ctrl+J

### 화면 최대 해상도 반영 — 글자 · 틀 · 아이콘 (vr0.1.0.033, f61 — 10pt 화면은 이전과 픽셀까지 같음)
- **글자 크기 자동**이 화면의 실제 밀도도 봄: 4K 를 100 % 로 쓰면 27" ≈ **14pt** · 24" ≈ **15pt** · 5K ≈ **16pt** (전: 높이만 봐서 13pt 가 끝) —
  보통 모니터 · 권장 배율(4K 150 % 등)은 전과 같음 · `config.txt font_auto_dpi = 0` = 예전처럼 화면 높이만
- **글자 크기 단계 9 ~ 16pt** (보기 → 글자 크기, Ctrl+= / Ctrl+-) — 15 · 16pt 추가
- 큰 글자에서 **메뉴 막대 글자**도 함께 커짐 (전: 16pt 를 골라도 메뉴 막대만 9pt)
- **틀도 글자를 따라감**: 카드 안 여백 · 줄 간격 · 최소 크기 · 대화상자 크기 · 메뉴 아이콘 · 체크 표시 · 슬라이더 두께(볼륨 손잡이 잘림 수정) · EQ 손잡이
- 직접 그리는 글자 칸: 비주얼라이저 '레벨' 의 지금 dB(큰 글자에서 '-12 dB' 가 '2 dB' 로 잘리던 것) · 눈금 · 노브 · EQ 글자 줄 높이를 글꼴로 잼
- **앱 아이콘** (Android 런처와 같은 모양): 제목 줄 · 작업 표시줄 · 트레이 · exe 파일 — 크기 · 배율마다 벡터로 또렷 (`build.sh exe` 가 16~256px `.ico` 를 만들어 넣음)
- 테마 메뉴 색 견본 · 켜기 표시도 벡터 (큰 글자 · 300 % 에서 흐리지 않음)

### 성능 병목 2차 (vr0.1.0.032, f60 — 그림 · 소리 · 목록 결과는 이전과 같음)
- **PC 비주얼라이저**: 기본 모드 '레벨' 은 dB 를 값이 들어올 때 한 번만 계산 (프레임마다 600번 → 2번, 프레임 약 25 % ↓) ·
  LED 막대는 칸 740개를 하나씩 칠하던 것 → 색 묶음 3번 (`drawRects`, 프레임 약 2배 빠름, 픽셀까지 같음 확인) ·
  밴드 계산 계획 캐시 · 그리지 않을 오디오 버퍼는 변환을 미룸
- **PC 목록**: 곡 이름 표시 · 검색 · 폴더 정렬에서 `Path` 객체를 만들지 않음 (2만 곡 이름 68 → 8 ms · 검색 58 → 14 ms · 정렬 72 → 18 ms) ·
  여러 곡 빼기 한 번에 (2만 곡 중 5천 곡 7 → 1.8 ms)
- **PC 라이브러리 스캔**은 따로 작업 줄 → 첫 스캔(수천 곡 태그 읽기) 동안에도 추천 홈 · 하루 정리가 기다리지 않음 · 종료하면 곡 사이에서 멈춤 (DB 닫힌 뒤 쓰기 방지)
- **Android**: 사운드 처리 버퍼를 배열로 한 번에 읽고 씀 · 컴프레서는 문턱 아래면 log10 · pow 건너뜀 (JVM 측정 약 2.5~3배, 결과 비트까지 같음 — `DspTest`) ·
  90/120 Hz 화면에서 스펙트럼 그리기 약 60fps 상한 · 스펙트럼 크기 계산 `hypot` → `sqrt` (같은 값)
- 테스트: `src/pc/tests/test_v032_perf.py` (전 구현과 그림 · 값 · 목록 비교) · Android `DspTest.compressorFastPathBitIdentical`

### 기능별 모듈화 · 리팩토링 2차 (vr0.1.0.030)
- **PC** 긴 함수 나누기 (동작 · 화면 · 단축키는 같음, 메뉴 363줄 · 스타일시트 18테마×2글자크기 결과를 이전과 비교해 같음 확인):
  메뉴 233줄 → 메뉴마다 함수 (`win_menus._menu_*` + 반복되던 켜기/끄기 · 하나 고르기 → `_check` · `_radio`) ·
  제목 줄 · 메뉴 막대 접기 · Alt → `win_menubar.py` · 스타일시트 133줄 → `ui/skin_css.py` 묶음 7개 ·
  단순 배치 → `_build_pages/_rail/_side` · 사운드 화면 → `_build_eq/_tone/_dyn` · 가사 찾기 93줄 → 단계별 함수
- **Android** 설정 화면 149줄 → 카드마다 함수 (`ui/SettingsCards.kt`, 줄 모양 `SettingToggle` · `SettingStepper`)
- **iOS** 기능별 폴더 `App/Player · Library · Visualizer · Settings · Theme` · 재생 엔진 → 재생 / 스펙트럼 계산(`SpectrumTap`) / 잠금화면(`PlayerEngine+System`)
- 구조 규칙 테스트 추가: 함수 하나 80줄 미만 (PC, 아이콘 모양 표 제외) · iOS 파일마다 타입 1번 정의 · 괄호 짝
- v031 재검: `skin_css` 를 먼저 import 하면 순환 import 오류 → 고침 (모든 PC 모듈 단독 import 확인) · Android 설정 카드가 Kotlin 2.0 강한 건너뛰기에서도 값이 바로 바뀌게 카드 안에서 다시 그리기

### iPhone(iOS) 앱 · ipa 빌드 환경 (vr0.1.0.028)
- `src/ios/` — Swift(SwiftUI) iOS 16+ 앱 1단계: 곡 목록(파일 앱에서 가져오기) · 재생(AVAudioEngine, 백그라운드 · 잠금화면) · 비주얼라이저 5모드 · 테마 18개
- 계산(`YampCore`: 스펙트럼 밴드 · 움직임 · 색) 과 테마 표는 PC · Android 와 같은 값 (`testdata/` 공용 값 · `tools/gen_ios.py` 가 생성)
- **`build_all.cmd ios`** → 내 GitHub 저장소에 올림 → GitHub Actions(macOS) 빌드 → `dist/yMp3Player_<ver>_ios_unsigned.ipa` → **Sideloadly + 무료 Apple ID** 로 설치 (7일마다 다시)
- 처음 준비 (GitHub 저장소 · `gh auth login` · `ios.cfg` · iTunes/Sideloadly · 개발자 모드): **`docs/ios_setup.md`**
- v029: 저장소 `young2608/2024_work` 의 **전용 브랜치 `ymp3player`** 에 올리면 자동 빌드 (main · 다른 내용은 그대로) · 빌드 시각은 exe · apk 와 같은 값

### 비주얼라이저 표현 방식 추가 (vr0.1.0.027, PC + Android — 다른 앱 조사 반영)
- 모드 5개: **스펙트럼 · 웨이브 · 원형**(Avee · foobar2000 Radial) **· 스펙트로그램**(foobar2000) **· 레벨**
- 스펙트럼 **막대 모양 4가지**: 둥근(기본) · **LED**(Winamp · foobar2000 LED Bars) · **미러**(가운데 = 낮은 소리) · **반사**(바닥 반사) — 스펙트럼 아이콘을 **한 번 더 누르면** 바뀜 (기억)
- 색은 모두 테마 색 · PC 와 Android 같은 계산 (`testdata/vis_cases.txt`)

### 비주얼라이저 재구성 (vr0.1.0.026, PC + Android)
- 이름: "소리 시각화" → **비주얼라이저**, 모드 = **스펙트럼 · 웨이브 · 레벨** (스펙트럼 먼저, config `vis_mode` 값은 그대로)
- **움직임**: 들어온 값을 그대로 그리던 막대 → 오를 때 50 ms · 내릴 때 350 ms 부드러운 곡선 + 꼭대기 0.5초 머문 뒤 중력 낙하 (Winamp · foobar2000 · Poweramp 방식) — 시험 신호에서 프레임마다 흔들림 약 1/4
- **웨이브**: 사인파 모양 오실로스코프 → 스펙트럼을 가운데 선 위아래로 펼친 부드러운 곡선 (스펙트럼이 없으면 지금 위치 앞뒤 3초 파형)
- **밴드**: 19 → 24 (50 Hz ~ 16 kHz) · 낮은 밴드 3~4개가 똑같은 높이로 붙어 보이던 것 → 보간으로 서로 다르게 · 높은 소리 +3 dB/옥타브 보정으로 고르게
- 앨범아트 위 스펙트럼 · LCD 옆 작은 스펙트럼도 같은 움직임 · PC 와 Android 같은 계산 (`testdata/vis_cases.txt` 로 확인)

### 추천 모음 (vr0.1.0.025)
- **단축키**: 글자 크게 / 작게 / 자동 = **Ctrl+= / Ctrl+- / Ctrl+0** · 테마 한 단계 밝게 / 어둡게 = **Ctrl+Shift+PgUp / PgDown** (라이트 ↔ 다크 10단계, 다른 테마에서 누르면 라이트 또는 다크부터) — 바꾸면 알림 표시
- **검색칸 돋보기 · 지우기(×)**: 아래로 처지고 작던 것 → 칸 가운데 · 18px (버튼 스타일이 입력칸 안 버튼에도 걸려 칸보다 커졌던 것)
- **가사 글자도 글자 배율을 따라감** (자동 글자 · 13 · 14pt 에서 가사도 같이 커짐, 10pt = 그대로) · 상단 시세 칸 모서리 · 여백도 배율

### 라이트 · 다크 5단계 테마 (vr0.1.0.024)
- 보기 → 테마 (Android: 설정 → 화면 → 테마)에 두 묶음 추가 — 기존 8 테마는 그대로, 모두 18개
  - **라이트 · 라이트+ · 라이트++ · 라이트+++ · 라이트++++** (`light1`~`light5`): `+` 마다 바탕이 한 단계 덜 눈부시게 (흰색 → 연한 회색), 글자는 더 진하게
  - **다크 · 다크+ · 다크++ · 다크+++ · 다크++++** (`dark1`~`dark5`): `+` 마다 한 단계 더 어둡게 (진한 회색 → **완전 검정, OLED**), 글자는 더 밝게
  - 강조색 = 인디고(남보라) 하나로 통일 · 본문 글자 대비 7:1 이상 (WCAG AAA) · 모든 대비 규칙 통과
- **어두운 모드 따라가기**: 라이트 n단계 ↔ 다크 n단계 짝 (라이트++ → 다크++)
- `config.txt`: `theme = light3` · `theme = dark5` 처럼 직접 써도 됨 · 표지 없는 칸(♪ · 첫 글자)도 테마를 바꾸면 바로 새 색으로

### 고해상도 · 큰 화면 틀/글자 정리 (vr0.1.0.023)
- **글자 크기 자동** (`config.txt` `font_auto = 1`, 보기 → 글자 크기 → 자동): 화면 크기에 맞춰 1080p = 10pt · 1440p = 11 · 4K(배율 100 %) = 13pt — 다른 크기 모니터로 옮기면 다시 맞춤
- **글자 크기 단계** 9 · 10 · 11 · 12 · **13 · 14pt** (v033: 15 · 16pt 까지) — 고르면 자동은 꺼짐
- **틀이 글자를 따라감**: 왼쪽 레일 · 재생 막대 · 표지 · 아이콘 · 버튼 둥근 모서리 · 간격 · 미니 플레이어가 글자 크기와 같은 비율로 (10pt = 이전과 픽셀까지 같음, 1 · 2px 선은 그대로 선명)
- **아주 넓은 창**: 지금 재생 카드는 최대 폭에서 가운데 정렬 · 오른쪽 가사 패널 최대 폭 제한 · 처음 창 크기는 큰 화면이면 화면의 60 %
- 곡이 없을 때 표지 자리에 **♪** (빈 칸 대신) · 글자를 키워 버튼 줄이 넘치면 창을 그만큼 넓힘 · 저장된 위치가 없는 모니터면 주 화면으로

### 남은 추천 모아서 진행 (vr0.1.0.022)
- **곡 넘길 때 표지 디코드를 백그라운드로**: 큰 앨범아트(3000px JPEG)에서 화면 멈춤 111ms → 0.5ms · 빨리 넘긴 곡의 늦은 표지는 버림 · 미니 플레이어도 같은 그림을 받아 씀
- **자동 가사 캐시 정리**: `config.txt` `lyrics_cache_max = 5000` (0 = 제한 없음) — 넘으면 하루 한 번 오래 안 쓴 것부터, **직접 편집한 가사는 지우지 않음**
- 재생 목록 검색: 2000곡 넘는 목록은 입력이 멈춘 뒤 한 번 거름 (작은 목록은 전처럼 바로) · 앨범 격자 스크롤 때 보이는 칸만 찾음 · Qt 엔진 스펙트럼은 버퍼 끝 1024 프레임만 변환
- 구조: 테마 색 표 → `ui/themes.py` (색 값 #rrggbb 는 이 파일에만) · 시세 · 앨범 표지 작업도 공통 백그라운드(`core/bg.py`)

### 장시간 사용 3차 점검 (vr0.1.0.020)
- 화면 동작 30바퀴 반복 점검(대화상자 · 메뉴 · 미니 창 · 테마 · 글자 크기 · 탭 · 검색 · 격자 …): Qt 객체 · 창 수 그대로 확인
- **미니 플레이어**를 열고 닫을 때마다 창이 남던 것(파이썬 GC 가 돌 때 임의 시점에 지워짐) → 닫으면 바로 정리
- **앨범 격자 메모리**: 표지 없는 칸 그림을 픽스맵으로 들고 있지 않고 그릴 때만 그림 (앨범 2000개 · 220px · 200 % 측정: 메모리 +396MB → +16MB, 그림은 같음) · 표지 캐시는 개수(300)와 **크기(48MB)** 로 제한, 밀려난 칸은 자리 그림으로
- **가사 캐시**: 가사를 찾을 때마다 캐시 폴더 전체를 훑던 것 제거 (캐시 1만 개: 저장 50번 352ms → 2ms) — 오래 쓸수록 느려지던 원인
- **라이브러리 탭**: 탭을 떠나면 목록 캐시를 놓음 · **DB**: 실행 중에도 **하루 한 번** 정리(재생 기록 · 파형 캐시 · 빈 공간 · WAL 비우기), WAL 파일 4MB 상한
- 종료 처리 두 번 불려도 안전 · `tools/soak.py` 기록에 최상위 창 수 · 파이썬 객체 수 추가

### 기능별 모듈화 · 리팩토링 (vr0.1.0.019)
- 큰 파일을 기능별로 나눔 (화면 · 동작은 같음, 이전 import 경로도 그대로 동작):
  재생목록 → `track` · `scan` · `playlist_io` / 가사 서비스 → `cache` · `resolve` / 설정 → `config_schema` /
  네온 위젯 → `section` · `wave_seek` · `neon_base` / 라이브러리 탭 → `home_view` · `queue_view` · `track_menu` /
  상단 바 → `ticker_service` / 대화상자 → `lyrics_dialogs` / 아이콘 → `icon_paths`
- 곡 키(경로 → 12자리)는 `core/keys.py` 한 곳 (데이터 층이 가사 모듈을 부르던 의존 제거)
- 시각화 계산(dB · 파일 파형 구간 · 파동 자동 키움)은 `domain/vis_math.py` 한 곳 (Android VisMath.kt 와 같은 역할, 두 벌이던 `to_db` 통합)
- 백그라운드 작업 공통 `core/bg.py` (가사 진단 · 다른 가사 찾기 · 일반 작업) — 창을 닫는 중 검색이 끝나도 안전
- CUE 트랙 태그 맞춤을 `data/cue.merge_track_info` 로 · 스마트 재생목록 메뉴는 통계를 1번만 읽음 (전에는 8번)
- 구조 규칙 테스트: core · domain · data 는 화면/앱 모듈을 부르지 않음 · 계산/데이터 모듈은 Qt 없이 · 모든 파일 450줄 미만

### 성능 최적화 (vr0.1.0.018)
- **라이브러리 탭**: 검색은 입력이 멈추면(0.25초) 한 번만 · DB 목록은 캐시 · 탭이 안 보일 때 바뀌면 열 때 한 번 다시 만듦 (2만 곡: 글자마다 약 0.3초 멈춤 → 없음)
- **라이브러리 재스캔**(시작할 때마다): 곡마다 DB 조회 → 키 목록 한 번 읽어 비교 · 없어진 곡은 한 번에 정리
- **DB(SQLite) WAL 모드** (PC · Android): 재생 기록 · 좋아요 저장이 디스크 동기화를 덜 기다림 (`library.db-wal` · `-shm` 파일이 함께 생김 — 정상)
- **폴더 탭**: 폴더를 고르고 재생할 때 폴더를 3~4번 돌던 것 → 1번
- 곡 파형 만들기 · 재생 막대 파형 그리기 · 스펙트럼 계산 · 가사 줄 이동 · 앨범 표지 표시 계산 줄임 (화면 모양은 같음)

### 곡 파형 · 소리 파동 크게 + 더 선명 (vr0.1.0.017)
- **재생 막대 곡 파형** 24 → **44px** (`config.txt` `wave_height = 24~80`) · 막대를 실제 화면 픽셀에 맞춰 그려 가장자리 번짐 없음 · 위아래 대칭 · 작은 소리도 보이게 살짝 키움
- **소리 시각화 → 파동**: 자동 키움(최대 8배, 블럭 높이의 약 85 %) · 곡선 아래 옅은 면 · 굵은 선 · 블럭 기본 높이 키움 (시각화 : 다음 곡 = 2 : 1, 최소 180px)
- **아이콘 선을 실제 픽셀에 맞춤**: 125 · 150 % 에서 선이 두 줄로 번지던 것 → 선 굵기 정수 px · 직선 끝점 픽셀 경계
- **글자**: 힌팅 auto = 200 % 미만 모두 full (125 · 150 % 도 획을 픽셀에 맞춤) · 영문 글꼴 Segoe UI(힌팅 정보가 많은 고정 글꼴) 먼저
- `ui_scale_rounding = passthrough | round | floor` (floor = 125 · 150 % 를 100 % 로 그려 가장 선명, 대신 작아짐 → 글자 크기 키워 함께)

### 선명한 화면 · 글자 (vr0.1.0.016)
- **카드 그림자 효과 삭제** (v014): 그림자 효과가 카드 안 글자를 그림으로 한 번 더 그려 흐리게 하고 ClearType 을 끄던 문제 → 테두리 + 아래 진한 선으로 대신
- **글자 선명**: 힌팅 자동 (100 % = 획을 픽셀에 맞춤 · 125/150 % = 세로만 · 200 % 이상 = 없음) · 글꼴 Segoe UI(영문) + 맑은 고딕(한글) — 목록이 영문까지 맑은 고딕으로 그리던 것 수정
- **글자 크기 5단계** (큰 제목 1.7 · 제목 1.3 · 본문 1 · 보조 0.9 · 눈금 0.8 × 기준) · 보기 → **글자 크기** 9 / 10 / 11 / 12pt (바로 적용)
- **그림 고해상도**: 표지 · 하단 표지 · 미니 플레이어 · 앨범 격자 · 첫 글자 칸을 화면 배율 픽셀로 · 다른 배율 모니터로 옮기면 다시 그림
- 1px 선 픽셀 정렬 (EQ · 파형 가운데 선 · 재생 위치선) · 긴 제목은 `…` (마우스를 올리면 전체) · 목록 줄 높이 · 메뉴 · 키보드 초점 · 스크롤바 다듬기
- `config.txt`: `font_size = 10` · `font_hinting = auto|full|vertical|none` · `font_engine = auto|directwrite|gdi|freetype` (Windows, 글자가 흐릴 때 비교용)
- 도움말 → **화면 정보**: 배율 · 글꼴 · 힌팅 · Qt 버전 확인

### 블럭 크기 조절 · 접기/펼치기 · 도움말 겹침 수정 (vr0.1.0.015)
- 지금 재생의 **곡 정보 · 소리 시각화 · 다음 곡** 블럭: 카드 사이 경계를 **끌어서 높이 조절** (마우스를 올리면 손잡이 강조) · **경계 더블클릭 = 기본 크기**
- 블럭 **제목을 누르면 접기/펼치기** — 접으면 제목 줄만 남고 남는 높이는 다른 블럭으로, 펼치면 접기 전 높이로 · 곡 정보를 접으면 제목 줄에 곡 이름
- 크기 · 접힘은 다음 실행 때 그대로 (`state.json` `now_split` · `folds`) · 보기 → **지금 재생 블럭 기본 크기 (모두 펼침)**
- 가운데 ↔ 오른쪽(가사 · 대기열) 패널 경계도 마우스를 올리면 강조 (끌어서 폭 조절, 기존 기능)
- **F1 도움말 이름표 겹침 수정**: 이름표끼리 · 다른 버튼 · 안내 문구와 겹치지 않게 자리를 고름 (왼쪽 세로 메뉴는 오른쪽에), 안내 문구는 위쪽 가운데 상자

### 화면 정리 · 소리 시각화 · 선명한 화면 (vr0.1.0.014)
- **PC 제목 표시줄** = `[곡 - ] yMp3Player 버전__빌드시각  │  XRP ₩3,512 ▲1.24%  │  12:40 KST` (버전 표시는 이곳 한 곳, 메뉴 막대 오른쪽 상단 바 삭제)
  — 시세 상세: 보기 → 상단 바 → 시세 상세 보기… (제목 표시줄은 Windows 가 그려 색 없음 → ▲ ▼ 로 구분)
- **메뉴 막대 접기/펼치기**: 왼쪽 맨 위 ☰ · **Ctrl+Shift+M** · `menu_bar = 1|0` — 접어도 **Alt** 를 누르면 잠깐 보임, 단축키는 그대로
- **소리 시각화 블럭** (지금 재생, 접기 가능): 파동(오실로스코프) · 주파수 막대(최고 표시) · **소리 크기 그래프**(최근 10초 RMS 면 + 피크 선 + dB 눈금, 0 dB 가까우면 빨강)
  — mpv 엔진 · 스펙트럼 끔이면 "파일 파형 기준"으로 대신 · 보일 때 · 재생 중일 때만 30fps · `vis_mode`(state.json)
- **지금 재생 배치** (Spotify Now Playing · MusicBee/foobar 패널 참고): 정보 카드(큰 제목 · 아티스트·앨범 · 형식 · LCD) → 시각화 → **다음 곡 5곡**(대기열 먼저, 더블클릭 재생) · 빈 상태 안내 [파일 열기] [폴더 열기]
- 왼쪽 줄 그룹 구분선 [재생] [찾기] [소리] · 재생 막대 그룹 구분선 [패널] [재생 도구] [볼륨] [창]
- **HiDPI 선명**: 아이콘을 화면 배율(125 · 150 · 200 %)에서 바로 벡터로 그림 · 기본 글꼴(맑은 고딕/Segoe UI, 안티앨리어싱) · 1px 선 반 픽셀 정렬 · 밝은 테마 카드 옅은 그림자 · 첫 창 크기 화면에 맞춤
- Android: 재생 화면에 **소리 시각화** 카드 (같은 3가지 모드, 파형 데이터 · 레벨 차트)

### Android 비정상 종료 보고서 · 로그 보내기 (vr0.1.0.013)
- 앱이 종료되면 보고서(`files/crash/crash_*.txt`: 버전 · 기기 · 오류 전체 · 최근 앱 로그 · logcat) 저장 → 오류 화면 [로그 보내기] [복사] [다시 시작] [안전 모드로 시작]
- 시작하자마자 2번 연속 종료 → 안전 모드 권함 (테마 기본 · 시세/플로팅 가사/스펙트럼 끔 · 재생 목록 백업 `playlist.tsv.safe_bak`)
- 평소: 설정 → 정보 → [로그 보내기]
- v011~v012 시작 직후 종료 원인: Android 정규식이 `UNICODE_CHARACTER_CLASS` 플래그를 지원하지 않음 → 가사 검색 첫 사용 때 종료 (수정)

### 상단 바 · 업비트 시세 · KST 시각 (vr0.1.0.012)
- PC 메뉴바 오른쪽 / Android 위쪽 줄: `● XRP ₩3,512 ▲1.24%  │  11-09(월) 18:56:07 KST  │  버전__빌드시각`
- 업비트 공개 시세 API (`https://api.upbit.com/v1/ticker?markets=KRW-XRP`, 키 없음) 를 `ticker_interval_s`(10초)마다 — 상승 빨강 · 하락 파랑 (테마 토큰 rise/fall)
- 실패하면 흐리게 + 3번 연속 30초 / 6번 60초 간격 · 창이 최소화·트레이(Android: 앱이 안 보이면)면 조회·시계 멈춤
- 가격에 마우스(길게 누르기) = 전일 대비 · 고가/저가 · 24시간 거래대금 · 마지막 갱신 · PC 시계 차이 / 클릭 = 업비트 화면
- 설정: `topbar_ticker` · `ticker_market`(쉼표로 여러 개 → 3초마다 번갈아) · `ticker_interval_s` · `topbar_clock` · `topbar_clock_seconds` / 메뉴 보기 → 상단 바
- 진단 (`src/pc` 에서): `python main.py --ticker-test KRW-XRP` · 공용 테스트 `src/testdata/upbit_ticker_cases.txt`

### 가사 찾기 (vr0.1.0.011)
- 순서: 캐시 → (못 찾은 곡 기억 7일) → 음악 옆 .lrc → 태그 내장 → **알송 · LRCLIB · NetEase(선택) 동시 조회** (전체 `lyrics_timeout_s` 6초)
- 검색어 정리: `(feat. …)` `[MV]` `- Remastered` 제거, `아이유 (IU)` 같은 두 이름, 여러 가수 중 첫 가수 — 공용 규칙 `src/testdata/lyrics_query_cases.txt`
- 후보 점수 (제목 45 · 가수 30 · 앨범 10 · 싱크 15 · 길이 ±) `lyrics_min_score`(55) 이상만 자동 적용 — `src/testdata/lyrics_score_cases.txt`
- 알송: GetLyric7(mp3 MD5) · GetResembleLyric2 · GetResembleLyricList2 → GetLyricByID2, encData 내장 값 (`alsong_enc_data`, off = 끔)
- 못 찾으면 이유 표시 (인터넷 / 서버 오류 / 맞는 가사 없음 / 비슷한 것만) · **가사 → 가사 진단…** 보고서 (`log/lyrics_diag_*.txt`, `src/pc` 에서 `python main.py --lyrics-test 곡.mp3`)
- F5 다시 찾기: 지금 가사는 유지, 찾으면 바꿈 (직접 편집한 가사는 `.user.bak` 백업) · 찾은 가사를 음악 옆 .lrc 로 저장 (`lyrics_save_beside`, 기본 꺼짐)

### 테마 (vr0.1.0.011)
- 기본 **써니**: 흰 바탕 · 노랑(#FFC72C)·주황(#FF8A00) 은 채움(선택·재생 버튼·진행)에만, 강조 글자는 진주황(#C2410C)
- 보기 → 테마 (Android 설정 → 화면 → 테마): 써니 · 클린 블루 · 민트 · 체리 · 나이트 써니 · 네온 · 다크 블루 · 클래식 — 바로 적용
- 색은 공용 표 `src/testdata/themes.txt` (토큰 24개) 하나에서 — 글자 대비(WCAG 4.5:1)를 테스트로 검사 (`theme_contrast.txt`)
- `follow_system_dark = 1`: 어두운 모드일 때 써니 → 나이트 써니 (그 밖의 밝은 테마 → 다크 블루)
- 업데이트하면 이전 기본(네온)은 한 번만 써니로 바뀜 (다시 네온 선택 가능)

### 형식 · 녹음 듣기 (vr0.1.0.010)
- 지원 형식은 공용 표 `src/testdata/formats.txt` 한 곳 (PC `yamp/data/formats.py` · Android `data/Formats.kt` 가 테스트로 같은지 확인)
- 파일 열기 창: 모든 형식 / 음악 / 녹음·음성 / 오디오북 / 웹 / 큰 WAV / 고음질 / 영화·방송 / 트래커 / 재생목록 / CUE 로 골라 보기
- 트래커(mod·xm·it·s3m)는 FFmpeg 에 libopenmpt 가 있어야 소리가 남 — 없으면 오류 → 자동으로 다음 곡
- CUE 의 `REM REPLAYGAIN_ALBUM_GAIN/PEAK`(앞부분) · `REM REPLAYGAIN_TRACK_GAIN/PEAK`(트랙 안) 을 음량 맞춤에 사용
- CUE 트랙 가사 파일은 `앨범파일이름.NN.lrc` (예: `album.02.lrc`) — 앨범 전체 .lrc 를 모든 트랙에 쓰던 문제 수정
- 재생 → 녹음·강의 듣기: **무음 건너뛰기** (`skip_silence`, mpv 엔진) · **30분 넘는 파일 이어 듣기** (`resume_long`, 최근 200개, 3초 앞에서) · **음성 또렷하게** (프리셋 '음성')

### 장시간 운용 (vr0.1.0.007)
- 창을 최소화·트레이로 숨기면 LCD·시크바 갱신을 0.5초 간격으로 줄이고 스펙트럼 계산을 멈춤 (소리·미니 가사는 그대로)
- 제목 흐름·스펙트럼 타이머는 필요할 때만 동작, 우클릭 메뉴·대화상자는 닫히면 삭제 (누적 누수 제거)
- 곡 전환 시 목록 전체를 다시 만들지 않음, 가사 캐시는 색인(폴더 전체 검색 없음), 빨리 넘긴 곡의 가사 검색은 건너뜀
- DB: 태그 저장은 200곡마다 한 번 커밋, 재생 기록은 2년·10만 건 넘으면 정리, 파형 캐시는 3000개까지
- 5분마다 설정·세션 자동 저장 (비정상 종료 대비)
- 점검 도구 (`src/pc` 에서): `python tools/soak.py --folder "D:\Music" --minutes 60` → `log/soak_*.csv` · `python tools/leakcheck.py . 30` (화면 동작 반복, v020)
- vr0.1.0.008 (2차): mpv 위치 이벤트를 UI 스레드로 넘기지 않음 · 스펙트럼 꺼짐/창 숨김이면 Qt 버퍼 시그널 끊음 ·
  자동 저장은 바뀐 것만 · 일시정지 깜빡임 10분 후 정지 · 아이콘 캐시 · 파형 디코드 1.5초 지연(빨리 넘기면 생략) ·
  DB 빈 공간 25% 넘으면 VACUUM · soak.py `--ui` (화면 조작 반복) · 파이썬 메모리 증가 상위 10곳 기록 (`soak_*.top.txt`)

## 7. 폴더 구조 (vr0.1.0.021 정리: 진입점 · 소스 · 보조 스크립트 · 문서 · 산출물 분리)
```
00__build/
├─ build_all.cmd            ← 더블클릭 빌드 (= build.sh all) · build_all.cmd doctor | test | exe | apk | ios | clean | help
├─ ios.cfg.example          ← iOS 빌드 설정 견본 (ios.cfg 로 복사 · GitHub 저장소) — v028
├─ .github/workflows/ios.yml   GitHub Actions(macOS) iOS 빌드 → 서명 없는 ipa — v028
├─ build.sh / build_all.sh  ← MSYS2 UCRT64 터미널용 진입점 (경로는 이 폴더 기준)
├─ README.md                ← 이 문서
├─ .gitignore · .gitattributes   산출물 제외 · 줄 끝 고정 (.cmd/.ps1 = CRLF, .sh = LF)
├─ scripts/
│  └─ build_all.ps1         build_all.cmd 가 부르는 로그 실시간 표시 (직접 실행할 일 없음)
├─ docs/                    기록 (DELETED_FILES_*.txt …) · ios_setup.md (아이폰 빌드 · 설치) — 진행 문서(fNN)는 상위 02__patch · 01__doc
├─ src/                     ★ 소스는 모두 여기
│  ├─ pc/                   PC 앱 (PyQt6)
│  │  ├─ main.py · config.txt · requirements.txt(pip 참고용)
│  │  ├─ yamp/version.py    ← 버전 단일 소스 (Android 도 읽음)
│  │  ├─ yamp/core          config(읽기·저장) + config_schema(기본값·범위) · logger · build_info · keys · bg
│  │  ├─ yamp/domain        recommend · dsp · smart · ticker · resume · vis_math   (Qt 없음, Android 와 같은 규칙)
│  │  ├─ yamp/data          library(SQLite) · recorder · playlist + track · scan · playlist_io · tags · cue · formats
│  │  ├─ yamp/audio         engine(Qt) · mpv_engine(libmpv) · visualizer · waveform
│  │  ├─ yamp/lyrics        service(Qt 스레드) + cache · resolve · providers/ · diag · lrc · query · score
│  │  ├─ yamp/ui            위젯 · 화면 조각 (skin+themes(색 표)+skin_css(스타일시트) · metrics(틀 크기) · icons+icon_paths · neon · section · wave_seek · library_views …)
│  │  ├─ yamp/app           controller(+ctl_*) · mainwindow(+win_*: menus · menubar · layout · classic · now · actions · tray · native) · topbar(+ticker_service) · jobs
│  │  ├─ yamp/winplat       Windows 연동 (작업 표시줄 · 전역 단축키 · 테마 · SMTC · 절전/종료)
│  │  ├─ tests/             pytest (test_v0NN_*.py = 버전별 · conftest · gen_testdata)
│  │  └─ tools/             soak(장시간) · leakcheck(화면 동작 누수) · qt_doctor(Qt 환경 점검)
│  ├─ android/              Android 앱 (Gradle: gradlew · settings · app/src/main · app/src/test)
│  │  └─ app/src/main/java/com/ascen/yamp/  core · data · domain · lyrics · playback · app · ui
│  ├─ ios/                  iPhone 앱 (v028): project.yml(XcodeGen) · App/(SwiftUI: Player · Library · Visualizer · Settings · Theme — v030) · YampCore/(계산 · swift test) · tools/gen_ios.py
│  └─ testdata/             PC · Android · iOS 공용 테스트 벡터 (recommend · dsp · cue · formats · themes · lyrics · upbit …)
└─ dist/                    산출물 (빌드가 만듦 · 소스 아님): exe 폴더 · _win64.zip · .apk · _ios_unsigned.ipa · _release.zip · build_*.log
```
- **경로 규칙**: 빌드 스크립트는 00__build 를 기준으로 `src/pc` · `src/android` 를 찾음 · Android 는 `src/android` 의 상위(`src`)에서 `pc/yamp/version.py` 를 읽음 · 양쪽 테스트는 위로 올라가며 `testdata/` 를 찾음
- PyInstaller 중간물은 `src/pc/build/` (빌드 후 `clean` 이 지움), Gradle 중간물은 `src/android/.gradle` · `app/build`

내부 패키지 이름(`yamp`, `com.ascen.yamp`)은 기존 설치·데이터 호환을 위해 그대로 두었습니다.
