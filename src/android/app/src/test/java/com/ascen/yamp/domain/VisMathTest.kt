package com.ascen.yamp.domain

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

class VisMathTest {
    private fun bytes(vararg v: Int) = ByteArray(v.size) { v[it].toByte() }

    @Test fun modes() {
        assertEquals("chart", VisMath.parseMode(null))
        assertEquals("chart", VisMath.parseMode("xx"))
        assertEquals("wave", VisMath.parseMode("wave"))
        assertEquals("bars", VisMath.parseMode("bars"))
    }

    @Test fun rmsPeakFromUnsigned8bit() {
        // 128 = 0 (무음)
        val silent = ByteArray(64) { 128.toByte() }
        assertEquals(0f, VisMath.rms(silent), 0f)
        assertEquals(0f, VisMath.peak(silent), 0f)
        // 0 / 255 번갈아 = 거의 최대 크기 사각파 → RMS ≈ 피크 ≈ 1
        val sq = bytes(0, 255, 0, 255)
        assertEquals(1f, VisMath.peak(sq), 0.01f)
        assertEquals(1f, VisMath.rms(sq), 0.01f)
        // 192 / 64 = ±0.5
        val half = bytes(192, 64, 192, 64)
        assertEquals(0.5f, VisMath.peak(half), 1e-6f)
        assertEquals(0.5f, VisMath.rms(half), 1e-6f)
        // len 으로 앞부분만
        val mix = bytes(192, 64, 0, 0)
        assertEquals(0.5f, VisMath.peak(mix, 2), 1e-6f)
        assertEquals(0f, VisMath.rms(ByteArray(0)), 0f)
        assertEquals(-1f, VisMath.sample(0.toByte()), 0f)
        assertEquals(0f, VisMath.sample(128.toByte()), 0f)
    }

    @Test fun db() {
        assertEquals(-60f, VisMath.toDb(0f), 0f)
        assertEquals(-60f, VisMath.toDb(1e-6f), 0f)          // 바닥
        assertEquals(0f, VisMath.toDb(1f), 1e-4f)
        assertEquals(-6.02f, VisMath.toDb(0.5f), 0.01f)
        assertEquals(0f, VisMath.toDb(2f), 0f)                // 0 dB 위는 자름
        assertEquals(0f, VisMath.dbFrac(-60f), 0f)
        assertEquals(1f, VisMath.dbFrac(0f), 0f)
        assertEquals(0.8f, VisMath.dbFrac(-12f), 1e-6f)
        assertEquals(0.6f, VisMath.dbFrac(-24f), 1e-6f)
        assertEquals("-∞ dB", VisMath.dbText(0f))
        assertTrue(VisMath.dbText(0.5f).endsWith(" dB"))
    }

    @Test fun wavePointsResample() {
        val out = FloatArray(3)
        VisMath.wavePoints(bytes(0, 128, 255), 3, out)
        assertEquals(-1f, out[0], 0f); assertEquals(0f, out[1], 0f); assertEquals(127 / 128f, out[2], 1e-6f)
        VisMath.wavePoints(ByteArray(10), 0, out)
        assertEquals(0f, out[0] + out[1] + out[2], 0f)
        val big = FloatArray(256)
        VisMath.wavePoints(ByteArray(1024) { 192.toByte() }, 1024, big)
        assertEquals(0.5f, big[255], 1e-6f)
    }

    @Test fun peaksWindowAroundPosition() {
        val peaks = floatArrayOf(0f, 1f, 0f, 1f)        // 칸 1초씩 (곡 4초)
        assertEquals(1f, VisMath.peakAt(peaks, 4000, 1500), 1e-6f)    // 칸 1 가운데
        assertEquals(0.5f, VisMath.peakAt(peaks, 4000, 1000), 1e-6f)  // 칸 0 · 1 사이
        assertEquals(0f, VisMath.peakAt(peaks, 4000, 0), 1e-6f)
        assertEquals(1f, VisMath.peakAt(peaks, 4000, 4000), 1e-6f)    // 끝 = 마지막 칸
        assertEquals(0f, VisMath.peakAt(peaks, 4000, 5000), 0f)       // 곡 밖
        assertEquals(0f, VisMath.peakAt(null, 4000, 100), 0f)
        assertEquals(0f, VisMath.peakAt(peaks, 0, 100), 0f)
        val out = FloatArray(5)
        VisMath.peaksWindow(peaks, 4000, 1500, 1000, out)              // 500..2500
        assertEquals(0.0f, out[0], 1e-6f)
        assertEquals(1f, out[2], 1e-6f)                                 // 가운데 = 지금
        assertEquals(0.0f, out[4], 1e-6f)
        VisMath.peaksWindow(peaks, 4000, 0, 3000, out)                  // 앞쪽 곡 밖 = 0
        assertEquals(0f, out[0], 0f)
    }

    @Test fun ticks() {
        assertEquals(1, VisMath.ticks(-1, 33, 300))
        assertEquals(0, VisMath.ticks(10, 33, 300))
        assertEquals(3, VisMath.ticks(100, 33, 300))
        assertEquals(300, VisMath.ticks(1_000_000, 33, 300))
    }

    @Test fun historyRing() {
        val h = LevelHistory(3)
        assertEquals(0, h.size)
        h.push(0.1f, 0.2f); h.push(0.3f, 0.4f)
        assertEquals(2, h.size)
        assertEquals(0.1f, h.rmsAt(0), 0f)
        assertEquals(0.4f, h.peakAt(1), 0f)
        h.push(0.5f, 0.6f); h.push(0.7f, 0.9f)     // 가장 오래된 0.1 밀려남
        assertEquals(3, h.size)
        assertEquals(0.3f, h.rmsAt(0), 0f)
        assertEquals(0.7f, h.rmsAt(2), 0f)
        assertEquals(0.9f, h.recentPeak(1), 0f)
        assertEquals(0.9f, h.recentPeak(10), 0f)
        assertEquals(0.6f, LevelHistory(4).apply { push(0f, 0.6f); push(0f, 0.1f) }.recentPeak(5), 0f)
        h.clear()
        assertEquals(0, h.size)
        assertEquals(0f, h.recentPeak(3), 0f)
    }

    // ------------------------------------------------------------ v026 (f51): 비주얼라이저 — PC 와 같은 값 (testdata/vis_cases.txt)
    private fun find(rel: String): File {
        var d: File? = File("").absoluteFile
        while (d != null) {
            val f = File(d, rel)
            if (f.exists()) return f
            d = d.parentFile
        }
        error("$rel 를 찾을 수 없음")
    }

    private fun mags(form: String, bins: Int): FloatArray = FloatArray(bins) { k ->
        when (form) {
            "inv" -> 1000f / (k + 1)
            "flat" -> 50f
            else -> when (k) { 1 -> 4000f; 2 -> 2000f; 40 -> 300f; else -> 0f }
        }
    }

    private fun floats(s: String) = s.split(",").map { it.toFloat() }

    @Test fun sharedVisCasesBandsAndSmoother() {
        val rows = find("testdata/vis_cases.txt").readLines(Charsets.UTF_8)
            .map { it.trim() }.filter { it.isNotEmpty() && !it.startsWith("#") }.map { it.split("|") }
        var nb = 0
        var ns = 0
        val sm = BandSmoother(3)
        for (r in rows) {
            if (r[0] == "bands") {
                val bins = r[1].toInt()
                val out = FloatArray(VisMath.VIS_BANDS)
                VisMath.bandsFromMags(mags(r[5], bins), bins, r[2].toDouble(), out, r[3].toDouble(), r[4].toDouble())
                val exp = floats(r[6])
                for (i in exp.indices) assertEquals("${r[5]} band $i", exp[i], out[i], 2e-5f)
                nb++
            } else if (r[0] == "step") {
                if (r[2] != "-") sm.setTarget(floats(r[2]).toFloatArray())
                sm.step(r[1].toDouble())
                val ev = floats(r[3])
                val ep = floats(r[4])
                for (i in 0 until 3) {
                    assertEquals("step $ns v$i", ev[i], sm.v[i], 2e-5f)
                    assertEquals("step $ns p$i", ep[i], sm.peaks[i], 2e-5f)
                }
                ns++
            }
        }
        assertEquals(4, nb)
        assertTrue(ns >= 18)
    }

    @Test fun smootherIdleAndStale() {
        val sm = BandSmoother(4)
        assertTrue(sm.idle())
        sm.setTarget(floatArrayOf(1f, 1f, 1f, 1f))
        sm.step(0.05)
        assertTrue(sm.v[1] in 0.55f..0.7f)            // 오를 때 τ 50 ms
        repeat(9) { sm.step(0.033) }                  // 새 값 없음 0.25초 넘음 → 목표 0
        assertEquals(0f, sm.targetAt(0), 0f)
        repeat(150) { sm.step(0.033) }
        assertTrue(sm.idle())
    }

    // ------------------------------------------------------------ v027 (f53): 막대 모양 · 원형 · 스펙트로그램 — PC 와 같은 값
    @Test fun sharedVisCasesHeatLedStyleMirror() {
        val rows = find("testdata/vis_cases.txt").readLines(Charsets.UTF_8).map { it.trim() }.filter { !it.startsWith("#") }.map { it.split("|") }
        var nh = 0
        for (r in rows) when (r[0]) {
            "heat" -> {
                val stops = r[2].split(",").map { it.removePrefix("#").toInt(16) }.toIntArray()
                val c = VisMath.heatArgb(r[1].toFloat(), stops)
                val e = r[3].split(",").map { it.toInt() }
                assertEquals("heat ${r[1]}", listOf(e[0], e[1], e[2]), listOf((c shr 16) and 0xFF, (c shr 8) and 0xFF, c and 0xFF))
                nh++
            }
            "led" -> assertEquals("led ${r[1]} ${r[2]}", r[4].toInt(), VisMath.ledCells(r[1].toFloat(), r[2].toFloat(), r[3].toFloat()))
            "style" -> assertEquals(r[2], VisMath.nextBarStyle(r[1]))
            "mirror" -> {
                val n = r[1].toInt()
                val out = IntArray(n * 2)
                VisMath.mirrorOrder(n, out)
                assertEquals(r[2], out.joinToString(","))
            }
        }
        assertTrue(nh >= 8)
    }

    @Test fun modesStylesGram() {
        assertEquals(listOf("bars", "wave", "radial", "gram", "chart"), VisMath.MODES)
        assertEquals("gram", VisMath.parseMode("gram"))
        assertEquals("round", VisMath.parseBarStyle("zzz"))
        assertEquals("led", VisMath.parseBarStyle("led"))
        val g = GramHistory(3, 4)
        for (k in 0 until 6) g.push(floatArrayOf(k.toFloat(), k + 0.5f, k + 0.25f))
        assertEquals(4, g.size)
        assertEquals(2f, g.at(0, 0), 0f)
        assertEquals(5.5f, g.at(3, 1), 0f)
        g.push(floatArrayOf(1f))
        assertEquals(0f, g.at(3, 2), 0f)
        g.clear()
        assertEquals(0, g.size)
    }
}
