package com.ascen.yamp.ui

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.gestures.detectDragGestures
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.ascen.yamp.app.AppViewModel
import com.ascen.yamp.domain.Dsp
import com.ascen.yamp.domain.SoundSettings
import kotlin.math.abs
import kotlin.math.max
import kotlin.math.roundToInt

private val EQ_LABELS = listOf("Pre", "31", "62", "125", "250", "500", "1k", "2k", "4k", "8k", "16k")

private fun dbText(v: Double): String {
    val r = (v * 2).roundToInt() / 2.0
    val t = if (r == r.toLong().toDouble()) r.toLong().toString() else "%.1f".format(r)
    return if (r > 0) "+$t" else t
}

/**
 * ② 사운드 화면 (vr0.1.0.006, 시안 ②): 프리앰프 + 10밴드 EQ, 응답 곡선, 프리셋, 톤(베이스·트레블·밸런스), 다이내믹(리미터·압축).
 * 바꾸면 바로 적용 (SoundEngine — ExoPlayer 오디오 처리기). EQ 켬/끔은 머리줄 알약.
 */
@Composable
fun SoundScreen(vm: AppViewModel) {
    val s = LocalSkin.current
    val snd = vm.sound
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        ScreenHeader("사운드") {
            // vr0.1.0.009: 아이콘만 (이름 · 상태는 길게 누르기 팝업)
            IconAction(YIcons.reset, "sound_reset", vm::resetSound, framed = true, size = 36.dp, iconSize = 18.dp)
            IconAction(YIcons.power, "eq_toggle", { vm.updateSound(snd.copy(enabled = !snd.enabled)) }, framed = true, size = 40.dp,
                iconSize = 20.dp, active = snd.enabled, tint = if (snd.enabled) s.accentText else s.dim, state = if (snd.enabled) "켬" else "끔", toggle = snd.enabled)
        }
        CollapsibleCard("sound_eq", "이퀄라이저 (프리앰프 + 10밴드, ±12 dB)",
            contentPadding = PaddingValues(start = 6.dp, end = 6.dp, bottom = 10.dp)) {
            EqSliders(snd, { i, v ->
                if (i == 0) vm.updateSound(snd.copy(preampDb = (v * 2).roundToInt() / 2.0, enabled = true))
                else vm.setBand(i - 1, v)
            })
            if (!snd.enabled) Text("EQ 꺼짐 — 막대를 움직이면 켜집니다", color = s.dim, fontSize = 11.sp,
                textAlign = TextAlign.Center, modifier = Modifier.fillMaxWidth().padding(top = 4.dp))
        }
        CollapsibleCard("sound_curve", "응답 곡선", contentPadding = PaddingValues(start = 8.dp, end = 8.dp, bottom = 8.dp)) {
            val levels by vm.levels.collectAsStateWithLifecycle()
            ResponseCurve(snd, levels, Modifier.fillMaxWidth().height(80.dp))
        }
        PresetCard(vm, snd)
        CollapsibleCard("sound_tone", "톤 · 밸런스", contentPadding = PaddingValues(start = 4.dp, end = 4.dp, bottom = 12.dp)) {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceAround) {
                Knob(snd.bassDb.toFloat(), { vm.updateSound(snd.copy(bassDb = it.toDouble(), enabled = true)) }, -12f..12f, 0f,
                    s.hue(4), "베이스", "${dbText(snd.bassDb)} dB", size = 70.dp, step = 0.5f)
                Knob(snd.trebleDb.toFloat(), { vm.updateSound(snd.copy(trebleDb = it.toDouble(), enabled = true)) }, -12f..12f, 0f,
                    s.hue(6), "트레블", "${dbText(snd.trebleDb)} dB", size = 70.dp, step = 0.5f)
                val b = snd.balance
                val bt = when {
                    abs(b) < 0.005 -> "C"
                    b < 0 -> "L ${(abs(b) * 20).roundToInt()}"        // 0.05 단위 → 1 ~ 20
                    else -> "R ${(b * 20).roundToInt()}"
                }
                Knob(b.toFloat(), { vm.updateSound(snd.copy(balance = it.toDouble())) }, -1f..1f, 0f,
                    s.hue(1), "밸런스", bt, size = 70.dp, step = 0.05f)
            }
        }
        CollapsibleCard("sound_dyn", "다이내믹 (리미터 · 압축)", contentPadding = PaddingValues(start = 8.dp, end = 8.dp, bottom = 12.dp)) {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                IconAction(YIcons.limiter, "limiter", { vm.updateSound(snd.copy(limiter = !snd.limiter)) }, framed = true, size = 40.dp,
                    iconSize = 20.dp, active = snd.limiter, state = if (snd.limiter) "켬" else "끔", toggle = snd.limiter)
                IconAction(YIcons.compressor, "comp", { vm.updateSound(snd.copy(comp = !snd.comp)) }, framed = true, size = 40.dp,
                    iconSize = 20.dp, active = snd.comp, state = if (snd.comp) "켬" else "끔", toggle = snd.comp)
                Spacer(Modifier.weight(1f))
            }
            Text("리미터: -1 dBFS 를 넘는 소리를 눌러 찢어짐 방지 · 압축: 큰 소리와 작은 소리 차이를 줄임",
                color = s.dim, fontSize = 11.sp, modifier = Modifier.padding(top = 6.dp, start = 4.dp))
            if (snd.comp) Row(Modifier.fillMaxWidth().padding(top = 10.dp), horizontalArrangement = Arrangement.SpaceAround) {
                Knob(snd.compThresholdDb.toFloat(), { vm.updateSound(snd.copy(compThresholdDb = it.toDouble())) }, -60f..0f, -18f,
                    s.hue(2), "Threshold", "%.0f dB".format(snd.compThresholdDb), size = 54.dp, step = 1f)
                Knob(snd.compRatio.toFloat(), { vm.updateSound(snd.copy(compRatio = it.toDouble())) }, 1f..20f, 3f,
                    s.hue(1), "Ratio", "%.1f:1".format(snd.compRatio), size = 54.dp, step = 0.5f)
                Knob(snd.compAttackMs.toFloat(), { vm.updateSound(snd.copy(compAttackMs = it.toDouble())) }, 0.1f..200f, 10f,
                    s.hue(4), "Attack", "%.0f ms".format(snd.compAttackMs), size = 54.dp, step = 0.5f)
                Knob(snd.compReleaseMs.toFloat(), { vm.updateSound(snd.copy(compReleaseMs = it.toDouble())) }, 5f..2000f, 120f,
                    s.hue(5), "Release", "%.0f ms".format(snd.compReleaseMs), size = 54.dp, step = 5f)
                Knob(snd.compMakeupDb.toFloat(), { vm.updateSound(snd.copy(compMakeupDb = it.toDouble())) }, 0f..24f, 0f,
                    s.hue(7), "Gain", "+%.1f dB".format(snd.compMakeupDb), size = 54.dp, step = 0.5f)
            }
        }
        Text("소리 처리는 이 앱 안에서 직접 계산합니다 (기기 이퀄라이저와 무관 · PC 와 같은 계산식)",
            color = s.dim, fontSize = 10.sp, modifier = Modifier.padding(horizontal = 6.dp))
        Spacer(Modifier.height(8.dp))
    }
}

/** 세로 EQ 슬라이더 11개 (프리앰프 + 10밴드): 밴드마다 테마 bands 색 + 빛, 손잡이(어두운 테마 = text, 밝은 테마 = 흰 면 + knobRim). 끌기 = 값, 두 번 탭 = 0 */
@Composable
private fun EqSliders(snd: SoundSettings, onChange: (Int, Double) -> Unit) {
    val s = LocalSkin.current
    val vals = listOf(snd.preampDb) + snd.bands
    val cur by rememberUpdatedState(vals)
    val change by rememberUpdatedState(onChange)
    var col by remember { mutableIntStateOf(-1) }
    Column(Modifier.fillMaxWidth()) {
        Canvas(
            Modifier.fillMaxWidth().height(200.dp)
                .pointerInput(Unit) {
                    detectTapGestures(onDoubleTap = { o ->
                        val i = (o.x / (size.width / 11f)).toInt().coerceIn(0, 10)
                        change(i, 0.0)
                    })
                }
                .pointerInput(Unit) {
                    val top = 14.dp.toPx()
                    val bot = size.height - 14.dp.toPx()
                    fun valueAt(y: Float): Double = (((bot + top) / 2 - y) / ((bot - top) / 2) * 12.0).coerceIn(-12.0, 12.0)
                    detectDragGestures(
                        onDragStart = { o -> col = (o.x / (size.width / 11f)).toInt().coerceIn(0, 10); change(col, valueAt(o.y)) },
                        onDragEnd = { col = -1 },
                        onDragCancel = { col = -1 },
                    ) { ch, _ ->
                        ch.consume()
                        if (col >= 0) {
                            val v = valueAt(ch.position.y)
                            if (abs(v - cur[col]) >= 0.25) change(col, v)
                        }
                    }
                },
        ) {
            val colW = size.width / 11f
            val top = 14.dp.toPx()
            val bot = size.height - 14.dp.toPx()
            val mid = (top + bot) / 2
            val sw = 4.dp.toPx()
            for (i in 0 until 11) {
                val x = colW * i + colW / 2
                val v = vals[i]
                val y = (mid - (v / 12.0 * (bot - top) / 2)).toFloat()
                val c = s.bands[i]
                drawLine(s.line, Offset(x, top), Offset(x, bot), strokeWidth = sw, cap = StrokeCap.Round)
                if (i > 0) drawLine(c.copy(alpha = 0.22f), Offset(x, y), Offset(x, bot), strokeWidth = sw, cap = StrokeCap.Round)
                // 빛 (넓고 흐린 선) + 값 선 (가운데 ~ 값)
                if (s.dark) drawLine(c.copy(alpha = 0.25f), Offset(x, minOf(mid, y)), Offset(x, max(mid, y)), strokeWidth = sw * 3f, cap = StrokeCap.Round)
                drawLine(c, Offset(x, minOf(mid, y)), Offset(x, max(mid, y)), strokeWidth = sw, cap = StrokeCap.Round)
                // 손잡이: 어두운 테마 = 밝은 text 색, 밝은 테마 = 흰 면 + knobRim 테두리
                val hw = minOf(18.dp.toPx(), colW * 0.8f)
                val hh = 12.dp.toPx()
                drawRoundRect(if (s.dark) s.text else s.surface, Offset(x - hw / 2, y - hh / 2), Size(hw, hh), CornerRadius(3.dp.toPx(), 3.dp.toPx()))
                if (!s.dark) drawRoundRect(s.knobRim, Offset(x - hw / 2, y - hh / 2), Size(hw, hh), CornerRadius(3.dp.toPx(), 3.dp.toPx()),
                    style = Stroke(1.5f))
                drawLine(s.knobRim, Offset(x - hw * 0.28f, y), Offset(x + hw * 0.28f, y), strokeWidth = 1.5.dp.toPx())
                if (i == col) drawRoundRect(c, Offset(x - hw / 2, y - hh / 2), Size(hw, hh), CornerRadius(3.dp.toPx(), 3.dp.toPx()),
                    style = Stroke(2f))
            }
        }
        Row(Modifier.fillMaxWidth()) {
            for (i in 0 until 11) Text(EQ_LABELS[i], color = s.dim, fontSize = 9.sp, textAlign = TextAlign.Center, modifier = Modifier.weight(1f))
        }
        Row(Modifier.fillMaxWidth()) {
            for (i in 0 until 11) Text(dbText(vals[i]), color = s.text, fontSize = 9.sp, textAlign = TextAlign.Center, modifier = Modifier.weight(1f))
        }
    }
}

/** 응답 곡선: graphBg 바탕, 스펙트럼(흐린 막대, 켜져 있을 때) 위에 EQ 곡선(fill2 선 + 빛), 0 dB 점선 graphGrid. 세로 범위 ±15 dB */
@Composable
private fun ResponseCurve(snd: SoundSettings, levels: FloatArray, modifier: Modifier = Modifier) {
    val s = LocalSkin.current
    val freqs = remember { Dsp.logFreqs(86) }
    val resp = remember(snd) { Dsp.responseDb(snd, freqs) }
    Canvas(modifier) {
        val w = size.width
        val h = size.height
        val mid = h / 2
        drawRect(s.graphBg, Offset.Zero, size)
        // 스펙트럼 (24밴드 → 86칸 보간, v026)
        if (levels.any { it > 0.01f }) {
            val n = 86
            val bw = w / n
            for (k in 0 until n) {
                val p = k / (n - 1f) * (levels.size - 1)
                val i0 = p.toInt().coerceIn(0, levels.size - 1)
                val i1 = (i0 + 1).coerceAtMost(levels.size - 1)
                val v = levels[i0] + (levels[i1] - levels[i0]) * (p - i0)
                val bh = v * (h - 6f)
                drawRect(s.spectrumHi.copy(alpha = 0.35f), Offset(k * bw + bw * 0.2f, h - bh), Size(bw * 0.6f, bh))
            }
        }
        drawLine(s.graphGrid, Offset(0f, mid), Offset(w, mid), strokeWidth = 1.5f,
            pathEffect = PathEffect.dashPathEffect(floatArrayOf(6f, 8f)))
        val path = Path()
        resp.forEachIndexed { i, db ->
            val x = i / (resp.size - 1f) * w
            val y = (mid - (db / 15.0).coerceIn(-1.0, 1.0) * (mid - 4f)).toFloat()
            if (i == 0) path.moveTo(x, y) else path.lineTo(x, y)
        }
        drawPath(path, s.fill2.copy(alpha = 0.25f), style = Stroke(width = 7.dp.toPx(), cap = StrokeCap.Round))
        drawPath(path, s.fill2, style = Stroke(width = 2.5.dp.toPx(), cap = StrokeCap.Round))
    }
}

/** 프리셋 알약 (기본 8개 + 내 프리셋) · ＋ = 지금 값을 내 프리셋으로 저장 · 내 프리셋 길게 누르기 = 삭제 */
@OptIn(ExperimentalFoundationApi::class)
@Composable
private fun PresetCard(vm: AppViewModel, snd: SoundSettings) {
    val s = LocalSkin.current
    var showSave by remember { mutableStateOf(false) }
    var del by remember { mutableStateOf("") }
    val presets = vm.userPresets.toList()
    val curName = remember(snd, presets) { vm.presetNameOf(snd) }
    CollapsibleCard("sound_presets", "프리셋", subtitle = if (snd.enabled && curName.isNotEmpty()) "지금: $curName" else "",
        contentPadding = PaddingValues(start = 10.dp, end = 10.dp, bottom = 12.dp)) {
        Row(Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Dsp.PRESETS.forEach { (n, _) -> Pill(n, on = snd.enabled && n == curName, onClick = { vm.applyPreset(n) }) }
        }
        Row(Modifier.fillMaxWidth().padding(top = 8.dp).horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp),
            verticalAlignment = Alignment.CenterVertically) {
            presets.forEach { (n, _) ->
                val on = snd.enabled && n == curName
                Text(n, color = if (on) s.accentText else s.text, fontSize = 13.sp, maxLines = 1,
                    modifier = Modifier.clip(RoundedCornerShape(50))
                        .combinedClickable(onClick = { vm.applyPreset(n) }, onLongClick = { del = n })
                        .padding(horizontal = 12.dp, vertical = 7.dp))
            }
            IconAction(YIcons.plus, "preset_save", { showSave = true }, framed = true, size = 34.dp, iconSize = 18.dp)
        }
    }
    if (showSave) {
        var name by remember { mutableStateOf("") }
        AlertDialog(onDismissRequest = { showSave = false }, title = { Text("내 프리셋 저장") },
            text = {
                Column {
                    Text("지금 EQ · 프리앰프 · 베이스/트레블 값을 저장합니다", fontSize = 12.sp)
                    Spacer(Modifier.height(6.dp))
                    SkinField(name, { name = it }, "이름 (예: 출근길)", Modifier.fillMaxWidth())
                }
            },
            confirmButton = { TextButton({ vm.saveUserPreset(name); showSave = false }) { Text("저장") } },
            dismissButton = { TextButton({ showSave = false }) { Text("취소") } })
    }
    if (del.isNotEmpty()) AlertDialog(onDismissRequest = { del = "" }, title = { Text("프리셋 삭제") },
        text = { Text("'$del' 프리셋을 지울까요?") },
        confirmButton = { TextButton({ vm.deleteUserPreset(del); del = "" }) { Text("삭제") } },
        dismissButton = { TextButton({ del = "" }) { Text("취소") } })
}
