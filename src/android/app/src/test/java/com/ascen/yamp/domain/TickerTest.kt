package com.ascen.yamp.domain

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test
import java.io.File

/** vr0.1.0.012 (f23): 업비트 시세 · KST — PC tests 와 같은 벡터 (testdata/upbit_ticker_cases.txt · upbit_ticker_sample.json) */
class TickerTest {
    private fun find(rel: String): File {
        var d: File? = File("").absoluteFile
        while (d != null) {
            val f = File(d, rel)
            if (f.exists()) return f
            d = d.parentFile
        }
        error("$rel 를 찾을 수 없음")
    }

    private fun cases(): List<List<String>> = find("testdata/upbit_ticker_cases.txt").readLines(Charsets.UTF_8)
        .filter { it.isNotBlank() && !it.startsWith("#") }.map { it.split("|") }

    @Test fun sharedVectors() {
        val all = cases()
        assertTrue(all.size >= 40)
        val bad = mutableListOf<String>()
        val kinds = HashSet<String>()
        for (c in all) {
            kinds += c[0]
            val (got, want) = when (c[0]) {
                "price" -> Ticker.fmtPrice(c[1].toDouble()) to c[2]
                "rate" -> Ticker.fmtRate(c[1], c[2].toDouble()) to c[3]
                "cp" -> Ticker.fmtChangePrice(c[1].toDouble(), c[2].toDouble()) to c[3]
                "won" -> Ticker.fmtWonBig(c[1].toDouble()) to c[2]
                "kst" -> Ticker.kstLabel(c[1].toLong(), c[2] == "1", c[3] == "1") to c[4]
                "interval" -> Ticker.nextInterval(c[1].toInt(), c[2].toInt()).toString() to c[3]
                "markets" -> Ticker.parseMarkets(c[1]).joinToString(";") to c[2]
                else -> { fail("모르는 종류 ${c[0]}"); continue }
            }
            if (got != want) bad += "${c.joinToString("|")} → $got"
        }
        assertEquals(emptyList<String>(), bad)
        assertEquals(setOf("price", "rate", "cp", "won", "kst", "interval", "markets"), kinds)
    }

    @Test fun parseSample() {
        val q = Ticker.parseUpbit(find("testdata/upbit_ticker_sample.json").readText(Charsets.UTF_8)).single()
        assertEquals("KRW-XRP", q.market)
        assertEquals("XRP", q.symbol)
        assertEquals(3512.0, q.price, 0.0)
        assertEquals("RISE", q.change)
        assertEquals(43.0, q.changePrice, 0.0)
        assertEquals(0.0123955030, q.changeRate, 0.0)
        assertEquals(3540.0, q.high, 0.0)
        assertEquals(3455.0, q.low, 0.0)
        assertEquals(1234567890123.4, q.value24h, 0.0)
        assertEquals(1794218167000L, q.tsMs)
        assertEquals("₩3,512", Ticker.fmtPrice(q.price))
        assertEquals("▲1.24%", Ticker.fmtRate(q.change, q.changeRate))
        assertEquals("+43", Ticker.fmtChangePrice(q.changePrice, q.price))
        assertEquals("1.2조원", Ticker.fmtWonBig(q.value24h))
    }

    @Test fun parseErrorsAndMissing() {
        try { Ticker.parseUpbit("""{"error":{"name":404,"message":"Code not found"}}"""); fail() } catch (e: IllegalArgumentException) {
            assertTrue(e.message!!.contains("Code not found"))
        }
        try { Ticker.parseUpbit("<html>"); fail() } catch (_: IllegalArgumentException) {}
        assertEquals(emptyList<Quote>(), Ticker.parseUpbit("[]"))
        // 빠진 값 · null → 0 / EVEN, trade_timestamp 없으면 timestamp
        val q = Ticker.parseUpbit("""[{"market":"KRW-BTC","trade_price":null,"timestamp":1000}]""").single()
        assertEquals(Quote("KRW-BTC", 0.0, "EVEN", tsMs = 1000), q)
        val two = Ticker.parseUpbit("""[{"market":"KRW-XRP","trade_price":1},{"market":"KRW-BTC","trade_price":2}]""")
        assertEquals(listOf("KRW-XRP", "KRW-BTC"), two.map { it.market })
    }

    @Test fun detailTextLikePcTooltip() {
        val q = Quote("KRW-XRP", 3512.0, "RISE", 43.0, 0.0123955030, 3540.0, 3455.0, 1234567890123.4, 1794218167000)
        assertEquals(
            "업비트 KRW-XRP · 현재가 3,512원\n전일 대비 +43원 (▲1.24%)\n고가 3,540 · 저가 3,455 · 24시간 거래대금 1.2조원\n" +
                "마지막 갱신 18:56:07 KST\n업비트 시세 · 정보 표시용 (지연 가능) · 누르면 업비트 화면",
            Ticker.detail(q, 1794218167000))
        val t = Ticker.detail(q, 0, "인터넷 없음", skewS = 45)
        assertTrue(t.contains("아직 갱신 전\n갱신 실패 (인터넷 없음)\n기기 시계가 45초 빠름"))
        assertTrue(Ticker.detail(q, 0, skewS = -31).contains("기기 시계가 31초 느림"))
        assertTrue(!Ticker.detail(q, 0, skewS = 30).contains("기기 시계"))
    }

    @Test fun clockSkewAndUrl() {
        assertEquals(0, Ticker.clockSkewS(0, 123456))
        assertEquals(40, Ticker.clockSkewS(1_000_000, 1_040_000))
        assertEquals(-40, Ticker.clockSkewS(1_040_000, 1_000_000))
        assertEquals(2, Ticker.clockSkewS(0 + 1, 2501))      // 2.5 → 2 (Python round = 짝수 반올림)
        assertEquals("https://upbit.com/exchange?code=CRIX.UPBIT.KRW-XRP", Ticker.exchangeUrl("KRW-XRP"))
        // KST 는 기기 시간대와 상관없음
        val old = java.util.TimeZone.getDefault()
        try {
            java.util.TimeZone.setDefault(java.util.TimeZone.getTimeZone("America/Los_Angeles"))
            assertEquals("11-09(월) 18:56:07 KST", Ticker.kstLabel(1794218167000))
        } finally { java.util.TimeZone.setDefault(old) }
    }

    @Test fun encodeDecode() {
        val q = Quote("KRW-XRP", 3512.5, "FALL", -12.5, -0.0035, 3540.0, 3455.0, 1.5e12, 1794218167000)
        assertEquals(q, Ticker.decode(Ticker.encode(q)))
        assertNull(Ticker.decode(null))
        assertNull(Ticker.decode(""))
        assertNull(Ticker.decode("KRW-XRP|x|RISE|0|0|0|0|0|0"))
    }
}
