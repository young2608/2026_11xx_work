"""vr0.1.0.007: 장시간 운용 (메모리 누수·느려짐) · 모듈화 구조 검사"""
import gc
import os
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


# ---------------------------------------------------------------- 모듈 구조
def test_controller_modules_and_api():
    from yamp.app import controller as C
    from yamp.app.ctl_playback import PlaybackMixin
    from yamp.app.ctl_library import LibraryMixin
    assert issubclass(C.Controller, PlaybackMixin) and issubclass(C.Controller, LibraryMixin)
    for name in ("play_index", "next", "prev", "seek", "play_folder", "set_sound", "toggle_like", "radio",
                 "cycle_ab", "sleep_start", "request_home", "scan_library", "maintenance", "set_ui_active",
                 "autosave", "adjust_offset", "shutdown"):
        assert callable(getattr(C.Controller, name)), name
    # 파일 크기: 한 파일이 너무 커지지 않게 (모듈화 유지)
    for f in (PC / "yamp" / "app").glob("*.py"):
        assert len(f.read_text(encoding="utf-8").splitlines()) < 450, f.name


# ---------------------------------------------------------------- DB
def test_library_batch_and_prune(tmp_path):
    from yamp.data.library import Library
    lib = Library(tmp_path / "l.db")
    with lib.batch():
        for i in range(50):
            lib.upsert(f"/m/{i}.mp3", f"t{i}", "a", "b", now=1000)
        assert lib._batch == 1
    assert lib._batch == 0 and len(lib.all_tracks()) == 50
    k = lib.all_tracks()[0]["key"]
    now = 2_000_000_000
    for i in range(30):
        lib.record_play(k, now - 800 * 86400 + i, 1000, 1000, 1, 0, 1)      # 2년 넘은 기록
    for i in range(20):
        lib.record_play(k, now - 10 + i, 1000, 1000, 1, 0, 2)
    assert lib.prune_plays(now) == 30
    assert lib.prune_plays(now, max_rows=5) == 15
    assert lib.db.execute("SELECT COUNT(*) FROM plays").fetchone()[0] == 5
    lib.close()


# ---------------------------------------------------------------- 가사 캐시 색인
def test_lyrics_cache_index(tmp_path):
    from yamp.lyrics.service import LyricsCache
    from yamp.lyrics.providers.base import Query
    c = LyricsCache(tmp_path)
    q = Query("/m/a.mp3", "제목", "가수", "", 100, "")
    assert c.get(q) is None
    c.put(q, "[00:01.00]하나", "alsong")
    assert c.get(q)[1] == "alsong"
    c2 = LyricsCache(tmp_path)                      # 새로 만들면 폴더를 한 번 읽어 색인
    assert c2.get(q)[0].startswith("[re:yAmp/alsong]")
    c2.remove(q)
    assert c2.get(q) is None and not list(tmp_path.glob("*.lrc"))


def test_lyrics_stale_job_skipped():
    from yamp.lyrics.service import _Job, _Emitter
    em = _Emitter()
    got = []
    em.done.connect(lambda r, ly: got.append(r))
    _Job(1, None, [], None, False, em, current=lambda: 2).run()          # 이미 다음 곡 → 건너뜀
    assert got == []


# ---------------------------------------------------------------- 파형 캐시 정리
def test_waveform_cache_trim(tmp_path):
    from yamp.audio.waveform import WaveformCache
    c = WaveformCache(tmp_path)
    for i in range(12):
        f = tmp_path / f"{i:02d}.txt"
        f.write_text("0.1")
        os.utime(f, (1000 + i, 1000 + i))
    assert c.trim(5) == 7
    assert sorted(p.name for p in tmp_path.glob("*.txt")) == [f"{i:02d}.txt" for i in range(7, 12)]


# ---------------------------------------------------------------- 메뉴·대화상자 누수
def test_exec_menu_deletes(app):
    from PyQt6.QtCore import QPoint, QTimer
    from PyQt6.QtWidgets import QMenu, QWidget
    from yamp.ui.qtutil import exec_menu
    w = QWidget()
    for _ in range(5):
        m = QMenu(w)
        m.addAction("x")
        QTimer.singleShot(10, m.close)
        exec_menu(m, QPoint(0, 0))
    app.processEvents()
    from PyQt6.QtCore import QCoreApplication, QEvent
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete.value)
    assert len(w.findChildren(QMenu)) == 0


# ---------------------------------------------------------------- 타이머가 계속 깨어나지 않음
def test_idle_timers_stop(app):
    from yamp.ui import skin
    from yamp.ui.widgets import ScrollTitle, SpectrumWidget
    st = ScrollTitle(skin.get("neon"))
    st.resize(300, 22)
    st.show()
    st.set_text("짧은 제목")
    assert not st._t.isActive()                        # 짧으면 흐르지 않음 → 타이머 정지
    st.set_text("아주 " * 60)
    assert st._t.isActive()
    st.hide()
    assert not st._t.isActive()
    sp = SpectrumWidget(skin.get("neon"))
    sp.show()
    assert not sp._decay.isActive()
    sp.set_levels([1.0] * 19)
    assert sp._decay.isActive()
    for _ in range(80):
        sp._fall()
    assert not sp._decay.isActive()                    # 다 내려가면 정지


# ---------------------------------------------------------------- 오래 돌리기 (축소판 소크 테스트)
def test_soak_track_changes_no_growth(app, tmp_path):
    """곡 전환·메뉴·창 숨김을 반복해도 메인 창 자식 객체 수가 늘지 않음"""
    os.environ["YAMP_HOME"] = str(tmp_path)
    from PyQt6.QtCore import QCoreApplication, QEvent, QObject
    from yamp.core.config import Config
    from yamp.app.mainwindow import MainWindow
    music = tmp_path / "m"
    music.mkdir()
    for i in range(4):
        _wav(music / f"{i}.wav")
    cfg = Config(tmp_path)
    cfg["waveform"] = False
    w = MainWindow(cfg)
    w.show()
    w.ctrl.add_paths([str(music)])
    w.ctrl._pool.waitForDone(3000)

    def settle():
        for _ in range(3):
            app.processEvents()
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete.value)
        gc.collect()

    def cycle(n):
        for k in range(n):
            w.ctrl.play_index(k % 4, autoplay=False)
            w.ctrl._on_tick(force=True)
            w._on_ab((100, 200))
            w._on_ab(None)
        settle()

    cycle(8)
    base_children = len(w.findChildren(QObject))
    t0 = time.perf_counter()
    cycle(60)
    dt = time.perf_counter() - t0
    assert len(w.findChildren(QObject)) <= base_children + 5
    assert dt < 30
    # 창 숨김 → 화면 시그널 줄이기
    w.showMinimized()
    settle()
    w.ctrl.set_ui_active(False)
    got = []
    w.ctrl.positionChanged.connect(lambda p, d: got.append(p))
    for _ in range(20):
        w.ctrl._on_tick()
    assert len(got) == 2                              # 20틱 → 2번만
    w.ctrl.set_ui_active(True)
    w.quit_app()
