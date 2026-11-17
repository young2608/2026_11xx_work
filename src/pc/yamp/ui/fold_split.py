# -*- coding: utf-8 -*-
"""블럭 크기 조절 + 접기/펼치기 (vr0.1.0.015)

FoldSplitter: 세로로 쌓인 Section(제목 줄 + 본문) 블럭 사이를 마우스로 끌어 크기 조절.
  - 블럭 제목을 누르면 접힘 → 제목 줄 높이만 남고, 남는 높이는 펼쳐진 블럭이 나눠 가짐
  - 다시 펼치면 접기 전 높이로
  - 크기는 cfg[key] (state.json) 에 저장 → 다음 실행 때 그대로
  - 경계 손잡이를 더블클릭 = 기본 크기로 (reset)
"""
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QSplitter, QSplitterHandle

QMAX = 16777215


class _Handle(QSplitterHandle):
    def __init__(self, o, parent):
        super().__init__(o, parent)
        self.setToolTip("끌어서 크기 조절 · 더블클릭 = 기본 크기")

    def mouseDoubleClickEvent(self, e):
        self.splitter().reset_sizes()


class FoldSplitter(QSplitter):
    def __init__(self, cfg=None, key: str = "", parent=None):
        super().__init__(Qt.Orientation.Vertical, parent)
        self.setObjectName("foldSplit")
        self.cfg, self.key = cfg, key
        self.setChildrenCollapsible(False)
        self.setHandleWidth(12)                      # 카드 사이 간격 = 손잡이 (끌기 쉬운 폭)
        self.secs = []
        self.defaults = []                           # 기본 비율 (stretch)
        self._open_size = {}                         # 접기 전 높이
        self._restored = False
        self.splitterMoved.connect(lambda *_: self._save())

    def createHandle(self):
        return _Handle(self.orientation(), self)

    def add_section(self, sec, stretch: int = 1):
        self.addWidget(sec)
        self.setStretchFactor(len(self.secs), stretch)       # 0 = 창 크기가 바뀌어도 그대로 (내용 높이)
        self.secs.append(sec)
        self.defaults.append(stretch)
        sec.toggled.connect(lambda on, s=sec: self._on_fold(s, on))
        self._limit(sec)

    # ---- 접기
    @staticmethod
    def head_h(sec) -> int:
        m = sec.layout().contentsMargins()
        return max(sec.btn.sizeHint().height(), sec.head.sizeHint().height()) + m.top() + m.bottom() + 2

    def _limit(self, sec):
        if sec.is_open():
            sec.setMaximumHeight(QMAX)
            sec.setMinimumHeight(0)
        else:
            h = self.head_h(sec)
            sec.setMinimumHeight(h)
            sec.setMaximumHeight(h)

    def _on_fold(self, sec, on):
        i = self.secs.index(sec)
        sizes = self.sizes()
        others = [k for k, s in enumerate(self.secs) if k != i and s.is_open()]
        others = [k for k in others if self.defaults[k] > 0] or others     # 늘고 주는 건 늘어나는 블럭부터 (곡 정보는 그대로)
        hh = self.head_h(sec)
        self._limit(sec)
        if not on:
            self._open_size[i] = sizes[i]
            delta = max(0, sizes[i] - hh)                 # 남는 높이 → 펼친 블럭들에 비율대로 (빈 칸 없음)
            sizes[i] = hh
        else:
            want = self._open_size.get(i) or max(120, sum(sizes) // max(1, len(sizes)))
            room = sum(max(0, sizes[k] - 80) for k in others)
            give = min(want - hh, room) if others else want - hh
            delta = -max(0, give)                         # 펼친 블럭들에서 비율대로 덜어 옴 (각 80px 은 남김)
            sizes[i] = hh + max(0, give)
        if others and delta:
            sizes = share(sizes, others, delta, 80)
        self.setSizes(sizes)
        QTimer.singleShot(0, self._save)

    def showEvent(self, e):
        super().showEvent(e)
        if not self._restored:                       # 처음 보일 때 한 번 (창 크기가 정해진 뒤)
            QTimer.singleShot(0, self.restore)

    # ---- 저장 · 복원 · 기본
    def _save(self):
        if self.cfg is not None and self.key and self._restored:
            self.cfg[self.key] = [int(v) for v in self.sizes()]

    def restore(self):
        """창이 처음 보인 뒤 한 번 (크기가 정해진 다음이어야 비율이 맞음)"""
        if self._restored:
            return
        sv = self.cfg[self.key] if (self.cfg is not None and self.key) else None
        if isinstance(sv, list) and len(sv) == len(self.secs) and all(isinstance(v, int) and v >= 0 for v in sv) and sum(sv) > 0:
            self.setSizes(sv)
        else:
            self.reset_sizes(save=False)
        self._restored = True

    def reset_sizes(self, save: bool = True):
        """기본 크기: stretch 0 블럭 = 내용에 맞는 높이, 나머지 = stretch 비율 · 접힌 블럭 = 제목 줄"""
        total = max(1, sum(self.sizes()) or self.height())
        nat = {i: max(s.minimumSizeHint().height(), s.sizeHint().height())
               for i, s in enumerate(self.secs) if s.is_open() and self.defaults[i] == 0}
        flex = [i for i, s in enumerate(self.secs) if s.is_open() and self.defaults[i] > 0]
        fixed = sum(self.head_h(s) for s in self.secs if not s.is_open()) + sum(nat.values())
        st = sum(self.defaults[i] for i in flex) or 1
        free = max(0, total - fixed)
        sizes = []
        for i, s in enumerate(self.secs):
            sizes.append(self.head_h(s) if not s.is_open() else nat.get(i, free * self.defaults[i] // st))
        self.setSizes(sizes)
        self._open_size.clear()
        if save:
            self._restored = True
            self._save()

def share(sizes: list, idx: list, delta: int, floor: int = 0) -> list:
    """sizes[idx] 에 delta 를 현재 크기 비율로 나눠 더함 (빼기면 floor 아래로 안 내려감) — 합계 보존"""
    out = list(sizes)
    if delta >= 0:
        tot = sum(out[k] for k in idx) or 1
        for k in idx:
            out[k] += delta * out[k] // tot
        out[idx[-1]] += delta - sum(delta * sizes[k] // tot for k in idx)
        return out
    need = -delta
    room = {k: max(0, out[k] - floor) for k in idx}
    tot = sum(room.values()) or 1
    took = 0
    for k in idx:
        t = min(room[k], need * room[k] // tot)
        out[k] -= t
        took += t
    for k in idx:                                         # 나머지 몇 px
        t = min(max(0, out[k] - floor), need - took)
        out[k] -= t
        took += t
    return out
