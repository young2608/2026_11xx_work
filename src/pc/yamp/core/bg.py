# -*- coding: utf-8 -*-
"""백그라운드 작업 공통 (vr0.1.0.019 R9) — QThreadPool 에서 fn() 을 돌리고 결과를 UI 스레드로 시그널 한 번.

전에는 화면마다 같은 모양의 QObject(시그널) + QRunnable 쌍을 따로 만들었음 (가사 진단 · 다른 가사 찾기 · 일반 작업).
  - 예외: on_error(e) 의 값을 결과로 (없으면 None) · log_errors=True 면 로그에 전체 기록
  - 종료 중(받는 쪽 QObject 가 이미 삭제됨) emit 의 RuntimeError 는 조용히 무시 — 전에는 '다른 가사 찾기'에 이 처리가 빠져 있었음

사용:
    em = BgEmitter(); em.done.connect(self._on_result)
    pool.start(BgTask(lambda: 무거운_일(), em, on_error=lambda e: 기본값))
"""
import logging

from PyQt6.QtCore import QObject, QRunnable, pyqtSignal

log = logging.getLogger("yamp.bg")


class BgEmitter(QObject):
    done = pyqtSignal(object)


class BgTask(QRunnable):
    def __init__(self, fn, emitter: BgEmitter, on_error=None, log_errors: bool = False, logger=None):
        super().__init__()
        self.fn, self.emitter, self.on_error, self.log_errors = fn, emitter, on_error, log_errors
        self.log = logger or log                  # 재검(f37): 부르는 쪽 로그 이름 유지 (일반 작업 = yamp.jobs)

    def run(self):
        try:
            r = self.fn()
        except Exception as e:  # noqa — 작업 오류가 스레드 밖으로 나가 앱을 멈추지 않게
            if self.log_errors:
                self.log.exception("job: %s", e)
            r = self.on_error(e) if self.on_error else None
        try:
            self.emitter.done.emit(r)
        except RuntimeError:                      # 종료 중 (받는 쪽이 이미 삭제됨)
            pass
