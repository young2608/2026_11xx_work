"""yMp3Player (yamp 패키지) — Winamp 컨셉 음악 플레이어 + 싱크 가사 (PC, PyQt6).

사용:
  python main.py [파일/폴더 ...]
  python main.py --lyrics-test "곡.mp3"     가사 진단 (태그 → 검색어 → 공급자별 응답 → 후보 점수, log/ 에 저장)
  python main.py --alsong-test "곡.mp3"     (= --lyrics-test)
  python main.py --ticker-test [KRW-XRP]    업비트 시세 1회 조회 (상단 바 진단, v012)
  python main.py --lrclib-test "아티스트" "제목"
"""
import sys

from yamp.core.version import title_label


def _lyrics_test(path):
    from yamp.core.config import Config
    from yamp.data.tags import read_tags
    from yamp.lyrics import diag
    from yamp.lyrics.providers.base import Query
    cfg = Config()
    info = read_tags(path)
    text, saved = diag.run(cfg, Query(path, info.title, info.artist, info.album, info.duration, info.lyrics),
                           cfg.path_of("log_dir"))
    print(text)
    if saved:
        print("저장:", saved)
    return 0 if "결과: 찾음" in text else 1


def _ticker_test(market):
    import time
    from yamp.data import upbit
    from yamp.domain import ticker as T
    try:
        qs, server_ms = upbit.fetch(T.parse_markets(market), 5)
    except Exception as e:  # noqa
        print("업비트 시세 조회 실패:", e)
        return 1
    now = int(time.time() * 1000)
    for q in qs:
        print(T.tooltip(q, now, now))
    print("PC 시각 - 서버 시각:", T.clock_skew_s(server_ms, now), "초 ·", T.kst_label(now))
    return 0 if qs else 1


def _lrclib_test(artist, title):
    from yamp.lyrics.providers.base import Query
    from yamp.lyrics.providers.lrclib import LrclibProvider
    txt = LrclibProvider(8).fetch(Query("", title, artist))
    print("LRCLIB:", "성공" if txt else "실패")
    if txt:
        print("\n".join(txt.splitlines()[:8]))
    return 0 if txt else 1


def main():
    args = sys.argv[1:]
    if args[:1] in (["--lyrics-test"], ["--alsong-test"]) and len(args) >= 2:
        return _lyrics_test(args[1])
    if args[:1] == ["--lrclib-test"] and len(args) >= 3:
        return _lrclib_test(args[1], args[2])
    if args[:1] == ["--ticker-test"]:
        return _ticker_test(args[1] if len(args) > 1 else "KRW-XRP")
    if args[:1] in (["--version"], ["-V"]):
        print(title_label())
        return 0

    from PyQt6.QtWidgets import QApplication
    from yamp.core import logger
    from yamp.core.config import Config
    from yamp.app.mainwindow import MainWindow

    from PyQt6.QtGui import QGuiApplication
    from yamp.ui import skin as skinmod

    cfg = Config()                     # exe(소스: pc/) 폴더의 config.txt 읽기 (없으면 생성) — v016: 글꼴 엔진 때문에 앱보다 먼저
    # v016 (f29 G3 · G5): 분수 배율(125 · 150 %)을 그대로 (흐린 확대 없음) · Windows 글꼴 엔진 선택 (진단용)
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(skinmod.rounding_policy(str(cfg["ui_scale_rounding"])))   # v017
    argv = list(sys.argv)
    if "-platform" not in argv:
        argv[1:1] = skinmod.qt_platform_args(str(cfg["font_engine"]))
    app = QApplication(argv)
    app.setApplicationName("yMp3Player")
    logger.setup(cfg)                  # log/NN__YYYY__MMDD.txt rotation
    w = MainWindow(cfg)
    w.ctrl.restore_session()
    files = [a for a in args if not a.startswith("-")]
    if files:
        w.ctrl.add_paths(files, play_first=True)
    w.show()
    rc = app.exec()
    logger.shutdown()
    return rc


if __name__ == "__main__":
    sys.exit(main())
