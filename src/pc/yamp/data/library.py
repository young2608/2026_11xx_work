# -*- coding: utf-8 -*-
"""
라이브러리 DB (SQLite, data/library.db) — 곡 정보 · 재생 기록 · 좋아요/별점 · 사용자 태그.
Android data/LibraryDb.kt 와 같은 스키마. 추천(domain/recommend.py) 의 입력을 만든다.

key = 파일 경로(소문자) MD5 앞 12자리 (가사 캐시 키와 같음)
스레드: 한 연결 + Lock (태그 스캔 스레드와 UI 스레드가 함께 사용)
"""
import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path

from ..core.keys import track_key  # noqa: F401  (v019 R2: 가사 모듈 의존 제거, 이전 import 호환)
from ..domain.recommend import TrackStat

SCHEMA = """
CREATE TABLE IF NOT EXISTS tracks(
  key TEXT PRIMARY KEY, path TEXT, title TEXT, artist TEXT, album TEXT, genre TEXT, year TEXT,
  folder TEXT, duration_ms INTEGER DEFAULT 0, added_at INTEGER DEFAULT 0,
  liked INTEGER DEFAULT 0, rating INTEGER DEFAULT 0, play_count INTEGER DEFAULT 0,
  skip_count INTEGER DEFAULT 0, last_played INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS plays(
  id INTEGER PRIMARY KEY AUTOINCREMENT, key TEXT, started_at INTEGER, listened_ms INTEGER,
  duration_ms INTEGER, completed INTEGER, skipped INTEGER, session_id INTEGER);
CREATE INDEX IF NOT EXISTS plays_key ON plays(key);
CREATE INDEX IF NOT EXISTS plays_time ON plays(started_at);
CREATE TABLE IF NOT EXISTS tags(key TEXT, tag TEXT, PRIMARY KEY(key, tag));
CREATE TABLE IF NOT EXISTS folders(path TEXT PRIMARY KEY, pinned INTEGER DEFAULT 0, last_played INTEGER DEFAULT 0);
"""
# vr0.1.0.006 추가 열 (기존 DB 는 ALTER TABLE 로 추가)
EXTRA_COLS = (("cue_no", "INTEGER DEFAULT 0"), ("start_ms", "INTEGER DEFAULT 0"), ("end_ms", "INTEGER DEFAULT -1"),
              ("cue_path", "TEXT DEFAULT ''"), ("codec", "TEXT DEFAULT ''"), ("bits", "INTEGER DEFAULT 0"),
              ("samplerate", "INTEGER DEFAULT 0"))


# 장시간 운용 (vr0.1.0.007): 재생 기록 표가 끝없이 커지지 않게
PLAYS_KEEP_DAYS = 730        # 2년 지난 기록은 정리
PLAYS_MAX_ROWS = 100_000     # 그래도 많으면 오래된 것부터
CO_PAIRS_RECENT = 20_000     # '같이 들은 곡' 계산은 최근 기록만
WAL_LIMIT_BYTES = 4 * 1024 * 1024   # v020 (f40 L1): WAL 파일 최대 유지 크기 (없으면 한 번 커진 -wal 파일이 그대로 남음)


def is_network_path(path: str) -> bool:
    """네트워크 드라이브(\\\\서버\\공유, 연결된 네트워크 드라이브 문자)인지 — SQLite WAL 은 네트워크 파일 시스템에서 쓰면 안 됨"""
    p = os.path.abspath(str(path))
    if p.startswith(("\\\\", "//")):
        return True
    if os.name == "nt" and len(p) >= 2 and p[1] == ":":
        try:
            import ctypes
            return ctypes.windll.kernel32.GetDriveTypeW(p[:2] + "\\") == 4      # DRIVE_REMOTE
        except Exception:  # noqa
            return False
    return False


def apply_pragmas(db, wal: bool = True) -> str:
    """v018 (f33 P3): 커밋 속도 — WAL(쓰기 중에도 읽기 가능, 커밋마다 DB 파일 전체 동기화 안 함)
    + synchronous=NORMAL(WAL 에서는 정전 시 마지막 커밋 몇 개만 잃을 수 있고 DB 는 깨지지 않음).
    재생 기록 · 곡 갱신 · 좋아요 같은 UI 스레드 커밋이 디스크 동기화(fsync)를 기다리는 시간을 줄임.
    WAL 을 못 쓰는 곳(일부 네트워크 드라이브)은 기본(DELETE)으로 둠. 반환: 실제 journal_mode"""
    mode = "delete"
    try:
        if wal:
            mode = str(db.execute("PRAGMA journal_mode=WAL").fetchone()[0]).lower()
            db.execute("PRAGMA synchronous=NORMAL")
        else:                                           # WAL 은 DB 파일에 남음 → 네트워크 위치면 기본으로 되돌림
            mode = str(db.execute("PRAGMA journal_mode=DELETE").fetchone()[0]).lower()
        db.execute("PRAGMA temp_store=MEMORY")
        db.execute("PRAGMA cache_size=-8000")          # 8MB 페이지 캐시 (기본 2MB)
        db.execute(f"PRAGMA journal_size_limit={WAL_LIMIT_BYTES}")   # v020 (f40 L1): 체크포인트 뒤 -wal 파일을 이 크기로 줄임
    except sqlite3.Error:
        pass
    return mode


class Library:
    def __init__(self, path):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._batch = 0
        self.db = sqlite3.connect(self.path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        with self._lock:
            self.journal = apply_pragmas(self.db, wal=not is_network_path(self.path))   # v018 (f33 P3): WAL · synchronous=NORMAL
            self.db.executescript(SCHEMA)
            have = {r[1] for r in self.db.execute("PRAGMA table_info(tracks)")}
            for name, decl in EXTRA_COLS:
                if name not in have:
                    self.db.execute(f"ALTER TABLE tracks ADD COLUMN {name} {decl}")
            self.db.commit()

    def close(self):
        with self._lock:
            self.db.commit()
            try:
                self.db.execute("PRAGMA optimize")     # 통계 갱신 (다음 실행 쿼리 계획)
            except sqlite3.Error:
                pass
            self.db.close()

    # ---------------------------------------------------------- 커밋 묶기
    def _commit(self):
        """batch() 안에서는 커밋을 미룸 (태그 스캔 등 대량 저장 시 디스크 쓰기 횟수 줄임)"""
        if not self._batch:
            self.db.commit()

    def commit(self):
        with self._lock:
            self.db.commit()

    @contextmanager
    def batch(self):
        with self._lock:
            self._batch += 1
        try:
            yield self
        finally:
            with self._lock:
                self._batch -= 1
                if not self._batch:
                    self.db.commit()

    def vacuum_if_needed(self, ratio: float = 0.25, min_pages: int = 256) -> bool:
        """정리로 빈 페이지가 전체의 25% 넘으면 VACUUM (파일 크기 줄임) — vr0.1.0.008"""
        with self._lock:
            pages = self.db.execute("PRAGMA page_count").fetchone()[0]
            free = self.db.execute("PRAGMA freelist_count").fetchone()[0]
            if pages < min_pages or free < pages * ratio or self._batch:
                return False
            self.db.commit()
            self.db.execute("VACUUM")
            return True

    def checkpoint(self) -> bool:
        """v020 (f40 L1): WAL 내용을 본 DB 에 합치고 -wal 파일을 비움 (장시간 실행 중 하루 한 번 정리 때). WAL 아니면 False"""
        if getattr(self, "journal", "") != "wal":
            return False
        with self._lock:
            if self._batch:
                return False
            self.db.commit()
            try:
                self.db.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
                return True
            except sqlite3.Error:
                return False

    # ---------------------------------------------------------- 정리 (시작할 때 + 실행 중 하루 한 번, v020)
    def prune_plays(self, now=None, keep_days=PLAYS_KEEP_DAYS, max_rows=PLAYS_MAX_ROWS) -> int:
        now = int(now or time.time())
        with self._lock:
            n = self.db.execute("DELETE FROM plays WHERE started_at < ?", (now - keep_days * 86400,)).rowcount
            total = self.db.execute("SELECT COUNT(*) FROM plays").fetchone()[0]
            if total > max_rows:
                n += self.db.execute("DELETE FROM plays WHERE id IN (SELECT id FROM plays ORDER BY id LIMIT ?)",
                                     (total - max_rows,)).rowcount
            self.db.commit()
        return n

    # ---------------------------------------------------------- 곡
    def upsert(self, path: str, title="", artist="", album="", genre="", year="", duration_s=0.0, now=None,
               uid=None, cue=(0, 0, -1, ""), codec="", bits=0, sr=0):
        """uid: CUE 트랙이면 'path|cue:n' (키), cue = (번호, 시작ms, 끝ms, cue 경로)"""
        k = track_key(uid or path)
        now = int(now or time.time())
        cno, cs, ce, cp = cue
        with self._lock:
            self.db.execute(
                """INSERT INTO tracks(key, path, title, artist, album, genre, year, folder, duration_ms, added_at,
                                      cue_no, start_ms, end_ms, cue_path, codec, bits, samplerate)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(key) DO UPDATE SET path=excluded.path, title=excluded.title, artist=excluded.artist,
                   album=excluded.album, folder=excluded.folder,
                   genre=CASE WHEN excluded.genre<>'' THEN excluded.genre ELSE genre END,
                   year=CASE WHEN excluded.year<>'' THEN excluded.year ELSE year END,
                   duration_ms=CASE WHEN excluded.duration_ms>0 THEN excluded.duration_ms ELSE duration_ms END,
                   cue_no=excluded.cue_no, start_ms=excluded.start_ms, end_ms=excluded.end_ms, cue_path=excluded.cue_path,
                   codec=CASE WHEN excluded.codec<>'' THEN excluded.codec ELSE codec END,
                   bits=CASE WHEN excluded.bits>0 THEN excluded.bits ELSE bits END,
                   samplerate=CASE WHEN excluded.samplerate>0 THEN excluded.samplerate ELSE samplerate END""",
                (k, path, title, artist, album, genre, year, os.path.dirname(path), int(duration_s * 1000), now,
                 int(cno), int(cs), int(ce), cp, codec, int(bits or 0), int(sr or 0)))
            self._commit()
        return k

    # ---------------------------------------------------------- 폴더 (F8 고정 · 마지막 재생)
    def pin_folder(self, path, pinned: bool):
        with self._lock:
            self.db.execute("INSERT INTO folders(path, pinned) VALUES(?,?) ON CONFLICT(path) DO UPDATE SET pinned=excluded.pinned",
                            (path, 1 if pinned else 0))
            self._commit()

    def pinned_folders(self) -> list[str]:
        with self._lock:
            return [r[0] for r in self.db.execute("SELECT path FROM folders WHERE pinned=1 ORDER BY path")]

    def folder_played(self, path, now=None):
        with self._lock:
            self.db.execute("INSERT INTO folders(path, last_played) VALUES(?,?) ON CONFLICT(path) DO UPDATE SET last_played=excluded.last_played",
                            (path, int(now or time.time())))
            self._commit()

    def has(self, path) -> bool:
        with self._lock:
            return self.db.execute("SELECT 1 FROM tracks WHERE key=?", (track_key(path),)).fetchone() is not None

    def track(self, key):
        with self._lock:
            r = self.db.execute("SELECT * FROM tracks WHERE key=?", (key,)).fetchone()
        return dict(r) if r else None

    def all_tracks(self) -> list[dict]:
        with self._lock:
            return [dict(r) for r in self.db.execute("SELECT * FROM tracks ORDER BY artist, album, title")]

    def remove_missing(self, stop=None) -> int:
        """없어진 파일의 곡을 지움. stop (v032 f60 P7): 참이 되면 (앱 종료) 중간에 그만두고 아무것도 지우지 않음"""
        with self._lock:
            rows = self.db.execute("SELECT key, path FROM tracks").fetchall()
        gone = []
        for i, (k, path) in enumerate(rows):                            # 파일 확인은 잠금 밖 (UI 스레드가 기다리지 않게)
            if stop is not None and i % 256 == 0 and stop():
                return 0
            if not os.path.exists(path):
                gone.append((k,))
        if gone:                                                        # v018: 한 번에 지움 (executemany)
            with self._lock:
                self.db.executemany("DELETE FROM tracks WHERE key=?", gone)
                self._commit()
        return len(gone)

    # ---------------------------------------------------------- 좋아요 · 별점 · 태그
    def set_liked(self, key, liked: bool):
        with self._lock:
            self.db.execute("UPDATE tracks SET liked=? WHERE key=?", (1 if liked else 0, key))
            self._commit()

    def liked(self, key) -> bool:
        with self._lock:
            r = self.db.execute("SELECT liked FROM tracks WHERE key=?", (key,)).fetchone()
        return bool(r and r[0])

    def set_rating(self, key, rating: int):
        with self._lock:
            self.db.execute("UPDATE tracks SET rating=? WHERE key=?", (max(0, min(5, int(rating))), key))
            self._commit()

    def add_tag(self, key, tag):
        with self._lock:
            self.db.execute("INSERT OR IGNORE INTO tags(key, tag) VALUES(?,?)", (key, tag))
            self._commit()

    def remove_tag(self, key, tag):
        with self._lock:
            self.db.execute("DELETE FROM tags WHERE key=? AND tag=?", (key, tag))
            self._commit()

    def tags_of(self, key) -> list[str]:
        with self._lock:
            return [r[0] for r in self.db.execute("SELECT tag FROM tags WHERE key=? ORDER BY tag", (key,))]

    # ---------------------------------------------------------- 재생 기록
    def record_play(self, key, started_at, listened_ms, duration_ms, completed, skipped, session_id):
        with self._lock:
            self.db.execute("INSERT INTO plays(key, started_at, listened_ms, duration_ms, completed, skipped, session_id)"
                            " VALUES(?,?,?,?,?,?,?)",
                            (key, int(started_at), int(listened_ms), int(duration_ms), int(completed), int(skipped),
                             int(session_id)))
            self.db.execute("UPDATE tracks SET play_count=play_count+?, skip_count=skip_count+?, "
                            "last_played=CASE WHEN ? THEN ? ELSE last_played END WHERE key=?",
                            (int(bool(completed)), int(bool(skipped)), int(listened_ms > 0), int(started_at), key))
            self._commit()

    def clear_history(self):
        with self._lock:
            self.db.execute("DELETE FROM plays")
            self.db.execute("UPDATE tracks SET play_count=0, skip_count=0, last_played=0")
            self._commit()

    def last_played_key(self):
        with self._lock:
            r = self.db.execute("SELECT key FROM plays WHERE listened_ms>0 ORDER BY started_at DESC, id DESC LIMIT 1").fetchone()
        return r[0] if r else None

    def recent_keys(self, now, within_s=3600) -> list[str]:
        with self._lock:
            return [r[0] for r in self.db.execute("SELECT DISTINCT key FROM plays WHERE started_at>=?", (int(now) - within_s,))]

    def co_pairs(self) -> dict:
        """같은 세션에서 연달아 들은 곡 쌍 → 횟수"""
        out = {}
        with self._lock:
            rows = self.db.execute(
                "SELECT key, session_id FROM (SELECT key, session_id, started_at, id FROM plays WHERE listened_ms>0 "
                "ORDER BY id DESC LIMIT ?) ORDER BY session_id, started_at, id", (CO_PAIRS_RECENT,)).fetchall()
        prev = None
        for k, sid in rows:
            if prev and prev[1] == sid and prev[0] != k:
                out[(prev[0], k)] = out.get((prev[0], k), 0) + 1
            prev = (k, sid)
        return out

    def stats(self, now=None) -> list[TrackStat]:
        now = int(now or time.time())
        with self._lock:
            rec = {r[0]: r[1] for r in self.db.execute(
                "SELECT key, SUM(completed) FROM plays WHERE started_at>=? GROUP BY key", (now - 30 * 86400,))}
            tg = {}
            for k, t in self.db.execute("SELECT key, tag FROM tags"):
                tg.setdefault(k, []).append(t)
            rows = self.db.execute("SELECT * FROM tracks").fetchall()
        return [TrackStat(r["key"], r["artist"] or "", r["album"] or "", r["genre"] or "", r["folder"] or "",
                          bool(r["liked"]), r["rating"] or 0, r["play_count"] or 0, r["skip_count"] or 0,
                          r["last_played"] or 0, r["added_at"] or 0, int(rec.get(r["key"], 0) or 0),
                          tuple(tg.get(r["key"], ()))) for r in rows]

    # ---------------------------------------------------------- 폴더 스캔
    def scan(self, folders, read_tags, stop=lambda: False) -> int:
        """folders 의 새 파일만 태그 읽어 추가. 반환: 추가 수"""
        from .playlist import scan_tracks
        with self.batch():
            return self._scan(folders, read_tags, stop, scan_tracks)

    def known_keys(self) -> set:
        """v018 (f33 P2): DB 에 있는 곡 키 전체 (재스캔 때 곡마다 SELECT 하지 않게)"""
        with self._lock:
            return {r[0] for r in self.db.execute("SELECT key FROM tracks")}

    def _scan(self, folders, read_tags, stop, scan_tracks) -> int:
        n = 0
        known = self.known_keys()
        for d in folders:
            if not os.path.isdir(d):
                continue
            for t in scan_tracks(d):
                if stop():
                    return n
                key = track_key(t.uid)
                if key in known:
                    continue
                known.add(key)                  # 겹치는 라이브러리 폴더(D:\Music · D:\Music\Pop)에서 같은 곡 두 번 읽지 않게
                i = read_tags(t.path)
                if t.cue_no:
                    self.upsert(t.path, t.title, t.artist, t.album, i.genre, i.year, t.duration, uid=t.uid,
                                cue=(t.cue_no, t.start_ms, t.end_ms, t.cue_path), codec=i.codec, bits=i.bits, sr=i.samplerate)
                else:
                    self.upsert(t.path, i.title, i.artist, i.album, i.genre, i.year, i.duration,
                                codec=i.codec, bits=i.bits, sr=i.samplerate)
                n += 1
                if n % 200 == 0:
                    self.commit()
        return n
