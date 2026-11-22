package com.ascen.yamp.domain

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File
import kotlin.math.PI
import kotlin.math.sin

/**
 * PC tests 와 같은 공용 벡터 (00__build/src/testdata/dsp_cases.txt) → 계수 · 응답 곡선 · 처리 결과 일치 확인.
 * 형식: pc/tests/gen_testdata.py build_dsp_text()
 */
class DspTest {
    private fun findCases(name: String): File {
        var d: File? = File("").absoluteFile
        while (d != null) {
            val f = File(d, "testdata/$name")
            if (f.exists()) return f
            d = d.parentFile
        }
        error("testdata/$name 를 찾을 수 없음 (cwd=${File("").absolutePath})")
    }

    /** PC test_signal 과 같은 결정적 시험 신호: 100Hz + 3kHz 사인 + 32번째 프레임 임펄스 (인터리브) */
    private fun testSignal(fs: Int, ch: Int, frames: Int): DoubleArray {
        val out = DoubleArray(frames * ch)
        var o = 0
        for (i in 0 until frames) {
            var v = 0.6 * sin(2 * PI * 100 * i / fs) + 0.3 * sin(2 * PI * 3000 * i / fs)
            if (i == 32) v += 0.5
            for (c in 0 until ch) out[o++] = v * (if (c == 0) 1.0 else 0.8)
        }
        return out
    }

    private data class SetCase(val settings: SoundSettings, val text: String, val fs: Int, val ch: Int)

    private val lines by lazy { findCases("dsp_cases.txt").readLines(Charsets.UTF_8).filter { it.isNotBlank() } }

    private fun sets(): Map<String, SetCase> = lines.filter { it.startsWith("SET ") }.associate { l ->
        val p = l.removePrefix("SET ").split("|")
        p[0] to SetCase(SoundSettings.fromText(p[1]), p[1], p[2].toInt(), p[3].toInt())
    }

    @Test fun settingsTextRoundTrip() {
        val ss = sets()
        assertEquals(10, ss.size)
        for ((id, c) in ss) {
            assertEquals("toText $id", c.text, c.settings.toText())
            assertEquals("roundtrip $id", c.settings, SoundSettings.fromText(c.settings.toText()))
        }
        // 범위 밖 · 잘못된 값
        val s = SoundSettings.fromText("on=1;pre=99;eq=1,x,3;bal=-5;ratio=0.2;att=abc;mk=30")
        assertEquals(12.0, s.preampDb, 0.0)
        assertEquals(List(10) { 0.0 }, s.bands)
        assertEquals(-1.0, s.balance, 0.0)
        assertEquals(1.0, s.compRatio, 0.0)
        assertEquals(10.0, s.compAttackMs, 0.0)
        assertEquals(24.0, s.compMakeupDb, 0.0)
        assertEquals("0.1", Dsp.fmtG(0.1))
        assertEquals("-18", Dsp.fmtG(-18.0))
        assertEquals("1e+06", Dsp.fmtG(1_000_000.0))
        assertEquals("1.5e-05", Dsp.fmtG(0.000015))
        assertEquals("0.333333", Dsp.fmtG(1.0 / 3))
    }

    @Test fun coefficients() {
        val ss = sets()
        val byId = HashMap<String, MutableList<List<Double>>>()
        lines.filter { it.startsWith("COEF ") }.forEach { l ->
            val p = l.removePrefix("COEF ").split("|")
            byId.getOrPut(p[0]) { ArrayList() }.add(p[2].split(",").map { it.toDouble() })
        }
        var n = 0
        for ((id, c) in ss) {
            val got = Dsp.chain(c.settings, c.fs)
            val exp = byId[id].orEmpty()
            assertEquals("filter count $id", exp.size, got.size)
            for (k in exp.indices) for (j in 0 until 5) {
                assertEquals("$id[$k][$j]", exp[k][j], got[k].toList()[j], 1e-7); n++
            }
        }
        assertTrue(n > 50)
    }

    @Test fun responseCurve() {
        val ss = sets()
        for (l in lines.filter { it.startsWith("RESP ") }) {
            val p = l.removePrefix("RESP ").split("|")
            val c = ss.getValue(p[0])
            val pairs = p[1].split(",").map { it.split(":") }
            val got = Dsp.responseDb(c.settings, pairs.map { it[0].toDouble() }, c.fs)
            pairs.forEachIndexed { i, kv -> assertEquals("${p[0]} f=${kv[0]}", kv[1].toDouble(), got[i], 1e-5) }
        }
        assertEquals(64, Dsp.logFreqs().size)
        assertEquals(20000.0, Dsp.logFreqs().last(), 1e-6)
    }

    @Test fun processing() {
        val ss = sets()
        var n = 0
        for (l in lines.filter { it.startsWith("PROC ") }) {
            val p = l.removePrefix("PROC ").split("|")
            val c = ss.getValue(p[0])
            val y = testSignal(c.fs, c.ch, 256)
            Dsp.Processor(c.settings, c.fs, c.ch).process(y)
            for (kv in p[1].split(",")) {
                val (i, v) = kv.split(":")
                assertEquals("${p[0]} #$i", v.toDouble(), y[i.toInt()], 1e-6); n++
            }
        }
        assertTrue(n > 100)
        // 꺼짐(평탄) → 통과
        assertTrue(!Dsp.Processor(SoundSettings(), 44100, 2).active)
        assertTrue(Dsp.Processor(SoundSettings(limiter = true), 44100, 2).active)
    }

    @Test fun compressorAndBalance() {
        for (l in lines.filter { it.startsWith("CGAIN ") }) {
            val p = l.removePrefix("CGAIN ").split("|").map { it.toDouble() }
            assertEquals(l, p[3], Dsp.compGainDb(p[0], p[1], p[2]), 1e-6)
        }
        for (l in lines.filter { it.startsWith("BAL ") }) {
            val p = l.removePrefix("BAL ").split("|").map { it.toDouble() }
            val (lg, rg) = Dsp.balanceGains(p[0])
            assertEquals(l, p[1], lg, 1e-6)
            assertEquals(l, p[2], rg, 1e-6)
        }
        assertEquals(9, Dsp.PRESETS.size)
        assertEquals("음성" to listOf(-8, -6, -3, 0, 1, 3, 4, 3, 1, -2).map { it.toDouble() }, Dsp.PRESETS[8])   // vr0.1.0.010 V4 (PC 와 같은 순서 · 값)
        assertEquals("평탄", Dsp.PRESETS[0].first)
    }

    // ------------------------------------------------ vr0.1.0.008: 계수 펼침 · 비정규화 방지 (결과 동일 확인)

    /** vr0.1.0.007 까지의 처리 (Coef 객체 · 상태 정리 없음) — 새 Processor 와 비트 단위로 같아야 함 */
    private fun referenceProcess(s: SoundSettings, fs: Int, ch: Int, data: DoubleArray) {
        val coefs = Dsp.chain(s, fs)
        val nf = coefs.size
        val z = DoubleArray(ch * nf * 2)
        val pre = if (s.enabled) Dsp.dbToLin(s.preampDb) else 1.0
        val (bl, br) = if (ch == 2) Dsp.balanceGains(s.balance) else 1.0 to 1.0
        var envC = 0.0
        var envL = 1.0
        val cAtt = Dsp.timeCoef(s.compAttackMs, fs); val cRel = Dsp.timeCoef(s.compReleaseMs, fs)
        val lAtt = Dsp.timeCoef(Dsp.LIMIT_ATTACK_MS, fs); val lRel = Dsp.timeCoef(Dsp.LIMIT_RELEASE_MS, fs)
        val lThr = Dsp.dbToLin(Dsp.LIMIT_DB); val makeup = Dsp.dbToLin(s.compMakeupDb)
        val frame = DoubleArray(ch)
        var o = 0
        for (i in 0 until data.size / ch) {
            for (c in 0 until ch) {
                var x = data[o + c] * pre
                var zi = c * nf * 2
                for (cf in coefs) {
                    val y = cf.b0 * x + z[zi]
                    z[zi] = cf.b1 * x - cf.a1 * y + z[zi + 1]
                    z[zi + 1] = cf.b2 * x - cf.a2 * y
                    x = y; zi += 2
                }
                frame[c] = x * (if (ch == 2 && c == 1) br else bl)
            }
            var peak = 0.0
            for (c in 0 until ch) peak = kotlin.math.max(peak, kotlin.math.abs(frame[c]))
            if (s.comp) {
                val coef = if (peak > envC) cAtt else cRel
                envC = coef * envC + (1 - coef) * peak
                val g = Dsp.dbToLin(Dsp.compGainDb(20 * kotlin.math.log10(kotlin.math.max(envC, 1e-9)), s.compThresholdDb, s.compRatio)) * makeup
                for (c in 0 until ch) frame[c] *= g
                peak *= g
            }
            if (s.limiter) {
                val target = if (peak > lThr) lThr / peak else 1.0
                val coef = if (target < envL) lAtt else lRel
                envL = coef * envL + (1 - coef) * target
                for (c in 0 until ch) frame[c] = kotlin.math.max(-1.0, kotlin.math.min(1.0, frame[c] * envL))
            }
            for (c in 0 until ch) data[o + c] = frame[c]
            o += ch
        }
    }

    @Test fun flattenedProcessorBitIdentical() {
        for ((id, c) in sets()) {
            val a = testSignal(c.fs, c.ch, 2048)
            val b = a.copyOf()
            Dsp.Processor(c.settings, c.fs, c.ch).process(a)
            referenceProcess(c.settings, c.fs, c.ch, b)
            for (i in a.indices) assertEquals("$id #$i", b[i], a[i], 0.0)
            // 버퍼를 나눠 처리해도 (ExoPlayer 는 수 ms 단위 버퍼) 결과가 같음 — 상태 정리는 아주 작은 값만
            val d = testSignal(c.fs, c.ch, 2048)
            val p = Dsp.Processor(c.settings, c.fs, c.ch)
            var off = 0
            val chunk = 300 * c.ch
            while (off < d.size) {
                val n = minOf(chunk, d.size - off)
                val buf = d.copyOfRange(off, off + n)
                p.process(buf)
                System.arraycopy(buf, 0, d, off, n)
                off += n
            }
            for (i in d.indices) assertEquals("$id chunk #$i", b[i], d[i], 1e-15)
        }
    }

    @Test fun denormalFlushAfterLongSilence() {
        assertEquals(0.0, Dsp.flushDenormal(1e-30), 0.0)
        assertEquals(0.0, Dsp.flushDenormal(-Double.MIN_VALUE), 0.0)
        assertEquals(1e-20, Dsp.flushDenormal(1e-20), 0.0)
        assertEquals(-0.5, Dsp.flushDenormal(-0.5), 0.0)
        // 저음 EQ + 컴프레서: 소리 한 번 → 무음 30초 (버퍼 1024프레임씩) → 필터 상태 · 엔벨로프 모두 0
        val s = SoundSettings(enabled = true, bands = listOf(12.0, 10.0, 8.0, 0.0, 0.0, 0.0, 0.0, 0.0, 6.0, 6.0),
            bassDb = 9.0, trebleDb = 6.0, comp = true, limiter = true).clamp()
        val fs = 44100
        val p = Dsp.Processor(s, fs, 2)
        p.process(testSignal(fs, 2, 1024))
        assertTrue(p.nonZeroState() > 0)
        val buf = DoubleArray(1024 * 2)
        for (k in 0 until 30 * fs / 1024) {
            java.util.Arrays.fill(buf, 0.0)
            p.process(buf)
            for (v in buf) assertTrue(v == 0.0 || kotlin.math.abs(v) >= java.lang.Double.MIN_NORMAL)
        }
        assertEquals(0, p.nonZeroState())
        // 다시 소리가 나면 정상 처리 (무음 뒤 첫 버퍼 = 새 처리기와 같음, 엔벨로프 envL 은 1 근처라 그대로)
        val again = testSignal(fs, 2, 512)
        p.process(again)
        assertTrue(again.all { it.isFinite() } && again.any { it != 0.0 })
    }
    /** v032 (f60 A2): 컴프레서 '문턱 아래면 log10 · pow 건너뛰기' — 문턱 · 비율 · 크기 여러 가지에서 옛 식과 비트까지 같음 */
    @Test fun compressorFastPathBitIdentical() {
        val rnd = java.util.Random(32)
        for (th in listOf(-60.0, -40.0, -18.0, -6.0, -0.5, 0.0)) for (ratio in listOf(1.0, 3.0, 20.0)) for (ch in 1..2) {
            val s = SoundSettings(comp = true, limiter = th > -10, compThresholdDb = th, compRatio = ratio,
                compAttackMs = 2.0, compReleaseMs = 80.0, compMakeupDb = 4.0).clamp()
            for (amp in listOf(1e-7, 0.003, 0.05, 0.3, 1.0, 2.0)) {
                val a = DoubleArray(1500 * ch) { (rnd.nextDouble() * 2 - 1) * amp }
                val b = a.copyOf()
                Dsp.Processor(s, 44100, ch).process(a)
                referenceProcess(s, 44100, ch, b)
                for (i in a.indices) assertEquals("th=$th r=$ratio amp=$amp #$i", b[i], a[i], 0.0)
            }
        }
    }
}
