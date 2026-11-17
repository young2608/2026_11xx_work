package com.ascen.yamp.ui

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.runtime.withFrameNanos
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.ascen.yamp.app.AppViewModel
import com.ascen.yamp.domain.LevelHistory
import com.ascen.yamp.domain.VisMath
import com.ascen.yamp.playback.Fx
import kotlinx.coroutines.delay

/**
 * 비주얼라이저 블럭 (vr0.1.0.014, f26 §3.3 · D8 → v026 f51 재구성): 스펙트럼 · 웨이브 · 레벨. 제목 줄 오른쪽 아이콘으로 모드 바꾸기
 *   (vis_mode 값은 그대로 bars / wave / chart).
 *   스펙트럼 = 막대 + 떨어지는 꼭대기 · 웨이브 = 스펙트럼을 위아래 대칭 부드러운 곡선 (둘 다 BandSmoother — 천천히 움직임)
 *     스펙트럼 끔이면 웨이브 = 파일 파형 앞뒤 3초 포락선 (가운데 = 지금) · 오실로스코프(사인파 모양)는 없앰
 *   v027 (f53, 다른 앱 표현 방식): 원형(Avee · foobar2000 Radial) · 스펙트로그램(foobar2000) 추가,
 *     스펙트럼 막대 모양 4가지 = 둥근 · LED(Winamp) · 미러 · 반사 (audioMotion) — 스펙트럼 아이콘을 한 번 더 누르면 바뀜
 *   레벨 = 최근 10초 RMS 면 + 피크 선 + dB 눈금
 *   데이터: 스펙트럼(Visualizer) 켬 = 실제 소리 RMS/피크, 끔 = 파일 파형(peaks) + 재생 위치 ("파일 파형 기준")
 *   그리기: 화면이 보이고 재생 중일 때만, 최대 30fps (장시간 운용 규칙). 접으면 내용이 빠져 루프도 멈춤
 */
@Composable
fun VisCard(vm: AppViewModel) {
    val s = LocalSkin.current
    val mode = vm.visMode
    CollapsibleCard("play_vis", "비주얼라이저", contentPadding = PaddingValues(start = 10.dp, end = 10.dp, bottom = 10.dp),
        actions = {
            IconAction(YIcons.visBars, "vis_bars", { vm.setVisMode(VisMath.MODE_BARS) }, size = 30.dp, iconSize = 16.dp,
                active = mode == VisMath.MODE_BARS, tint = if (mode == VisMath.MODE_BARS) s.accentText else s.dim)
            IconAction(YIcons.visWave, "vis_wave", { vm.setVisMode(VisMath.MODE_WAVE) }, size = 30.dp, iconSize = 16.dp,
                active = mode == VisMath.MODE_WAVE, tint = if (mode == VisMath.MODE_WAVE) s.accentText else s.dim)
            IconAction(YIcons.visRadial, "vis_radial", { vm.setVisMode(VisMath.MODE_RADIAL) }, size = 30.dp, iconSize = 16.dp,
                active = mode == VisMath.MODE_RADIAL, tint = if (mode == VisMath.MODE_RADIAL) s.accentText else s.dim)
            IconAction(YIcons.visGram, "vis_gram", { vm.setVisMode(VisMath.MODE_GRAM) }, size = 30.dp, iconSize = 16.dp,
                active = mode == VisMath.MODE_GRAM, tint = if (mode == VisMath.MODE_GRAM) s.accentText else s.dim)
            IconAction(YIcons.visChart, "vis_chart", { vm.setVisMode(VisMath.MODE_CHART) }, size = 30.dp, iconSize = 16.dp,
                active = mode == VisMath.MODE_CHART, tint = if (mode == VisMath.MODE_CHART) s.accentText else s.dim)
        }) {
        Box(Modifier.fillMaxWidth().height(VIS_H).clip(RoundedCornerShape(10.dp)).background(s.graphBg)) {
            val needSpec = mode == VisMath.MODE_BARS || mode == VisMath.MODE_RADIAL || mode == VisMath.MODE_GRAM
            if (needSpec && !vm.spectrumOn) {
                Text("스펙트럼: 설정 → 화면 → 스펙트럼 켜기 (마이크 권한)", color = s.dim, fontSize = 10.sp,
                    modifier = Modifier.align(Alignment.Center).padding(8.dp))
            } else if (mode == VisMath.MODE_BARS) {
                // v027: 막대 모양 = 둥근 · LED · 미러 · 반사 (스펙트럼 아이콘을 한 번 더 누르면 바뀜)
                VmSpectrum(vm, true, Modifier.fillMaxSize().padding(horizontal = 6.dp, vertical = 6.dp), shape = vm.visBarStyle)
            } else if (mode == VisMath.MODE_RADIAL) {
                VmSpectrum(vm, true, Modifier.fillMaxSize().padding(4.dp), shape = "radial")
            } else if (mode == VisMath.MODE_GRAM) {
                GramView(vm, Modifier.fillMaxSize().padding(6.dp))
            } else if (mode == VisMath.MODE_WAVE && vm.spectrumOn) {
                // v026 웨이브: 스펙트럼 곡선 (스펙트럼 켬)
                VmSpectrum(vm, true, Modifier.fillMaxSize().padding(horizontal = 4.dp, vertical = 6.dp), shape = "wave")
            } else VisLive(vm, mode)
        }
    }
}

/** 파동 · 레벨 차트 (프레임 루프 + 그리기). 버퍼 · Path 는 재사용 → 프레임마다 메모리 할당 없음 */
@Composable
private fun VisLive(vm: AppViewModel, mode: String) {
    val s = LocalSkin.current
    val density = LocalDensity.current
    val pts = remember { FloatArray(WAVE_POINTS) }
    val hist = remember { LevelHistory(HIST_SIZE) }
    val linePath = remember { Path() }
    val areaPath = remember { Path() }
    val thin = remember(density) { Stroke(width = with(density) { 1.5.dp.toPx() }, cap = StrokeCap.Round, join = StrokeJoin.Round) }
    val dash = remember(density) { with(density) { PathEffect.dashPathEffect(floatArrayOf(4.dp.toPx(), 4.dp.toPx())) } }
    // 위(spectrum_hi) → 아래(spectrum_lo) — 테마 토큰만
    val areaBrush = remember(s) { Brush.verticalGradient(listOf(s.spectrumHi, s.spectrumLo)) }
    var frame by remember { mutableLongStateOf(0L) }
    var fromFile by remember { mutableStateOf(!vm.spectrumOn) }
    var levelNow by remember { mutableFloatStateOf(0f) }
    var clip by remember { mutableStateOf(false) }

    // 이 블럭이 보일 때만 Visualizer 파형 복사
    DisposableEffect(Unit) {
        Fx.waveWanted = true
        onDispose { Fx.waveWanted = false }
    }
    val playing = vm.isPlaying
    val visible = vm.uiVisible
    LaunchedEffect(playing, visible, mode) {
        if (!playing || !visible) return@LaunchedEffect
        var lastMs = -1L
        var textMs = 0L
        while (true) {
            val nowMs = withFrameNanos { it / 1_000_000 }
            val live = vm.spectrumOn && Fx.running
            if (fromFile == live) fromFile = !live
            val r: Float
            val p: Float
            if (mode == VisMath.MODE_WAVE) {
                // v026: 여기 오는 웨이브 = 스펙트럼 끔 → 파일 파형 앞뒤 3초 (오실로스코프 없앰)
                VisMath.peaksWindow(vm.wave, vm.durationMs, vm.positionMs, WINDOW_HALF_MS, pts)
            }
            if (live) {
                r = Fx.waveRms
                p = Fx.wavePeak
            } else {
                // 파일 파형: 0..1 피크 포락선 — 평균(RMS) 은 사인파 기준 피크 × 0.707 로 어림
                p = VisMath.peakAt(vm.wave, vm.durationMs, vm.positionMs)
                r = p * RMS_OF_PEAK
            }
            // 기록: TICK_MS 마다 1칸 (프레임이 늦으면 빈 칸을 같은 값으로 채움 → 10초 폭 유지)
            val n = if (lastMs < 0) 1 else VisMath.ticks(nowMs - lastMs, TICK_MS, HIST_SIZE)
            for (k in 0 until n) hist.push(r, p)
            if (lastMs < 0 || n >= HIST_SIZE) lastMs = nowMs else lastMs += n * TICK_MS
            // dB 글 · 클립 표시는 0.2초마다 (글자 재구성 줄이기)
            if (nowMs - textMs >= TEXT_MS) {
                textMs = nowMs
                levelNow = r
                val c = live && hist.recentPeak(CLIP_TICKS) >= VisMath.CLIP_PEAK
                if (clip != c) clip = c
            }
            frame = nowMs
            delay(FRAME_MS)
        }
    }

    Box(Modifier.fillMaxSize()) {
        Canvas(Modifier.fillMaxSize()) {
            if (frame < 0L) return@Canvas         // 프레임마다 다시 그리기 (state 읽기)
            val w = size.width
            val h = size.height
            if (mode == VisMath.MODE_WAVE) {
                val mid = h / 2
                drawLine(s.graphGrid, Offset(0f, mid), Offset(w, mid), 1f)
                val m = pts.size
                val step = w / (m - 1)
                run {
                    // 파일 파형 ±3초: 위아래 대칭 포락선, 왼쪽 반(지난 부분) = wave_played, 전체 = wave_rest
                    areaPath.reset()
                    areaPath.moveTo(0f, mid)
                    for (i in 0 until m) areaPath.lineTo(i * step, mid - pts[i] * mid * WAVE_AMP)
                    for (i in m - 1 downTo 0) areaPath.lineTo(i * step, mid + pts[i] * mid * WAVE_AMP)
                    areaPath.close()
                    drawPath(areaPath, s.waveRest)
                    val half = m / 2
                    linePath.reset()
                    linePath.moveTo(0f, mid)
                    for (i in 0..half) linePath.lineTo(i * step, mid - pts[i] * mid * WAVE_AMP)
                    for (i in half downTo 0) linePath.lineTo(i * step, mid + pts[i] * mid * WAVE_AMP)
                    linePath.close()
                    drawPath(linePath, s.wavePlayed)
                    drawLine(s.accentText, Offset(half * step, 0f), Offset(half * step, h), 2f)
                }
            } else {
                // 레벨 차트: dB 눈금 (-6 · -12 · -24) + 0 dB 선 (클립이면 굵게 peak 색)
                for (db in VisMath.GRID_DB) {
                    val y = h * (1 - VisMath.dbFrac(db))
                    drawLine(s.graphGrid, Offset(0f, y), Offset(w, y), 1f, pathEffect = dash)
                }
                if (clip) drawLine(s.peak, Offset(0f, 2f), Offset(w, 2f), 4f)
                else drawLine(s.graphGrid, Offset(0f, 1f), Offset(w, 1f), 1f)
                val n = hist.size
                if (n >= 2) {
                    val step = w / (HIST_SIZE - 1)
                    val x0 = w - (n - 1) * step        // 새 값은 오른쪽에서 들어옴
                    // RMS 면
                    areaPath.reset()
                    areaPath.moveTo(x0, h)
                    for (i in 0 until n) areaPath.lineTo(x0 + i * step, h * (1 - VisMath.levelFrac(hist.rmsAt(i))))
                    areaPath.lineTo(w, h)
                    areaPath.close()
                    drawPath(areaPath, areaBrush, alpha = 0.75f)
                    // 피크 선
                    linePath.reset()
                    for (i in 0 until n) {
                        val x = x0 + i * step
                        val y = h * (1 - VisMath.levelFrac(hist.peakAt(i)))
                        if (i == 0) linePath.moveTo(x, y) else linePath.lineTo(x, y)
                    }
                    drawPath(linePath, s.peak, style = thin)
                }
            }
        }
        if (mode == VisMath.MODE_CHART) {
            // 눈금 글자 (선 바로 아래) · 지금 dB · 클립
            for (db in VisMath.GRID_DB) Text("${db.toInt()}", color = s.dim, fontSize = 9.sp,
                modifier = Modifier.align(Alignment.TopStart).padding(start = 4.dp, top = VIS_H * (1 - VisMath.dbFrac(db)) + 1.dp))
            Text(VisMath.dbText(levelNow), color = s.text, fontSize = 11.sp,
                modifier = Modifier.align(Alignment.TopEnd).padding(end = 6.dp, top = 4.dp))
            if (clip) Text("클립 0 dB", color = s.peak, fontSize = 10.sp,
                modifier = Modifier.align(Alignment.TopCenter).padding(top = 4.dp))
        }
        if (fromFile || mode == VisMath.MODE_WAVE) Text("파일 파형 기준", color = s.dim, fontSize = 9.sp,
            modifier = Modifier.align(Alignment.BottomStart).padding(start = 6.dp, bottom = 3.dp))
    }
}

/** 블럭 높이 */
private val VIS_H = 110.dp
/** 파동 점 수 */
private const val WAVE_POINTS = 256
/** 파동 높이 비율 (위아래 여백) */
private const val WAVE_AMP = 0.92f
/** 파일 파형 파동: 지금 위치 앞뒤 3초 */
private const val WINDOW_HALF_MS = 3000L
/** 레벨 차트 기록: 33ms × 300칸 ≈ 10초 */
private const val TICK_MS = 33L
private const val HIST_SIZE = 300
/** 클립 표시: 최근 약 1초 */
private const val CLIP_TICKS = 30
/** 프레임 상한 ≈ 30fps (withFrameNanos 뒤 쉬는 시간) */
private const val FRAME_MS = 25L
/** dB 글 갱신 주기 */
private const val TEXT_MS = 200L
/** 파일 피크 → 평균 어림 (사인파 RMS = 피크 / √2) */
private const val RMS_OF_PEAK = 0.707f
