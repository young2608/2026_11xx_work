package com.ascen.yamp.domain

import java.math.BigDecimal
import java.math.MathContext
import java.math.RoundingMode
import kotlin.math.PI
import kotlin.math.abs
import kotlin.math.cos
import kotlin.math.exp
import kotlin.math.log10
import kotlin.math.max
import kotlin.math.min
import kotlin.math.pow
import kotlin.math.sin
import kotlin.math.sqrt

/**
 * 사운드 처리 계산 (순수 Kotlin — Android 비의존). PC yamp/domain/dsp.py 와 **같은 식 · 같은 순서**.
 * 공용 테스트 벡터: 00__build/src/testdata/dsp_cases.txt (pc/tests/gen_testdata.py 생성, DspTest 가 읽음)
 *
 * 구성 (RBJ Audio EQ Cookbook 바이쿼드, 샘플레이트별 계수)
 *   프리앰프(dB) → 10밴드 피킹 EQ(31~16k, Q=1.41) → 베이스 로우셸프(100Hz) → 트레블 하이셸프(8kHz)
 *   → 밸런스(L/R 게인) → 컴프레서(피크 검출, threshold/ratio/attack/release/makeup) → 리미터(-1 dBFS)
 * 실제 소리 처리: playback/SoundProcessor.kt (ExoPlayer 오디오 처리기) 가 Processor 사용
 */
object Dsp {
    val EQ_FREQS = intArrayOf(31, 62, 125, 250, 500, 1000, 2000, 4000, 8000, 16000)
    const val EQ_Q = 1.41
    const val BASS_HZ = 100.0
    const val TREBLE_HZ = 8000.0
    const val SHELF_S = 1.0
    const val LIMIT_DB = -1.0
    const val LIMIT_ATTACK_MS = 1.0
    const val LIMIT_RELEASE_MS = 80.0

    /** 프리셋 (PC 와 같은 순서) */
    val PRESETS: List<Pair<String, List<Double>>> = listOf(
        "평탄" to List(10) { 0.0 },
        "베이스 강조" to listOf(6, 5, 4, 2, 0, 0, 0, 0, 0, 0).map { it.toDouble() },
        "고음 강조" to listOf(0, 0, 0, 0, 0, 1, 2, 4, 5, 6).map { it.toDouble() },
        "보컬" to listOf(-2, -2, -1, 1, 3, 4, 3, 1, 0, -1).map { it.toDouble() },
        "록" to listOf(5, 3, 1, -1, -2, -1, 1, 3, 4, 5).map { it.toDouble() },
        "클래식" to listOf(4, 3, 2, 1, 0, 0, 0, 1, 2, 3).map { it.toDouble() },
        "재즈" to listOf(3, 2, 1, 2, -1, -1, 0, 1, 2, 3).map { it.toDouble() },
        "댄스" to listOf(6, 5, 2, 0, 0, -1, -2, -2, 0, 0).map { it.toDouble() },
        // vr0.1.0.010 V4: 녹음·강의 — 저음 줄이고 2~4kHz(말소리) 올림 (PC dsp.py 와 같은 값 · 같은 순서)
        "음성" to listOf(-8, -6, -3, 0, 1, 3, 4, 3, 1, -2).map { it.toDouble() },
    )

    /** 바이쿼드 계수 (b0, b1, b2, a1, a2) — a0 로 정규화 */
    class Coef(val b0: Double, val b1: Double, val b2: Double, val a1: Double, val a2: Double) {
        fun toList(): List<Double> = listOf(b0, b1, b2, a1, a2)
    }

    // ---------------------------------------------------------------- 바이쿼드 계수 (RBJ)
    fun peaking(fs: Double, f0: Double, q: Double, gainDb: Double): Coef {
        val a = 10.0.pow(gainDb / 40)
        val w = 2 * PI * f0 / fs
        val al = sin(w) / (2 * q)
        val cw = cos(w)
        val a0 = 1 + al / a
        return Coef((1 + al * a) / a0, (-2 * cw) / a0, (1 - al * a) / a0, (-2 * cw) / a0, (1 - al / a) / a0)
    }

    private fun shelfAlpha(a: Double, w: Double, s: Double): Double = sin(w) / 2 * sqrt((a + 1 / a) * (1 / s - 1) + 2)

    fun lowShelf(fs: Double, f0: Double, s: Double, gainDb: Double): Coef {
        val a = 10.0.pow(gainDb / 40)
        val w = 2 * PI * f0 / fs
        val cw = cos(w)
        val al = shelfAlpha(a, w, s)
        val sq = 2 * sqrt(a) * al
        val a0 = (a + 1) + (a - 1) * cw + sq
        return Coef((a * ((a + 1) - (a - 1) * cw + sq)) / a0, (2 * a * ((a - 1) - (a + 1) * cw)) / a0,
            (a * ((a + 1) - (a - 1) * cw - sq)) / a0, (-2 * ((a - 1) + (a + 1) * cw)) / a0,
            ((a + 1) + (a - 1) * cw - sq) / a0)
    }

    fun highShelf(fs: Double, f0: Double, s: Double, gainDb: Double): Coef {
        val a = 10.0.pow(gainDb / 40)
        val w = 2 * PI * f0 / fs
        val cw = cos(w)
        val al = shelfAlpha(a, w, s)
        val sq = 2 * sqrt(a) * al
        val a0 = (a + 1) - (a - 1) * cw + sq
        return Coef((a * ((a + 1) + (a - 1) * cw + sq)) / a0, (-2 * a * ((a - 1) + (a + 1) * cw)) / a0,
            (a * ((a + 1) + (a - 1) * cw - sq)) / a0, (2 * ((a - 1) - (a + 1) * cw)) / a0,
            ((a + 1) - (a - 1) * cw - sq) / a0)
    }

    /** 활성 필터 계수 목록 (0 dB 필터는 뺌 — 계산 절약, 결과 동일) */
    fun chain(s: SoundSettings, fs: Int): List<Coef> {
        val out = ArrayList<Coef>()
        if (!s.enabled) return out
        val f = fs.toDouble()
        val nyq = f / 2
        for (i in EQ_FREQS.indices) {
            val g = s.bands.getOrElse(i) { 0.0 }
            val f0 = EQ_FREQS[i].toDouble()
            if (abs(g) >= 0.01 && f0 < nyq * 0.95) out.add(peaking(f, f0, EQ_Q, g))
        }
        if (abs(s.bassDb) >= 0.01) out.add(lowShelf(f, BASS_HZ, SHELF_S, s.bassDb))
        if (abs(s.trebleDb) >= 0.01 && TREBLE_HZ < nyq * 0.95) out.add(highShelf(f, TREBLE_HZ, SHELF_S, s.trebleDb))
        return out
    }

    /** 한 바이쿼드의 주파수 f 에서의 크기(dB) */
    fun magnitudeDb(c: Coef, fs: Double, f: Double): Double {
        val w = 2 * PI * f / fs
        val c1 = cos(w); val s1 = sin(w); val c2 = cos(2 * w); val s2 = sin(2 * w)
        val nr = c.b0 + c.b1 * c1 + c.b2 * c2
        val ni = -(c.b1 * s1 + c.b2 * s2)
        val dr = 1 + c.a1 * c1 + c.a2 * c2
        val di = -(c.a1 * s1 + c.a2 * s2)
        val num = nr * nr + ni * ni
        val den = dr * dr + di * di
        return 10 * log10(max(num, 1e-30) / max(den, 1e-30))
    }

    /** 응답 곡선 (프리앰프 포함). EQ 꺼짐이면 0 */
    fun responseDb(s: SoundSettings, freqs: List<Double>, fs: Int = 48000): List<Double> {
        if (!s.enabled) return freqs.map { 0.0 }
        val cs = chain(s, fs)
        return freqs.map { f ->
            var sum = 0.0
            for (c in cs) sum += magnitudeDb(c, fs.toDouble(), f)
            s.preampDb + sum
        }
    }

    fun logFreqs(n: Int = 64, lo: Double = 20.0, hi: Double = 20000.0): List<Double> =
        (0 until n).map { i -> lo * (hi / lo).pow(i / (n - 1).toDouble()) }

    // ---------------------------------------------------------------- 실시간 처리
    fun dbToLin(db: Double): Double = 10.0.pow(db / 20)

    /** (왼쪽, 오른쪽) 배율 — 가운데 0 이면 (1,1), 오른쪽(+) 으로 갈수록 왼쪽이 줄어듦 */
    fun balanceGains(b: Double): Pair<Double, Double> = min(1.0, 1.0 - b) to min(1.0, 1.0 + b)

    fun timeCoef(ms: Double, fs: Int): Double = exp(-1.0 / (max(ms, 0.01) * 0.001 * fs))

    /** 컴프레서 정적 곡선 (하드 니): 줄일 dB (≤ 0) */
    fun compGainDb(levelDb: Double, th: Double, ratio: Double): Double {
        val over = levelDb - th
        return if (over > 0) -over * (1 - 1 / ratio) else 0.0
    }

    /** 비정규화(denormal) 수 방지 기준: 필터 상태 · 엔벨로프가 이보다 작으면 0 (−500 dB — 소리·테스트 벡터 영향 없음) */
    const val DENORMAL_EPS = 1e-25

    /** |v| < DENORMAL_EPS 이면 0 (긴 무음 뒤 IIR 상태가 비정규화 수로 남아 CPU 가 튀는 것 방지) */
    fun flushDenormal(v: Double): Double = if (abs(v) < DENORMAL_EPS) 0.0 else v

    /**
     * 인터리브 프레임 처리 (채널 1~2). PC Processor 와 같은 순서·식.
     * 필터 상태를 가지므로 설정·포맷이 바뀌면 새로 만든다 (SoundProcessor).
     * vr0.1.0.008: 계수를 DoubleArray 한 줄로 펼침 (샘플마다 객체 참조 없음 — 같은 값 · 같은 계산 순서),
     *              process() 끝에서 아주 작은 상태값을 0 으로 (긴 무음 → 비정규화 수 → CPU 급증 방지, 결과 동일)
     */
    class Processor(val s: SoundSettings, val fs: Int, val ch: Int) {
        private val coefs: Array<Coef> = chain(s, fs).toTypedArray()
        private val nf = coefs.size
        /** 필터 k 의 계수 = cf[k*5 + 0..4] (b0, b1, b2, a1, a2) */
        private val cf = DoubleArray(nf * 5).also { a ->
            for (k in 0 until nf) {
                val c = coefs[k]
                a[k * 5] = c.b0; a[k * 5 + 1] = c.b1; a[k * 5 + 2] = c.b2; a[k * 5 + 3] = c.a1; a[k * 5 + 4] = c.a2
            }
        }
        // 채널별·필터별 상태 (DF2T): z[(c * nf + k) * 2 + 0/1]
        private val z = DoubleArray(ch * nf * 2)
        private val pre = if (s.enabled) dbToLin(s.preampDb) else 1.0
        private val balL: Double
        private val balR: Double
        private var envC = 0.0          // 컴프레서 검출 (선형 피크 엔벨로프)
        private var envL = 1.0          // 리미터 게인
        private val cAtt = timeCoef(s.compAttackMs, fs)
        private val cRel = timeCoef(s.compReleaseMs, fs)
        private val lAtt = timeCoef(LIMIT_ATTACK_MS, fs)
        private val lRel = timeCoef(LIMIT_RELEASE_MS, fs)
        private val lThr = dbToLin(LIMIT_DB)
        private val makeup = dbToLin(s.compMakeupDb)
        private val frame = DoubleArray(ch)

        init {
            val b = if (ch == 2) balanceGains(s.balance) else 1.0 to 1.0
            balL = b.first
            balR = b.second
        }

        val active: Boolean
            get() = coefs.isNotEmpty() || abs(pre - 1) > 1e-9 || balL != 1.0 || balR != 1.0 || s.comp || s.limiter

        /** data: 인터리브 샘플 (제자리 처리). frames = data.size / ch */
        fun process(data: DoubleArray, len: Int = data.size) {
            val n = len / ch
            var o = 0
            for (i in 0 until n) {
                for (c in 0 until ch) {
                    var x = data[o + c] * pre
                    var zi = c * nf * 2
                    var ci = 0
                    for (k in 0 until nf) {
                        val y = cf[ci] * x + z[zi]
                        z[zi] = cf[ci + 1] * x - cf[ci + 3] * y + z[zi + 1]
                        z[zi + 1] = cf[ci + 2] * x - cf[ci + 4] * y
                        x = y
                        zi += 2
                        ci += 5
                    }
                    frame[c] = x * (if (ch == 2 && c == 1) balR else balL)
                }
                var peak = 0.0
                for (c in 0 until ch) peak = max(peak, abs(frame[c]))
                if (s.comp) {
                    val coef = if (peak > envC) cAtt else cRel
                    envC = coef * envC + (1 - coef) * peak
                    val lvl = 20 * log10(max(envC, 1e-9))
                    val g = dbToLin(compGainDb(lvl, s.compThresholdDb, s.compRatio)) * makeup
                    for (c in 0 until ch) frame[c] = frame[c] * g
                    peak *= g
                }
                if (s.limiter) {
                    val target = if (peak > lThr) lThr / peak else 1.0
                    val coef = if (target < envL) lAtt else lRel
                    envL = coef * envL + (1 - coef) * target
                    for (c in 0 until ch) frame[c] = max(-1.0, min(1.0, frame[c] * envL))
                }
                for (c in 0 until ch) data[o + c] = frame[c]
                o += ch
            }
            flushState()
        }

        /** 버퍼 끝마다: 비정규화 직전의 상태값 → 0 (버퍼 안 계산은 그대로라 출력 동일) */
        private fun flushState() {
            for (i in z.indices) z[i] = flushDenormal(z[i])
            envC = flushDenormal(envC)
        }

        /** 테스트용: 필터 상태 중 0 이 아닌 값 개수 */
        internal fun nonZeroState(): Int = z.count { it != 0.0 } + (if (envC != 0.0) 1 else 0)
    }

    /** Python f"{v:g}" 와 같은 숫자 글자 (유효숫자 6자리, 뒤 0 제거) */
    fun fmtG(v: Double): String {
        if (v.isNaN()) return "nan"
        if (v.isInfinite()) return if (v > 0) "inf" else "-inf"
        if (v == 0.0) return if (1.0 / v < 0) "-0" else "0"
        val bd = BigDecimal(v).round(MathContext(6, RoundingMode.HALF_EVEN))
        val e = bd.precision() - bd.scale() - 1
        if (e < -4 || e >= 6) {
            val mant = bd.movePointLeft(e).stripTrailingZeros().toPlainString()
            val es = if (e < 0) "-" else "+"
            return mant + "e" + es + abs(e).toString().padStart(2, '0')
        }
        return bd.stripTrailingZeros().toPlainString()
    }
}

/** 사운드 설정 (PC SoundSettings 와 같은 항목 · 같은 텍스트 형식). 변경은 copy(...).clamp() */
data class SoundSettings(
    val enabled: Boolean = false,               // EQ·톤 (밸런스·다이내믹은 따로)
    val preampDb: Double = 0.0,
    val bands: List<Double> = List(10) { 0.0 },
    val bassDb: Double = 0.0,
    val trebleDb: Double = 0.0,
    val balance: Double = 0.0,                  // -1 (왼쪽) ~ +1 (오른쪽)
    val limiter: Boolean = false,
    val comp: Boolean = false,
    val compThresholdDb: Double = -18.0,
    val compRatio: Double = 3.0,
    val compAttackMs: Double = 10.0,
    val compReleaseMs: Double = 120.0,
    val compMakeupDb: Double = 0.0,
) {
    fun clamp(): SoundSettings {
        fun c(v: Double, lo: Double, hi: Double) = max(lo, min(hi, v))
        return copy(
            preampDb = c(preampDb, -12.0, 12.0),
            bands = (bands + List(10) { 0.0 }).take(10).map { c(it, -12.0, 12.0) },
            bassDb = c(bassDb, -12.0, 12.0),
            trebleDb = c(trebleDb, -12.0, 12.0),
            balance = c(balance, -1.0, 1.0),
            compThresholdDb = c(compThresholdDb, -60.0, 0.0),
            compRatio = c(compRatio, 1.0, 20.0),
            compAttackMs = c(compAttackMs, 0.1, 200.0),
            compReleaseMs = c(compReleaseMs, 5.0, 2000.0),
            compMakeupDb = c(compMakeupDb, 0.0, 24.0),
        )
    }

    /** 무엇이든 소리를 바꾸는 설정이 켜져 있는지 (꺼져 있으면 처리기는 그대로 통과) */
    val anyActive: Boolean
        get() = (enabled && (abs(preampDb) > 1e-9 || bands.any { abs(it) >= 0.01 } || abs(bassDb) >= 0.01 || abs(trebleDb) >= 0.01)) ||
            abs(balance) > 1e-9 || limiter || comp

    fun toText(): String {
        val f = Dsp::fmtG
        return listOf(
            "on=${if (enabled) 1 else 0}", "pre=${f(preampDb)}", "eq=" + bands.joinToString(",") { f(it) },
            "bass=${f(bassDb)}", "treble=${f(trebleDb)}", "bal=${f(balance)}",
            "lim=${if (limiter) 1 else 0}", "comp=${if (comp) 1 else 0}", "th=${f(compThresholdDb)}",
            "ratio=${f(compRatio)}", "att=${f(compAttackMs)}", "rel=${f(compReleaseMs)}",
            "mk=${f(compMakeupDb)}",
        ).joinToString(";")
    }

    companion object {
        fun fromText(text: String?): SoundSettings {
            var s = SoundSettings()
            for (part in (text ?: "").split(";")) {
                val eq = part.indexOf('=')
                val k = (if (eq >= 0) part.substring(0, eq) else part).trim()
                val v = if (eq >= 0) part.substring(eq + 1) else ""
                val d = v.trim().toDoubleOrNull()
                when (k) {
                    "on" -> s = s.copy(enabled = v.trim() == "1")
                    "pre" -> if (d != null) s = s.copy(preampDb = d)
                    "eq" -> {
                        val items = v.split(",").map { x -> if (x.isBlank()) 0.0 else x.trim().toDoubleOrNull() }
                        if (items.all { it != null }) s = s.copy(bands = items.map { it ?: 0.0 })
                    }
                    "bass" -> if (d != null) s = s.copy(bassDb = d)
                    "treble" -> if (d != null) s = s.copy(trebleDb = d)
                    "bal" -> if (d != null) s = s.copy(balance = d)
                    "lim" -> s = s.copy(limiter = v.trim() == "1")
                    "comp" -> s = s.copy(comp = v.trim() == "1")
                    "th" -> if (d != null) s = s.copy(compThresholdDb = d)
                    "ratio" -> if (d != null) s = s.copy(compRatio = d)
                    "att" -> if (d != null) s = s.copy(compAttackMs = d)
                    "rel" -> if (d != null) s = s.copy(compReleaseMs = d)
                    "mk" -> if (d != null) s = s.copy(compMakeupDb = d)
                }
            }
            return s.clamp()
        }
    }
}
