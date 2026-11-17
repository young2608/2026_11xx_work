"""장시간 운용 점검 (소크 테스트) — vr0.1.0.007

실제 창을 띄우고 폴더의 곡을 자동으로 넘기며 (곡당 --per 초), 1분마다
메모리(RSS)·파이썬 힙·Qt 객체 수·타이머 수를 log/soak_YYYYmmdd_HHMM.csv 에 기록.
끝나면 처음 대비 증가량을 요약 출력. 숫자가 계속 오르기만 하면 누수 의심.

  python tools/soak.py --folder "D:\\Music" --minutes 60 --per 20
  python tools/soak.py --folder D:/Music --minutes 600 --hidden     (창 최소화 상태로)
"""
import argparse
import csv
import gc
import os
import sys
import time
import tracemalloc
from pathlib import Path

PC = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PC))


def rss_mb() -> float:
    try:
        import psutil
        return psutil.Process().memory_info().rss / 1e6
    except ImportError:
        pass
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        class PMC(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + \
                       [(n, ctypes.c_size_t) for n in ("PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage",
                                                       "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage",
                                                       "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage")]
        c = PMC()
        c.cb = ctypes.sizeof(c)
        ctypes.windll.psapi.GetProcessMemoryInfo(ctypes.windll.kernel32.GetCurrentProcess(), ctypes.byref(c), c.cb)
        return c.WorkingSetSize / 1e6
    try:
        with open("/proc/self/status") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1]) / 1e3
    except OSError:
        pass
    return 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--folder", required=True)
    ap.add_argument("--minutes", type=float, default=30)
    ap.add_argument("--per", type=float, default=20, help="곡당 재생 초")
    ap.add_argument("--hidden", action="store_true", help="창을 최소화한 채로")
    ap.add_argument("--ui", action="store_true", help="UI 조작도 반복 (탭 전환·블럭 접기·사운드 프리셋·우클릭 메뉴)")
    ap.add_argument("--sample-s", type=float, default=60, help="기록 간격(초)")
    a = ap.parse_args()

    from PyQt6.QtCore import QObject, QTimer
    from PyQt6.QtWidgets import QApplication
    from yamp.core.config import Config
    from yamp.app.mainwindow import MainWindow

    app = QApplication(sys.argv)
    cfg = Config(Path(os.environ.get("YAMP_HOME", PC)))
    w = MainWindow(cfg)
    w.show()
    if a.hidden:
        w.showMinimized()
    w.ctrl.play_folder(a.folder, True)
    tracemalloc.start()
    out = cfg.path_of("log_dir") / time.strftime("soak_%Y%m%d_%H%M.csv")
    out.parent.mkdir(parents=True, exist_ok=True)
    f = open(out, "w", newline="", encoding="utf-8")
    wr = csv.writer(f)
    wr.writerow(["min", "rss_mb", "py_heap_mb", "qobjects", "qtimers_active", "tracks_played", "engine",
                 "toplevel", "py_objects"])          # v020 (f40 L6): 메인 창 밖 창(대화상자 · 메뉴 · 미니 창) 수 · 파이썬 객체 수
    t0 = time.monotonic()
    rows = []
    played = [0]

    def sample():
        if f.closed:
            return
        gc.collect()
        objs = w.findChildren(QObject)
        timers = sum(1 for o in objs if isinstance(o, QTimer) and o.isActive())
        r = [round((time.monotonic() - t0) / 60, 1), round(rss_mb(), 1),
             round(tracemalloc.get_traced_memory()[0] / 1e6, 2), len(objs), timers, played[0],
             getattr(w.ctrl.engine, "name", "?"), len(app.topLevelWidgets()), len(gc.get_objects())]
        rows.append(r)
        wr.writerow(r)
        f.flush()
        print("soak", r, flush=True)

    snap0 = []

    def nxt():
        played[0] += 1
        w.ctrl.next()
        if a.ui:
            ui_step(played[0])

    def ui_step(k):
        """화면 조작 반복 — 메뉴·대화상자·접기 누수 확인용 (vr0.1.0.008)"""
        from PyQt6.QtCore import QPoint
        from PyQt6.QtWidgets import QMenu
        from yamp.ui.qtutil import exec_menu
        if w.tabs is not None:                     # 클래식 배치: 탭
            w.tabs.setCurrentIndex(k % w.tabs.count())
        else:                                      # 단순 배치(v009 기본): 페이지 — v019 재검: 전에는 여기서 AttributeError
            w.go_page(w.pages.widget(k % w.pages.count()))
        secs = w.sections()
        if secs:
            secs[k % len(secs)].toggle()
        if k % 3 == 0:
            names = list(__import__("yamp.domain.dsp", fromlist=["PRESETS"]).PRESETS)
            w.soundv.set_preset(names[k % len(names)])
        m = QMenu(w)
        m.addAction("x")
        QTimer.singleShot(5, m.close)
        exec_menu(m, QPoint(0, 0))

    def first_snapshot():
        snap0.append(tracemalloc.take_snapshot())

    def stop():
        for t in w.findChildren(QTimer):           # 곡 넘기기·기록 타이머 먼저 정지
            if t.parent() is w:
                t.stop()
        sample()
        f.close()
        a0, a1 = rows[1] if len(rows) > 1 else rows[0], rows[-1]
        print(f"\n결과: {out}\n  RSS {a0[1]} → {a1[1]} MB, 파이썬 힙 {a0[2]} → {a1[2]} MB, "
              f"Qt 객체 {a0[3]} → {a1[3]}, 동작 타이머 {a0[4]} → {a1[4]}, 곡 {a1[5]}, 엔진 {a1[6]}, "
              f"최상위 창 {a0[7]} → {a1[7]}, 파이썬 객체 {a0[8]} → {a1[8]}")
        if snap0:                                  # 파이썬 메모리가 가장 많이 늘어난 곳 10개 (누수 위치 찾기)
            top = tracemalloc.take_snapshot().compare_to(snap0[0], "lineno")[:10]
            txt = "\n".join(str(x) for x in top)
            print("  파이썬 메모리 증가 상위:\n" + txt)
            out.with_suffix(".top.txt").write_text(txt, encoding="utf-8")
        w.quit_app()
        app.quit()

    QTimer(w, interval=int(a.per * 1000), timeout=nxt).start()
    QTimer(w, interval=int(a.sample_s * 1000), timeout=sample).start()
    QTimer.singleShot(3000, sample)
    QTimer.singleShot(int(min(a.sample_s, 60) * 1000) + 500, first_snapshot)   # 시작 직후 할당은 빼고 비교
    QTimer.singleShot(int(a.minutes * 60_000), stop)
    sys.exit(app.exec())


if __name__ == "__main__":
    os.environ.setdefault("YAMP_HOME", str(PC))
    main()
