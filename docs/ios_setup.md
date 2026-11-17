# iPhone(iOS) 빌드 · 설치 안내 (vr0.1.0.028~)

Windows 에서는 iOS 앱을 직접 만들 수 없습니다 (Xcode 는 macOS 전용). 그래서
**`build_all.cmd` → 소스를 내 GitHub 저장소에 올림 → GitHub Actions 의 Mac 이 빌드 → 완성된 `.ipa` 를 `dist\` 로 받음** 순서로 만듭니다.
설치는 무료 Apple ID 로 **Sideloadly** 가 서명해서 아이폰에 넣습니다 (무료 계정은 **7일마다 다시 설치**).

```
[Windows PC]                         [GitHub]                          [iPhone]
build_all.cmd ios ──git push──▶ 내 저장소 ──Actions(macOS)──▶ ipa
      ▲                                                        │
      └──────────── gh run download (dist\…_ios_unsigned.ipa) ◀┘
dist\…ipa ──▶ Sideloadly (Apple ID 로 서명) ──USB──▶ 아이폰에 설치 (7일)
```

## 1. 처음 한 번만 준비
### 1.1 GitHub (v029: 이미 쓰는 저장소도 됨)
- 사용 저장소: **`young2608/2024_work`** (ios.cfg 에 설정됨)
- 소스는 **전용 브랜치 `ymp3player`** 에만 올립니다 → 저장소의 `main` 이나 다른 내용은 건드리지 않습니다 (처음 올릴 때 브랜치가 새로 생김)
- 이 브랜치에 올라가면 GitHub Actions 가 **자동으로** iOS 빌드를 시작합니다 (`.github/workflows/ios.yml` 의 push 브랜치)
- **비공개 저장소면** Mac 빌드 시간을 무료 분량의 10배로 차감합니다 (무료 2,000분 → Mac 약 200분, 한 번 5~10분 → 한 달 약 20~40번).
  자주 빌드하려면 공개 저장소를 새로 만들어 `ios.cfg` 의 `GH_REPO` 만 바꾸면 됩니다 (새 저장소는 README 없이).
- 저장소 **Settings → Actions → General** 에서 Actions 가 꺼져 있으면 "Allow all actions" 로 켜기

### 1.2 PC 도구 (MSYS2 UCRT64 터미널에서)
```bash
pacman -S --needed git mingw-w64-ucrt-x86_64-github-cli
gh auth login          # GitHub.com → HTTPS → Login with a web browser → 화면의 코드 입력
```
(GitHub CLI 를 Windows 에 따로 설치해도 됩니다: `winget install GitHub.cli`)

### 1.3 설정 파일
`00__build\ios.cfg` (v029 에 만들어 둠 — 없으면 `ios.cfg.example` 을 복사)
```
GH_REPO=young2608/2024_work
GH_BRANCH=ymp3player
IOS_PUSH=1
IOS_IN_ALL=1
```
`ios.cfg` 는 git 에 올라가지 않습니다. `GH_REPO` 가 비어 있으면 iOS 단계는 건너뛰고 PC · Android 빌드만 합니다.

### 1.4 아이폰 · 설치 도구 (Windows)
1. **iTunes · iCloud 를 Apple 홈페이지 버전으로 설치** (Microsoft Store 버전은 Sideloadly 가 인식하지 못함)
2. **Sideloadly** 설치 (sideloadly.io)
3. 아이폰을 USB 로 연결 → "이 컴퓨터를 신뢰" → iTunes 를 한 번 열어 기기 인식 확인
4. 아이폰 **설정 → 개인정보 보호 및 보안 → 개발자 모드 → 켜기** (iOS 16 이상, 재시작됨)

## 2. 빌드
```
build_all.cmd ios      ← 아이폰만 (약 5~10분, 대부분 GitHub 의 Mac 이 빌드하는 시간)
build_all.cmd          ← PC exe + Android apk + 아이폰 ipa 모두 (ios.cfg 의 IOS_IN_ALL=1 일 때)
```
- 화면 · 로그에 빌드 주소(https://github.com/…/actions/runs/…)가 나옵니다. 웹에서 진행 상황을 볼 수 있습니다.
- 성공하면 `dist\yMp3Player_vr0.1.0.0xx_ios_unsigned.ipa`
- 실패하면 실패한 단계 로그 끝 60줄이 빌드 로그에 나옵니다 (전체 로그는 Actions 화면 → 아티팩트 `ios-build-log`).
- GitHub 웹에서 보기: 저장소 → **Actions → iOS build** → 실행 → 끝나면 아래 **Artifacts → ipa** 내려받기.
  (웹의 "Run workflow" 버튼은 워크플로 파일이 기본 브랜치(main)에도 있을 때만 보입니다 — 평소에는 build_all.cmd ios 로 충분)

## 3. 아이폰에 설치 (무료 Apple ID)
1. Sideloadly 실행 → 아이폰 선택
2. `dist\…_ios_unsigned.ipa` 를 창에 끌어다 놓기
3. **Apple account** 칸에 Apple ID → **Start** → 암호 · 2단계 코드 입력 (Apple 로만 전송)
4. 아이폰 **설정 → 일반 → VPN 및 기기 관리** → 내 Apple ID → **신뢰** (처음 한 번)
5. 홈 화면의 yMp3Player 실행

**7일 제한**: 무료 계정으로 설치한 앱은 7일 뒤 열리지 않습니다 → 같은 ipa 를 Sideloadly 로 다시 Start (곡 · 설정은 그대로 남음).
무료 계정은 이런 방식으로 동시에 3개 앱까지입니다.

## 4. 앱 사용 (iOS 1단계)
| 화면 | 할 수 있는 것 |
|---|---|
| 곡 목록 | **+** 로 파일 앱에서 음악 가져오기 (앱 폴더로 복사) · 당겨서 새로 고침 · 밀어서 삭제 · 위 왼쪽 = 버전__빌드 시각 |
| 아래 미니 플레이어 | 재생/일시정지 · 다음 · 누르면 지금 재생 |
| 지금 재생 | 표지 · 위치 막대 · 이전/재생/다음 · 섞기 · 반복 · **비주얼라이저 5모드** (스펙트럼은 다시 누르면 막대 모양: 둥근 · LED · 미러 · 반사) |
| 설정 (톱니) | 테마 18개 (PC · Android 와 같음) · 어두운 모드 따라가기 |
| 잠금화면 · 제어 센터 | 재생/일시정지 · 이전/다음 · 위치 이동 · 표지 · 백그라운드 재생 |

음악 넣는 다른 방법: **파일 앱 → 나의 iPhone → yMp3Player** 폴더에 복사 · PC iTunes 의 파일 공유.
가사 · EQ · 라이브러리 · 시세는 다음 단계 (f55 설계 §5).

## 5. 자주 묻는 것
| 증상 | 해결 |
|---|---|
| `GitHub 로그인 필요` | MSYS2 에서 `gh auth login` |
| `push 실패` | `gh auth login` 계정이 저장소에 쓰기 권한이 있는지 · 저장소 이름 · `ymp3player` 브랜치에 다른 기록이 있으면 `GH_BRANCH` 를 새 이름으로 (ios.yml 의 `branches:` 도 같이) |
| `빌드 실행을 찾지 못함` | 저장소 Settings → Actions 가 켜져 있는지 · Actions 화면에서 실행이 생겼는지 |
| Sideloadly 가 아이폰을 못 찾음 | Apple 홈페이지판 iTunes · iCloud 설치, USB 재연결, 신뢰 |
| 앱이 "신뢰하지 않는 개발자" | 설정 → 일반 → VPN 및 기기 관리 → 신뢰 |
| 7일 뒤 앱이 안 열림 | 무료 계정 제한 — Sideloadly 로 다시 설치 |
