package com.ascen.yamp.ui

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.background
import androidx.compose.foundation.basicMarquee
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectHorizontalDragGestures
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.setValue
import androidx.compose.runtime.snapshotFlow
import androidx.compose.runtime.withFrameNanos
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.Shadow
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.TextUnit
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.ascen.yamp.app.AppViewModel
import com.ascen.yamp.data.fmtTime
import com.ascen.yamp.domain.BandSmoother
import com.ascen.yamp.domain.VisMath
import com.ascen.yamp.playback.Fx
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.first
import kotlin.math.max

/*
 * 재생 위치를 읽는 작은 부품들 (vr0.1.0.007).
 * 위치(positionMs)는 화면을 보는 중 초당 20번 바뀜 → 위치를 읽는 곳을 여기 작은 컴포저블 / 그리기 단계로만 모아
 * 카드 전체(앨범아트 · 제목 · 버튼)가 매번 다시 구성되지 않게 함.
 */

/** 이보다 작은 레벨은 0 으로 봄 (일시정지 중 프레임 루프 멈춤) */
private const val LEVEL_EPS = 0.01f

/** v032 (f60 A3): 스펙트럼 프레임 뒤 쉬는 시간 — 60 Hz 화면 = 그대로 60fps · 90 Hz ≈ 45fps · 120 Hz = 60fps */
private const val SPECTRUM_GAP_MS = 12L

/** 위치 글자 (경과 시간) — 이 Text 만 다시 구성됨 */
@Composable
fun PosText(vm: AppViewModel, color: Color, fontSize: TextUnit, prefix: String = "") {
    Text(prefix + fmtTime(vm.positionMs), color = color, fontSize = fontSize)
}

/** LCD 시간 (탭 → 경과/남은 시간) */
@Composable
fun LcdClock(vm: AppViewModel, remaining: Boolean, onToggle: () -> Unit, modifier: Modifier = Modifier) {
    val s = LocalSkin.current
    val pos = vm.positionMs
    val dur = vm.durationMs
    val txt = if (remaining && dur > 0) "-" + fmtTime(max(0L, dur - pos)) else fmtTime(pos)
    // 빛(그림자)은 어두운 테마만 — 밝은 바탕에서는 번져 보임
    Text(txt, color = s.lcdFg, fontFamily = FontFamily.Monospace, fontSize = 28.sp, fontWeight = FontWeight.Bold,
        style = if (s.dark) TextStyle(shadow = Shadow(s.lcdFg, Offset.Zero, 18f)) else TextStyle(),
        modifier = modifier.clickable(onClick = onToggle))
}

/** 스펙트럼 레벨을 여기서만 구독 (초당 20번 바뀜 → 앨범아트 카드 전체가 다시 구성되지 않게). wave = 웨이브 모양 (v026) */
@Composable
fun VmSpectrum(vm: AppViewModel, on: Boolean, modifier: Modifier = Modifier, shape: String = "round") {
    val levels by vm.levels.collectAsStateWithLifecycle()
    NeonSpectrum(levels, on, modifier, LocalSkin.current, shape)
}

/**
 * 스펙트럼 막대 / 웨이브. on = false 면 그리지 않음.
 * v026 (f51): 움직임 = BandSmoother (오를 때 50 ms · 내릴 때 350 ms 곡선, 꼭대기 0.5초 머문 뒤 낙하) — 전에는 20Hz 로 오는 값을
 *   그대로 올리고 프레임마다 일정하게 깎아 너무 빨리 흔들렸음. 프레임 간격(dt) 기준이라 기기 fps 와 무관.
 *   wave = 가운데 선 위아래 대칭 부드러운 곡선 (낮은 소리 → 높은 소리), 옅은 선 = 꼭대기.
 *   모두 내려앉고 새 레벨이 없으면(일시정지 · 무음) 프레임 루프를 멈추고 새 레벨을 기다림
 */
@Composable
fun NeonSpectrum(levels: FloatArray, on: Boolean, modifier: Modifier = Modifier, s: Skin = LocalSkin.current, shape: String = "round") {
    val wave = shape == "wave"
    val mirrorIdx = remember { IntArray(Fx.BANDS * 2) }
    val n = Fx.BANDS
    val sm = remember { BandSmoother(n) }
    var frame by remember { mutableLongStateOf(0L) }
    val latest by rememberUpdatedState(levels)
    val upper = remember { Path() }
    val lower = remember { Path() }
    if (on) LaunchedEffect(Unit) {
        var seen: FloatArray? = null
        var last = -1L
        while (true) {
            if (sm.idle()) {
                val prev = seen
                snapshotFlow { latest }.first { a -> a !== prev && a.any { it > LEVEL_EPS } }
                last = -1L
            }
            withFrameNanos { tm ->
                val cur = latest
                if (cur !== seen) { sm.setTarget(cur); seen = cur }
                sm.step(if (last < 0) 1.0 / 60 else (tm - last) / 1e9)
                last = tm
                frame = tm
            }
            // v032 (f60 A3): 90 · 120 Hz 화면에서 화면 주사율 그대로(초당 90~120번) 다시 그리던 것 → 약 60fps 상한
            //   (값은 20Hz 로 오고 움직임은 지난 시간(dt) 기준이라 모양 · 속도는 같음. 60 Hz 화면은 그대로 60fps)
            delay(SPECTRUM_GAP_MS)
        }
    }
    // 위(peak) → spectrum_hi → 아래(spectrum_lo) — 써니 = 진주황 · 노랑 · 주황, 네온 = 분홍 · 노랑 · 초록
    val brush = remember(s) { Brush.verticalGradient(listOf(s.peak, s.spectrumHi, s.spectrumLo)) }
    val waveBrush = remember(s) { Brush.verticalGradient(listOf(s.spectrumHi, s.spectrumLo, s.spectrumHi)) }
    Canvas(modifier) {
        if (!on || frame < 0L) return@Canvas      // 프레임마다 다시 그리기 (state 읽기)
        val v = sm.v
        val pk = sm.peaks
        if (wave) {
            val mid = size.height / 2
            val amp = mid - 2f
            bandCurve(upper, v, size.width, mid, -amp, true)
            bandCurve(lower, v, size.width, mid, amp, true)
            drawPath(upper, waveBrush, alpha = 0.85f)
            drawPath(lower, waveBrush, alpha = 0.85f)
            bandCurve(upper, v, size.width, mid, -amp, false)
            bandCurve(lower, v, size.width, mid, amp, false)
            drawPath(upper, s.wavePlayed, style = Stroke(width = 1.6f * density))
            drawPath(lower, s.wavePlayed, style = Stroke(width = 1.6f * density))
            bandCurve(upper, pk, size.width, mid, -amp, false)
            bandCurve(lower, pk, size.width, mid, amp, false)
            drawPath(upper, s.peak, alpha = 0.45f, style = Stroke(width = 1f * density))
            drawPath(lower, s.peak, alpha = 0.45f, style = Stroke(width = 1f * density))
            drawLine(s.graphGrid, Offset(0f, mid), Offset(size.width, mid), 1f)
            return@Canvas
        }
        if (shape == "radial") { drawRadial(v, pk, s); return@Canvas }
        // v027 막대 모양: round(둥근) · led(LED 칸) · mirror(가운데 = 낮은 소리) · reflex(바닥 반사)
        val mirror = shape == "mirror"
        if (mirror) VisMath.mirrorOrder(n, mirrorIdx)
        val cnt = if (mirror) n * 2 else n
        val slot = size.width / cnt
        val gap = max(if (mirror) 1.5f else 2f, slot * 0.28f)
        val bw = slot - gap
        val base = if (shape == "reflex") size.height * 0.70f else size.height
        val hmax = base - 4f
        val cell = VisMath.LED_CELL * density
        val cellGap = 2f * density
        val total = max(1, ((hmax + cellGap) / (cell + cellGap)).toInt())
        for (j in 0 until cnt) {
            val i = if (mirror) mirrorIdx[j] else j
            val x = j * slot + gap / 2
            val top = max(v[i], pk[i])
            if (shape == "led") {
                val lit = VisMath.ledCells(v[i], hmax, cell, cellGap)
                val topOn = VisMath.ledCells(top, hmax, cell, cellGap)
                for (c in 0 until total) {
                    val y = size.height - (c + 1) * (cell + cellGap) + cellGap
                    when {
                        c < lit -> drawRect(brush, Offset(x, y), Size(bw, cell))
                        c == topOn - 1 && topOn > lit -> drawRect(s.peak, Offset(x, y), Size(bw, cell))
                        else -> drawRect(s.graphGrid, Offset(x, y), Size(bw, cell))
                    }
                }
                continue
            }
            val bh = (v[i] * hmax).coerceAtLeast(2f)
            drawRect(brush, Offset(x - bw * 0.15f, base - bh), Size(bw * 1.3f, bh), alpha = 0.16f)   // 빛
            drawRoundRect(brush, Offset(x, base - bh), Size(bw, bh), CornerRadius(3f, 3f), alpha = 0.92f)
            if (shape == "reflex") {
                val rh = minOf(size.height - base - 1f, bh * 0.45f)
                if (rh > 0f) drawRect(s.spectrumLo, Offset(x, base + 1f), Size(bw, rh), alpha = 0.25f)        // 반사
            }
            val py = base - top * hmax - 3f * density
            drawRect(s.peak, Offset(x, py), Size(bw, 2f * density))                                           // 꼭대기
        }
        if (shape == "reflex") drawLine(s.graphGrid, Offset(0f, base), Offset(size.width, base), 1f)
    }
}

/**
 * 원형 스펙트럼 (v027 — foobar2000 Radial · audioMotion radial · Avee): 가운데 원 둘레 2n 막대, 12시 = 낮은 소리, 좌우 대칭, 꼭대기 = 점
 */
private fun androidx.compose.ui.graphics.drawscope.DrawScope.drawRadial(v: FloatArray, pk: FloatArray, s: Skin) {
    val n = v.size
    val cx = size.width / 2
    val cy = size.height / 2
    val side = minOf(size.width, size.height)
    val r0 = side * 0.16f
    val span = side * 0.32f - 4f
    drawCircle(s.fill1Soft, r0 - 2f, Offset(cx, cy))
    drawCircle(s.line, r0 - 2f, Offset(cx, cy), style = Stroke(width = 1f * density))
    val m = 2 * n
    val bw = max(2f, (2 * Math.PI * r0 / m * 0.55).toFloat())
    for (j in 0 until m) {
        val i = if (j < n) j else m - 1 - j
        val a = -Math.PI / 2 + 2 * Math.PI * (j + 0.5) / m
        val ca = kotlin.math.cos(a).toFloat()
        val sa = kotlin.math.sin(a).toFloat()
        val ln = max(2f, v[i] * span)
        val c = androidx.compose.ui.graphics.lerp(s.spectrumLo, s.spectrumHi, v[i].coerceIn(0f, 1f))
        drawLine(c, Offset(cx + ca * r0, cy + sa * r0), Offset(cx + ca * (r0 + ln), cy + sa * (r0 + ln)), bw, cap = StrokeCap.Round)
        val d = r0 + max(v[i], pk[i]) * span + bw
        drawCircle(s.peak, bw * 0.45f, Offset(cx + ca * d, cy + sa * d))
    }
}

/**
 * 웨이브 곡선 (v026): 밴드 값(0..1)을 Catmull-Rom → 3차 베지어로, 양 끝 0. amp 음수 = 위쪽.
 * fill = true → 가운데 선에서 닫힌 면, false → 곡선만. Path 재사용 (메모리 할당 없음)
 */
private fun bandCurve(path: Path, vals: FloatArray, w: Float, mid: Float, amp: Float, fill: Boolean) {
    val n = vals.size
    val cnt = n + 2
    fun vy(j: Int): Float = if (j <= 0 || j >= cnt - 1) 0f else vals[j - 1]
    fun vx(j: Int): Float = w * j.coerceIn(0, cnt - 1) / (cnt - 1)
    path.reset()
    path.moveTo(0f, mid)
    for (i in 0 until cnt - 1) {
        val c1x = vx(i) + (vx(i + 1) - vx(i - 1)) / 6
        val c1y = max(0f, vy(i) + (vy(i + 1) - vy(i - 1)) / 6)
        val c2x = vx(i + 1) - (vx(i + 2) - vx(i)) / 6
        val c2y = max(0f, vy(i + 1) - (vy(i + 2) - vy(i)) / 6)
        path.cubicTo(c1x, mid + c1y * amp, c2x, mid + c2y * amp, vx(i + 1), mid + vy(i + 1) * amp)
    }
    if (fill) path.close()
}

/**
 * 파형 시크바: 재생된 부분 wavePlayed, 나머지 waveRest, A-B 구간 fill1Soft. 탭/끌기 = 이동.
 * wave == null (끄기 · 계산 전 · 실패) → 일반 막대 모양.
 * posMs 는 그리기 단계에서만 읽음 (vr0.1.0.007) → 위치가 바뀌어도 다시 그리기만, 재구성 없음
 */
@Composable
fun WaveSeekBar(wave: FloatArray?, posMs: () -> Long, durMs: Long, abA: Long, abB: Long, onSeek: (Long) -> Unit, modifier: Modifier = Modifier) {
    val s = LocalSkin.current
    var drag by remember { mutableFloatStateOf(-1f) }
    val seek by rememberUpdatedState(onSeek)
    val dur by rememberUpdatedState(durMs)
    Canvas(
        modifier
            .pointerInput(Unit) {
                detectTapGestures { o -> if (dur > 0) seek(((o.x / size.width).coerceIn(0f, 1f) * dur).toLong()) }
            }
            .pointerInput(Unit) {
                detectHorizontalDragGestures(
                    onDragStart = { o -> drag = (o.x / size.width).coerceIn(0f, 1f) },
                    onDragEnd = { if (dur > 0 && drag >= 0f) seek((drag * dur).toLong()); drag = -1f },
                    onDragCancel = { drag = -1f },
                ) { ch, _ ->
                    ch.consume()
                    drag = (ch.position.x / size.width).coerceIn(0f, 1f)
                }
            },
    ) {
        val frac = if (drag >= 0f) drag else if (durMs > 0) (posMs().toFloat() / durMs).coerceIn(0f, 1f) else 0f
        val w = size.width
        val h = size.height
        if (durMs > 0 && abA >= 0) {
            val a = (abA.toFloat() / durMs).coerceIn(0f, 1f) * w
            val b = if (abB > abA) (abB.toFloat() / durMs).coerceIn(0f, 1f) * w else a + 3f
            drawRect(s.fill1Soft, Offset(a, 0f), Size(max(3f, b - a), h))
        }
        if (wave != null && wave.isNotEmpty()) {
            val n = wave.size
            val step = w / n
            val bw = max(1.5f, step * 0.6f)
            for (i in 0 until n) {
                val bh = max(3f, wave[i] * (h - 4f))
                val x = i * step + (step - bw) / 2
                val played = (i + 0.5f) / n <= frac
                drawRoundRect(if (played) s.wavePlayed else s.waveRest, Offset(x, (h - bh) / 2), Size(bw, bh), CornerRadius(bw / 2, bw / 2))
            }
        } else {
            val y = h / 2
            drawLine(s.waveRest, Offset(4f, y), Offset(w - 4f, y), strokeWidth = 6f, cap = StrokeCap.Round)
            drawLine(s.fill1, Offset(4f, y), Offset(4f + (w - 8f) * frac, y), strokeWidth = 6f, cap = StrokeCap.Round)
        }
        // 현재 위치 손잡이
        val px = if (w >= 4f) (frac * w).coerceIn(2f, w - 2f) else (frac * w).coerceIn(0f, w.coerceAtLeast(0f))   // v013: 아주 좁을 때 예외 방지
        drawLine(s.text, Offset(px, 2f), Offset(px, h - 2f), strokeWidth = 2.5f, cap = StrokeCap.Round)
    }
}

// ------------------------------------------------------------ 다른 탭 아래 미니 플레이어
@OptIn(ExperimentalFoundationApi::class)
@Composable
fun MiniPlayer(vm: AppViewModel, onOpen: () -> Unit, modifier: Modifier = Modifier) {
    val s = LocalSkin.current
    val t = vm.currentTrack ?: return
    Column(modifier.neonCard(s)) {
        Row(Modifier.fillMaxWidth().clickable(onClick = onOpen).padding(start = 14.dp, end = 6.dp, top = 6.dp, bottom = 4.dp),
            verticalAlignment = Alignment.CenterVertically) {
            // 제목 부분 길게 누르기 = '재생 화면' 설명 (누르면 재생 화면으로)
            TipBox("mini_open", Modifier.weight(1f), anchorModifier = Modifier.fillMaxWidth(), contentAlignment = Alignment.CenterStart) {
                Column(Modifier.fillMaxWidth()) {
                    Text(t.display, color = s.text, fontSize = 13.sp, maxLines = 1, overflow = TextOverflow.Clip,
                        modifier = Modifier.basicMarquee(iterations = Int.MAX_VALUE))
                    MiniLine(vm)
                }
            }
            IconAction(YIcons.prev, "prev", vm::prev, size = 40.dp, iconSize = 20.dp)
            IconAction(if (vm.isPlaying) YIcons.pause else YIcons.play, if (vm.isPlaying) "pause" else "play", vm::toggle,
                size = 44.dp, iconSize = 26.dp, tint = s.accentText)
            IconAction(YIcons.next, "next", vm::next, size = 40.dp, iconSize = 20.dp)
        }
        // 진행 막대: 위치는 그리기 단계에서만 읽음
        val accent = s.fill2
        Box(Modifier.fillMaxWidth().padding(horizontal = 14.dp).padding(bottom = 6.dp).height(2.dp).background(s.waveRest)
            .drawBehind {
                val dur = vm.durationMs.coerceAtLeast(1)
                val f = (vm.positionMs.toFloat() / dur).coerceIn(0f, 1f)
                drawRect(accent, Offset.Zero, Size(size.width * f, size.height))
            })
    }
}

/** 미니 플레이어 둘째 줄: 현재 가사 줄 (싱크 가사가 없으면 위치 / 길이) */
@Composable
private fun MiniLine(vm: AppViewModel) {
    val s = LocalSkin.current
    val ly = vm.lyrics
    val line = if (ly != null && ly.synced) ly.blocks.getOrNull(vm.lyricIndex)?.lines?.firstOrNull().orEmpty() else ""
    Text(line.ifEmpty { "${fmtTime(vm.positionMs)} / ${fmtTime(vm.durationMs)}" }, color = s.accentText,
        fontSize = 11.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
}
