# -*- coding: utf-8 -*-
"""지금 재생 페이지 (vr0.1.0.014, f26 §3.4) — MainWindow 믹스인

  정보 카드(표지 · 큰 제목 · 아티스트·앨범 · 형식 · LCD) → 소리 시각화 블럭(VisBlock) → 다음 곡 5곡
  빈 상태: [파일 열기] [폴더 열기] 안내 · 밝은 테마 카드 옅은 그림자
  시각화는 창이 보이고 · 이 페이지이고 · 블럭이 펼쳐져 있고 · 재생 중일 때만 30fps (장시간 운용)
"""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QVBoxLayout, QWidget

from ..ui import metrics
from ..ui.iconbutton import IconButton


class NowMixin:
    def _wire_now(self):
        if getattr(self, "vis", None) is None:
            return
        c = self.ctrl
        c.visFrame.connect(self.vis.on_frame)
        c.levels.connect(self.vis.on_levels)
        self.vis.source = lambda: (self.seek.peaks, c.rel_pos(), c.rel_dur(), c.engine.is_playing())
        self.sec_vis.toggled.connect(lambda _o: self._sync_vis())
        self.refresh_up_next()                                 # 빈 상태 안내 · (다음 곡 없음) 바로 표시

    def _page_now(self):
        """v014 (f26 §3.4): 곡 정보 → 소리 시각화 → 다음 곡 (Spotify Now Playing + Up next 흐름) · 빈 상태 안내
        v015 (f28): 세 블럭 모두 Section(제목 누르면 접기/펼치기) + FoldSplitter(경계를 끌어 크기 조절, 더블클릭 = 기본)"""
        from ..ui.fold_split import FoldSplitter
        from ..ui.section import Section
        from ..ui.vis_block import VisBlock
        w = QWidget()
        v = QVBoxLayout(w)
        metrics.margins(v, 20, 12, 20, 12)
        v.setSpacing(0)
        # ---- 곡 정보
        body = QWidget()
        cv = QHBoxLayout(body)
        metrics.margins(cv, 8, 4, 8, 8)
        metrics.spacing(cv, 18)
        metrics.fix(self.cover, 160, 160)
        cv.addWidget(self.cover, 0, Qt.AlignmentFlag.AlignTop)
        right = QVBoxLayout()
        metrics.spacing(right, 4)
        from ..ui.widgets import ElideLabel
        self.now_title = ElideLabel("yMp3Player", objectName="nowTitle")      # v016: 긴 제목은 … + 마우스를 올리면 전체
        self.now_sub = ElideLabel("음악 파일·폴더를 끌어다 놓거나 아래 버튼으로 여세요", objectName="nowSub")
        for lb in (self.now_title, self.now_sub):
            metrics.fix(lb, min_w=80)
        right.addWidget(self.now_title)
        right.addWidget(self.now_sub)
        right.addWidget(self.info)
        lcd = QFrame(objectName="lcd")
        lh = QHBoxLayout(lcd)
        metrics.margins(lh, 6, 4, 6, 4)
        lh.addWidget(self.lcd)
        lh.addWidget(self.spec, 1)
        right.addWidget(lcd)
        self.empty_row = QWidget()
        er = QHBoxLayout(self.empty_row)
        metrics.margins(er, 0, 4, 0, 0)
        er.addWidget(IconButton("addFile", "open", self.open_files, size=22))
        er.addWidget(IconButton("addFolder", "open_folder", self.open_folder, size=22))
        hint = QLabel("파일 열기 · 폴더 열기 (Ctrl+O · Ctrl+Shift+O)", objectName="emptyHint")
        hint.setWordWrap(True)
        metrics.fix(hint, min_w=60)
        er.addWidget(hint, 1)
        right.addWidget(self.empty_row)
        right.addStretch(1)
        cv.addLayout(right, 1)
        self.title.setParent(w)                                # 예전 LCD 제목 줄 (클래식 배치용) — 단순 배치에서는 숨김
        self.title.hide()
        self.sec_info = Section("곡 정보", "main.info", self.cfg, body)
        self.sec_info.toggled.connect(lambda _o: self._info_head())
        # ---- 소리 시각화
        self.vis = VisBlock(self.cfg, header=False)
        self.sec_vis = Section("비주얼라이저", "main.vis", self.cfg, self.vis)        # v026: 이름 (Poweramp · foobar2000 · Winamp 처럼)
        self.sec_vis.head.addLayout(self.vis.mode_row)              # 모드 버튼은 제목 줄 오른쪽 (세로 공간 절약)
        # ---- 다음 곡
        self.up_next = QListWidget(objectName="upNext")
        metrics.fix(self.up_next, min_h=60)
        self.up_next.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.up_next.itemDoubleClicked.connect(self._play_up_next)
        self.sec_next = Section("다음 곡", "main.next", self.cfg, self.up_next)
        # ---- 크기 조절 · 접기
        self.now_split = FoldSplitter(self.cfg, "now_split")
        for sec, st in ((self.sec_info, 0), (self.sec_vis, 4), (self.sec_next, 2)):   # 곡 정보 = 내용 높이, 시각화 : 다음 곡 = 2:1 (v017 시각화 크게)
            sec.setObjectName("card")
            self.now_split.add_section(sec, st)
        v.addWidget(self.now_split, 1)
        w.tools = []
        return w

    def _info_head(self):
        """곡 정보를 접으면 제목 줄에 지금 곡 이름 (접어도 무슨 곡인지 보이게)"""
        t = self.ctrl.current_track() if self.sec_info is not None else None
        self.sec_info.btn.setText("곡 정보" if self.sec_info.is_open() or t is None else f"곡 정보 — {t.display}")

    def reset_now_blocks(self):
        """보기 메뉴: 지금 재생 블럭 모두 펼치고 기본 크기로"""
        if getattr(self, "now_split", None) is None:
            return
        for s in self.now_split.secs:
            s.set_open(True)
        self.now_split.reset_sizes()

    # ---- v016 (f29 G4 · G5): 표지를 화면 배율에 맞춰 · 모니터/배율이 바뀌면 다시
    # ---- v022 (N1): 곡이 바뀌면 표지(JPEG/PNG, 수 MB 일 수 있음) 디코드 · 축소를 백그라운드에서
    #   전에는 UI 스레드에서 QImage.loadFromData + 800px 축소 → 큰 앨범아트면 곡 넘길 때 수십 ms 멈춤.
    #   세대 번호로 빨리 넘긴 곡의 늦은 결과는 버림 · 디코드가 끝날 때까지 이전 표지를 그대로 둠(깜빡임 없음)
    def load_cover(self, t, info):
        from PyQt6.QtCore import QThreadPool
        from ..core.bg import BgEmitter, BgTask
        self._cover_gen = getattr(self, "_cover_gen", 0) + 1
        self._cover_ph = info.album or t.display
        data = bytes(info.cover or b"")
        if not data:
            self._apply_cover(None)
            return
        if getattr(self, "_cover_pool", None) is None:
            self._cover_pool = QThreadPool(self)
            self._cover_pool.setMaxThreadCount(1)
            self._cover_em = BgEmitter(self)
            self._cover_em.done.connect(self._on_cover_ready)
        gen = self._cover_gen
        self._cover_pool.start(BgTask(lambda: (gen, decode_cover(data)), self._cover_em, on_error=lambda e: (gen, None)))

    def _on_cover_ready(self, r):
        gen, img = r
        if gen == getattr(self, "_cover_gen", 0):
            self._apply_cover(img)

    def _apply_cover(self, img):
        self._cover_src = img
        self.render_covers()
        mp = getattr(self, "mini_player", None)
        if mp is not None:
            mp.set_cover_image(img)

    def render_covers(self):
        from ..ui.album_grid import placeholder
        from ..ui.hidpi import dpr, hi_pixmap
        r = dpr(self)
        src, name = getattr(self, "_cover_src", None), getattr(self, "_cover_ph", None)
        simple = self.is_simple()
        targets = [(self.cover, self.cover.width(), self.cover.height())]
        if simple and getattr(self, "bar_cover", None) is not None:
            targets.append((self.bar_cover, self.bar_cover.width(), self.bar_cover.height()))
        for lab, w, h in targets:
            if src is not None:
                lab.setPixmap(hi_pixmap(src, w, h, r, expand=True))
            elif simple:                                    # 표지 없는 곡: 앨범 이름 첫 글자 색 칸 · v023: 곡 없음 = ♪ (빈 칸 대신)
                lab.setPixmap(placeholder(name if name is not None else "♪", w, r))
            else:
                lab.clear()
        self.cover.setVisible(src is not None or simple)
        self._cover_dpr = r

    def on_dpr_changed(self):
        """창이 다른 배율의 모니터로 옮겨짐: 글꼴 힌팅 · 표지 · 앨범 격자 다시 (아이콘은 벡터 엔진이 알아서)"""
        from PyQt6.QtWidgets import QApplication
        from ..ui import skin as _sk
        from ..ui.hidpi import dpr
        r = dpr(self)
        if self.cfg["font_auto"] and self.effective_font_pt() != _sk.font_pt("body"):    # v023: 다른 크기 화면으로
            self.set_font_size(None)
        if abs(r - getattr(self, "_cover_dpr", 0.0)) < 1e-3:
            return
        _sk.apply_app_font(QApplication.instance(), self.effective_font_pt(), str(self.cfg["font_hinting"]), r)
        self.render_covers()
        grid = getattr(getattr(self, "libv", None), "grid", None)
        if grid is not None and hasattr(grid, "refresh_dpr"):
            grid.refresh_dpr()
        self.update()

    def effective_font_pt(self) -> float:
        """v023: font_auto = 화면 크기에 맞춘 pt / 아니면 font_size"""
        if self.cfg["font_auto"]:
            metrics.USE_DPI = bool(self.cfg["font_auto_dpi"])          # v033 (f61 H1)
            return float(metrics.screen_font_pt(self if self.isVisible() else None))
        return float(self.cfg["font_size"])

    def set_font_size(self, pt):
        """보기 → 글자 크기 (바로 적용, 다시 시작 없음) — v016 G9 · v023: pt=None = 자동(화면 맞춤), 틀 크기도 함께"""
        from PyQt6.QtWidgets import QApplication
        from ..ui import skin as _sk
        from ..ui.hidpi import dpr
        if pt is None:
            self.cfg["font_auto"] = True
        else:
            self.cfg["font_auto"] = False
            self.cfg["font_size"] = int(pt)
        pt = self.effective_font_pt()
        _sk.apply_app_font(QApplication.instance(), pt, str(self.cfg["font_hinting"]), dpr(self))
        self.apply_skin()
        self.apply_metrics()
        for a in getattr(self, "a_font_sizes", {}).values():
            a.setChecked(not self.cfg["font_auto"] and a.data() == int(pt))
        if getattr(self, "a_font_auto", None) is not None:
            self.a_font_auto.setChecked(bool(self.cfg["font_auto"]))

    def step_font(self, delta: int):
        """v025: Ctrl+= / Ctrl+- 글자 한 단계 (자동이었으면 지금 크기에서 시작)"""
        from ..ui import skin as _sk
        self.set_font_size(_sk.next_font_pt(self.effective_font_pt(), delta))
        if hasattr(self, "toast"):
            self.toast.show_msg(f"글자 크기 {int(self.cfg['font_size'])}pt")

    def step_theme(self, delta: int):
        """v025: Ctrl+Shift+PgUp / PgDown 단계 테마 한 칸 (밝게 / 어둡게)"""
        from ..ui import skin as _sk
        t = _sk.step_theme(self.cfg["theme"], delta)
        self.apply_skin(t)
        if hasattr(self, "toast"):
            self.toast.show_msg(f"테마: {_sk.SKINS[t].label}")

    def apply_metrics(self):
        """v023: 고정 크기(레일 · 재생 막대 · 표지 · 아이콘 …)를 지금 글자 배율로 다시 + 표지 다시 그림"""
        for r in [self] + [w for w in (getattr(self, "mini", None), getattr(self, "mini_player", None)) if w is not None]:
            metrics.reapply(r)
        self.render_covers()
        if hasattr(self, "_auto_panel"):
            self._auto_panel()
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(0, self._fit_min)                   # 배치가 새 크기로 다시 계산된 뒤

    def _fit_min(self):
        """글자가 커져 버튼 줄이 넘치면 창을 그만큼 넓힘 (최대화 · 전체 화면이면 그대로)"""
        hint = self.minimumSizeHint()
        if self.isMaximized() or self.isFullScreen():
            return
        if self.width() < hint.width() or self.height() < hint.height():
            self.resize(max(self.width(), hint.width()), max(self.height(), hint.height()))

    # ---- 다음 곡 (대기열 → 목록 순서, 5곡)
    def upcoming(self, n: int = 5) -> list:
        c = self.ctrl
        out = [("q", i, t) for i, t in enumerate(list(c.queue)[:n])]
        pl = c.pl
        if len(out) < n and len(pl):
            cur = pl.current
            if c.cfg["shuffle"]:
                pl._ensure_order()
                order = pl._order
                k = order.index(cur) if cur in order else -1
                seq = order[k + 1:] + (order[:k + 1] if c.cfg["repeat"] == "all" else [])
            else:
                seq = list(range(cur + 1, len(pl))) + (list(range(0, max(0, cur + 1))) if c.cfg["repeat"] == "all" else [])
            for i in seq:
                if len(out) >= n:
                    break
                if i != cur:
                    out.append(("p", i, pl.items[i]))
        return out[:n]

    def refresh_up_next(self):
        if getattr(self, "up_next", None) is None:
            return
        self.up_next.clear()
        items = self.upcoming(5)
        for kind, i, t in items:
            it = QListWidgetItem(("⏭ 대기열 · " if kind == "q" else "") + t.display)
            it.setData(Qt.ItemDataRole.UserRole, (kind, i))
            self.up_next.addItem(it)
        if not items:
            self.up_next.addItem(QListWidgetItem("(다음 곡 없음)"))
        has = len(self.ctrl.pl) > 0
        self.empty_row.setVisible(not has)

    def _play_up_next(self, it):
        d = it.data(Qt.ItemDataRole.UserRole)
        if not d:
            return
        kind, i = d
        c = self.ctrl
        if kind == "q":
            if 0 <= i < len(c.queue):
                t = c.queue.pop(i)
                c.queueChanged.emit()
                c.play_index(c._ensure_in_playlist(t))
        else:
            c.play_index(i)

    # ---- v014 지금 재생: 시각화는 보일 때 · 재생 중일 때만 30fps / 다음 곡 목록
    def _sync_vis(self):
        v = getattr(self, "vis", None)
        if v is None:
            return
        on = (self.isVisible() and not self.isMinimized() and self.pages.currentWidget() is self.page_now
              and self.sec_vis.is_open() and self.ctrl.engine.is_playing())
        v.set_active(on)

    def _refresh_now(self, *_a):
        if getattr(self, "up_next", None) is not None:
            self.refresh_up_next()

    # ---- 장시간 운용: 창이 최소화·트레이로 숨겨지면 화면 갱신을 줄임 (소리·미니 가사는 그대로)
    def _sync_active(self):
        active = self.isVisible() and not self.isMinimized()
        self.ctrl.set_ui_active(active)
        if getattr(self, "topbar", None) is not None:
            self.topbar.set_active(active)            # 시세·시계: 창이 보일 때만 (v012)
        if not active:
            self.spec.set_levels([0.0] * self.spec.n)
        self._sync_vis()

    def _on_queue(self):
        self._refresh_now()
        n = len(self.ctrl.queue)
        if self.tabs is not None:
            self.tabs.setTabText(3, f"대기열 ({n})" if n else "대기열")
        if self.b_panel_queue is not None:
            self.b_panel_queue.set_state(f"다음 재생 {n}곡" if n else "비어 있음")

    def screen_info(self) -> str:
        """도움말 → 화면 정보 (v016 G10): 흐릴 때 원인 확인용"""
        from PyQt6.QtCore import QT_VERSION_STR
        from PyQt6.QtGui import QFontInfo
        from PyQt6.QtWidgets import QApplication
        from ..ui import skin as _sk
        from ..ui.hidpi import dpr
        app = QApplication.instance()
        scr = self.screen() or app.primaryScreen()
        fi = QFontInfo(app.font())
        st = getattr(app, "_yamp_font", None) or (0, "?", 0)
        r = dpr(self)
        lines = [f"Qt {QT_VERSION_STR} · 플랫폼 {app.platformName()}"]
        if scr is not None:
            g = scr.geometry()
            lines += [f"화면: {scr.name()} · 논리 {g.width()}×{g.height()}",
                      f"배율(DPR): {r:g}  ({round(r * 100)} %) · 논리 DPI {scr.logicalDotsPerInch():.0f}"]
        lines += [f"글꼴: {fi.family()} {fi.pointSizeF():g}pt (설정 {'자동' if self.cfg['font_auto'] else str(self.cfg['font_size']) + 'pt'} · 틀 배율 {metrics.k():.2f})",
                  f"힌팅: {st[1]} (설정 {self.cfg['font_hinting']}) · 글꼴 엔진 설정: {self.cfg['font_engine']}",
                  f"글자 단계: 큰 제목 {_sk.fs('h1')} · 제목 {_sk.fs('h2')} · 본문 {_sk.fs('body')} · "
                  f"보조 {_sk.fs('cap')} · 눈금 {_sk.fs('tiny')}"]
        return "\n".join(lines)

    def show_screen_info(self):
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.information(self, "화면 정보", self.screen_info() +
                                "\n\n글자가 흐리면: config.txt 의 font_hinting / font_engine 을 바꿔 비교해 보세요.")


def decode_cover(data: bytes):
    """표지 바이트 → QImage (최대 800px) 또는 None — 작업 스레드에서 부름 (v016 G4: 원본은 800px 까지만 들고 화면 배율에 맞춰 그림)"""
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QImage
    img = QImage()
    if not data or not img.loadFromData(data):
        return None
    if max(img.width(), img.height()) > 800:      # 3000px 앨범아트(수십 MB)를 들고 있지 않게
        img = img.scaled(800, 800, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
    return img
