# -*- coding: utf-8 -*-
"""가사 캐시 · 못 찾은 곡 기억 (vr0.1.0.019 R3 — lyrics/service.py 에서 나눔, Qt 비의존)

LyricsCache    data/lyrics/<가수 - 제목>__<키>.lrc (폴더 색인 메모리 보관)
NotFoundStore  data/lyrics/_notfound.json {키: 확인 시각} — lyrics_notfound_days 동안 다시 묻지 않음 (f18 L6)
"""
import json
import logging
import os
import re
import threading
import time
from pathlib import Path

from ..core.keys import cache_key
from .providers.base import Query
from .providers.local import read_text_any

log = logging.getLogger("yamp.lyrics")


def _safe(s: str) -> str:
    return re.sub(r'[\\/:*?"<>|\r\n\t]+', "_", s or "").strip()[:60]


def source_of(p: Path) -> str:
    """캐시 파일 첫 줄 [re:yAmp/<출처>] 의 출처 (읽기 실패 · 표시 없음 = '')"""
    try:
        with open(p, "rb") as f:
            head = f.read(64).decode("utf-8", "replace")
    except OSError:
        return ""
    m = re.match(r"\s*\[re:yAmp/(\w+)\]", head)
    return m.group(1) if m else ""


class LyricsCache:
    """가사 캐시 폴더. 파일 이름 '<가수 - 제목>__<키>.lrc'.

    vr0.1.0.007: 곡마다 폴더 전체를 glob 하던 것을 '키 → 파일' 색인(처음 한 번만 폴더 읽음)으로 바꿈.
    캐시가 수천 개가 되어도 곡 전환 시간이 늘지 않음. 여러 스레드(가사 작업 2개)에서 쓰므로 Lock.
    """

    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._index: dict[str, Path] | None = None
        self._dups: dict[str, list] = {}         # v020 (f40 L4): 같은 키 파일이 여러 개(예전 이름 등)면 여기 — remove 가 함께 지움

    def _idx(self) -> dict:
        if self._index is None:
            idx = {}
            for p in self.root.glob("*__*.lrc"):
                k = p.stem.rsplit("__", 1)[-1]
                if k in idx:
                    self._dups.setdefault(k, []).append(idx[k])
                idx[k] = p
            self._index = idx
        return self._index

    def path_for(self, q: Query) -> Path:
        name = f"{_safe(q.artist)} - {_safe(q.title)}" if q.artist else (_safe(q.title) or "track")
        return self.root / f"{name}__{cache_key(q.path)}.lrc"

    def get(self, q: Query) -> tuple[str, str] | None:
        with self._lock:
            p = self._idx().get(cache_key(q.path))
        if p is None or not p.exists():
            return None
        try:
            os.utime(p)                          # v022 (N3): 최근 사용 표시 → trim 이 오래 안 쓴 것부터 지움
        except OSError:
            pass
        text = read_text_any(p)
        m = re.search(r"^\[re:yAmp/(\w+)\]", text, re.M)
        return text, (m.group(1) if m else "cache")

    def put(self, q: Query, text: str, source: str):
        old = self.get(q)
        if old and old[1] == "user" and source != "user":      # 직접 편집한 가사는 덮기 전에 백업 (vr0.1.0.011)
            try:
                (self.root / f"{cache_key(q.path)}.user.bak").write_text(old[0], encoding="utf-8")
            except OSError as e:
                log.warning("user lyric backup: %s", e)
        self.remove(q)
        body = f"[re:yAmp/{source}]\n" + text.strip() + "\n"
        p = self.path_for(q)
        p.write_text(body, encoding="utf-8")
        with self._lock:
            self._idx()[cache_key(q.path)] = p

    def trim(self, max_files: int, keep_sources=("user",)) -> int:
        """v022 (N3): 캐시 파일이 max_files 를 넘으면 오래 안 쓴(수정 · 사용 시각) 것부터 지움 — 하루 한 번 정리 작업에서.
        직접 편집한 가사(source=user)는 지우지 않음. 0 이하 = 제한 없음. 반환: 지운 수"""
        if max_files <= 0:
            return 0
        with self._lock:
            items = list(self._idx().items())
        if len(items) <= max_files:
            return 0
        rows = []
        for k, p in items:
            try:
                rows.append((p.stat().st_mtime, k, p))
            except OSError:
                with self._lock:
                    if self._idx().get(k) == p:
                        self._idx().pop(k, None)
        rows.sort()
        over, n = len(rows) - max_files, 0
        for _mt, k, p in rows:
            if n >= over:
                break
            if source_of(p) in keep_sources:
                continue
            try:
                p.unlink()
            except OSError:
                continue
            with self._lock:
                if self._idx().get(k) == p:
                    self._idx().pop(k, None)
            n += 1
        return n

    def remove(self, q: Query):
        k = cache_key(q.path)
        with self._lock:
            p = self._idx().pop(k, None)
            extra = self._dups.pop(k, [])
        # v020 (f40 L4): 전에는 여기서 폴더 전체를 glob (가사를 찾을 때마다 캐시 파일 수만큼 → 캐시가 커질수록 느려짐)
        #   → 시작 때 만든 색인 + 같은 키 파일 목록만 지움 (파일은 이 클래스로만 생김)
        for f in ([p] if p else []) + extra:
            try:
                f.unlink()
            except OSError:
                pass


class NotFoundStore:
    """못 찾은 곡 기억 (data/lyrics/_notfound.json, {키: 확인 시각}) — f18 L6"""

    def __init__(self, path: Path, days: int = 7):
        self.path = Path(path)
        self.days = int(days)
        self._lock = threading.Lock()
        self._d: dict | None = None

    def _load(self) -> dict:
        if self._d is None:
            try:
                self._d = json.loads(self.path.read_text(encoding="utf-8"))
                if not isinstance(self._d, dict):
                    self._d = {}
            except (OSError, ValueError):
                self._d = {}
        return self._d

    def _save(self):
        try:
            self.path.write_text(json.dumps(self._d, ensure_ascii=False), encoding="utf-8")
        except OSError as e:
            log.warning("notfound save: %s", e)

    def age_days(self, key: str, now: float | None = None) -> int | None:
        """기억 기간 안이면 지난 날 수, 아니면 None"""
        if self.days <= 0:
            return None
        with self._lock:
            t = self._load().get(key)
        if t is None:
            return None
        age = ((now or time.time()) - float(t)) / 86400
        return int(age) if age < self.days else None

    def add(self, key: str, now: float | None = None):
        if self.days <= 0:
            return
        with self._lock:
            d = self._load()
            d[key] = int(now or time.time())
            cut = (now or time.time()) - self.days * 86400
            for k in [k for k, v in d.items() if v < cut]:     # 지난 기록 정리
                d.pop(k, None)
            self._save()

    def remove(self, key: str):
        with self._lock:
            if self._load().pop(key, None) is not None:
                self._save()
