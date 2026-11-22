"""vr0.1.0.009: 단순 배치 (아이콘 레일 · 아래 재생 막대 · 오른쪽 패널) · 글자 없는 버튼 + 설명 팝업 ·
빠른 찾기 · 스마트 재생목록 · 목록 끝 동작/알람 · 앨범 격자 · 되돌리기 · 미니 플레이어 · 도움말 오버레이"""
import os
import re
import sys
import time
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
if sys.platform.startswith("linux"):
    os.environ.setdefault("QT_AUDIO_BACKEND", "alsa")
PC = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PC))


@pytest.fixture
def app():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _wav(path, sec=0.3, sr=22050):
    from conftest import write_wav        # vr0.1.0.010: soundfile 없이 표준 wave
    write_wav(path, sec, sr)


# ---------------------------------------------------------------- 설명 표
def test_tips_table_complete():
    from yamp.ui import tips
    for k, (n, sc, d) in tips.TIPS.items():
        assert n and d, k
    h = tips.html("ab", "1.0초 ~ 3.0초 반복 중")
    assert "<b>구간 반복 A-B</b>" in h and "반복 중" in h and "[" in h
    rows = tips.shortcut_rows()
    assert ("빠른 찾기", "Ctrl+K") in rows
    # 단축키가 서로 겹치지 않음 (같은 키를 두 기능이 쓰면 둘 다 동작 안 함)
    seen = {}
    for k, (n, sc, d) in tips.TIPS.items():
        for one in [x.strip() for x in re.split(r"·", sc) if x.strip()]:
            if one in seen and seen[one] != n:
                pytest.fail(f"단축키 겹침: {one} — {seen[one]} / {n}")
            seen[one] = n


def test_source_has_no_text_buttons():
    """명령 버튼에 글자를 다시 쓰지 않도록: QPushButton("글자") · pill 글자 버튼 금지 (대화상자 확인/취소 제외)"""
    bad = []
    for f in (PC / "yamp").rglob("*.py"):
        src = f.read_text(encoding="utf-8")
        for m in re.finditer(r'QPushButton\("([^"]+)"\)', src):
            bad.append(f"{f.name}: {m.group(1)}")
        if 'objectName="pill"' in src and "setText(" in src and f.name != "sound_view.py":
            bad.append(f"{f.name}: pill 글자 버튼")
    assert not bad, bad


def test_smart_rules():
    from yamp.domain.recommend import TrackStat
    from yamp.domain.smart import RULES, build
    now = 10_000_000
    ts = [TrackStat("a", liked=True, last_played=now - 40 * 86400, completed=5, added_at=1),
          TrackStat("b", liked=True, last_played=now - 10, completed=1, added_at=3, rating=5),
          TrackStat("c", added_at=9),
          TrackStat("d", skipped=4, completed=0, last_played=now - 5, added_at=2)]
    assert build("liked", ts, now) == ["b", "a"]
    assert build("liked_rest", ts, now) == ["a"]
    assert build("top", ts, now) == ["a", "b"]
    assert build("recent_added", ts, now)[0] == "c"
    assert build("never", ts, now) == ["c"]
    assert build("rated4", ts, now) == ["b"]
    assert build("skipped", ts, now) == ["d"]
    assert build("nope", ts, now) == [] and len(RULES) == 7


def test_album_grouping():
    from yamp.ui.album_grid import albums_of
    rows = [{"key": "1", "album": "B", "artist": "x", "path": "/b/1"}, {"key": "2", "album": "A", "artist": "y", "path": "/a/2"},
            {"key": "3", "album": "A", "artist": "y", "path": "/a/3"}, {"key": "4", "album": "", "artist": "", "path": "/c"}]
    al = albums_of(rows)
    assert [a[0] for a in al] == ["(앨범 없음)", "A", "B"] and al[1][2] == ["2", "3"] and al[1][1] == "y"


def test_quick_find_match():
    from yamp.ui.quick_find import match, search_tracks
    assert match("가수 이름 - 노래 제목", "노래 가수") and not match("abc", "abd")
    rows = [{"title": f"곡{i}", "artist": "가수", "path": f"/m/{i}"} for i in range(50)]
    assert len(search_tracks(rows, "가수")) == 30 and search_tracks(rows, "곡7")[0]["title"] == "곡7"


def test_lyrics_index_cache():
    from yamp.lyrics import lrc
    ly = lrc.parse("[00:01.00]a\n[00:02.00]b\n[00:03.00]c", "t")
    assert [ly.index_at(x) for x in (0, 1500, 2500, 9999)] == [-1, 0, 1, 2]
    ly.blocks.append(lrc.Block(4000, ["d"]))                 # 블록이 바뀌면 캐시 갱신
    assert ly.index_at(4500) == 3


# ---------------------------------------------------------------- 컨트롤러: 되돌리기 · 목록 끝 · 알람
def test_undo_and_end_action_and_alarm(app, tmp_path, monkeypatch):
    os.environ["YAMP_HOME"] = str(tmp_path)
    from yamp.core.config import Config
    from yamp.app.controller import Controller
    cfg = Config(tmp_path)
    c = Controller(cfg)
    for n in "abc":
        (tmp_path / f"{n}.mp3").write_bytes(b"\0" * 10)
    c.add_paths([str(tmp_path / f"{n}.mp3") for n in "abc"])
    c.remove([0])
    c.move(0, 1)
    c.clear()
    assert len(c.pl) == 0
    assert c.undo() and len(c.pl) == 2
    assert c.undo() and [Path(t.path).name for t in c.pl.items] == ["b.mp3", "c.mp3"]
    assert c.undo() and len(c.pl) == 3
    assert not c.undo()
    # 목록 끝 동작
    called = []
    import yamp.winplat.power as power
    monkeypatch.setattr(power, "shutdown_pc", lambda d=60: called.append(("shutdown", d)) or True)
    c.set_end_action("shutdown")
    c.on_list_end()
    assert called == [("shutdown", 60)]
    c.set_end_action("bogus")
    assert cfg["end_action"] == "stop"
    # 알람
    played = []
    monkeypatch.setattr(c, "play_index", lambda i, *a, **k: played.append(i))
    c.set_alarm("07:30")
    t = time.strptime("2026-11-04 07:30", "%Y-%m-%d %H:%M")
    assert c.check_alarm(t) is True and played == [0]
    assert c.check_alarm(t) is False                      # 같은 날 두 번 안 울림
    assert c.check_alarm(time.strptime("2026-11-04 07:31", "%Y-%m-%d %H:%M")) is False
    c.set_alarm("")
    assert c.check_alarm(t) is False
    c.shutdown()


# ---------------------------------------------------------------- 단순 배치 화면
def test_simple_layout_window(app, tmp_path):
    os.environ["YAMP_HOME"] = str(tmp_path)
    from PyQt6.QtWidgets import QToolButton
    from yamp.core.config import Config
    from yamp.app.mainwindow import MainWindow
    from yamp.ui.iconbutton import IconButton
    music = tmp_path / "m"
    music.mkdir()
    for i in range(3):
        _wav(music / f"{i}.wav")
    cfg = Config(tmp_path)
    cfg["library_folders"] = str(music)
    cfg["help_overlay_shown"] = True
    w = MainWindow(cfg)
    w.resize(1200, 720)
    w.show()
    app.processEvents()
    assert w.is_simple() and w.tabs is None and w.pages.count() == 6
    # 모든 보이는 도구 버튼: 글자 없이 아이콘만 + 설명(tip_key)
    for b in w.findChildren(QToolButton):
        if b.isVisible() and b.window() is w and b.objectName() in ("iconBtn", "railBtn", "playBig"):
            assert isinstance(b, IconButton)
            assert b.toolButtonStyle().name == "ToolButtonIconOnly" and b.property("tip_key"), b.text()
            assert "<b>" in b.toolTip()
    # 레일 → 페이지
    w.go_page(w.soundv)
    assert w.pages.currentWidget() is w.page_sound and w.rail_btns[w.page_sound].isChecked()
    assert cfg["last_page"] == "sound"
    w.go_page(w.page_folder)
    assert w.current_page() is w.page_folder
    # 오른쪽 패널 열고 닫기
    w.toggle_panel("queue", force=True)
    assert w.side.isVisible() and w.side_stack.currentWidget() is w.queuev and cfg["side_panel"] == "queue"
    w.toggle_panel("queue")
    assert not w.side.isVisible() and cfg["side_panel"] == ""
    w.toggle_panel("lyrics")
    assert w.side.isVisible() and w.b_panel_lyrics.isChecked()
    # 재생 → 아래 막대
    w.ctrl.play_folder(str(music), False)
    app.processEvents()
    assert w.bar_title.text() and w.b_play.property("tip_key") == "play"
    w.ctrl._on_state("playing")
    assert w.b_play.icon_name == "pause"
    w.ctrl.cycle_repeat()
    assert "지금:" in w.b_rep.toolTip()
    w.ctrl.cycle_ab()
    w.ctrl.cycle_ab()
    assert w.b_ab.isChecked() and "반복 중" in w.b_ab.toolTip()
    # 알림(토스트)
    w.ctrl.message.emit("테스트 알림")
    assert w.toast.isVisible() and w.toast.text() == "테스트 알림"
    # 도움말 오버레이
    ov = w.show_help_overlay()
    assert len(ov.items) >= 15
    ov.close()
    # 앨범 격자
    w.go_page(w.libv)
    w.libv.set_view("grid")
    w.ctrl.scan_library()
    w.ctrl._scan_jobs.waitForDone(5000)          # v032 (f60 P7): 스캔은 따로 작업 줄
    w.ctrl._jobs.waitForDone(5000)
    app.processEvents()
    assert cfg["lib_view"] == "grid" and w.libv.grid.count() >= 1
    w.libv.set_view("tree")
    # 빠른 찾기 명령
    from yamp.ui.quick_find import QuickFind
    q = QuickFind(w, w.quick_commands())
    q.edit.setText("셔플")
    assert q.list.count() >= 1
    sh = cfg["shuffle"]
    q.run_current()
    assert cfg["shuffle"] != sh
    # 미니 플레이어
    w.toggle_mini_player()
    assert w.mini_player is not None and w.mini_player.isVisible()
    w.mini_player.close()
    app.processEvents()
    assert w.mini_player is None
    # 좁은 창 → 패널 자동 닫힘
    for _ in range(2):                                    # 첫 번째는 최소 폭에 걸림 → 버튼 숨긴 뒤 한 번 더
        w.resize(800, 600)
        app.processEvents()
    assert not w.side.isVisible() and not w.b_ab.isVisible()
    w.resize(1200, 720)
    app.processEvents()
    assert w.side.isVisible() and w.b_ab.isVisible()
    for name in ("neon", "classic", "dark", "light"):
        w.apply_skin(name)
    w.apply_skin("neon")
    w.go_page(w.page_now)
    w.grab().save(str(tmp_path / "v009.png"))
    w.quit_app()


def test_classic_layout_still_works(app, tmp_path):
    os.environ["YAMP_HOME"] = str(tmp_path)
    from yamp.core.config import Config
    from yamp.app.mainwindow import MainWindow
    cfg = Config(tmp_path)
    cfg["layout"] = "classic"
    w = MainWindow(cfg)
    w.show()
    app.processEvents()
    assert not w.is_simple() and w.tabs.count() == 6 and w.pages is None
    w.go_page(w.soundv)
    assert w.tabs.currentWidget() is w.soundv
    w.toggle_panel("queue")
    assert w.tabs.currentWidget() is w.queuev
    w.quit_app()
