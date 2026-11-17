"""플레이리스트 모델/뷰: 드래그&드롭(탐색기 파일), Delete 삭제, Ctrl+↑↓ 이동, 더블클릭 재생, 검색."""
from PyQt6.QtCore import QAbstractListModel, QModelIndex, Qt, pyqtSignal
from PyQt6.QtGui import QAction, QColor, QFont
from PyQt6.QtWidgets import QAbstractItemView, QListView, QMenu

from ..data.playlist import Playlist, fmt_time
from . import skin
from .qtutil import exec_menu


class PlaylistModel(QAbstractListModel):
    def __init__(self, pl: Playlist, parent=None):
        super().__init__(parent)
        self.pl = pl
        self.cur_color = QColor(skin.current().accent_text)      # 지금 곡 (테마가 바뀌면 apply_skin 이 갱신)
        self.filter = ""
        self._rows: list[int] = []   # 표시 행 → 실제 인덱스
        self._rebuild()

    def _rebuild(self):
        f = self.filter.lower()
        if f:
            self._rows = [i for i, t in enumerate(self.pl.items)
                          if f in t.display.lower() or f in t.album.lower()]
        else:
            self._rows = list(range(len(self.pl.items)))

    FILTER_DELAY_MS = 150          # v022 (N4): 곡이 많으면 입력이 멈춘 뒤 한 번 거름
    FILTER_INSTANT_MAX = 2000      # 이 곡 수 이하는 글자마다 바로 (전과 같음)

    def request_filter(self, text: str):
        """검색 칸 입력 → 작은 목록은 바로, 큰 목록(2000곡 초과)은 150ms 뒤 한 번 (글자마다 전체 다시 거르기 방지)"""
        if len(self.pl.items) <= self.FILTER_INSTANT_MAX:
            self.set_filter(text)
            return
        from PyQt6.QtCore import QTimer
        t = getattr(self, "_filter_t", None)
        if t is None:
            t = self._filter_t = QTimer(self, singleShot=True, interval=self.FILTER_DELAY_MS)
            t.timeout.connect(self._apply_pending_filter)
        self._pending_filter = text
        t.start()

    def _apply_pending_filter(self):
        self.set_filter(getattr(self, "_pending_filter", ""))

    def set_filter(self, text: str):
        self.beginResetModel()
        self.filter = text.strip()
        self._rebuild()
        self.endResetModel()

    def refresh(self):
        self.beginResetModel()
        self._rebuild()
        self.endResetModel()

    def refresh_rows(self):
        if self._rows:
            self.dataChanged.emit(self.index(0), self.index(len(self._rows) - 1))

    def real_index(self, row: int) -> int:
        return self._rows[row] if 0 <= row < len(self._rows) else -1

    def row_of(self, real: int) -> int:
        try:
            return self._rows.index(real)
        except ValueError:
            return -1

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._rows)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        i = self._rows[index.row()]
        t = self.pl.items[i]
        if role == Qt.ItemDataRole.DisplayRole:
            d = fmt_time(t.duration) if t.duration else ""
            return f"{i + 1}. {t.display}" + (f"   [{d}]" if d else "")
        if role == Qt.ItemDataRole.ToolTipRole:
            return t.path
        if role == Qt.ItemDataRole.ForegroundRole and i == self.pl.current:
            return self.cur_color
        if role == Qt.ItemDataRole.FontRole and i == self.pl.current:
            f = QFont()
            f.setBold(True)
            return f
        return None


class PlaylistView(QListView):
    playRequested = pyqtSignal(int)          # 실제 인덱스
    filesDropped = pyqtSignal(list)
    removeRequested = pyqtSignal(list)
    moveRequested = pyqtSignal(int, int)
    researchLyrics = pyqtSignal(int)
    openFolder = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setUniformItemSizes(True)
        self.doubleClicked.connect(lambda ix: self.playRequested.emit(self.model().real_index(ix.row())))
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._menu)

    def selected_real(self) -> list[int]:
        m = self.model()
        return sorted(m.real_index(ix.row()) for ix in self.selectedIndexes())

    # 탐색기 → 드롭
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
        else:
            super().dragEnterEvent(e)

    def dragMoveEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
        else:
            super().dragMoveEvent(e)

    def dropEvent(self, e):
        if e.mimeData().hasUrls():
            paths = [u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()]
            if paths:
                self.filesDropped.emit(paths)
            e.acceptProposedAction()
        else:
            super().dropEvent(e)

    def keyPressEvent(self, e):
        k, mod = e.key(), e.modifiers()
        sel = self.selected_real()
        if k == Qt.Key.Key_Delete and sel:
            self.removeRequested.emit(sel)
            return
        if k in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and sel:
            self.playRequested.emit(sel[0])
            return
        if mod & Qt.KeyboardModifier.ControlModifier and k in (Qt.Key.Key_Up, Qt.Key.Key_Down) and len(sel) == 1:
            if not self.model().filter:
                j = sel[0] + (-1 if k == Qt.Key.Key_Up else 1)
                self.moveRequested.emit(sel[0], j)
            return
        super().keyPressEvent(e)

    def _menu(self, pos):
        ix = self.indexAt(pos)
        m = QMenu(self)
        if ix.isValid():
            r = self.model().real_index(ix.row())
            m.addAction("재생", lambda: self.playRequested.emit(r))
            m.addAction("가사 다시 찾기", lambda: self.researchLyrics.emit(r))
            m.addAction("폴더 열기", lambda: self.openFolder.emit(r))
            m.addSeparator()
        sel = self.selected_real()
        a = QAction("선택 삭제 (Del)", m)
        a.setEnabled(bool(sel))
        a.triggered.connect(lambda: self.removeRequested.emit(sel))
        m.addAction(a)
        exec_menu(m, self.viewport().mapToGlobal(pos))
