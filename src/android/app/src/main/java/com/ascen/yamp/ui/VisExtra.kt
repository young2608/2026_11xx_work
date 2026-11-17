package com.ascen.yamp.ui

import android.graphics.Bitmap
import androidx.compose.foundation.Canvas
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.setValue
import androidx.compose.runtime.withFrameNanos
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.FilterQuality
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.IntSize
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.ascen.yamp.app.AppViewModel
import com.ascen.yamp.domain.BandSmoother
import com.ascen.yamp.domain.GramHistory
import com.ascen.yamp.domain.VisMath
import com.ascen.yamp.playback.Fx

/**
 * 스펙트로그램 (vr0.1.0.027, f53 — foobar2000 Spectrogram 방식): 오른쪽에서 들어와 왼쪽으로 흐르는 색 지도.
 *   가로 = 최근 약 5초 (33 ms 마다 1칸, 150칸) · 세로 = 24 밴드 (아래 = 낮은 소리) · 밝을수록(밝은 테마는 진할수록) 큼.
 *   색 = 테마 graph_bg → spectrum → peak (PC vis_draw.gram_stops 와 같은 순서). 움직임은 BandSmoother 로 고른 값.
 *   그리기: 150×24 Bitmap 하나를 재사용(setPixels) → 늘려 그림. 재생 중 · 보일 때만, 새 레벨이 없고 다 내려앉으면 쉼
 */
@Composable
fun GramView(vm: AppViewModel, modifier: Modifier = Modifier) {
    val s = LocalSkin.current
    val levels by vm.levels.collectAsStateWithLifecycle()
    val latest by rememberUpdatedState(levels)
    val n = Fx.BANDS
    val cols = VisMath.GRAM_COLS
    val sm = remember { BandSmoother(n) }
    val gram = remember { GramHistory(n, cols) }
    val bmp = remember { Bitmap.createBitmap(cols, n, Bitmap.Config.ARGB_8888) }
    val img = remember(bmp) { bmp.asImageBitmap() }
    val pixels = remember { IntArray(cols * n) }
    val stops = remember(s) {
        if (s.dark) intArrayOf(s.def.argb("graph_bg"), s.def.argb("spectrum_lo"), s.def.argb("spectrum_hi"), s.def.argb("peak"))
        else intArrayOf(s.def.argb("graph_bg"), s.def.argb("spectrum_hi"), s.def.argb("spectrum_lo"), s.def.argb("peak"))
    }
    var frame by remember { mutableLongStateOf(0L) }
    val playing = vm.isPlaying
    val visible = vm.uiVisible
    LaunchedEffect(playing, visible, stops) {
        if (!visible) return@LaunchedEffect
        var seen: FloatArray? = null
        var last = -1L
        var acc = 0.0
        while (true) {
            withFrameNanos { tm ->
                val cur = latest
                if (cur !== seen) { sm.setTarget(cur); seen = cur }
                val dt = if (last < 0) TICK_S else (tm - last) / 1e9
                last = tm
                sm.step(dt)
                acc += dt
                var pushed = false
                while (acc >= TICK_S) { acc -= TICK_S; if (playing) { gram.push(sm.v); pushed = true } }
                if (pushed || frame == 0L) {
                    // 비트맵 다시 채움 (가로 = 칸, 세로 = 밴드: 위 = 높은 소리) — 덜 찬 기록은 오른쪽에 붙임
                    val off = cols - gram.size
                    val bg = VisMath.heatArgb(0f, stops)
                    for (x in 0 until cols) {
                        for (b in 0 until n) {
                            val y = n - 1 - b
                            pixels[y * cols + x] = if (x < off) bg else VisMath.heatArgb(gram.at(x - off, b), stops)
                        }
                    }
                    bmp.setPixels(pixels, 0, cols, 0, 0, cols, n)
                    frame = tm
                }
            }
            if (!playing && sm.idle()) break
        }
    }
    Canvas(modifier) {
        if (frame < 0L) return@Canvas                // 새 칸이 생길 때마다 다시 그리기 (state 읽기)
        drawImage(img, IntOffset.Zero, IntSize(cols, n), IntOffset.Zero,
            IntSize(size.width.toInt().coerceAtLeast(1), size.height.toInt().coerceAtLeast(1)), filterQuality = FilterQuality.Low)
        drawLine(s.graphGrid, Offset(0f, size.height - 0.5f), Offset(size.width, size.height - 0.5f), 1f)
    }
}

/** 스펙트로그램 1칸 시간 (초) */
private const val TICK_S = 0.033
