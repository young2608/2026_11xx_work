# -*- coding: utf-8 -*-
"""
앨범 격자 (vr0.1.0.009) — 라이브러리를 앨범 표지 격자로. 크기 슬라이더로 표지 크기 조절.
  - 표지는 보이는 앨범만 백그라운드 스레드 1개로 읽음 (첫 곡의 내장 표지), 메모리 캐시 300개 (LRU)
  - 더블클릭 = 앨범 재생, 우클릭 = 곡 메뉴
"""
from collections import OrderedDict

from PyQt6.QtCore import QRectF, QSize, Qt, QThreadPool, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QIcon, QIconEngine, QImage, QLinearGradient, QPainter, QPixmap
from PyQt6.QtWidgets import QListView, QListWidget, QListWidgetItem

from ..core.bg import BgEmitter, BgTask
from . import skin as skinmod, tips

ROLE = Qt.ItemDataRole.UserRole
CACHE_MAX = 300
CACHE_MAX_BYTES = 48 * 1024 * 1024    # v020 (f40 L2): 표지 픽스맵 합계 상한 (220px · 200 % 이면 1장 ≈ 0.77MB → 300장 ≈ 230MB 였음)


def pm_bytes(pm) -> int:
    return max(1, pm.width()) * max(1, pm.height()) * 4


def albums_of(rows) -> list[tuple[str, str, list[str], str]]:
    """[(앨범, 가수, [키], 첫 곡 경로)] — 앨범 이름순. Qt 비의존 (테스트 대상)"""
    groups = OrderedDict()
    for r in sorted(rows, key=lambda r: ((r.get("album") or "").lower(), r.get("cue_no") or 0, r.get("path") or "")):
        alb = (r.get("album") or "").strip() or "(앨범 없음)"
        g = groups.setdefault(alb, {"artists": {}, "keys": [], "path": r.get("path") or ""})
        a = (r.get("artist") or "").strip()
        if a:
            g["artists"][a] = g["artists"].get(a, 0) + 1
        g["keys"].append(r["key"])
    out = []
    for alb, g in groups.items():
        artist = max(g["artists"], key=g["artists"].get) if g["artists"] else ""
        if len(g["artists"]) > 2:
            artist = "여러 가수"
        out.append((alb, artist, g["keys"], g["path"]))
    return out


def load_cover_image(path: str, side: int):
    """앨범 첫 곡의 내장 표지 → 가운데 정사각 side×side(실제 픽셀) QImage, 없으면 None — 작업 스레드에서 (v016 · v022 N7)"""
    from ..data.tags import read_tags
    info = read_tags(path, want_cover=True)
    img = QImage()
    if not (info.cover and img.loadFromData(info.cover)):
        return None
    img = img.scaled(side, side, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
    if img.width() > side or img.height() > side:          # 가운데 정사각으로 (v016)
        img = img.copy((img.width() - side) // 2, (img.height() - side) // 2, side, side)
    return img


def _paint_placeholder(p: QPainter, name: str, side: float):
    """자리 그림 그리기 (논리 좌표 0..side) — placeholder() 와 아이콘 엔진이 같이 씀"""
    s = skinmod.current()
    k = 2 + sum(map(ord, name)) % 5
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    g = QLinearGradient(0, 0, side, side)
    g.setColorAt(0, QColor(s.bands[k]))
    g.setColorAt(1, QColor(s.bands[min(len(s.bands) - 1, k + 4)]))
    p.fillRect(QRectF(0, 0, side, side), g)
    p.setPen(skinmod.qcolor("on_fill", 150))
    f = QFont()
    f.setPixelSize(max(12, int(side) * 2 // 5))
    f.setBold(True)
    p.setFont(f)
    p.drawText(QRectF(0, 0, side, side), Qt.AlignmentFlag.AlignCenter, (name.strip() or "?")[:1].upper())


class _PlaceholderEngine(QIconEngine):
    """v020 (f40 L2): 표지 없는 칸 아이콘 — 픽스맵을 들고 있지 않고 그릴 때마다 그림 (보이는 칸만 · 테마 색 바로 따라감).
    전에는 앨범마다 실제 픽셀 픽스맵 1장 → 앨범 2000개 · 220px · 200 % 면 자리 그림만 약 1.5GB"""

    def __init__(self, name: str):
        super().__init__()
        self.name = name

    def paint(self, painter, rect, mode, state):
        painter.save()
        painter.translate(rect.x(), rect.y())
        side = min(rect.width(), rect.height())
        _paint_placeholder(painter, self.name, side)
        painter.restore()

    def scaledPixmap(self, size, mode, state, scale):
        side = min(size.width(), size.height())
        pm = QPixmap(max(1, round(side * scale)), max(1, round(side * scale)))
        pm.setDevicePixelRatio(max(1.0, float(scale)))
        p = QPainter(pm)
        _paint_placeholder(p, self.name, side)
        p.end()
        return pm

    def pixmap(self, size, mode, state):
        return self.scaledPixmap(size, mode, state, 1.0)

    def clone(self):
        return _PlaceholderEngine(self.name)


def placeholder_icon(name: str) -> QIcon:
    return QIcon(_PlaceholderEngine(name))


def placeholder(name: str, side: int, ratio: float = 1.0) -> QPixmap:
    """표지 없는 앨범: 테마 밴드 색 그라데이션 (써니 = 노랑 → 주황) + 첫 글자
    v016: side = 논리 크기, ratio = 화면 배율 → 실제 픽셀로 그려 선명 (devicePixelRatio 지정)"""
    ratio = max(1.0, float(ratio))
    pm = QPixmap(max(1, round(side * ratio)), max(1, round(side * ratio)))
    pm.setDevicePixelRatio(ratio)
    p = QPainter(pm)
    _paint_placeholder(p, name, side)
    p.end()
    return pm


class AlbumGrid(QListWidget):
    playRequested = pyqtSignal(list, str)        # 키 목록, 제목

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setViewMode(QListView.ViewMode.IconMode)
        self.setResizeMode(QListView.ResizeMode.Adjust)
        self.setMovement(QListView.Movement.Static)
        self.setUniformItemSizes(True)
        self.setWordWrap(True)
        self.setSpacing(8)
        self.side = 120
        self.ratio = 1.0                                   # v016: 화면 배율 (모니터를 옮기면 refresh_dpr)
        self._cache: OrderedDict[str, QPixmap] = OrderedDict()
        self._bytes = 0                                     # v020: 캐시 픽스맵 합계 (CACHE_MAX_BYTES)
        self._by_album = {}
        self._asked = set()
        self._gen = 0
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(1)
        self._em = BgEmitter(self)                          # v022 (N7): 공통 백그라운드 작업 (core/bg)
        self._em.done.connect(self._on_cover_bg)
        self.itemDoubleClicked.connect(lambda it: self.playRequested.emit(it.data(ROLE)[0], it.data(ROLE)[1]))
        self.verticalScrollBar().valueChanged.connect(lambda _v: self._request_visible())

    def _ph(self, name):
        return placeholder(name, self.side, self.ratio)

    @staticmethod
    def _ph_icon(name):
        return placeholder_icon(name)

    def refresh_dpr(self):
        """배율이 바뀌었으면 표지를 새 배율로 다시 (v016 G5)"""
        from .hidpi import dpr
        r = dpr(self)
        if abs(r - self.ratio) > 1e-3:
            self.ratio = r
            self.set_side(self.side)

    def set_side(self, side: int):
        from .hidpi import dpr
        self.ratio = dpr(self)
        self.side = int(side)
        self.setIconSize(QSize(self.side, self.side))
        self.setGridSize(QSize(self.side + 24, self.side + 46))
        self._cache.clear()
        self._bytes = 0
        self._asked.clear()
        for i in range(self.count()):
            it = self.item(i)
            it.setIcon(self._ph_icon(it.data(ROLE)[1]))
        self._request_visible()

    def set_rows(self, rows):
        from .hidpi import dpr
        self.ratio = dpr(self)
        self._gen += 1
        self.clear()
        self._asked.clear()
        self._by_album = {}                                 # v018 (f33 P12): 앨범 → 칸 (표지 도착 시 전체를 훑지 않게)
        self.setIconSize(QSize(self.side, self.side))
        self.setGridSize(QSize(self.side + 24, self.side + 46))
        self.setUpdatesEnabled(False)
        try:
            self._fill(rows)
        finally:
            self.setUpdatesEnabled(True)
        self._request_visible()

    def _fill(self, rows):
        for alb, artist, keys, path in albums_of(rows):
            it = QListWidgetItem(f"{alb}\n{artist}")
            it.setData(ROLE, (keys, alb, path))
            pm = self._cache.get(alb)
            it.setIcon(QIcon(pm) if pm else self._ph_icon(alb))
            it.setToolTip(self._tip(alb, artist, len(keys)))
            self.addItem(it)
            self._by_album[alb] = it

    @staticmethod
    def _tip(alb, artist, n):
        return f"<b>{alb}</b><br>{artist} · {n}곡<br>{tips.dim('더블클릭 = 앨범 재생')}"

    def set_skin(self, _s=None):
        """테마 바뀜: 표지 없는 칸 색 · 툴팁 다시"""
        for i in range(self.count()):
            it = self.item(i)
            keys, alb, _path = it.data(ROLE)
            if alb not in self._cache:
                it.setIcon(self._ph_icon(alb))
            artist = it.text().split("\n", 1)[-1]
            it.setToolTip(self._tip(alb, artist, len(keys)))

    def _request_visible(self):
        if not self.isVisible():
            return
        gen = self._gen
        for i in self.visible_rows():
            it = self.item(i)
            keys, alb, path = it.data(ROLE)
            if alb in self._cache or alb in self._asked or not path:
                continue
            self._asked.add(alb)
            px = max(1, round(self.side * self.ratio))         # 실제 픽셀로 읽음 (v016 G4)
            self._pool.start(BgTask(lambda alb=alb, path=path, px=px, g=gen: self._cover_work(alb, path, px, g), self._em))

    def visible_rows(self) -> list[int]:
        """v022 (N5): 화면에 보이는 칸 번호 — 칸은 왼→오, 위→아래 순서라 칸 아래쪽 y 가 번호 순으로 늘어남 →
        첫 보이는 칸을 이분 탐색으로 찾고 화면 아래까지만 확인 (전에는 스크롤마다 앨범 전체 위치 확인)"""
        vp = self.viewport().rect()
        n = self.count()
        lo, hi = 0, n
        while lo < hi:                                      # 첫 칸: 아래쪽이 화면 위보다 아래
            mid = (lo + hi) // 2
            if self.visualItemRect(self.item(mid)).bottom() < vp.top():
                lo = mid + 1
            else:
                hi = mid
        out = []
        for i in range(lo, n):
            r = self.visualItemRect(self.item(i))
            if r.top() > vp.bottom():
                break
            if r.intersects(vp):
                out.append(i)
        return out

    def _cover_work(self, alb, path, px, gen):
        """(작업 스레드) 목록이 다시 만들어졌으면(세대 바뀜) 건너뜀 · 표지 없으면 None"""
        if gen != self._gen:
            return None
        img = load_cover_image(path, px)
        return (alb, img) if img is not None else None

    def _on_cover_bg(self, r):
        if r:
            self._on_cover(*r)

    def showEvent(self, e):
        super().showEvent(e)
        self._request_visible()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._request_visible()

    def _on_cover(self, album, img):
        pm = QPixmap.fromImage(img)
        pm.setDevicePixelRatio(max(1.0, img.width() / max(1, self.side)))
        old = self._cache.pop(album, None)
        if old is not None:
            self._bytes -= pm_bytes(old)
        self._cache[album] = pm
        self._bytes += pm_bytes(pm)
        while self._cache and (len(self._cache) > CACHE_MAX or self._bytes > CACHE_MAX_BYTES):
            _k, gone = self._cache.popitem(last=False)          # 가장 오래된 표지부터 (화면에서 다시 보이면 다시 읽음)
            self._bytes -= pm_bytes(gone)
            self._asked.discard(_k)
            it = self._by_album.get(_k)
            if it is not None:                                  # 칸의 아이콘도 자리 그림으로 → 표지 메모리가 실제로 풀림
                it.setIcon(self._ph_icon(_k))
        it = getattr(self, "_by_album", {}).get(album)
        if it is not None:
            it.setIcon(QIcon(pm))

    def shutdown(self):
        self._gen += 1
        self._pool.clear()
        self._pool.waitForDone(1000)
