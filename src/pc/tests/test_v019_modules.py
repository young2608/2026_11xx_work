# -*- coding: utf-8 -*-
"""vr0.1.0.019 (f35 · f36) 기능별 모듈화 · 리팩토링 — 구조 규칙 + 이전 import 호환 + 옮긴 로직이 같은지"""
import ast
from pathlib import Path

import pytest

PC = Path(__file__).resolve().parents[1]
PKG = PC / "yamp"


@pytest.fixture(scope="module")
def app():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _imports(p: Path):
    """(모듈 경로 문자열, 상대 수준) 목록 — 함수 안의 늦은 import 포함"""
    out = []
    for node in ast.walk(ast.parse(p.read_text(encoding="utf-8"))):
        if isinstance(node, ast.ImportFrom):
            out.append(("." * node.level) + (node.module or ""))
        elif isinstance(node, ast.Import):
            out += [a.name for a in node.names]
    return out


# ---------------------------------------------------------------- 층 규칙
def test_layers_do_not_import_upwards():
    """core · domain · data 는 화면(ui) · 앱(app) 을 부르지 않음 · data 는 가사 모듈도 부르지 않음 (R2)"""
    bad = []
    for layer in ("core", "domain", "data"):
        for p in (PKG / layer).glob("*.py"):
            for m in _imports(p):
                if m.startswith(("..ui", "..app")) or (layer == "data" and m.startswith("..lyrics")):
                    bad.append(f"{layer}/{p.name}: {m}")
    assert not bad, bad


def test_pure_modules_have_no_qt():
    """계산 · 데이터 모듈은 Qt 없이 (테스트 · Android 이식 쉬움)"""
    pure = [*(PKG / "domain").glob("*.py"),
            *(PKG / "data" / n for n in ("track.py", "scan.py", "playlist_io.py", "playlist.py", "cue.py",
                                       "library.py", "formats.py", "tags.py")),
            *(PKG / "lyrics" / n for n in ("cache.py", "resolve.py", "lrc.py", "query.py", "score.py")),
            PKG / "core" / "keys.py", PKG / "core" / "config_schema.py", PKG / "core" / "config.py"]
    bad = [p.relative_to(PKG).as_posix() for p in pure if any(m.startswith("PyQt6") for m in _imports(p))]
    assert not bad, bad


def test_every_module_stays_small():
    """v007 규칙(app/ 450줄 미만)을 패키지 전체로"""
    big = [(p.relative_to(PKG).as_posix(), n) for p in PKG.rglob("*.py")
           if (n := len(p.read_text(encoding="utf-8").splitlines())) >= 450]
    assert not big, big


# ---------------------------------------------------------------- 이전 import 경로 그대로 (같은 객체)
@pytest.mark.parametrize("old, new, names", [
    ("yamp.data.playlist", "yamp.data.track", "Track is_audio fmt_time CUE_EXT"),
    ("yamp.data.playlist", "yamp.data.scan", "scan_tracks cue_tracks sort_tracks scan_dir"),
    ("yamp.data.playlist", "yamp.data.playlist_io", "load_m3u save_m3u load_playlist load_pls load_xspf load_wpl"),
    ("yamp.ui.folder_view", "yamp.data.scan", "folder_summary summary_text"),
    ("yamp.lyrics.service", "yamp.lyrics.cache", "LyricsCache NotFoundStore"),
    ("yamp.lyrics.service", "yamp.lyrics.resolve", "Result resolve resolve_full build_providers REASONS SOURCE_NAMES"),
    ("yamp.lyrics.service", "yamp.core.keys", "cache_key"),
    ("yamp.data.library", "yamp.core.keys", "track_key"),
    ("yamp.core.config", "yamp.core.config_schema", "FILE_DEFAULTS STATE_DEFAULTS CHOICES LIMITS DEFAULT_CONFIG_TEXT"),
    ("yamp.ui.neon", "yamp.ui.section", "Section"),
    ("yamp.ui.neon", "yamp.ui.wave_seek", "WaveformSeek bars_played"),
    ("yamp.ui.neon", "yamp.ui.neon_base", "band_color _Skinned _glow_pen"),
    ("yamp.ui.library_views", "yamp.ui.home_view", "HomeView"),
    ("yamp.ui.library_views", "yamp.ui.queue_view", "QueueView"),
    ("yamp.ui.library_views", "yamp.ui.track_menu", "track_menu show_smart_menu KEY_ROLE"),
    ("yamp.app.topbar", "yamp.app.ticker_service", "TickerService"),
    ("yamp.ui.dialogs", "yamp.ui.lyrics_dialogs", "LyricsEditorDialog LyricsPickDialog"),
    ("yamp.ui.vis_block", "yamp.domain.vis_math", "DB_FLOOR to_db db_y peaks_window"),
    ("yamp.audio.visualizer", "yamp.domain.vis_math", "to_db"),
    ("yamp.ui.icons", "yamp.ui.icon_paths", "path NAMES"),
    ("yamp.app.jobs", "yamp.core.bg", "BgEmitter"),
])
def test_old_import_paths_still_work(app, old, new, names):
    import importlib
    a, b = importlib.import_module(old), importlib.import_module(new)
    for n in names.split():
        if old == "yamp.app.jobs":
            assert a.JobEmitter is b.BgEmitter
            continue
        assert getattr(a, n) is getattr(b, n), (old, n)


def test_keys_one_rule():
    import hashlib
    from yamp.core.keys import cache_key, track_key
    p = "D:/Music/가수 - 제목.FLAC"
    assert cache_key(p) == track_key(p) == hashlib.md5(p.lower().encode("utf-8")).hexdigest()[:12]


# ---------------------------------------------------------------- 옮긴 로직이 같은지
def test_merge_track_info_same_as_before():
    from yamp.data.cue import merge_track_info
    from yamp.data.tags import TagInfo
    from yamp.data.track import Track

    def old(info, t):                                   # v018 ctl_playback.play_index 안의 코드 그대로
        info.title, info.artist = t.title, t.artist or info.artist
        info.album = t.album or info.album
        file_dur = info.duration
        info.duration = ((t.end_ms if t.end_ms > 0 else file_dur * 1000) - t.start_ms) / 1000
        info.lyrics = ""
        rg = dict(info.rg or {})
        for a, b in (("replaygain_track_gain", "replaygain_album_gain"),
                     ("replaygain_track_peak", "replaygain_album_peak")):
            if a in rg:
                rg.setdefault(b, rg.pop(a))
        rg.update(t.rg or {})
        info.rg = rg
        return info
    cases = [
        (TagInfo(title="F", artist="FA", album="AL", duration=600, lyrics="x",
                 rg={"replaygain_track_gain": "-3 dB", "replaygain_track_peak": "0.9"}),
         Track("/a.flac", "T2", "", "", 0, True, 2, 120_000, 300_000, "/a.cue", {"replaygain_track_gain": "-1 dB"})),
        (TagInfo(title="F", artist="FA", duration=600, rg={"replaygain_album_gain": "-5"}),
         Track("/a.flac", "T9", "CA", "CB", 0, True, 9, 500_000, -1, "/a.cue", None)),
    ]
    for info, t in cases:
        import copy
        a, b = merge_track_info(copy.deepcopy(info), t), old(copy.deepcopy(info), t)
        assert (a.title, a.artist, a.album, a.duration, a.lyrics, a.rg) == (b.title, b.artist, b.album, b.duration, b.lyrics, b.rg)
    assert merge_track_info(TagInfo(duration=600), cases[1][1]).duration == 100.0


def test_agc_step_same_as_before():
    from yamp.domain.vis_math import agc_step

    def old(gain, m):
        if m > 0.005:
            want = min(8.0, 0.85 / m)
            gain += (want - gain) * (0.35 if want < gain else 0.08)
        return gain
    g1 = g2 = 1.0
    for m in [0.0, 0.004, 0.005, 0.01, 0.05, 0.9, 1.0, 0.2, 0.001, 0.3] * 20:
        g1, g2 = agc_step(g1, m), old(g2, m)
        assert g1 == g2


def test_bg_task_errors_and_deleted_receiver(app):
    from PyQt6.QtCore import QThreadPool
    from yamp.core.bg import BgEmitter, BgTask
    got = []
    em = BgEmitter()
    em.done.connect(got.append)
    BgTask(lambda: 1 / 0, em, on_error=lambda e: ("오류", type(e).__name__)).run()
    BgTask(lambda: 42, em).run()
    BgTask(lambda: 1 / 0, em).run()                       # on_error 없음 → None
    app.processEvents()
    assert got == [("오류", "ZeroDivisionError"), 42, None]
    em2 = BgEmitter()
    em2.deleteLater()
    app.processEvents()
    from PyQt6.QtCore import QCoreApplication, QEvent
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete.value)
    BgTask(lambda: 1, em2).run()                          # 받는 쪽이 지워져도 예외가 스레드 밖으로 나가지 않음
    pool = QThreadPool()
    pool.start(BgTask(lambda: 7, em))
    pool.waitForDone(2000)
    app.processEvents()
    assert got[-1] == 7


def test_smart_lists_one_stats_call(tmp_path):
    from yamp.app.ctl_library import LibraryMixin
    from yamp.data.library import Library
    from yamp.domain.smart import RULES

    class C(LibraryMixin):
        pass
    c = C()
    c.library = Library(tmp_path / "l.db")
    for i in range(20):
        k = c.library.upsert(f"/m/{i}.mp3", f"t{i}", "a", "b", now=1000 + i)
        if i % 3 == 0:
            c.library.set_liked(k, True)
    calls = []
    orig = c.library.stats
    c.library.stats = lambda now=None: calls.append(1) or orig(now)
    many = c.smart_lists(RULES)
    assert len(calls) == 1
    for r in RULES:
        assert many[r] == c.smart_list(r), r
    c.library.close()


def test_job_logs_under_yamp_jobs(app, caplog):
    """재검(f37): 일반 작업 오류 로그 이름이 v018 과 같은 'yamp.jobs' (공통화 뒤 'yamp.bg' 로 바뀌었던 것 수정)"""
    import logging
    from yamp.app.jobs import Job, JobEmitter
    em = JobEmitter()
    got = []
    em.done.connect(got.append)
    with caplog.at_level(logging.ERROR):
        Job(lambda: 1 / 0, em).run()
    app.processEvents()
    assert got == [None]
    assert any(r.name == "yamp.jobs" and "job:" in r.getMessage() for r in caplog.records)


def test_soak_ui_step_handles_simple_layout():
    """재검(f37): tools/soak.py --ui 가 단순 배치(기본, tabs 없음)에서 페이지로 넘김"""
    src = (PC / "tools" / "soak.py").read_text(encoding="utf-8")
    assert "if w.tabs is not None" in src and "w.go_page(w.pages.widget(" in src
