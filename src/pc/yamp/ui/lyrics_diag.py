# -*- coding: utf-8 -*-
"""가사 진단 창 (vr0.1.0.011, f18 L8) — 도구/가사 → 가사 진단…
백그라운드에서 lyrics.diag.run 실행 → 보고서 표시 · 복사 · 로그 폴더 열기. 색은 테마 스타일시트를 따름 (고정 색 없음)."""
from PyQt6.QtCore import QThreadPool, QUrl
from PyQt6.QtGui import QDesktopServices, QFont, QGuiApplication
from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QPlainTextEdit, QVBoxLayout

from ..core.bg import BgEmitter, BgTask
from .iconbutton import IconButton


class LyricsDiagDialog(QDialog):
    def __init__(self, ctrl, parent=None):
        super().__init__(parent)
        self.setWindowTitle("가사 진단")
        self.resize(760, 560)
        self.ctrl = ctrl
        v = QVBoxLayout(self)
        self.status = QLabel("지금 곡으로 가사를 새로 찾으며 단계별로 기록하는 중… (최대 몇 초)")
        self.status.setWordWrap(True)
        v.addWidget(self.status)
        self.text = QPlainTextEdit(readOnly=True)
        f = QFont("Consolas")
        f.setStyleHint(QFont.StyleHint.Monospace)
        self.text.setFont(f)
        v.addWidget(self.text, 1)
        row = QHBoxLayout()
        self.b_rerun = IconButton("refresh", "diag_rerun", self.start)
        self.b_copy = IconButton("save", "diag_copy",
                                 lambda: QGuiApplication.clipboard().setText(self.text.toPlainText()))
        self.b_folder = IconButton("folder", "diag_folder", lambda: QDesktopServices.openUrl(
            QUrl.fromLocalFile(str(ctrl.cfg.path_of("log_dir")))))
        for b in (self.b_rerun, self.b_copy, self.b_folder):
            row.addWidget(b)
        row.addStretch(1)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        bb.rejected.connect(self.reject)
        row.addWidget(bb)
        v.addLayout(row)
        self._em = BgEmitter()                            # v019 (R9): 공통 백그라운드 작업
        self._em.done.connect(self._on_bg)   # 바운드 메서드 → 창이 닫혀 삭제되면 자동으로 연결 끊김
        self._pool = QThreadPool(self)
        self.start()

    def start(self):
        from ..lyrics import diag
        q = self.ctrl.lyrics.last_query
        if q is None:
            self.status.setText("재생 중인 곡이 없습니다")
            return
        cfg = self.ctrl.cfg
        self.status.setText("지금 곡으로 가사를 새로 찾으며 단계별로 기록하는 중…")
        def work():
            text, saved = diag.run(cfg, q, cfg.path_of("log_dir"))
            return text, saved or ""
        self._pool.start(BgTask(work, self._em, on_error=lambda e: (f"진단 중 오류: {e}", "")))

    def _on_bg(self, r):
        self._done(*r)

    def _done(self, text, saved):
        self.text.setPlainText(text)
        self.status.setText(f"저장: {saved}" if saved else "완료")

    def done(self, r):
        self._pool.waitForDone(100)
        super().done(r)
