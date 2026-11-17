# -*- coding: utf-8 -*-
"""가사 대화상자 (vr0.1.0.019 R8 — ui/dialogs.py 에서 나눔)
LyricsEditorDialog  가사 편집기 (A1) — 붙여넣기 · 줄마다 시각 찍기 · 미리 듣기
LyricsPickDialog    다른 가사 찾기 (A2) — 공급자 후보 목록에서 고르기 (백그라운드 검색)"""
from PyQt6.QtCore import QThreadPool, QTimer
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (QCheckBox, QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QLineEdit, QListWidget,
                             QListWidgetItem, QMessageBox, QPlainTextEdit, QSplitter, QVBoxLayout)

from ..core.bg import BgEmitter, BgTask
from ..lyrics import lrc
from ..lyrics.editor import LyricEditor
from .iconbutton import IconButton


class LyricsEditorDialog(QDialog):
    """A1 가사 편집기: 왼쪽 텍스트, 오른쪽 싱크 줄. 재생 중 F9(또는 '찍기') = 현재 줄에 시각 → 다음 줄"""

    def __init__(self, ctrl, parent=None):
        super().__init__(parent)
        self.ctrl = ctrl
        self.setWindowTitle("가사 편집기 — F9: 시각 찍기, Alt+←/→: ±0.1초, 줄 더블클릭: 그 위치로")
        self.resize(820, 560)
        self.ed = LyricEditor.from_lyrics(ctrl.cur_lyrics)
        if not self.ed.lines:
            self.ed = LyricEditor.from_text("")
        v = QVBoxLayout(self)
        sp = QSplitter()
        self.text = QPlainTextEdit(self.ed.text())
        self.text.setPlaceholderText("가사를 붙여 넣거나 입력하세요 (한 줄 = 한 소절)")
        self.list = QListWidget()
        sp.addWidget(self.text)
        sp.addWidget(self.list)
        v.addWidget(sp, 1)
        row = QHBoxLayout()
        self.pos = QLabel()
        b_stamp = IconButton("stamp", "ed_stamp")
        b_m = IconButton("back01", "ed_minus")
        b_p = IconButton("fwd01", "ed_plus")
        b_clear = IconButton("trash", "ed_clear")
        b_play = IconButton("play", "ed_play")
        for w in (self.pos, b_play, b_stamp, b_m, b_p, b_clear):
            row.addWidget(w)
        row.setStretch(0, 1)
        v.addLayout(row)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.also_lrc = QCheckBox("음악 폴더에 .lrc 로도 저장")
        self.also_lrc.setChecked(True)
        h = QHBoxLayout()
        h.addWidget(self.also_lrc)
        h.addStretch(1)
        h.addWidget(bb)
        v.addLayout(h)
        b_stamp.clicked.connect(self.stamp)
        b_m.clicked.connect(lambda: self._nudge(-100))
        b_p.clicked.connect(lambda: self._nudge(100))
        b_clear.clicked.connect(self._clear)
        b_play.clicked.connect(ctrl.toggle)
        QShortcut(QKeySequence("F9"), self, activated=self.stamp)
        QShortcut(QKeySequence("Alt+Left"), self, activated=lambda: self._nudge(-100))
        QShortcut(QKeySequence("Alt+Right"), self, activated=lambda: self._nudge(100))
        self.text.textChanged.connect(self._text_changed)
        self.list.currentRowChanged.connect(self.ed.select)
        self.list.itemDoubleClicked.connect(self._seek_line)
        bb.accepted.connect(self._save)
        bb.rejected.connect(self.reject)
        self._t = QTimer(self, interval=100, timeout=self._update_pos)
        self._t.start()
        self._refresh()

    def _text_changed(self):
        self.ed.set_text(self.text.toPlainText())
        self._refresh()

    def _refresh(self):
        self.list.blockSignals(True)
        self.list.clear()
        for l in self.ed.lines:
            ts = lrc.fmt_ts(l.t_ms) if l.t_ms >= 0 else "[--:--.--]"
            self.list.addItem(QListWidgetItem(f"{ts} {l.text}"))
        self.list.setCurrentRow(self.ed.cur)
        self.list.blockSignals(False)

    def _update_pos(self):
        p = self.ctrl.engine.position()
        self.pos.setText(f"재생 위치 {lrc.fmt_ts(p)}   찍은 줄 {self.ed.stamped()}/{len(self.ed.lines)}")

    def stamp(self):
        self.ed.stamp(self.ctrl.engine.position())
        self._refresh()

    def _nudge(self, d):
        self.ed.nudge(d)
        self._refresh()

    def _clear(self):
        self.ed.clear_times()
        self._refresh()

    def _seek_line(self, item):
        i = self.list.row(item)
        if self.ed.lines[i].t_ms >= 0:
            self.ctrl.seek(max(0, self.ed.lines[i].t_ms - self.ctrl.lyrics_offset()))

    def _save(self):
        text = self.ed.to_lrc()
        self.ctrl.lyrics.use_text(text, "user")
        t = self.ctrl.current_track()
        if self.also_lrc.isChecked() and t:
            import os
            try:
                with open(os.path.splitext(t.path)[0] + ".lrc", "w", encoding="utf-8") as f:
                    f.write(text)
            except OSError as e:
                QMessageBox.warning(self, "가사 저장", f".lrc 저장 실패: {e}")
        self.accept()


class LyricsPickDialog(QDialog):
    """A2 다른 가사 찾기: 알송 + LRCLIB 후보 목록 → 미리보기 → 선택"""

    def __init__(self, ctrl, parent=None):
        super().__init__(parent)
        self.ctrl = ctrl
        self.setWindowTitle("다른 가사 찾기")
        self.resize(760, 520)
        q = ctrl.lyrics.last_query
        v = QVBoxLayout(self)
        row = QHBoxLayout()
        self.title = QLineEdit(q.title if q else "")
        self.artist = QLineEdit(q.artist if q else "")
        self.title.setPlaceholderText("제목")
        self.artist.setPlaceholderText("가수")
        b = IconButton("search", "pick_search")
        for w in (QLabel("제목"), self.title, QLabel("가수"), self.artist, b):
            row.addWidget(w)
        v.addLayout(row)
        sp = QSplitter()
        self.list = QListWidget()
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        sp.addWidget(self.list)
        sp.addWidget(self.preview)
        v.addWidget(sp, 1)
        self.status = QLabel()
        v.addWidget(self.status)
        bb = QDialogButtonBox()
        self.use = bb.addButton("이 가사 사용", QDialogButtonBox.ButtonRole.AcceptRole)
        bb.addButton(QDialogButtonBox.StandardButton.Cancel)
        v.addWidget(bb)
        self.items = []
        self._req = 0
        self._em = BgEmitter()                            # v019 (R9): 공통 백그라운드 작업 (종료 중 emit 안전)
        self._em.done.connect(self._on_bg)   # 바운드 메서드 → 창이 닫혀 삭제되면 자동으로 연결 끊김
        self._pool = QThreadPool(self)
        b.clicked.connect(self.search)
        self.title.returnPressed.connect(self.search)
        self.artist.returnPressed.connect(self.search)
        self.list.currentRowChanged.connect(self._show)
        self.list.itemDoubleClicked.connect(lambda _: self._accept())
        bb.accepted.connect(self._accept)
        bb.rejected.connect(self.reject)
        if self.title.text():
            QTimer.singleShot(0, self.search)

    def search(self):
        from ..lyrics.providers import alsong, lrclib
        t, a = self.title.text().strip(), self.artist.text().strip()
        if not t:
            return
        cfg = self.ctrl.cfg
        self._req += 1
        req = self._req
        self.status.setText("검색 중…")
        self.list.clear()
        self.items = []
        to = float(cfg["lyrics_timeout_s"] or 5)

        q = self.ctrl.lyrics.last_query
        alb, dur = (q.album, q.duration) if q else ("", 0.0)

        def work():                           # vr0.1.0.011: 공급자 동시 조회 · 점수순
            from concurrent.futures import ThreadPoolExecutor
            from ..lyrics.providers import netease
            jobs = []
            if cfg["lyrics_alsong"]:
                jobs.append(lambda: alsong.search_candidates(t, a, to, cfg["alsong_enc_data"] or "", album=alb, duration=dur))
            if cfg["lyrics_lrclib"]:
                jobs.append(lambda: lrclib.search_candidates(t, a, to, alb, dur))
            if cfg["lyrics_netease"]:
                jobs.append(lambda: netease.search_candidates(t, a, to, alb, dur))
            out = []
            with ThreadPoolExecutor(max(1, len(jobs))) as ex:
                for r in ex.map(lambda f: f(), jobs):
                    out += r
            out.sort(key=lambda d: (-d.get("score", 0), 0 if d.get("synced") else 1))
            return out
        self._pool.start(BgTask(lambda: (req, work()), self._em, on_error=lambda e: (req, [])))

    def _on_bg(self, r):
        self._done(*r)

    def _done(self, req, items):
        if req != self._req:
            return
        self.items = items
        for d in items:
            src = {"alsong": "알송", "lrclib": "LRCLIB", "netease": "NetEase"}.get(d["source"], d["source"])
            sc = f" · {d['score']}점" if "score" in d else ""
            self.list.addItem(f"[{src}{' · 싱크' if d.get('synced') else ''}{sc}] {d['artist']} - {d['title']}"
                              + (f"  ({d['album']})" if d.get("album") else ""))
        self.status.setText(f"{len(items)}건" if items else "결과 없음 (제목·가수를 바꿔 보세요)")
        if items:
            self.list.setCurrentRow(0)

    def _show(self, i):
        if 0 <= i < len(self.items):
            ly = lrc.parse(self.items[i]["lyric"])
            self.preview.setPlainText("\n".join(" / ".join(b.lines) for b in ly.blocks[:40]))

    def _accept(self):
        i = self.list.currentRow()
        if 0 <= i < len(self.items):
            d = self.items[i]
            self.ctrl.lyrics.use_text(d["lyric"], d["source"])
            self.accept()
