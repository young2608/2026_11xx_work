package com.ascen.yamp.ui

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.gestures.detectDragGestures
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlin.math.cos
import kotlin.math.roundToInt
import kotlin.math.sin

/**
 * 원형 노브 (시안 knob): 270° 호 (135° → 405°), 바탕 호 line, 값 호(색) + 빛, 안쪽 원 knob / 테두리 knobRim, 바늘 text.
 *   위/오른쪽으로 끌면 커지고 아래/왼쪽으로 끌면 작아짐. 두 번 탭 = 기본값.
 *   step > 0 이면 그 단위로 맞춤. onChange 는 끄는 동안 계속 호출.
 */
@Composable
fun Knob(
    value: Float,
    onChange: (Float) -> Unit,
    range: ClosedFloatingPointRange<Float>,
    default: Float,
    color: Color,
    label: String,
    valueText: String,
    modifier: Modifier = Modifier,
    size: Dp = 64.dp,
    step: Float = 0f,
) {
    val s = LocalSkin.current
    val cur by rememberUpdatedState(value)
    val change by rememberUpdatedState(onChange)
    var acc by remember { mutableFloatStateOf(value) }
    val lo = range.start
    val hi = range.endInclusive
    fun snap(v: Float): Float {
        val c = v.coerceIn(lo, hi)
        return if (step > 0f) ((c / step).roundToInt() * step).coerceIn(lo, hi) else c
    }
    Column(modifier, horizontalAlignment = Alignment.CenterHorizontally) {
        Canvas(
            Modifier.size(size)
                .pointerInput(lo, hi, default) {
                    detectTapGestures(onDoubleTap = { change(default) })
                }
                .pointerInput(lo, hi, step) {
                    detectDragGestures(
                        onDragStart = { acc = cur },
                        onDrag = { ch, d ->
                            ch.consume()
                            // 노브 크기 × 2.5 를 끌면 전체 범위
                            acc = (acc + (d.x - d.y) / (this.size.width * 2.5f) * (hi - lo)).coerceIn(lo, hi)
                            val v = snap(acc)
                            if (v != cur) change(v)
                        },
                    )
                },
        ) {
            val stroke = this.size.width * 0.075f
            val r = this.size.width / 2f - stroke * 1.4f
            val c = Offset(this.size.width / 2f, this.size.height / 2f)
            val tl = Offset(c.x - r, c.y - r)
            val sz = Size(r * 2, r * 2)
            val frac = if (hi > lo) ((value - lo) / (hi - lo)).coerceIn(0f, 1f) else 0f
            drawArc(s.line, 135f, 270f, false, tl, sz, style = Stroke(stroke, cap = StrokeCap.Round))
            if (frac > 0.002f) {
                // 빛(어두운 테마만): 넓고 흐린 호 → 실제 호
                if (s.dark) drawArc(color.copy(alpha = 0.22f), 135f, 270f * frac, false, tl, sz, style = Stroke(stroke * 2.6f, cap = StrokeCap.Round))
                drawArc(color, 135f, 270f * frac, false, tl, sz, style = Stroke(stroke, cap = StrokeCap.Round))
            }
            val inner = r - stroke * 1.9f
            drawCircle(s.knob, inner, c)
            drawCircle(s.knobRim, inner, c, style = Stroke(1.5f))
            val a = Math.toRadians((135.0 + 270.0 * frac))
            val nl = inner * 0.72f
            drawLine(s.text, c, Offset(c.x + nl * cos(a).toFloat(), c.y + nl * sin(a).toFloat()), strokeWidth = stroke * 0.75f, cap = StrokeCap.Round)
        }
        Text(label, color = s.dim, fontSize = 10.sp, maxLines = 1, modifier = Modifier.padding(top = 3.dp))
        if (valueText.isNotEmpty()) Text(valueText, color = s.text, fontSize = 10.sp, maxLines = 1)
    }
}
