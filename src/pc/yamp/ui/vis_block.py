# -*- coding: utf-8 -*-
"""비주얼라이저 블럭 (vr0.1.0.014, f26 §3.3 → v026 f51 재구성) — 지금 재생 화면

  모드 (config 값은 그대로): bars = 스펙트럼 (막대 + 떨어지는 꼭대기) · wave = 웨이브 (스펙트럼을 위아래 대칭 부드러운 곡선)
        chart = 레벨 (최근 10초 소리 크기: RMS 면 + 피크 선 + dB 눈금)
  v026: 막대 · 웨이브는 BandSmoother (오를 때 50 ms · 내릴 때 350 ms 곡선, 꼭대기 0.5초 머문 뒤 중력 낙하) — 전에는
        들어온 값을 그대로 그려 너무 빨리 흔들렸음 · 오실로스코프(사인파 모양) 없앰
        파일 파형 기준(mpv · 스펙트럼 끔): 웨이브 = 지금 위치 앞뒤 3초 파형 포락선(가운데 = 지금) · 막대 = 그 포락선을 밴드로
  데이터: Qt 엔진 = 재생 중 오디오 버퍼 (SpectrumAnalyzer.frame / levels)
          mpv 엔진 · 스펙트럼 끔 = 곡 파형(peaks) + 재생 위치로 대신 ("파일 파형 기준")
  그리기: 30fps, 멈춤 · 창/페이지 안 보임이면 멈춤 (장시간 운용) · 색 = 테마 토큰 · 1px 선은 반 픽셀 정렬
"""
from collections import deque

from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer
from PyQt6.QtGui import QColor, QFontMetrics, QLinearGradient, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from . import skin as skinmod
from .iconbutton import IconButton
import time

from ..domain.vis_math import (BAR_STYLES, DB_FLOOR, DB_GRID, VIS_BANDS, VIS_MODES, BandSmoother,  # noqa: F401
                               GramHistory, db_y, next_bar_style, peaks_window, smooth_curve, to_db)
from . import metrics, vis_draw

MODES = VIS_MODES                  # v027: bars · wave · radial · gram · chart
HIST_S = 10.0
FPS = 30


class VisView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.mode = "chart"
        self.wave: list[float] = [0.0] * 256           # 파일 파형 포락선 (웨이브 · 파일 기준)
        self.sm = BandSmoother(VIS_BANDS)              # v026: 막대 · 웨이브 움직임
        self.bar_style = "round"                       # v027: round · led · mirror · reflex
        self.gram = GramHistory(VIS_BANDS)             # v027: 스펙트로그램 기록 (이 모드일 때만 쌓음)
        self.hist: deque = deque(maxlen=int(HIST_S * FPS))      # (rms, peak)
        self._hist_db: deque = deque(maxlen=self.hist.maxlen)   # v032 (f60 P1): 같은 칸의 (rms dB, 피크 dB) — 넣을 때 한 번만 계산
        self.cur_db = DB_FLOOR
        self.fallback = False
        self.gain = 1.0                                   # (v017 파동 자동 키움 — 오실로스코프와 함께 쓰지 않음, 호환용)
        self._t = None
        metrics.fix(self, min_h=180)  # v033 (f61 H5): 글자 배율

    # 예전 이름 (v025 까지): 지금 보이는 막대 높이 · 꼭대기
    bands = property(lambda self: self.sm.v)
    peak_hold = property(lambda self: self.sm.peaks)

    # ---- 데이터
    def push_frame(self, wave, rms, peak):
        self.fallback = False
        self._hist_add(rms, peak)
        self.cur_db = to_db(peak)

    def _hist_add(self, rms, peak):
        """레벨 기록 한 칸 + 그 dB (v032 f60 P1: 전에는 그릴 때마다 300칸 × 2 번 log10 — 기본 모드 '레벨' 프레임 시간의 약 40 %)"""
        self.hist.append((rms, peak))
        self._hist_db.append((to_db(rms), to_db(peak)))

    def _hist_dbs(self):
        """(rms dB, 피크 dB) 목록 — hist 를 밖에서 직접 바꿨으면(예전 코드 · 테스트) 다시 계산해 맞춤"""
        if len(self._hist_db) != len(self.hist):
            self._hist_db = deque(((to_db(r), to_db(p)) for r, p in self.hist), maxlen=self.hist.maxlen)
        return self._hist_db

    def push_bands(self, lv):
        self.sm.set_target(lv)

    def push_fallback(self, peaks, pos_ms, dur_ms):
        """파일 파형 기준 (mpv · 스펙트럼 끔)"""
        self.fallback = True
        win = peaks_window(peaks, pos_ms, dur_ms, 256)
        self.wave = win
        lvl = win[len(win) // 2] if win else 0.0
        self._hist_add(lvl * 0.7, lvl)
        self.cur_db = to_db(lvl)
        n = self.sm.n
        self.sm.set_target([win[int(i * (len(win) - 1) / (n - 1))] if win else 0.0 for i in range(n)])

    def tick(self, dt: float | None = None):
        """프레임마다 (VisBlock 타이머): 움직임 한 단계. dt = None → 실제 지난 시간"""
        now = time.monotonic()
        if dt is None:
            dt = 1.0 / FPS if self._t is None else now - self._t
        self._t = now
        self.sm.step(dt)
        if self.mode == "gram":
            self.gram.push(self.sm.v)

    def clear(self):
        self.hist.clear()
        self._hist_db.clear()
        self.wave = [0.0] * 256
        self.sm.reset()
        self.gram.clear()
        self.cur_db = DB_FLOOR
        self.update()

    # ---- 그리기
    def paintEvent(self, _e):
        s = skinmod.current()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        rad = metrics.dp(10)                              # v033 (f61 H6): 모서리 · 안쪽 여백도 글자 배율 (10pt = 그대로)
        path.addRoundedRect(r, rad, rad)
        p.fillPath(path, QColor(s.graph_bg))
        p.setPen(QPen(QColor(s.line), 1))
        p.drawPath(path)
        mx, my = metrics.dp(10), metrics.dp(8)
        inner = r.adjusted(mx, my, -mx, -my)
        getattr(self, "_draw_" + self.mode, self._draw_chart)(p, inner, s)
        if self.fallback:
            p.setPen(QColor(s.dim))
            p.setFont(skinmod.role_font(self.font(), "tiny"))
            p.drawText(inner, int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom), "파일 파형 기준")
        p.end()

    def _chart_cols(self):
        """v033 (f61 H6): 눈금 글자 칸 · 지금 dB 칸 폭을 글꼴로 잼 — 전에는 28 · 44px 고정이라 큰 글자(13~16pt)에서
        '-12 dB' 가 '2 dB' 처럼 잘렸음. 10pt 는 글자가 칸보다 작아 예전 값 그대로 (그림 같음)"""
        ft = QFontMetrics(skinmod.role_font(self.font(), "tiny"))
        fb = QFontMetrics(skinmod.role_font(self.font(), "body", bold=True))
        lab_w = max(28, ft.horizontalAdvance("-48"))
        db_w = max(44, fb.horizontalAdvance("-60 dB"))
        return lab_w, db_w, max(18, fb.height())

    def _grid(self, p, r, s, labels=True):
        f = skinmod.role_font(self.font(), "tiny")
        p.setFont(f)
        th = QFontMetrics(f).height()
        lab_w = self._chart_cols()[0]
        last = -1e9
        for db in DB_GRID:
            y = round(db_y(db, r.top(), r.height())) + 0.5
            p.setPen(QPen(QColor(s.graph_grid), 1, Qt.PenStyle.DashLine))
            p.drawLine(QPointF(r.left() + lab_w + 2, y), QPointF(r.right(), y))
            if labels and y - last >= th:                # v016: 눈금 글자끼리 겹치면 건너뜀 (큰 글자 · 낮은 블럭)
                last = y
                p.setPen(QColor(s.dim))
                p.drawText(QRectF(r.left(), y - th / 2, lab_w, th), int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter), f"{db}")

    def _draw_chart(self, p, r, s):
        self._grid(p, r, s)
        lab_w, db_w, db_h = self._chart_cols()
        plot = r.adjusted(lab_w + 4, 0, -(db_w + 2), 0)
        n = self.hist.maxlen or 1
        if self.hist:
            step = plot.width() / max(1, n - 1)
            x0 = plot.right() - (len(self.hist) - 1) * step
            area = QPainterPath(QPointF(x0, plot.bottom()))
            line = QPainterPath()
            top, ph = plot.top(), plot.height()
            for i, (rd, pd) in enumerate(self._hist_dbs()):   # v032 (f60 P1): dB 는 넣을 때 계산해 둔 값 (y 식은 db_y 와 같음)
                x = x0 + i * step
                area.lineTo(x, top + ph * (min(0.0, rd) / DB_FLOOR))
                y2 = top + ph * (min(0.0, pd) / DB_FLOOR)
                line.moveTo(x, y2) if i == 0 else line.lineTo(x, y2)
            area.lineTo(plot.right(), plot.bottom())
            area.closeSubpath()
            g = QLinearGradient(0, plot.top(), 0, plot.bottom())
            c1, c2 = QColor(s.spectrum_hi), QColor(s.spectrum_lo)
            c1.setAlpha(200)
            c2.setAlpha(90)
            g.setColorAt(0, c1)
            g.setColorAt(1, c2)
            p.fillPath(area, g)
            p.setPen(QPen(QColor(s.peak), 1.4))
            p.drawPath(line)
        # 지금 dB · 0 dB(클리핑) 표시
        p.setFont(skinmod.role_font(self.font(), "body", bold=True))
        clip = self.cur_db > -0.5
        p.setPen(QColor(s.rise if clip else s.accent_text))
        txt = "—" if self.cur_db <= DB_FLOOR else f"{self.cur_db:.0f} dB"
        p.drawText(QRectF(r.right() - db_w, r.top(), db_w, db_h), int(Qt.AlignmentFlag.AlignRight), txt)

    @staticmethod
    def _curve(vals, r, mid, amp, sign):
        """부드러운 곡선 (위 sign=-1 / 아래 +1) — 양 끝 0"""
        segs = smooth_curve(vals, r.left(), r.right())
        path = QPainterPath(QPointF(r.left(), mid))
        for c1x, c1y, c2x, c2y, x, y in segs:
            path.cubicTo(QPointF(c1x, mid + sign * c1y * amp), QPointF(c2x, mid + sign * c2y * amp),
                         QPointF(x, mid + sign * y * amp))
        return path

    def _draw_wave(self, p, r, s):
        """v026 웨이브: 스펙트럼(낮은 소리 → 높은 소리)을 가운데 선 위아래 대칭 곡선으로 · 옅은 꼭대기 곡선
        파일 파형 기준이면 지금 위치 앞뒤 3초 포락선 (가운데 세로선 = 지금)"""
        mid = round(r.center().y()) + 0.5
        amp = r.height() / 2 - 2
        if self.fallback:
            vals = [max(0.0, float(v)) for v in self.wave[::4]]
        else:
            vals = list(self.sm.v)
        top = self._curve(vals, r, mid, amp, -1)
        bot = self._curve(vals, r, mid, amp, 1)
        body = QPainterPath(top)
        body.connectPath(bot.toReversed())
        body.closeSubpath()
        g = QLinearGradient(0, r.top(), 0, r.bottom())
        hi, lo = QColor(s.spectrum_hi), QColor(s.spectrum_lo)
        hi.setAlpha(150)
        lo.setAlpha(150)
        core = QColor(s.spectrum_lo)
        core.setAlpha(230)
        g.setColorAt(0, hi)
        g.setColorAt(0.5, core)
        g.setColorAt(1, hi)
        p.fillPath(body, g)
        pen = QPen(QColor(s.wave_played), 1.6)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        p.drawPath(top)
        p.drawPath(bot)
        if not self.fallback:                                  # 꼭대기(최근 최고) = 옅은 선
            pk = QColor(s.peak)
            pk.setAlpha(110)
            p.setPen(QPen(pk, 1.0))
            p.drawPath(self._curve(self.sm.peaks, r, mid, amp, -1))
            p.drawPath(self._curve(self.sm.peaks, r, mid, amp, 1))
        else:
            x = round(r.center().x()) + 0.5
            p.setPen(QPen(QColor(s.accent_text), 1.5))
            p.drawLine(QPointF(x, r.top()), QPointF(x, r.bottom()))
        p.setPen(QPen(QColor(s.graph_grid), 1))
        p.drawLine(QPointF(r.left(), mid), QPointF(r.right(), mid))

    def _draw_bars(self, p, r, s):
        """v026 스펙트럼 · v027 막대 모양 4가지 (vis_draw.draw_bars)"""
        vis_draw.draw_bars(p, r, s, self.sm.v, self.sm.peaks, self.bar_style)

    def _draw_radial(self, p, r, s):
        vis_draw.draw_radial(p, r, s, self.sm.v, self.sm.peaks)

    def _draw_gram(self, p, r, s):
        vis_draw.draw_gram(p, r, s, self.gram)


class VisBlock(QWidget):
    """제목은 Section(접기)이 그림 — 여기는 모드 버튼 줄 + 그림"""

    def __init__(self, cfg, parent=None, header=True):
        super().__init__(parent)
        self.cfg = cfg
        self.view = VisView(self)
        self.view.mode = cfg["vis_mode"] if cfg["vis_mode"] in MODES else "chart"
        bs = cfg["vis_bar_style"]
        self.view.bar_style = bs if bs in BAR_STYLES else "round"
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        metrics.spacing(v, 6)
        row = QHBoxLayout()
        metrics.spacing(row, 2)
        self.mode_row = row                 # Section 제목 줄로 옮겨 붙일 수 있음 (지금 재생 페이지)
        self.btns = {}
        for mode, icon, key in (("bars", "eq", "vis_bars"), ("wave", "wave", "vis_wave"), ("radial", "radial", "vis_radial"),
                                ("gram", "gram", "vis_gram"), ("chart", "chart", "vis_chart")):   # v026: 스펙트럼 먼저 · v027: 원형 · 스펙트로그램
            b = IconButton(icon, key, lambda _=False, m=mode: self.set_mode(m), checkable=True, size=18)
            self.btns[mode] = b
            row.addWidget(b)
        if header:
            row.insertStretch(0, 1)
            v.addLayout(row)
        v.addWidget(self.view, 1)
        self._sync_btns()
        self._timer = QTimer(self, interval=int(1000 / FPS), timeout=self._frame)
        self.active = False
        self.source = None            # 대신 그릴 때: () -> (peaks, pos_ms, dur_ms, playing)
        self._got_pcm = 0

    def _frame(self):
        self.tick_fallback()
        self.view.tick()                                    # v026: 막대 · 웨이브 움직임 (지난 시간 기준)
        self.view.update()

    BAR_STYLE_NAMES = {"round": "둥근 막대", "led": "LED", "mirror": "미러 (가운데 = 낮은 소리)", "reflex": "반사"}

    def set_mode(self, m):
        """v027: 이미 스펙트럼인데 스펙트럼 버튼을 또 누르면 막대 모양 바꾸기 (둥근 → LED → 미러 → 반사)"""
        if m not in MODES:
            return
        if m == "bars" and self.view.mode == "bars":
            self.set_bar_style(next_bar_style(self.view.bar_style))
        self.view.mode = m
        self.cfg["vis_mode"] = m
        self._sync_btns()
        self.view.update()

    def set_bar_style(self, st):
        if st in BAR_STYLES:
            self.view.bar_style = st
            self.cfg["vis_bar_style"] = st
            self._sync_btns()
            self.view.update()

    def _sync_btns(self):
        for m, b in self.btns.items():
            b.setChecked(m == self.view.mode)
        b = self.btns.get("bars")
        if b is not None:
            b.set_state(f"막대 모양: {self.BAR_STYLE_NAMES.get(self.view.bar_style, '')} — 다시 누르면 바뀜")

    def on_frame(self, fr):
        self._got_pcm = 6                                   # 최근 0.2초 안에 PCM 이 왔음
        self.view.push_frame(*fr)

    def on_levels(self, lv):
        self.view.push_bands(lv)

    def tick_fallback(self):
        """PCM 이 안 오면(mpv · 스펙트럼 끔) 파일 파형으로"""
        if self._got_pcm > 0:
            self._got_pcm -= 1
            return
        if self.source is None:
            return
        peaks, pos, dur, playing = self.source()
        if playing and peaks:
            self.view.push_fallback(peaks, pos, dur)

    def set_active(self, on: bool):
        """보일 때 · 재생 중만 30fps"""
        on = bool(on)
        if on == self.active:
            return
        self.active = on
        if on:
            self._timer.start()
        else:
            self._timer.stop()
            self.view.update()

    def set_skin(self, _s=None):
        self.view.update()
