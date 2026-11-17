# -*- coding: utf-8 -*-
"""vr0.1.0.020 (f40) 장시간 사용 — 메모리 누수 · 느려짐 3차 점검 (L1~L7)"""
import os
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def app():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _flush(app):
    """테스트는 이벤트 루프(exec) 밖 → deleteLater 를 직접 처리"""
    from PyQt6.QtCore import QCoreApplication, QEvent
    for _ in range(3):
        app.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete.value)


# ---------------------------------------------------------------- L1 DB: WAL 크기 제한 · 비우기 · 하루 한 번 정리
def test_wal_limit_and_checkpoint(tmp_path):
    from yamp.data.library import WAL_LIMIT_BYTES, Library
    lib = Library(tmp_path / "l.db")
    if lib.journal != "wal":
        pytest.skip("이 파일 시스템은 WAL 미지원")
    assert lib.db.execute("PRAGMA journal_size_limit").fetchone()[0] == WAL_LIMIT_BYTES
    for i in range(300):
        lib.record_play(f"k{i}", 1_000_000 + i, 1000, 2000, 1, 0, 1)
    wal = Path(str(tmp_path / "l.db") + "-wal")
    assert wal.exists() and wal.stat().st_size > 0
    assert lib.checkpoint() is True
    assert wal.stat().st_size == 0                          # 비워짐
    with lib.batch():
        assert lib.checkpoint() is False                    # 묶음 저장 중에는 하지 않음
    assert lib.db.execute("SELECT COUNT(*) FROM plays").fetchone()[0] == 300
    lib.close()


def test_maintenance_runs_daily(tmp_path, app):
    os.environ["YAMP_HOME"] = str(tmp_path)
    from yamp.app.controller import MAINT_MS, Controller
    from yamp.core.config import Config
    c = Controller(Config(tmp_path))
    try:
        assert MAINT_MS == 24 * 3600 * 1000
        assert c._maint.isActive() and c._maint.interval() == MAINT_MS
        got = []
        c._jem.done.disconnect()
        c._jem.done.connect(got.append)
        c.maintenance()
        c._jobs.waitForDone(5000)
        app.processEvents()
        assert got and got[0][0] == "maint" and len(got[0][1]) >= 4      # (기록 정리, 파형 정리, VACUUM, WAL 비우기[, v022 가사 정리])
    finally:
        c.shutdown()
    assert not c._maint.isActive()


# ---------------------------------------------------------------- L2 앨범 격자: 자리 그림 공유 · 표지 메모리 상한
def test_album_placeholders_no_pixmap_per_album(app):
    """자리 그림은 아이콘 엔진이 그릴 때만 그림 (앨범마다 픽스맵을 들고 있지 않음) · 그림은 v016 placeholder() 와 픽셀까지 같음"""
    from PyQt6.QtCore import QSize
    from yamp.ui import album_grid as AG
    g = AG.AlbumGrid()
    g.side, g.ratio = 120, 1.0
    rows = [{"key": f"k{i}", "album": f"Album {i}", "artist": "a", "path": "", "cue_no": 0} for i in range(400)]
    g.set_rows(rows)
    assert g.count() == 400
    for i in (0, 7, 399):
        alb = g.item(i).data(AG.ROLE)[1]
        for side, r in ((120, 1.0), (100, 1.5), (220, 2.0)):
            a = g.item(i).icon().pixmap(QSize(side, side), r).toImage()
            b = AG.placeholder(alb, side, r).toImage()
            assert a == b, (alb, side, r)


def test_album_cover_cache_byte_cap(app, monkeypatch):
    from PyQt6.QtGui import QImage
    from yamp.ui import album_grid as AG
    monkeypatch.setattr(AG, "CACHE_MAX_BYTES", 3 * 200 * 200 * 4)   # 표지 3장분
    g = AG.AlbumGrid()
    g.side, g.ratio = 200, 1.0
    g.set_rows([{"key": f"k{i}", "album": f"A{i}", "artist": "", "path": "/x", "cue_no": 0} for i in range(6)])
    ph_key = g._ph("A0").cacheKey()
    for i in range(6):
        img = QImage(200, 200, QImage.Format.Format_ARGB32)
        img.fill(0xFF336699)
        g._on_cover(f"A{i}", img)
    assert len(g._cache) == 3 and g._bytes == 3 * 200 * 200 * 4
    assert list(g._cache) == ["A3", "A4", "A5"]
    # 밀려난 앨범의 칸은 자리 그림으로 돌아가 표지 메모리가 실제로 풀림 · 다시 보이면 다시 읽도록 요청 기록도 지움
    assert g._by_album["A0"].icon().pixmap(200, 200).cacheKey() != g._by_album["A5"].icon().pixmap(200, 200).cacheKey()
    assert "A0" not in g._asked and ph_key


# ---------------------------------------------------------------- L3 라이브러리 탭: 떠나면 캐시 놓음
def test_library_view_drops_cache_on_hide(tmp_path, app):
    from PyQt6.QtCore import QObject, pyqtSignal
    from PyQt6.QtWidgets import QStackedWidget, QWidget
    from yamp.core.config import Config
    from yamp.data.library import Library
    from yamp.ui.library_views import LibraryView
    base = tmp_path / "c"
    base.mkdir()

    class Ctl(QObject):
        libraryChanged = pyqtSignal()
        homeReady = pyqtSignal(object)

        def __init__(s):
            super().__init__()
            s.cfg = Config(base)
            s.library = Library(tmp_path / "l.db")
            for i in range(30):
                s.library.upsert(f"/m/{i}.mp3", f"t{i}", "a", "b")

        def scan_library(s):
            pass
    ctl = Ctl()
    st = QStackedWidget()
    other, lv = QWidget(), LibraryView(ctl)
    st.addWidget(other)
    st.addWidget(lv)
    st.setCurrentWidget(lv)
    st.show()
    _flush(app)
    lv.reload()
    assert lv._rows_cache is not None
    st.setCurrentWidget(other)                              # 탭 떠남
    _flush(app)
    assert lv._rows_cache is None and lv.tree.topLevelItemCount() == 1
    st.close()
    ctl.library.close()


# ---------------------------------------------------------------- L4 가사 캐시: 저장 때 폴더 전체 훑기 없음
def test_lyrics_cache_no_folder_scan_after_index(tmp_path, monkeypatch):
    from yamp.lyrics.cache import LyricsCache
    from yamp.lyrics.providers.base import Query
    from yamp.core.keys import cache_key
    q = Query("/m/a.mp3", "제목", "가수", "", 100, "")
    k = cache_key(q.path)
    (tmp_path / f"옛 이름__{k}.lrc").write_text("[00:01.00]옛", encoding="utf-8")       # 같은 키 파일 2개 (예전 이름)
    (tmp_path / f"가수 - 제목__{k}.lrc").write_text("[00:01.00]둘", encoding="utf-8")
    c = LyricsCache(tmp_path)
    assert c.get(q) is not None                              # 여기서 색인 (폴더 1번)
    calls = []
    orig = Path.glob
    monkeypatch.setattr(Path, "glob", lambda self, pat: calls.append(pat) or orig(self, pat))
    for i in range(20):
        c.put(q, f"[00:01.00]새 {i}", "alsong")
    c.put(Query("/m/b.mp3", "B", "", "", 1, ""), "[00:01.00]b", "lrclib")
    assert calls == []                                       # 전에는 저장마다 폴더 전체 glob
    files = sorted(p.name for p in tmp_path.glob("*.lrc"))
    assert files == sorted([f"가수 - 제목__{k}.lrc", f"B__{cache_key('/m/b.mp3')}.lrc"])   # 옛 이름 파일도 정리됨
    text = c.get(q)[0].replace("\r\n", "\n")          # v021: Windows 는 write_text 가 줄 끝을 CRLF 로 씀 (v020 Windows 빌드 실패 원인)
    assert text.endswith("[00:01.00]새 19\n") and c.get(q)[1] == "alsong"
    c.remove(q)
    assert c.get(q) is None


# ---------------------------------------------------------------- L7 화면 동작 반복 → 창 · Qt 객체 수 그대로 (누수 회귀 방지)
def test_ui_actions_do_not_accumulate(tmp_path, app, monkeypatch):
    from PyQt6.QtCore import QObject, QPoint
    from PyQt6.QtWidgets import QDialog, QMenu, QMessageBox
    monkeypatch.setattr(QDialog, "exec", lambda self: (self.show(), app.processEvents(), self.reject(), 0)[-1])
    monkeypatch.setattr(QMenu, "exec", lambda self, *a, **k: (self.popup(QPoint(0, 0)), app.processEvents(), self.close(), None)[-1])
    for name in ("about", "information", "warning", "critical", "question"):      # 정적 대화상자는 띄우지 않음
        monkeypatch.setattr(QMessageBox, name, staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok))
    os.environ["YAMP_HOME"] = str(tmp_path)
    from yamp.app.mainwindow import MainWindow
    from yamp.core.config import Config
    from yamp.ui.track_menu import show_smart_menu
    cfg = Config(tmp_path)
    cfg["topbar_ticker"] = False
    w = MainWindow(cfg)
    w.show()
    _flush(app)

    def one_round():
        for name in ("show_speed", "show_lyrics_editor", "show_lyrics_pick", "show_keys", "show_about"):
            getattr(w, name)()
            _flush(app)
        show_smart_menu(w, w.ctrl, w.libv.b_smart)
        w.toggle_mini_player()
        w.toggle_mini_player()
        w.show_help_overlay().close()
        w.libv.set_view("grid")
        w.libv.set_view("tree")
        for i in range(w.pages.count()):
            w.go_page(w.pages.widget(i))
        _flush(app)

    def counts():
        return len(app.topLevelWidgets()), len(w.findChildren(QObject))
    one_round()
    one_round()
    c0 = counts()
    for _ in range(4):
        one_round()
    c1 = counts()
    assert c1[0] <= c0[0] and c1[1] <= c0[1] + 2, (c0, c1)
    w.ctrl.shutdown()
    w.close()                                                # closeEvent 가 shutdown 을 한 번 더 부름 → 안전해야 함
    _flush(app)
