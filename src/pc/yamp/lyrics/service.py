"""가사 서비스 (백그라운드 스레드) — Qt 쪽만 (v019 R3: 캐시 = cache.py, 찾기 순서 = resolve.py).

vr0.1.0.011 (f18 L5·L6·L7):
  캐시 → (실패 기억) → 로컬 .lrc → 태그 내장 → 알송 · LRCLIB · NetEase **동시 조회** (전체 lyrics_timeout_s)
  → 후보 점수(score.py) 최고가 lyrics_min_score 이상이면 사용 · 캐시 저장
  → 아니면 이유(오프라인 / 서버 오류 / 0건 / 점수 미달)를 상태로 알림, '못 찾음'은 lyrics_notfound_days 동안 기억
곡이 바뀌면 이전 요청 결과는 req_id 비교로 버림.
"""
import logging
from pathlib import Path

from PyQt6.QtCore import QObject, QRunnable, QThreadPool, pyqtSignal

from ..core.keys import cache_key  # noqa: F401  (v019 R2: core/keys.py 로 옮김 — 이전 import 호환)
from . import lrc
from .providers.base import Query
# v019 (R3): 캐시 · 찾기 순서는 cache.py · resolve.py 로 나눔 — 이전 이름으로도 그대로 가져갈 수 있게 다시 내보냄
from .cache import LyricsCache, NotFoundStore, _safe  # noqa: F401
from .resolve import (REASONS, SOURCE_NAMES, Result, build_providers, resolve, resolve_full,  # noqa: F401
                      _parse_ok, _save_beside)

log = logging.getLogger("yamp.lyrics")


class _Emitter(QObject):
    done = pyqtSignal(int, object)            # req_id, Result


class _Job(QRunnable):
    def __init__(self, req_id, q, providers, cache, use_cache, emitter, current=lambda: None, opts=None):
        super().__init__()
        self.req_id, self.q, self.providers = req_id, q, providers
        self.cache, self.use_cache, self.emitter = cache, use_cache, emitter
        self.current = current
        self.opts = opts or {}

    def run(self):
        cur = self.current()
        if cur is not None and cur != self.req_id:     # 곡을 빨리 넘기면 줄 선 옛 검색(네트워크)은 건너뜀
            return
        try:
            res = resolve_full(self.q, self.providers, self.cache, self.use_cache, **self.opts)
        except Exception as e:  # pragma: no cover
            log.exception("lyrics job: %s", e)
            res = Result(None, "server")
        try:
            self.emitter.done.emit(self.req_id, res)
        except RuntimeError:                      # 종료 중 (받는 쪽이 이미 삭제됨)
            pass


class LyricsService(QObject):
    found = pyqtSignal(object)        # Lyrics | None (현재 곡만)
    searching = pyqtSignal(str)       # 상태 문구
    result = pyqtSignal(object)       # Result (현재 곡만, found 직전) — 이유 · 출처 · 점수

    def __init__(self, cfg, cache_dir: Path, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self.cache = LyricsCache(cache_dir)
        self.notfound = NotFoundStore(Path(cache_dir) / "_notfound.json", int(cfg["lyrics_notfound_days"] or 0))
        self.last_result: Result | None = None
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(2)
        self._req = 0
        self._research: set[int] = set()
        self._em = _Emitter()
        self._em.done.connect(self._on_done)
        self.last_query: Query | None = None

    def request(self, q: Query, use_cache: bool = True):
        self._req += 1
        self.last_query = q
        self.searching.emit("가사 찾는 중…")
        self.notfound.days = int(self.cfg["lyrics_notfound_days"] or 0)
        opts = {"notfound": self.notfound, "min_score": int(self.cfg["lyrics_min_score"] or 0),
                "timeout_s": float(self.cfg["lyrics_timeout_s"] or 6), "save_beside": bool(self.cfg["lyrics_save_beside"])}
        if not use_cache:
            self._research = {self._req}
        self.pool.start(_Job(self._req, q, build_providers(self.cfg), self.cache, use_cache, self._em,
                             lambda: self._req, opts))

    def research(self):
        if self.last_query:                  # 캐시는 지우지 않음 — 새로 찾으면 덮어씀, 못 찾으면 지금 가사 유지
            self.request(self.last_query, use_cache=False)

    def cancel(self):
        self._req += 1

    def use_text(self, text: str, source: str):
        """사용자가 고른/편집한 가사를 현재 곡 캐시에 저장하고 표시 (A1·A2)"""
        q = self.last_query
        if not q:
            return None
        self.cache.put(q, text, source)
        self.notfound.remove(cache_key(q.path))
        ly = lrc.parse(text, source)
        self._req += 1                       # 진행 중인 자동 검색 결과는 버림
        self.found.emit(None if lrc.is_empty(ly) else ly)
        return ly

    def _on_done(self, req_id, res):
        if req_id != self._req:
            return
        if res.lyrics is None and req_id in self._research and self.last_query:
            hit = self.cache.get(self.last_query)            # 다시 찾기 실패 → 지금 가사 유지
            if hit:
                ly = lrc.parse(hit[0], hit[1])
                if not lrc.is_empty(ly):
                    res.lyrics, res.source = ly, hit[1]
                    res.reason = "kept"
        self.last_result = res
        self.result.emit(res)
        self.found.emit(res.lyrics)

    def wait(self, ms: int = 3000):
        self.pool.waitForDone(ms)
