"""백그라운드 작업 (QThreadPool) — 태그 읽기 · 일반 작업.

장시간 운용 (vr0.1.0.007):
  - 태그 작업은 '세대(gen)' 가 바뀌면 바로 멈춤 (목록이 바뀐 뒤 옛 작업이 계속 도는 것 방지)
  - DB 저장은 BATCH 곡마다 한 번 커밋 (곡마다 커밋하면 수천 곡 폴더에서 디스크 쓰기가 수천 번)
"""
import logging

from PyQt6.QtCore import QObject, QRunnable, pyqtSignal

from ..core.bg import BgEmitter, BgTask
from ..data.tags import read_tags

log = logging.getLogger("yamp.jobs")
TAG_BATCH = 200          # 이 곡 수마다 화면 갱신 + DB 커밋


class TagEmitter(QObject):
    progress = pyqtSignal()


class TagJob(QRunnable):
    def __init__(self, tracks, em, gen_ref, gen, library=None):
        super().__init__()
        self.tracks, self.em, self.gen_ref, self.gen = tracks, em, gen_ref, gen
        self.library = library

    def _alive(self) -> bool:
        return self.gen_ref[0] == self.gen

    def run(self):
        lib = self.library
        if lib is not None:
            with lib.batch():
                self._scan(lib)
        else:
            self._scan(None)
        if self._alive():
            self.em.progress.emit()

    def _scan(self, lib):
        for k, t in enumerate(self.tracks):
            if not self._alive():                # 목록이 바뀌면 중단
                return
            if t.tagged:
                continue
            info = read_tags(t.path)
            if not t.cue_no:                     # CUE 트랙은 CUE 의 제목을 유지
                t.title, t.artist, t.album, t.duration = info.title, info.artist, info.album, info.duration
            t.tagged = True
            if lib is not None and not t.cue_no:
                try:
                    lib.upsert(t.path, info.title, info.artist, info.album, info.genre, info.year,
                               info.duration, codec=info.codec, bits=info.bits, sr=info.samplerate)
                except Exception as e:  # noqa  (DB 오류가 태그 스캔을 멈추지 않게)
                    log.debug("tag upsert: %s", e)
            if k % TAG_BATCH == TAG_BATCH - 1:
                if lib is not None:
                    lib.commit()
                self.em.progress.emit()


# v019 (R9): 일반 작업은 core/bg.py 공통 (같은 동작: 예외 → 로그 + None, 종료 중 emit 무시) — 이전 이름 유지
JobEmitter = BgEmitter


class Job(BgTask):
    """일반 백그라운드 작업: fn() 결과를 done 시그널로"""

    def __init__(self, fn, em):
        super().__init__(fn, em, on_error=None, log_errors=True, logger=log)   # 로그 이름 'yamp.jobs' 그대로 (v018 과 같게)
