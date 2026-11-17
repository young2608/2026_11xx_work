# -*- coding: utf-8 -*-
"""화면 동작 누수 점검 (vr0.1.0.020 f40) — 창의 거의 모든 동작(쪽 · 미니 창 · 대화상자 · 메뉴 · 테마 · 글자 크기 · 검색 ·
앨범 격자 · 스마트 메뉴 · 폴더 · 블럭 접기 · 되돌리기 …)을 N 바퀴 반복하며 Qt 객체 · 창 · 파이썬 객체 수를 기록.
모달 대화상자 · 메뉴는 띄웠다 바로 닫음 (사람 없이 돌게). soak.py(곡 넘기기 · 시간 축) 와 짝.

  python tools/leakcheck.py <pc 폴더> [바퀴=20] [음악 폴더]       (pc 폴더 = 이 파일의 상위, 보통 '.')
판정: 3바퀴 이후 qobjects · toplevel 이 늘지 않으면 정상. 'GC 의존 해제' 가 0 이 아니면 순환 참조로만 풀리는 Qt 객체가 있음."""
import collections
import gc
import os
import sys
import tempfile
import time
import tracemalloc

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
if sys.platform.startswith("linux"):
    os.environ.setdefault("QT_AUDIO_BACKEND", "alsa")
PC = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PC)
sys.path.insert(0, os.path.join(PC, "tests"))
N = max(4, int(sys.argv[2])) if len(sys.argv) > 2 else 20
from pathlib import Path
from PyQt6.QtCore import QObject, QPoint
from PyQt6.QtWidgets import QApplication, QDialog, QMenu, QMessageBox, QInputDialog, QFileDialog
app = QApplication([])
# 모달 창은 띄웠다가 바로 닫힘 (대화상자 만들기 · 지우기 경로만 확인)
QDialog.exec = lambda self: (self.show(), app.processEvents(), self.reject(), 0)[-1]
QMenu.exec = lambda self, *a, **k: (self.popup(QPoint(0, 0)), app.processEvents(), self.close(), None)[-1]
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.No)
QMessageBox.information = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
QMessageBox.warning = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
QMessageBox.about = staticmethod(lambda *a, **k: None)
QMessageBox.critical = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
QInputDialog.getText = staticmethod(lambda *a, **k: ("", False))
QInputDialog.getItem = staticmethod(lambda *a, **k: ("", False))
QInputDialog.getInt = staticmethod(lambda *a, **k: (0, False))
QFileDialog.getOpenFileNames = staticmethod(lambda *a, **k: ([], ""))
QFileDialog.getExistingDirectory = staticmethod(lambda *a, **k: "")
QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: ("", ""))
from conftest import write_wav
home = tempfile.mkdtemp()
music = Path(sys.argv[3]) if len(sys.argv) > 3 else Path(home) / "m"
if len(sys.argv) <= 3:
    for d in range(3):
        (music / f"a{d}").mkdir(parents=True)
        for k in range(6):
            write_wav(music / f"a{d}" / f"{k:02d} 가수{d} - 제목{k}.wav", sec=1.5)
from yamp.core.config import Config
cfg = Config(Path(home)); cfg["topbar_ticker"] = False; cfg["library_folders"] = str(music)
from yamp.app.mainwindow import MainWindow
w = MainWindow(cfg); w.resize(1100, 760); w.show(); app.processEvents()
w.ctrl.play_folder(str(music), True)

from PyQt6.QtCore import QCoreApplication, QEvent
def pump(ms=30):
    t = time.monotonic() + ms / 1000
    while time.monotonic() < t:
        app.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete.value)   # 이벤트 루프 밖이라 deleteLater 직접 처리

def all_qobjects():
    seen = 0
    for tw in app.topLevelWidgets():
        seen += 1 + len(tw.findChildren(QObject))
    return seen + len(app.findChildren(QObject))

TIMES = collections.Counter()
def safe(name, fn):
    t0 = time.monotonic()
    try:
        fn()
    except Exception as e:
        errors[name] = f"{type(e).__name__}: {e}"
    TIMES[name] += time.monotonic() - t0
    if os.environ.get("TRACE"):
        print("  ", name, round(time.monotonic() - t0, 2), flush=True)

errors = {}
themes = ["sunny", "neon", "dark", "mint"]

def one_round(k):
    c = w.ctrl
    safe("next", c.next); pump(40)
    for i in range(w.pages.count()):
        safe("page", lambda i=i: w.go_page(w.pages.widget(i))); pump(5)
    safe("mini", w.toggle_mini_player); pump(5); safe("mini2", w.toggle_mini_player)
    safe("mini_lyrics", w.toggle_mini); pump(5); safe("mini_lyrics2", w.toggle_mini)
    safe("help", lambda: w.show_help_overlay().close())
    safe("quick", w.show_quick_find)
    for tw in app.topLevelWidgets():
        if type(tw).__name__ in ("QuickFind", "HelpOverlay") and tw.isVisible():
            tw.close()
    safe("theme", lambda: (cfg.__setitem__("theme", themes[k % len(themes)]), w.apply_skin()))
    safe("font", lambda: w.set_font_size([9, 10, 11, 12][k % 4]))
    for name in ("show_speed", "show_sleep_menu", "show_lyrics_editor", "show_lyrics_pick", "show_lyrics_diag",
                 "edit_current_tags", "show_screen_info", "show_keys", "show_about", "show_ticker_detail",
                 "show_more_menu", "show_settings_menu", "show_alarm_dialog"):
        if hasattr(w, name):
            safe(name, getattr(w, name)); pump(5)
    safe("search", lambda: (w.libv.search.setText("가수1"), w.libv.reload(), w.libv.search.setText(""), w.libv.reload()))
    safe("grid", lambda: (w.libv.set_view("grid"), pump(5), w.libv.set_view("tree")))
    safe("smart", lambda: __import__("yamp.ui.track_menu", fromlist=["x"]).show_smart_menu(w, c, w.libv.b_smart))
    safe("home", lambda: w.home.refresh())
    safe("folder", lambda: w.folderv.select(str(music / f"a{k % 3}")))
    safe("sections", lambda: (w.set_all_sections(False), w.set_all_sections(True)))
    safe("panel", lambda: (w.toggle_panel("queue") if hasattr(w, "toggle_panel") else None))
    safe("dpr", w.on_dpr_changed)
    safe("menubar", lambda: (w.set_menu_bar(False), w.set_menu_bar(True)))
    safe("seek", lambda: c.seek(500))
    safe("undo", lambda: (c.move(0, 1), c.undo()))
    safe("queue", lambda: (c.play_next([c.current_key()]) if hasattr(c, "current_key") else None))
    safe("lyr", lambda: c.lyricsChanged.emit(None))
    safe("research", lambda: c.research_lyrics())
    pump(60)

gc.disable()                      # 순환 참조로만 풀리는 Qt 객체 찾기: GC 전/후 수 비교
for k in range(3):
    one_round(k); pump(30)
    before = (len(app.topLevelWidgets()), all_qobjects())
    gc.collect(); pump(30)
    after = (len(app.topLevelWidgets()), all_qobjects())
    print("GC 의존 해제: round", k, "toplevel", before[0], "->", after[0], " qobjects", before[1], "->", after[1], flush=True)
gc.enable()
tracemalloc.start()
rows = []
type0 = None
for k in range(N):
    one_round(k)
    if k in (2, N - 1) or k % 5 == 0:
        gc.collect(); pump(50); gc.collect()
        counts = collections.Counter(type(o).__name__ for o in gc.get_objects())
        r = (k, all_qobjects(), len(app.allWidgets()), len(app.topLevelWidgets()), round(tracemalloc.get_traced_memory()[0] / 1e6, 2),
             len(gc.get_objects()))
        rows.append(r)
        print("round %3d  qobjects %5d  widgets %5d  toplevel %3d  pyheap %6.2fMB  pyobjs %7d" % r, flush=True)
        if k == 2:
            type0 = counts; snap0 = tracemalloc.take_snapshot()
growth = collections.Counter({t: counts[t] - type0.get(t, 0) for t in counts})
print("\n파이썬 객체 증가 상위 (round 2 → 끝):")
for t, d in growth.most_common(15):
    if d > 0:
        print(f"  {t:35s} +{d}")
print("\n메모리 증가 상위 줄:")
for st in tracemalloc.take_snapshot().compare_to(snap0, "lineno")[:12]:
    print(" ", st)
tl = collections.Counter(type(t).__name__ for t in app.topLevelWidgets())
print("\n최상위 창:", dict(tl))
print("오류:", errors)
print("느린 동작:", [(k, round(v, 2)) for k, v in TIMES.most_common(8)])
w.ctrl.shutdown()
