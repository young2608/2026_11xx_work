package com.ascen.yamp.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File
import java.nio.file.Files
import java.time.LocalDate

/** PC tests/test_v002.py 와 같은 규칙 */
class CoreTest {
    private fun tmp(): File = Files.createTempDirectory("ump").toFile()

    @Test fun logSizeRotationKeeps8() {
        val d = tmp()
        var day = LocalDate.of(2026, 7, 16)
        val r = RingLog(d, 4096, 8) { day }
        assertEquals("00__2026__0716.txt", r.currentFile!!.name)
        for (i in 0 until 400) r.write("line %04d ".format(i) + "x".repeat(90))
        r.close()
        val names = d.list()!!.sorted()
        assertEquals(8, names.size)
        assertTrue(names.all { it.endsWith("__2026__0716.txt") })
        assertTrue(names.all { File(d, it).length() <= 4096 })
        assertEquals((0 until 8).map { "%02d".format(it) }.toSet(), names.map { it.take(2) }.toSet())
        assertFalse(names.joinToString("") { File(d, it).readText() }.contains("line 0000"))
    }

    @Test fun logDayRotationAndResume() {
        val d = tmp()
        var day = LocalDate.of(2026, 7, 16)
        val r = RingLog(d, 1 shl 20, 8) { day }
        r.write("a")
        day = LocalDate.of(2026, 7, 17)
        r.write("b")
        assertEquals("01__2026__0717.txt", r.currentFile!!.name)
        r.close()
        assertEquals("01__2026__0717.txt", RingLog(d, 1 shl 20, 8) { day }.also { it.close() }.currentFile!!.name)
        day = LocalDate.of(2026, 7, 18)
        assertEquals("02__2026__0718.txt", RingLog(d, 1 shl 20, 8) { day }.also { it.close() }.currentFile!!.name)
    }

    @Test fun configParseAndUpdate() {
        val (v, w) = ConfigTxt.parse("log_level = debug\nlog_max_files = 999\nlyrics_alsong = no\ntheme = DARK\nfoo = 1\nspectrum = maybe\nbad\n")
        assertEquals("DEBUG", v["log_level"])
        assertEquals("100", v["log_max_files"])
        assertEquals("0", v["lyrics_alsong"])
        assertEquals("dark", v["theme"])
        assertEquals(3, w.size)
        val (dv, dw) = ConfigTxt.parse(ConfigTxt.DEFAULT_TEXT)
        assertTrue(dw.isEmpty())
        assertEquals(ConfigTxt.DEFAULTS.keys, dv.keys)
        val up = ConfigTxt.update(ConfigTxt.DEFAULT_TEXT, mapOf("theme" to "light"))
        assertTrue(up.contains("theme            = light") && up.contains("# sunny (기본: 흰색·노랑·주황)"))
        assertEquals(ConfigTxt.DEFAULT_TEXT.lines().size, up.lines().size)
        // vr0.1.0.012 (f23): 상단 바 — 기본값 · 주기 5 ~ 3600 · 켬/끔
        assertEquals("1", dv["topbar_ticker"]); assertEquals("KRW-XRP", dv["ticker_market"]); assertEquals("10", dv["ticker_interval_s"])
        assertEquals("1", dv["topbar_clock"]); assertEquals("0", dv["topbar_clock_seconds"])
        assertEquals("5", ConfigTxt.norm("ticker_interval_s", "1")); assertEquals("3600", ConfigTxt.norm("ticker_interval_s", "99999"))
        assertEquals("1", ConfigTxt.norm("topbar_clock_seconds", "on"))
        assertEquals("KRW-XRP,KRW-BTC", ConfigTxt.parse("ticker_market = KRW-XRP,KRW-BTC\n").first["ticker_market"])
    }

    @Test fun configFileCreateSetReload() {
        val f = File(tmp(), "files/config.txt")
        val c = ConfigTxt(f)
        assertTrue(f.exists())
        assertEquals(8, c.int("log_max_files"))
        c.set("lyrics_alsong", false)
        c.set("log_max_size_kb", 64)
        val c2 = ConfigTxt(f)
        assertFalse(c2.bool("lyrics_alsong"))
        assertEquals(64, c2.int("log_max_size_kb"))
        assertTrue(c2.bool("lyrics_lrclib"))
    }
}
