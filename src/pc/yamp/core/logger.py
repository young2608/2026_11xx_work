# -*- coding: utf-8 -*-
"""
로그 파일 저장 (rotation) — 비동기 (QueueHandler → 백그라운드 스레드)

파일명 : log/NN__YYYY__MMDD.txt     예) log/00__2026__0716.txt
  NN   : 00 ~ (log_max_files-1) 순환 번호 (기본 8개 → 00..07)
  날짜 : 그 파일을 새로 연 날짜 (파일명엔 시각 없음, 각 줄에 시각 기록)

rotation 규칙
  - 현재 파일이 log_max_size_kb 를 넘으면 → 다음 번호로 새 파일
  - 날짜가 바뀌면                          → 다음 번호로 새 파일
  - 다음 번호의 기존 파일(가장 오래된 것)은 삭제 → 항상 최대 N 개 유지
  - 재시작 시: 가장 최근 파일이 오늘 날짜이고 크기 여유가 있으면 이어서 기록

성능: UI 스레드는 큐에 넣기만 함. flush 는 WARNING 이상 / 0.5초 경과 / 조용해지면 0.5초 뒤
설정: config.txt [log] log_level, log_dir, log_max_size_kb, log_max_files
"""
import atexit
import datetime
import logging
import logging.handlers
import os
import queue
import re
import sys
import threading
import time

_NAME_RE = re.compile(r"^(\d{2})__(\d{4})__(\d{4})\.txt$")
LOG_FORMAT = "%(asctime)s.%(msecs)03d [%(levelname)-5s] %(name)s: %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
FLUSH_SEC = 0.5


class RingFileHandler(logging.Handler):
    def __init__(self, log_dir, max_bytes=1024 * 1024, max_files=8, today=None):
        super().__init__()
        self.log_dir = str(log_dir)
        self.max_bytes = max(4096, int(max_bytes))
        self.max_files = max(1, min(int(max_files), 100))
        self._today = today or datetime.date.today      # 테스트에서 날짜 주입
        self._lock = threading.RLock()
        self._fp = None
        self._idx = 0
        self._day = None
        self._size = 0
        self._last_flush = 0.0
        self._timer = None
        os.makedirs(self.log_dir, exist_ok=True)
        self._open_initial()

    @staticmethod
    def file_name(idx, day):
        return f"{idx:02d}__{day:%Y}__{day:%m%d}.txt"

    def _scan(self):
        files = []
        for n in os.listdir(self.log_dir):
            m = _NAME_RE.match(n)
            if m:
                p = os.path.join(self.log_dir, n)
                files.append((os.path.getmtime(p), int(m.group(1)), n, p))
        return sorted(files)

    def _open_initial(self):
        today = self._today()
        files = self._scan()
        if files:
            _, idx, name, path = files[-1]
            if name == self.file_name(idx, today) and os.path.getsize(path) < self.max_bytes \
                    and idx < self.max_files:
                self._idx, self._day = idx, today
                self._fp = open(path, "a", encoding="utf-8")
                self._size = os.path.getsize(path)
                return
            self._idx = (idx + 1) % self.max_files
        else:
            self._idx = 0
        self._open_new(today)

    def _open_new(self, day):
        if self._fp:
            try:
                self._fp.close()
            except OSError:
                pass
        for _, idx, _, path in self._scan():          # 같은 번호 = 가장 오래된 파일 삭제
            if idx == self._idx or idx >= self.max_files:
                try:
                    os.remove(path)
                except OSError:
                    pass
        self._day = day
        self._size = 0
        self._fp = open(os.path.join(self.log_dir, self.file_name(self._idx, day)), "a", encoding="utf-8")

    def _rotate(self, day):
        self._idx = (self._idx + 1) % self.max_files
        self._open_new(day)

    @property
    def current_path(self):
        return self._fp.name if self._fp else ""

    def emit(self, record):
        try:
            msg = self.format(record) + "\n"
            n = len(msg.encode("utf-8"))
            with self._lock:
                today = self._today()
                if self._day != today or (self._size > 0 and self._size + n > self.max_bytes):
                    self._rotate(today)
                self._fp.write(msg)
                self._size += n
                now = time.monotonic()
                if record.levelno >= logging.WARNING or now - self._last_flush >= FLUSH_SEC:
                    self._fp.flush()
                    self._last_flush = now
                elif self._timer is None:
                    self._timer = threading.Timer(FLUSH_SEC, self._timed_flush)
                    self._timer.daemon = True
                    self._timer.start()
        except Exception:  # noqa
            self.handleError(record)

    def _timed_flush(self):
        with self._lock:
            self._timer = None
        self.flush()

    def flush(self):
        with self._lock:
            if self._fp:
                try:
                    self._fp.flush()
                except OSError:
                    pass

    def close(self):
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None
            if self._fp:
                self._fp.close()
                self._fp = None
        super().close()


_handler: RingFileHandler | None = None
_listener = None


def setup(cfg):
    """config.txt 값으로 루트 로거 구성. 반환: RingFileHandler (실패 시 None)"""
    global _handler, _listener
    from ..version import APP_NAME, full
    shutdown()
    level = getattr(logging, str(cfg["log_level"]).upper(), logging.INFO)
    root = logging.getLogger()
    root.setLevel(level)
    for h in list(root.handlers):
        root.removeHandler(h)
    fmt = logging.Formatter(LOG_FORMAT, DATE_FORMAT)
    sinks = []
    try:
        _handler = RingFileHandler(cfg.path_of("log_dir"), int(cfg["log_max_size_kb"]) * 1024, int(cfg["log_max_files"]))
        _handler.setFormatter(fmt)
        sinks.append(_handler)
    except OSError as e:
        print("log file open failed:", e, file=sys.stderr)
        _handler = None
    if sys.stderr is not None and not getattr(sys, "frozen", False):
        sh = logging.StreamHandler()
        sh.setFormatter(fmt)
        sinks.append(sh)
    if sinks:
        q = queue.SimpleQueue()
        root.addHandler(logging.handlers.QueueHandler(q))
        _listener = logging.handlers.QueueListener(q, *sinks, respect_handler_level=False)
        _listener.start()

    def _excepthook(t, v, tb):
        logging.getLogger("crash").critical("unhandled exception", exc_info=(t, v, tb))
        flush()
        sys.__excepthook__(t, v, tb)
    sys.excepthook = _excepthook
    lg = logging.getLogger("yamp")
    lg.info("===== start %s %s =====", APP_NAME, full())
    lg.info("config: %s  data: %s  log: %s", cfg.path, cfg.data_dir, _handler.current_path if _handler else "-")
    for w in getattr(cfg, "warnings", []):
        lg.warning(w)
    return _handler


def flush():
    if _handler:
        _handler.flush()


def shutdown():
    global _handler, _listener
    if _listener:
        try:
            _listener.stop()
        except Exception:  # noqa
            pass
        _listener = None
    if _handler:
        try:
            _handler.close()
        except Exception:  # noqa
            pass
        _handler = None


atexit.register(shutdown)
