package com.ascen.yamp.domain

import kotlin.math.abs
import kotlin.math.exp
import kotlin.math.ln
import kotlin.math.log10
import kotlin.math.max
import kotlin.math.min
import kotlin.math.pow
import kotlin.math.sqrt

/**
 * 소리 시각화 블럭 계산 (vr0.1.0.014, f26 D8) — 순수 Kotlin (JVM 테스트 VisMathTest).
 *   - Visualizer 파형 바이트(부호 없는 8비트, 128 = 0) → RMS · 피크 (0..1)
 *   - dB 변환 (바닥 -60 dB) · 차트 높이 비율
 *   - 레벨 차트 기록 (고정 크기 링 버퍼, 그리기 때 메모리 할당 없음)
 *   - 스펙트럼 끔: 파일 파형(peaks) 에서 재생 위치 앞뒤 구간 뽑기
 */
object VisMath {
    /** 모드 (SharedPreferences vis_mode) */
    const val MODE_WAVE = "wave"
    const val MODE_BARS = "bars"
    const val MODE_CHART = "chart"
    /** v027 (f53): 원형 · 스펙트로그램 */
    const val MODE_RADIAL = "radial"
    const val MODE_GRAM = "gram"
    val MODES = listOf(MODE_BARS, MODE_WAVE, MODE_RADIAL, MODE_GRAM, MODE_CHART)

    /** 스펙트럼 막대 모양 (v027): 둥근 · LED · 미러(가운데 = 낮은 소리) · 반사 */
    val BAR_STYLES = listOf("round", "led", "mirror", "reflex")
    fun parseBarStyle(s: String?): String = if (s in BAR_STYLES) s!! else "round"
    fun nextBarStyle(cur: String): String = BAR_STYLES[(BAR_STYLES.indexOf(cur) + 1) % BAR_STYLES.size]
    fun barStyleName(s: String): String = when (s) { "led" -> "LED"; "mirror" -> "미러 (가운데 = 낮은 소리)"; "reflex" -> "반사"; else -> "둥근 막대" }
    /** 스펙트로그램 기록 칸 (프레임 × 5초) · LED 칸 높이(dp) */
    const val GRAM_COLS = 150
    const val LED_CELL = 5f

    /** 모르는 값 → 기본 레벨 차트 */
    fun parseMode(s: String?): String = if (s in MODES) s!! else MODE_CHART

    /** dB 바닥 */
    const val DB_FLOOR = -60f
    /** 차트 눈금 */
    val GRID_DB = floatArrayOf(-6f, -12f, -24f)
    /** 클리핑으로 볼 피크 (0 dB 근처) */
    const val CLIP_PEAK = 0.995f

    /** 8비트 표본 하나 → -1..1 */
    fun sample(b: Byte): Float = ((b.toInt() and 0xFF) - 128) / 128f

    /** RMS 0..1 (len = 앞에서부터 쓸 길이) */
    fun rms(w: ByteArray, len: Int = w.size): Float {
        val n = min(len, w.size)
        if (n <= 0) return 0f
        var sum = 0.0
        for (i in 0 until n) { val v = sample(w[i]); sum += v * v }
        return sqrt(sum / n).toFloat().coerceIn(0f, 1f)
    }

    /** 피크(절댓값 최대) 0..1 */
    fun peak(w: ByteArray, len: Int = w.size): Float {
        val n = min(len, w.size)
        var m = 0f
        for (i in 0 until n) m = max(m, abs(sample(w[i])))
        return m.coerceIn(0f, 1f)
    }

    /** 0..1 크기 → dB (바닥 -60) */
    fun toDb(v: Float): Float {
        if (v <= 0f || v.isNaN()) return DB_FLOOR
        return max(DB_FLOOR, (20 * log10(v.toDouble())).toFloat()).coerceAtMost(0f)
    }

    /** dB → 차트 높이 비율 0..1 (바닥 = 0, 0 dB = 1) */
    fun dbFrac(db: Float): Float = ((db - DB_FLOOR) / -DB_FLOOR).coerceIn(0f, 1f)

    /** 크기 0..1 → 차트 높이 비율 */
    fun levelFrac(v: Float): Float = dbFrac(toDb(v))

    /** 화면 표시용 dB 글 ("-12.5 dB", 바닥이면 "-∞ dB") */
    fun dbText(v: Float): String {
        val db = toDb(v)
        return if (db <= DB_FLOOR) "-∞ dB" else "%.1f dB".format(db)
    }

    /**
     * 파형 바이트 → out.size 점 (-1..1) 으로 다시 뽑기 (가까운 표본). len 0 이면 모두 0.
     * 메모리 할당 없음.
     */
    fun wavePoints(w: ByteArray, len: Int, out: FloatArray) {
        val n = min(len, w.size)
        val m = out.size
        if (n <= 0) { out.fill(0f); return }
        for (i in 0 until m) {
            val k = if (m <= 1) 0 else ((i.toLong() * (n - 1)) / (m - 1)).toInt()
            out[i] = sample(w[k])
        }
    }

    /**
     * 파일 파형 peaks(곡 전체를 균등하게 나눈 0..1) 에서 posMs 의 값 (사이 값은 직선 보간).
     * 곡 밖 · 데이터 없음 = 0
     */
    fun peakAt(peaks: FloatArray?, durMs: Long, posMs: Long): Float {
        if (peaks == null || peaks.isEmpty() || durMs <= 0 || posMs < 0 || posMs > durMs) return 0f
        val n = peaks.size
        // 칸 i 의 가운데 = (i + 0.5) / n
        val x = posMs.toDouble() / durMs * n - 0.5
        val i0 = x.toInt().let { if (x < 0) -1 else it }
        val f = (x - i0).toFloat()
        val a = peaks[i0.coerceIn(0, n - 1)]
        val b = peaks[(i0 + 1).coerceIn(0, n - 1)]
        return (a + (b - a) * f).coerceIn(0f, 1f)
    }

    /** posMs ± halfMs 구간을 out.size 점으로 (가운데 = 지금 위치). 메모리 할당 없음 */
    fun peaksWindow(peaks: FloatArray?, durMs: Long, posMs: Long, halfMs: Long, out: FloatArray) {
        val m = out.size
        if (m == 0) return
        for (i in 0 until m) {
            val t = if (m == 1) posMs else posMs - halfMs + (2 * halfMs * i) / (m - 1)
            out[i] = peakAt(peaks, durMs, t)
        }
    }

    /** 경과 시간 → 기록에 넣을 칸 수 (tickMs 마다 1칸, 처음 = 1, 최대 cap) */
    fun ticks(elapsedMs: Long, tickMs: Long, cap: Int): Int =
        if (elapsedMs < 0 || tickMs <= 0) 1 else (elapsedMs / tickMs).toInt().coerceIn(0, cap)

    /** 미러 막대 배치 (2n칸의 밴드 번호): 높은 … 낮은 | 낮은 … 높은. out.size = 2n */
    fun mirrorOrder(n: Int, out: IntArray) {
        for (i in 0 until n) { out[i] = n - 1 - i; out[n + i] = i }
    }

    /** LED 막대: 높이 h 안 칸 수 중 v 만큼 켜진 칸 (반올림 .5 = 올림, 칸 사이 gap) — PC led_cells 와 같음 */
    fun ledCells(v: Float, h: Float, cell: Float = LED_CELL, gap: Float = 2f): Int {
        val total = max(1, ((h + gap).toDouble() / (cell + gap)).toInt())
        return kotlin.math.floor(v.toDouble() * total + 0.5).toInt().coerceIn(0, total)
    }

    /** 스펙트로그램 색: v(0..1) → 색 4개 (RGB Int) 고르게 보간 → 0xFFRRGGBB — PC heat_rgb 와 같음 */
    fun heatArgb(vIn: Float, stops: IntArray): Int {
        val v = vIn.toDouble().coerceIn(0.0, 1.0)
        val seg = stops.size - 1
        val x = v * seg
        val i = min(seg - 1, x.toInt())
        val f = x - i
        val a = stops[i]
        val b = stops[i + 1]
        fun ch(sh: Int): Int {
            val ca = (a shr sh) and 0xFF
            val cb = (b shr sh) and 0xFF
            return kotlin.math.floor(ca + (cb - ca) * f + 0.5).toInt()
        }
        return (0xFF shl 24) or (ch(16) shl 16) or (ch(8) shl 8) or ch(0)
    }

    // ================================================================ v026 (f51): 비주얼라이저 재구성 — PC vis_math.py 와 같은 규칙
    //   testdata/vis_cases.txt 로 PC · Android 같은 값 확인 (VisMathTest)
    /** 스펙트럼 밴드 수 · 범위 (50 Hz ~ 16 kHz 로그 간격) */
    const val VIS_BANDS = 24
    const val VIS_F_LO = 50.0
    const val VIS_F_HI = 16000.0
    /** 높은 소리 보정 dB/옥타브 (1 kHz 기준) */
    const val VIS_TILT_DB_OCT = 3.0

    /**
     * FFT 크기 mags[0 until bins] (mags[k] = k × binHz Hz) → out[n] 0..1.
     *   bin 보다 좁은 밴드(낮은 소리) = 가운데 주파수에서 bin 사이 직선 보간 (전: 3~4개가 같은 bin → 똑같은 높이)
     *   넓은 밴드 = bin 들의 RMS (전: 최댓값 → 들쭉날쭉) · +3 dB/옥타브 보정. 메모리 할당 없음
     */
    fun bandsFromMags(mags: FloatArray, bins: Int, binHz: Double, out: FloatArray, rangeDb: Double, ref: Double) {
        val n = out.size
        val m = min(bins, mags.size)
        if (m < 2 || binHz <= 0.0) { out.fill(0f); return }
        val ratio = VIS_F_HI / VIS_F_LO
        for (b in 0 until n) {
            val f0 = VIS_F_LO * ratio.pow(b / n.toDouble())
            val f1 = VIS_F_LO * ratio.pow((b + 1) / n.toDouble())
            val fc = sqrt(f0 * f1)
            val v: Double
            if (f1 - f0 < 2 * binHz) {
                val x = min(m - 1.0, max(1.0, fc / binHz))
                val k = x.toInt()
                val fr = x - k
                val a = mags[k].toDouble()
                val c = mags[min(m - 1, k + 1)].toDouble()
                v = a + (c - a) * fr
            } else {
                val k0 = max(1, (f0 / binHz).toInt())
                val k1 = min(m, max(k0 + 1, (f1 / binHz).toInt()))
                var sum = 0.0
                for (k in k0 until k1) { val q = mags[k].toDouble(); sum += q * q }
                v = if (k1 > k0) sqrt(sum / (k1 - k0)) else 0.0      // 나이퀴스트 넘는 밴드 = 0
            }
            val db = 20.0 * log10(max(v, 1e-9) / ref) + VIS_TILT_DB_OCT * (ln(fc / 1000.0) / ln(2.0))
            out[b] = ((db + rangeDb) / rangeDb).coerceIn(0.0, 1.0).toFloat()
        }
    }
}

/**
 * 막대 · 웨이브 움직임 (v026, f51 — PC BandSmoother 와 같은 규칙):
 *   이웃 밴드 섞기 0.2 · 0.6 · 0.2 → 오를 때 τ 50 ms, 내릴 때 τ 350 ms (dt 기준 지수 곡선 — fps 와 무관)
 *   꼭대기 = 0.5초 머문 뒤 중력 가속 낙하 · 새 값이 0.25초 넘게 안 오면 목표 = 0.
 *   계산은 Double (PC 와 같은 값), 그리기용 v · peaks 는 FloatArray. 메모리 할당 없음
 */
class BandSmoother(val n: Int) {
    val v = FloatArray(n)
    val peaks = FloatArray(n)
    private val dv = DoubleArray(n)
    private val dp = DoubleArray(n)
    private val hold = DoubleArray(n)
    private val fall = DoubleArray(n)
    private val target = DoubleArray(n)
    private val sm = DoubleArray(n)
    private var age = 0.0

    fun setTarget(lv: FloatArray) {
        for (i in 0 until n) target[i] = if (i < lv.size) lv[i].toDouble() else 0.0
        age = 0.0
    }

    fun targetAt(i: Int): Float = target[i].toFloat()

    fun step(dtIn: Double) {
        val dt = dtIn.coerceIn(0.0, 0.25)
        age += dt
        if (age > STALE_S) target.fill(0.0)
        for (i in 0 until n) sm[i] = A0 * target[max(0, i - 1)] + A1 * target[i] + A2 * target[min(n - 1, i + 1)]
        val ka = 1.0 - exp(-dt / ATTACK_S)
        val kr = 1.0 - exp(-dt / RELEASE_S)
        for (i in 0 until n) {
            var cur = dv[i]
            val want = sm[i]
            cur += (want - cur) * (if (want > cur) ka else kr)
            dv[i] = cur
            if (cur >= dp[i]) {
                dp[i] = cur; hold[i] = HOLD_S; fall[i] = 0.0
            } else if (hold[i] > 0) {
                hold[i] = max(0.0, hold[i] - dt)
            } else {
                fall[i] += GRAVITY * dt
                dp[i] = max(cur, dp[i] - fall[i] * dt)
            }
            v[i] = cur.toFloat()
            peaks[i] = dp[i].toFloat()
        }
    }

    /** 모두 내려앉고 새 값도 0 → 프레임 멈춰도 됨 */
    fun idle(eps: Double = 0.003): Boolean {
        for (i in 0 until n) if (dv[i] > eps || dp[i] > eps || target[i] > eps) return false
        return true
    }

    companion object {
        const val ATTACK_S = 0.05
        const val RELEASE_S = 0.35
        const val HOLD_S = 0.5
        const val GRAVITY = 2.5
        const val STALE_S = 0.25
        const val A0 = 0.2
        const val A1 = 0.6
        const val A2 = 0.2
    }
}

/**
 * 레벨 차트 기록: 최근 capacity 칸의 RMS · 피크 (0..1). 오래된 것부터 0..size-1 로 읽음.
 * 고정 배열 링 버퍼 — 넣기 · 읽기에 메모리 할당 없음.
 */
class LevelHistory(val capacity: Int) {
    private val rmsBuf = FloatArray(capacity)
    private val peakBuf = FloatArray(capacity)
    private var head = 0          // 다음에 쓸 칸
    var size = 0; private set

    fun push(rms: Float, peak: Float) {
        if (capacity <= 0) return
        rmsBuf[head] = rms
        peakBuf[head] = peak
        head = (head + 1) % capacity
        if (size < capacity) size++
    }

    private fun idx(i: Int): Int = (head - size + i + capacity) % capacity

    /** i = 0 (가장 오래됨) .. size-1 (가장 최근) */
    fun rmsAt(i: Int): Float = rmsBuf[idx(i)]
    fun peakAt(i: Int): Float = peakBuf[idx(i)]

    /** 가장 최근 n 칸의 피크 최댓값 */
    fun recentPeak(n: Int): Float {
        var m = 0f
        val k = min(n, size)
        for (j in 0 until k) m = max(m, peakAt(size - 1 - j))
        return m
    }

    fun clear() { head = 0; size = 0 }
}

/** 스펙트로그램 기록 (v027): 최근 cols 프레임 × n 밴드 링 버퍼 — 오래된 것부터 0..size-1. 메모리 할당 없음 */
class GramHistory(val n: Int, val cols: Int = VisMath.GRAM_COLS) {
    private val buf = FloatArray(n * cols)
    private var head = 0
    var size = 0; private set

    fun push(lv: FloatArray) {
        val o = head * n
        for (i in 0 until n) buf[o + i] = if (i < lv.size) lv[i] else 0f
        head = (head + 1) % cols
        if (size < cols) size++
    }

    /** i = 0 (가장 오래됨) .. size-1, band b */
    fun at(i: Int, b: Int): Float = buf[((head - size + i + cols) % cols) * n + b]

    fun clear() { head = 0; size = 0 }
}
