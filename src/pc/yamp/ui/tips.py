# -*- coding: utf-8 -*-
"""
버튼 설명 표 (vr0.1.0.009) — 화면의 명령 버튼은 아이콘만, 이름·단축키·설명은 마우스를 올리면 팝업.
도움말(단축키 창 · F1 이름표 오버레이)도 이 표 하나에서 만듦 → 문구가 어긋나지 않음.

  TIPS[key] = (이름, 단축키, 설명)
  html(key, state) → 툴팁 HTML (굵은 이름 + 단축키 칩 + 설명 + 현재 상태)
"""
import html as _h

from . import skin as _skin

TIPS: dict[str, tuple[str, str, str]] = {
    # ---- 재생
    "play":       ("재생 / 일시정지", "Space", "멈춘 곳부터 재생하거나 잠시 멈춤"),
    "pause":      ("일시정지", "C", "지금 위치에서 잠시 멈춤"),
    "stop":       ("정지", "V", "재생을 멈추고 처음으로"),
    "prev":       ("이전 곡", "Z · Ctrl+←", "3초 넘게 들었으면 곡 처음으로, 아니면 이전 곡"),
    "next":       ("다음 곡", "B · Ctrl+→", "대기열이 있으면 대기열 곡, 없으면 목록의 다음 곡"),
    "open":       ("파일 열기", "Ctrl+O", "음악·녹음 파일, CUE, 재생목록(m3u·pls·xspf·wpl)을 골라 목록에 추가"),
    "shuffle":    ("셔플", "S", "목록을 섞어서 재생 (노란색 = 켜짐)"),
    "repeat":     ("반복", "R", "끔 → 전체 → 1곡 순서로 바뀜"),
    "mute":       ("음소거", "M", "소리 끄기 / 켜기"),
    "volume":     ("볼륨", "+ / −", "끌어서 소리 크기 조절"),
    "like":       ("좋아요", "F", "이 곡을 좋아요로 표시 — 추천에 반영"),
    "ab":         ("구간 반복 A-B", "[", "한 번 누르면 A, 한 번 더 누르면 B — 그 사이를 반복. 세 번째에 해제"),
    "speed":      ("재생 속도 · 음정", "", "0.5~2배 속도, 음정 ±6 반음 (음정은 mpv 엔진)"),
    "diag_copy":  ("진단 결과 복사", "", "보고서 전체를 클립보드로 — 메일·메신저에 붙여 보내기"),
    "diag_folder": ("로그 폴더 열기", "", "저장된 lyrics_diag_*.txt 파일이 있는 폴더"),
    "diag_rerun": ("다시 진단", "", "지금 곡으로 가사 검색을 다시 해 보고 기록"),
    "skip_silence": ("무음 건너뛰기", "", "녹음·강의에서 1초 넘게 조용한 부분을 건너뜀 (mpv 엔진)"),
    "resume_long": ("긴 파일 이어 듣기", "", "30분 넘는 파일은 파일마다 들은 곳을 기억해 다음에 이어서 재생"),
    "voice_preset": ("음성 또렷하게", "", "사운드를 '음성' 프리셋으로 — 저음을 줄이고 말소리 대역을 올림"),
    "sleep":      ("슬립 타이머", "", "정한 시간 뒤나 곡이 끝나면 소리를 줄이며 멈춤. 목록 끝 동작·알람도 여기서"),
    "mini_lyrics": ("미니 가사창", "L · Ctrl+L", "다른 창 위에 뜨는 작은 가사창"),
    "mini_player": ("미니 플레이어", "Ctrl+M", "항상 위에 뜨는 작은 재생 창으로 바꿈"),
    "more":       ("더보기", "", "정지 · 파일 열기 · 미니 가사창 · 화면 설정"),
    "seek":       ("재생 위치", "← / →", "누르거나 끌어서 이동 (곡 모양 파형)"),
    # ---- 화면 이동 (왼쪽 레일)
    "nav_now":    ("지금 재생", "Ctrl+1", "표지 · 곡 정보 · 스펙트럼"),
    "nav_list":   ("재생 목록", "Ctrl+2", "지금 재생 목록 — 끌어서 순서 바꾸기, Del 로 빼기"),
    "nav_lib":    ("라이브러리", "Ctrl+3", "가수 · 앨범 · 장르 · 폴더별로 보기, 앨범 격자"),
    "nav_folder": ("폴더", "Ctrl+4", "폴더를 골라 그 폴더 곡만 재생"),
    "nav_home":   ("추천", "Ctrl+5", "재생 기록으로 만든 믹스 · 스마트 재생목록"),
    "nav_sound":  ("사운드", "Ctrl+6 · Ctrl+E", "이퀄라이저 · 톤 · 컴프레서 · 리미터"),
    "nav_settings": ("설정", "", "테마 · 배치 · config.txt · 로그 폴더"),
    "help":       ("도움말", "F1", "화면의 모든 버튼 이름을 한 번에 보여 줌"),
    # ---- 오른쪽 패널
    "panel_lyrics": ("가사 패널", "Ctrl+Shift+L", "오른쪽에 가사를 열고 닫음"),
    "panel_queue":  ("대기열 패널", "Ctrl+J", "오른쪽에 다음 재생할 곡을 열고 닫음"),
    "panel_close":  ("패널 닫기", "", "오른쪽 패널을 닫음"),
    # ---- 화면별 도구
    "search":     ("찾기", "Ctrl+F", "목록에서 제목·가수로 찾기"),
    "quick_find": ("빠른 찾기", "Ctrl+K", "곡 · 가수 · 폴더 · 명령을 한 칸에서 찾아 바로 실행"),
    "refresh":    ("새로고침", "", "다시 계산 / 다시 읽기"),
    "add_folder": ("라이브러리 폴더 추가", "", "음악 폴더를 라이브러리에 등록"),
    "open_folder": ("폴더 열기", "Ctrl+Shift+O", "폴더 안 음악을 모두 목록에 추가 (하위 폴더 포함)"),
    "menu_bar":   ("메뉴 막대 접기 / 펼치기", "Ctrl+Shift+M", "위 메뉴 막대를 숨겨 화면을 넓게 — 숨겨도 Alt 를 누르면 잠깐 보임, 단축키는 그대로"),
    "vis_bars":   ("스펙트럼", "", "낮은 소리(왼쪽) ~ 높은 소리(오른쪽) 크기 · 막대 위 짧은 선 = 최근 최고 · 한 번 더 누르면 막대 모양 (둥근 · LED · 미러 · 반사)"),
    "vis_wave":   ("웨이브", "", "스펙트럼을 가운데 선 위아래로 펼친 부드러운 곡선 · 스펙트럼이 없으면 지금 위치 앞뒤 3초 파형"),
    "vis_radial": ("원형", "", "스펙트럼을 가운데 원 둘레로 — 12시 = 낮은 소리, 좌우 대칭 · 점 = 최근 최고 (Avee · foobar2000 원형)"),
    "vis_gram":   ("스펙트로그램", "", "최근 5초 소리 지도 — 오른쪽에서 들어와 왼쪽으로 흐름, 아래 = 낮은 소리, 밝을수록 큼"),
    "vis_chart":  ("레벨", "", "최근 10초 소리 크기 — 면 = 평균(RMS), 선 = 최고(피크), 눈금 = dB · 0 dB 가까우면 빨강"),
    "scan":       ("다시 스캔", "", "라이브러리 폴더의 새 곡 · 지워진 곡 반영"),
    "view_grid":  ("앨범 격자 보기", "", "앨범 표지를 격자로"),
    "view_tree":  ("목록 보기", "", "가수·앨범·장르·폴더별 목록"),
    "smart":      ("스마트 재생목록", "", "규칙으로 자동으로 만들어지는 목록 (좋아요, 많이 들은 곡 …)"),
    "queue_clear": ("대기열 비우기", "", "다음 재생 목록을 모두 지움"),
    "undo":       ("되돌리기", "Ctrl+Z", "재생 목록에서 지우기 · 순서 바꾸기 · 비우기를 되돌림"),
    "folder_play": ("이 폴더 재생", "", "선택한 폴더 곡으로 재생 목록을 바꾸고 재생"),
    "folder_shuffle": ("이 폴더 셔플 재생", "", "섞어서 재생"),
    "folder_pin": ("폴더 고정", "", "자주 쓰는 폴더를 ★ 로 맨 위에 / 해제"),
    "folder_sub": ("하위 폴더 포함", "", "켜짐(노란색) = 아래 폴더 곡도 함께"),
    "eq_on":      ("이퀄라이저 켜기", "", "노란색 = 켜짐. 밴드를 움직이면 자동으로 켜짐"),
    "eq_reset":   ("초기화", "", "EQ · 프리앰프 · 톤을 0 으로"),
    "comp":       ("컴프레서", "", "작은 소리는 키우고 큰 소리는 눌러 고르게"),
    "limiter":    ("리미터", "", "−1 dBFS 를 넘지 않게 — 소리 찢어짐 방지"),
    # ---- 가사 편집기 · 다른 가사 찾기
    "ed_play":    ("재생 / 일시정지", "", "편집하면서 재생"),
    "ed_stamp":   ("시각 찍기", "F9", "지금 재생 위치를 선택한 줄에 넣고 다음 줄로"),
    "ed_minus":   ("0.1초 앞으로", "Alt+←", "선택한 줄 시각을 0.1초 당김"),
    "ed_plus":    ("0.1초 뒤로", "Alt+→", "선택한 줄 시각을 0.1초 미룸"),
    "ed_clear":   ("시각 모두 지우기", "", "모든 줄의 시각을 지움 (글자는 그대로)"),
    "pick_search": ("가사 검색", "", "제목·가수로 알송 · LRCLIB 에서 후보 찾기"),
}

def name(key: str) -> str:
    return TIPS.get(key, (key, "", ""))[0]


def html(key: str, state: str | None = None) -> str:
    n, sc, d = TIPS.get(key, (key, "", ""))
    s = _skin.current()                       # 색 = 지금 테마 (테마가 바뀌면 refresh_all 로 다시 만듦)
    out = f"<b>{_h.escape(n)}</b>"
    if sc:
        out += (f"&nbsp;&nbsp;<span style='background-color:{s.surface2}; color:{s.dim}; "
                f"font-family:Consolas,monospace;'>&nbsp;{_h.escape(sc)}&nbsp;</span>")
    if state:
        out += f"<br><span style='color:{s.accent_text}'>{_h.escape(state)}</span>"
    if d:
        out += f"<br>{dim(d)}"
    return out


def dim(text: str) -> str:
    """툴팁 안 보조 글자 (지금 테마의 dim 색)"""
    return f"<span style='color:{_skin.current().dim}'>{_h.escape(text)}</span>"


def simple(title: str, desc: str) -> str:
    """표에 없는 위젯용 툴팁: 굵은 제목 + 보조 설명"""
    return f"<b>{_h.escape(title)}</b><br>{dim(desc)}".replace("\n", "<br>")      # 여러 줄 설명 (v012)


def refresh_all(root):
    """테마가 바뀐 뒤: tip_key 가 있는 모든 위젯의 툴팁 색 다시 만들기"""
    from PyQt6.QtWidgets import QWidget
    ws = [root] + root.findChildren(QWidget)
    for w in ws:
        key = w.property("tip_key")
        if key:
            w.setToolTip(html(key, w.property("tip_state") or None))
        tt = w.property("tip_simple")
        if tt:
            w.setToolTip(simple(*tt))


def apply_simple(widget, title: str, desc: str):
    """표에 없는 위젯 툴팁 (테마가 바뀌면 refresh_all 이 다시 만듦)"""
    widget.setProperty("tip_simple", [title, desc])
    widget.setToolTip(simple(title, desc))


def plain(key: str) -> str:
    n, sc, d = TIPS.get(key, (key, "", ""))
    return f"{n}" + (f" ({sc})" if sc else "") + (f" — {d}" if d else "")


def apply(widget, key: str, state: str | None = None):
    """위젯에 설명 팝업 · 접근성 이름 · tip_key 속성 설정"""
    widget.setToolTip(html(key, state))
    widget.setAccessibleName(name(key))
    widget.setProperty("tip_key", key)
    widget.setProperty("tip_state", state or "")


def shortcut_rows() -> list[tuple[str, str]]:
    """도움말 → 단축키 창 (이름, 단축키) — 단축키 있는 것만"""
    seen, out = set(), []
    for n, sc, _d in TIPS.values():
        if sc and (n, sc) not in seen:
            seen.add((n, sc))
            out.append((n, sc))
    return out
