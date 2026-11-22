# -*- coding: utf-8 -*-
"""비주얼라이저 그리기 조각 (vr0.1.0.027, f53) — ui/vis_block.py 의 VisView 가 부름 (450줄 규칙 때문에 나눔)

  다른 앱 표현 방식 반영:
    막대 모양  round(둥근 · 기본) · led(LED 칸: Winamp · foobar2000 LED Bars · audioMotion LEDS)
               mirror(가운데 = 낮은 소리 대칭: audioMotion mirror) · reflex(바닥 반사: audioMotion Reflex)
    원형       foobar2000 Radial Bars · audioMotion radial · Avee Player 원형 스펙트럼 — 가운데 원 둘레로 막대, 위 = 낮은 소리 · 좌우 대칭
    스펙트로그램 foobar2000 Spectrogram — 오른쪽에서 들어와 왼쪽으로 흐르는 색 지도 (아래 = 낮은 소리, 밝을수록 큼)
  색은 모두 테마 토큰 (spectrum_lo · spectrum_hi · peak · graph_bg · fill1_soft …)
"""
import math

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QImage, QLinearGradient, QPainterPath, QPen

from ..domain.vis_math import LED_CELL, heat_rgb, led_cells, mirror_order
from . import metrics


def _grad(r, s, top=None, bottom=None):
    g = QLinearGradient(0, r.bottom() if bottom is None else bottom, 0, r.top() if top is None else top)
    g.setColorAt(0, QColor(s.spectrum_lo))
    g.setColorAt(1, QColor(s.spectrum_hi))
    return g


def draw_bars(p, r, s, v, pk, style="round"):
    """스펙트럼 막대 (style: round · led · mirror · reflex)"""
    if style == "mirror":
        order = mirror_order(len(v))
        v = [v[i] for i in order]
        pk = [pk[i] for i in order]
    n = len(v)
    if not n:
        return
    slot = r.width() / n
    gap = max(1.5 if style == "mirror" else 2.0, slot * 0.28)
    w = slot - gap
    peak = QColor(s.peak)
    if style == "reflex":                                     # 바닥선 = 높이 70 %, 아래 30 % 는 옅은 반사
        base = r.top() + r.height() * 0.70
        hmax = base - r.top() - 4
        g = _grad(r, s, top=r.top(), bottom=base)
        refl = QColor(s.spectrum_lo)
        refl.setAlpha(60)
        for i in range(n):
            x = r.left() + i * slot + gap / 2
            h = max(2.0, v[i] * hmax)
            p.fillRect(QRectF(x, base - h, w, h), g)
            rh = min(r.bottom() - base - 1, h * 0.45)
            if rh > 0:
                p.fillRect(QRectF(x, base + 1, w, rh), refl)
            y = base - max(v[i], pk[i]) * hmax - 3
            p.fillRect(QRectF(x, y, w, 2), peak)
        p.setPen(QPen(QColor(s.graph_grid), 1))
        p.drawLine(QPointF(r.left(), round(base) + 0.5), QPointF(r.right(), round(base) + 0.5))
        return
    hmax = r.height() - 4
    g = _grad(r, s)
    if style == "led":                                        # 칸 높이 LED_CELL(×글자 배율) · 칸 사이 2px · 꼭대기 = 켜진 칸 하나
        cell = max(3.0, LED_CELL * metrics.k())
        total = max(1, int((hmax + 2) // (cell + 2)))
        dim = QColor(s.graph_grid)
        # v032 (f60 P2): 칸마다 fillRect(24막대 × 30칸 ≈ 740번/프레임 — 파이썬 호출이 프레임 시간의 대부분) →
        #   색 묶음(꺼진 칸 · 켜진 칸 · 꼭대기)별로 사각형 목록을 모아 drawRects 3번. 칸끼리 2px 떨어져 겹치는 픽셀이 없고
        #   drawRects(펜 없음) 는 fillRect 와 같은 래스터 경로 → 픽셀까지 같은 그림 (test_v032_perf 가 비교)
        lit, top, off = [], [], []
        bottom = r.bottom()
        ys = [bottom - (c + 1) * (cell + 2) + 2 for c in range(total)]
        for i in range(n):
            x = r.left() + i * slot + gap / 2
            on = led_cells(v[i], hmax, cell)
            top_on = led_cells(max(v[i], pk[i]), hmax, cell)
            lit.extend(QRectF(x, ys[c], w, cell) for c in range(on))
            if top_on > on:
                top.append(QRectF(x, ys[top_on - 1], w, cell))
            off.extend(QRectF(x, ys[c], w, cell) for c in range(on, total) if not (c == top_on - 1 and top_on > on))
        p.save()
        p.setPen(Qt.PenStyle.NoPen)
        for rects, brush in ((off, dim), (lit, g), (top, peak)):
            if rects:
                p.setBrush(QBrush(brush))
                p.drawRects(rects)
        p.restore()
        return
    rad = min(3.0, w / 2)
    for i in range(n):                                        # round · mirror
        x = r.left() + i * slot + gap / 2
        h = max(2.0, v[i] * hmax)
        path = QPainterPath()
        path.addRoundedRect(QRectF(x, r.bottom() - h, w, h), rad, rad)
        p.fillPath(path, g)
        y = r.bottom() - max(v[i], pk[i]) * hmax - 3
        p.fillRect(QRectF(x, y, w, 2), peak)


def draw_radial(p, r, s, v, pk):
    """원형 스펙트럼: 가운데 원(반지름 = 짧은 변 16 %) 둘레 2n 개 막대(최대 길이 = 짧은 변 32 %), 12시 = 낮은 소리, 좌우 대칭 · 꼭대기 = 점"""
    n = len(v)
    if not n:
        return
    cx, cy = r.center().x(), r.center().y()
    side = min(r.width(), r.height())
    r0 = side * 0.16
    span = side * 0.32 - 4
    inner = QColor(s.fill1_soft)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(inner)
    p.drawEllipse(QPointF(cx, cy), r0 - 2, r0 - 2)
    p.setBrush(Qt.BrushStyle.NoBrush)
    lo, hi, pkc = QColor(s.spectrum_lo), QColor(s.spectrum_hi), QColor(s.peak)
    m = 2 * n
    bw = max(2.0, 2 * math.pi * r0 / m * 0.55)
    for j in range(m):
        i = j if j < n else m - 1 - j                         # 오른쪽 반: 낮은 → 높은, 왼쪽 반: 높은 → 낮은
        a = -math.pi / 2 + 2 * math.pi * (j + 0.5) / m
        ca, sa = math.cos(a), math.sin(a)
        ln = max(2.0, v[i] * span)
        c = QColor(lo)
        t = v[i]
        c.setRgb(int(lo.red() + (hi.red() - lo.red()) * t), int(lo.green() + (hi.green() - lo.green()) * t),
                 int(lo.blue() + (hi.blue() - lo.blue()) * t))
        pen = QPen(c, bw)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.drawLine(QPointF(cx + ca * r0, cy + sa * r0), QPointF(cx + ca * (r0 + ln), cy + sa * (r0 + ln)))
        d = r0 + max(v[i], pk[i]) * span + bw
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(pkc)
        p.drawEllipse(QPointF(cx + ca * d, cy + sa * d), bw * 0.45, bw * 0.45)
        p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QPen(QColor(s.line), 1))
    p.drawEllipse(QPointF(cx, cy), r0 - 2, r0 - 2)


_LUT_CACHE: dict = {}


def gram_stops(s) -> tuple:
    """스펙트로그램 색 4개 — 바탕에서 멀어질수록 진하게(밝은 테마) / 밝게(어두운 테마) 되도록 순서 (Android 와 같음)"""
    return (s.graph_bg, s.spectrum_lo, s.spectrum_hi, s.peak) if s.dark else (s.graph_bg, s.spectrum_hi, s.spectrum_lo, s.peak)


def _lut(s):
    key = gram_stops(s)
    lut = _LUT_CACHE.get(key)
    if lut is None:
        import numpy as np
        lut = np.zeros(256, dtype=np.uint32)
        for i in range(256):
            rr, gg, bb = heat_rgb(i / 255, key)
            lut[i] = 0xFF000000 | (rr << 16) | (gg << 8) | bb
        _LUT_CACHE.clear()
        _LUT_CACHE[key] = lut
    return lut


def gram_image(gram, s) -> QImage:
    """GramHistory → QImage (가로 = 칸(오래된 → 최근), 세로 = 밴드: 위 = 높은 소리)"""
    import numpy as np
    cols, n = gram.cols, gram.n
    arr = np.zeros((n, cols), dtype=np.float32)
    off = cols - gram.size                                    # 기록이 덜 찼으면 오른쪽에 붙임
    for i in range(gram.size):
        arr[:, off + i] = gram.col(i)[::-1]
    idx = np.clip(arr * 255 + 0.5, 0, 255).astype(np.uint8)
    pix = np.ascontiguousarray(_lut(s)[idx])
    img = QImage(pix.data, cols, n, cols * 4, QImage.Format.Format_RGB32)
    return img.copy()                                         # numpy 버퍼와 분리


def draw_gram(p, r, s, gram):
    p.save()
    clip = QPainterPath()
    clip.addRoundedRect(r, 6, 6)
    p.setClipPath(clip)
    p.setRenderHint(p.RenderHint.SmoothPixmapTransform, True)
    p.drawImage(r, gram_image(gram, s))
    p.restore()
