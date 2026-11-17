"""vr0.1.0.004: 추천 엔진(공용 벡터) · ReplayGain · 재생 기록 · 라이브러리 DB · 가사 편집기 · mpv af · 컨트롤러 기능"""
import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
if sys.platform.startswith("linux"):
    os.environ.setdefault("QT_AUDIO_BACKEND", "alsa")
PC = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PC))

from yamp.domain import recommend as R            # noqa: E402
from yamp.data.recorder import PlayRecorder       # noqa: E402
from yamp.data.library import Library, track_key  # noqa: E402
from yamp.lyrics.editor import LyricEditor        # noqa: E402
from yamp.lyrics import lrc                       # noqa: E402
from yamp.audio.mpv_engine import build_af, parse_eq_bands, create_engine  # noqa: E402

CASES = PC.parent / "testdata" / "recommend_cases.txt"


def load_cases():
    tracks, co, recent, expect, scores, gains, now = [], {}, [], {}, {}, [], 0
    for line in CASES.read_text(encoding="utf-8").splitlines():
        tag, _, rest = line.partition(" ")
        if tag == "NOW":
            now = int(rest)
        elif tag == "T":
            f = rest.split("|")
            tracks.append(R.TrackStat(f[0], f[1], f[2], f[3], f[4], f[5] == "1", int(f[6]), int(f[7]), int(f[8]),
                                      int(f[9]), int(f[10]), int(f[11]), tuple(x for x in f[12].split(",") if x)))
        elif tag == "CO":
            a, b, c = rest.split("|")
            co[(a, b)] = int(c)
        elif tag == "RECENT":
            recent.append(rest)
        elif tag == "EXPECT":
            k, v = rest.split("|")
            expect[k] = [x for x in v.split(",") if x]
        elif tag == "SCORE":
            k, v = rest.split("|")
            scores[k] = float(v)
        elif tag == "GAIN":
            gains.append(rest.split("|"))
    return tracks, co, recent, expect, scores, gains, now


# ---------------------------------------------------------------- 공용 벡터 (Android RecommendTest 와 같은 파일)
def test_recommend_shared_vectors():
    ts, co, recent, ex, scores, gains, now = load_cases()
    for t in ts:
        assert abs(R.score(t) - scores[t.key]) < 1e-6
    assert R.daily(ts, now) == ex["daily"]
    assert R.favorites(ts) == ex["favorites"]
    assert R.rediscover(ts, now) == ex["rediscover"]
    assert R.recent_added(ts, 5) == ex["recent"]
    for k, v in ex.items():
        if k.startswith("similar:"):
            assert R.similar(ts, k.split(":")[1], co, recent) == v
        if k.startswith("mood:"):
            assert R.mood(ts, k.split(":")[1]) == v
    for txt, peak, pre, f in gains:
        assert abs(R.gain_factor(R.parse_gain(txt), float(peak) if peak else None, float(pre)) - float(f)) < 1e-6


def test_testdata_is_fresh():
    """생성 스크립트 결과와 저장된 벡터가 같은지 — 비교만 (빌드 중 소스 파일을 다시 쓰지 않음).
    알고리즘을 바꾸면: python tests/gen_testdata.py"""
    import importlib.util
    spec = importlib.util.spec_from_file_location("gen", PC / "tests" / "gen_testdata.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    saved = CASES.read_bytes().decode("utf-8").replace("\r\n", "\n")
    assert m.build_text() == saved


def test_recommend_rules():
    ts, co, recent, *_ = load_cases()
    sim = R.similar(ts, "a01", co, recent)
    assert sim[0] == "a01" and "a02" not in sim               # 최근 재생 제외
    assert R.similar(ts, "zzz") == []
    d = R.diversify(["x1", "x2", "x3", "y1"], lambda k: k[0])
    assert d == ["x1", "x2", "y1", "x3"]
    import random
    a = R.daily(ts, 1_780_000_000, rng=random.Random(1))
    b = R.daily(ts, 1_780_000_000, rng=random.Random(1))
    assert a == b and sorted(a) == sorted(R.daily(ts, 1_780_000_000))
    cards = R.build_home(ts, 1_780_000_000, co, "a01", recent)
    ids = [c[0] for c in cards]
    assert ids[0] == "daily" and "similar" in ids and all(c[2] for c in cards)
    assert R.build_home([], 0) == []


# ---------------------------------------------------------------- 재생 기록 판정
def test_recorder_rules():
    r = PlayRecorder()
    r.start("k", 200_000, now=1000)
    for p in range(0, 120_001, 1000):            # 120초 들음 (60%)
        r.tick(p, True)
    rec = r.finish(now=1200)
    assert rec["completed"] and not rec["skipped"] and rec["listened_ms"] == 120_000
    r.start("k2", 200_000, now=1300)
    r.tick(0, True)
    r.tick(150_000, True)                        # 탐색(2초 넘는 점프) 은 제외
    r.tick(151_000, True)
    rec = r.finish(now=1301)
    assert rec["listened_ms"] == 1000 and rec["skipped"] and rec["session_id"] == 1000
    r.start("k3", 0, now=1301 + 31 * 60)         # 30분 넘게 쉼 → 새 세션
    r.tick(0, True)
    r.tick(1000, False)                          # 일시정지 중은 누적 안 함
    assert r.finish() is None
    assert r.session_id == 1301 + 31 * 60
    r.start("k4", 0)
    for p in range(0, 40_001, 1000):
        r.tick(p, True)
    rec = r.finish(ended_naturally=True)
    assert rec["completed"] and not rec["skipped"]


# ---------------------------------------------------------------- 라이브러리 DB
def test_library_db(tmp_path):
    lib = Library(tmp_path / "lib.db")
    pa, pb = str(tmp_path / "a.mp3"), str(tmp_path / "b.mp3")
    ka = lib.upsert(pa, "A", "IU", "Al", "K-Pop", "2020", 200, now=100)
    kb = lib.upsert(pb, "B", "IU", "Al", "K-Pop", "2020", 180, now=200)
    assert ka == track_key(pa) and lib.has(pa)
    lib.set_liked(ka, True)
    lib.set_rating(kb, 9)
    lib.add_tag(kb, "study")
    now = 10_000
    lib.record_play(ka, now - 50, 150_000, 200_000, True, False, 1)
    lib.record_play(kb, now - 40, 10_000, 180_000, False, True, 1)
    st = {t.key: t for t in lib.stats(now)}
    assert st[ka].liked and st[ka].completed == 1 and st[ka].completed_recent == 1
    assert st[kb].rating == 5 and st[kb].skipped == 1 and st[kb].tags == ("study",)
    assert lib.co_pairs() == {(ka, kb): 1}
    assert lib.last_played_key() == kb and set(lib.recent_keys(now)) == {ka, kb}
    lib.upsert(pa, "A2", "IU", "Al", "K-Pop", "2020", 0)       # 갱신해도 기록·좋아요 유지
    assert lib.track(ka)["title"] == "A2" and lib.track(ka)["duration_ms"] == 200_000 and lib.liked(ka)
    lib.clear_history()
    st = {t.key: t for t in lib.stats(now)}
    assert st[ka].completed == 0 and st[ka].liked and lib.co_pairs() == {}
    assert lib.remove_missing() == 2
    lib.close()


# ---------------------------------------------------------------- 가사 편집기
def test_lyric_editor():
    ed = LyricEditor.from_text("첫 줄\n\n둘째 줄\n셋째 줄")
    assert ed.stamp(1000) == 2                   # 빈 줄 건너뜀
    ed.stamp(2500)
    ed.nudge(-100, 2)
    ly = lrc.parse(ed.to_lrc())
    assert ly.synced and [b.t_ms for b in ly.blocks] == [1000, 2400]
    ed.set_text("첫 줄 수정\n\n둘째 줄\n셋째 줄\n넷째")
    assert ed.lines[0].t_ms == 1000 and ed.lines[0].text == "첫 줄 수정" and ed.lines[4].t_ms == -1
    ed2 = LyricEditor.from_lyrics(lrc.parse("[00:01.00]a\n[00:01.00]a-tr\n[00:03.00]b"))
    assert [(l.t_ms, l.text) for l in ed2.lines] == [(1000, "a"), (1000, "a-tr"), (3000, "b")]
    assert lrc.parse(ed2.to_lrc()).blocks[0].lines == ["a", "a-tr"]
    ed2.clear_times()
    assert ed2.stamped() == 0


# ---------------------------------------------------------------- mpv · EQ
def test_mpv_af_and_fallback():
    assert parse_eq_bands("1,2,x,99") == [1.0, 2.0, 0.0, 12.0] + [0.0] * 6
    assert build_af(False, [3] * 10, 0) == ""
    af = build_af(True, [3, 0, 0, 0, 0, 0, 0, 0, 0, -2.5], 2)
    assert af.startswith("lavfi=[equalizer=f=31:t=o:w=1:g=3,equalizer=f=16000:t=o:w=1:g=-2.5]")
    assert "rubberband=pitch-scale=1.122462" in af
    from PyQt6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    e, msg = create_engine("mpv")                # 작업 환경엔 libmpv 없음 → Qt 로 대체
    assert e.name in ("qt", "mpv")
    if e.name == "qt":
        assert "Qt" in msg
    e.shutdown()


# ---------------------------------------------------------------- 컨트롤러 (오프스크린)
@pytest.fixture()
def ctrl(tmp_path):
    from PyQt6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    os.environ["YAMP_HOME"] = str(tmp_path)
    from yamp.core.config import Config
    from yamp.app.controller import Controller
    c = Controller(Config(tmp_path))
    for i in range(4):
        (tmp_path / f"0{i}. 가수{i % 2} - 노래{i}.mp3").write_bytes(b"\x00" * 10)
    c.add_paths([str(tmp_path)])
    c._pool.waitForDone(3000)
    yield c
    c.shutdown()


def test_controller_queue_like_ab_sleep(ctrl, tmp_path):
    c = ctrl
    c.play_index(0, autoplay=False)
    c.play_next([2])
    c.enqueue([3])
    assert [t.path for t in c.queue] == [c.pl.items[2].path, c.pl.items[3].path]
    c.next()
    assert c.pl.current == 2 and len(c.queue) == 1          # 대기열 먼저
    c.clear_queue()
    assert c.queue == []
    k = c.current_key()
    c.toggle_like()
    assert c.library.liked(k)
    c.set_rating(c.pl.current, 4)
    assert c.library.track(k)["rating"] == 4
    c.repeat_range(1000, 500)
    assert c.ab == (1000, 4000)
    c.cycle_ab()
    assert c.ab is None
    c.set_speed(3.0)
    assert c.cfg["speed"] == 2.0
    c.sleep_start(30)
    assert c.sleep_remaining().endswith("분 남음")
    assert c._fade_factor(1000, 100000) == 1.0
    c._sleep_end = __import__("time").monotonic() + 10      # 10초 남음 / fade 30초
    assert 0.2 < c._fade_factor(1000, 100000) < 0.5
    c.sleep_cancel()
    c.cfg["crossfade_s"] = 4
    assert c._fade_factor(1000, 100000) == pytest.approx(0.25)
    assert c._fade_factor(98000, 100000) == pytest.approx(0.5)
    # 믹스 재생: 라이브러리 key 로
    keys = [track_key(t.path) for t in c.pl.items]
    c.play_mix(keys[1:], "테스트")
    assert c.pl.current == 1 and len(c.queue) == 2


def test_controller_rg_and_history(ctrl):
    c = ctrl
    from yamp.data.tags import TagInfo
    c.cfg["replaygain"] = "track"
    i = TagInfo(rg={"replaygain_track_gain": "-6 dB", "replaygain_album_gain": "-3 dB"})
    assert c._rg_factor(i) == pytest.approx(10 ** (-6 / 20))
    c.cfg["replaygain"] = "album"
    assert c._rg_factor(i) == pytest.approx(10 ** (-3 / 20))
    c.cfg["replaygain"] = "off"
    assert c._rg_factor(i) == 1.0
    c.play_index(0, autoplay=False)
    c.recorder.listened = 250_000                       # 4분 이상 → 완청 (테스트 파일은 길이 0)
    c.play_index(1, autoplay=False)                     # 이전 곡 기록됨
    st = {t.key: t for t in c.library.stats()}
    assert st[track_key(c.pl.items[0].path)].completed == 1
    c.cfg["history_enabled"] = False
    c.recorder.listened = 250_000
    c.play_index(2, autoplay=False)
    assert {t.key: t for t in c.library.stats()}[track_key(c.pl.items[1].path)].completed == 0


def test_mainwindow_v004(tmp_path):  # noqa
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    os.environ["YAMP_HOME"] = str(tmp_path)
    from yamp.core.config import Config
    from yamp.app.mainwindow import MainWindow
    from yamp.ui import dialogs as dlg
    cfg = Config(tmp_path)
    cfg["layout"] = "classic"                 # v009: 클래식 배치 기준
    w = MainWindow(cfg)
    w.show()
    (tmp_path / "가수 - 노래.mp3").write_bytes(b"\x00" * 10)
    w.ctrl.add_paths([str(tmp_path)])
    w.ctrl._pool.waitForDone(3000)
    app.processEvents()
    assert [w.tabs.tabText(i).split(" ")[0] for i in range(4)] == ["재생목록", "추천", "라이브러리", "대기열"]
    w.ctrl.play_index(0, autoplay=False)
    w.ctrl.toggle_like()
    app.processEvents()
    assert w.b_like.text() == "♥"
    w.ctrl.request_home()
    w.ctrl._jobs.waitForDone(3000)
    app.processEvents()
    w.libv.reload()
    assert w.libv.tree.topLevelItemCount() >= 1
    w.ctrl.play_next([0])
    app.processEvents()
    assert w.queuev.list.count() == 1 and w.tabs.tabText(3) == "대기열 (1)"
    for D in (dlg.SpeedDialog, dlg.EqDialog, dlg.LyricsEditorDialog):
        d = D(w.ctrl, w)
        d.show()
        app.processEvents()
        d.close()
    ed = dlg.LyricsEditorDialog(w.ctrl, w)
    ed.text.setPlainText("하나\n둘")
    ed.stamp()
    ed.also_lrc.setChecked(False)
    ed._save()
    assert w.ctrl.lyrics.cache.get(w.ctrl.lyrics.last_query)[1] == "user"
    w.lyv.set_three_line(False, False)
    w.toggle_mini()
    w.mini.set_click_through(True)
    assert w.cfg["mini_click_through"] is True
    w.mini.set_click_through(False)
    w.grab().save(str(tmp_path / "v004.png"))
    w.quit_app()
