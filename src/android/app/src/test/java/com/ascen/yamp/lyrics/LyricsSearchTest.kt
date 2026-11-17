package com.ascen.yamp.lyrics

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/**
 * vr0.1.0.011 (f18): 검색어 변형 L2 · 점수 L3 (PC 공용 벡터) · 알송 L1 (testdata/alsong_*.xml, 실제 태그 이름)
 *   · LRCLIB L4 · 결정/사유 L5~L7 · 진단 L8 · 단어 시각 L9 · NetEase L10
 */
class LyricsSearchTest {
    private fun find(name: String): File {
        var d: File? = File("").absoluteFile
        while (d != null) {
            val f = File(d, "testdata/$name")
            if (f.exists()) return f
            d = d.parentFile
        }
        error("testdata/$name 를 찾을 수 없음")
    }

    private fun cases(name: String): List<String> =
        find(name).readLines(Charsets.UTF_8).filter { it.isNotEmpty() && !it.startsWith("#") }

    // ------------------------------------------------------------ L2 · L3 (PC 와 같은 결과)
    @Test fun queryCasesMatchPc() {
        val all = cases("lyrics_query_cases.txt")
        assertTrue(all.size >= 15)
        for (line in all) {
            val p = line.split('|')
            val k = p.indexOf("=>")
            assertEquals(line, 2, k)
            val exp = p.drop(3).chunked(2).map { it[0] to it[1] }
            assertEquals(line, exp, Query.variants(p[0], p[1]))
        }
    }

    @Test fun scoreCasesMatchPc() {
        val all = cases("lyrics_score_cases.txt")
        assertTrue(all.size >= 10)
        for (line in all) {
            val p = line.split('|')
            assertEquals(line, 10, p.size)
            val got = Score.score(p[0], p[1], p[2], p[3].toDouble(), p[4], p[5], p[6], p[7].replace("\\n", "\n"), p[8].toDouble())
            assertEquals(line, p[9].toInt(), got)
        }
    }

    @Test fun queryHelpers() {
        assertEquals("아이유" to "IU", Query.splitAlt("아이유 (IU)"))
        assertEquals("아이유", Query.mainArtist("아이유, 김창완"))
        assertEquals("A", Query.mainArtist("A x B"))
        assertEquals("Dynamite", Query.cleanTitle("01. Dynamite (Official MV)"))
        assertEquals(1.0, Score.dice("abc", "ABC"), 1e-9)
        assertEquals(0.0, Score.dice("", "a"), 1e-9)
    }

    // ------------------------------------------------------------ L1 알송
    private val xml = { n: String -> find(n).readText(Charsets.UTF_8) }

    @Test fun alsongResemble2RealTags() {
        val items = Alsong.parseSearch(xml("alsong_resemble2.xml"))
        assertEquals(2, items.size)
        val b = items[1]
        assertEquals("좋은 날", b.title); assertEquals("아이유", b.artist); assertEquals("Real", b.album); assertEquals("222", b.id)
        assertEquals("[00:01.00]어쩜\n[00:01.00]eojjeom\n[00:03.00]이렇게", b.lyric)
        assertEquals("", items[0].album)             // <strAlbumName /> 빈 태그
        assertTrue(Alsong.parseSearch(xml("alsong_empty.xml")).isEmpty())
        assertTrue(Alsong.tagNames(xml("alsong_resemble2.xml")).contains("ST_GET_RESEMBLELYRIC2_RETURN"))
    }

    @Test fun alsongListAndById() {
        val l = Alsong.parseList(xml("alsong_list2.xml"))
        assertEquals(listOf("9001", "9002"), l.map { it.id })
        assertEquals(233.0, l[1].durS, 1e-9)
        assertTrue(Alsong.parseSearch(xml("alsong_list2.xml")).isEmpty())    // 목록 항목에는 가사 없음
        assertEquals("[00:01.00]어쩜\n[00:03.00]이렇게", Alsong.parseLyric(xml("alsong_byid2.xml")))
        assertEquals("[00:01.00]어쩜\n[00:03.00]이렇게", Alsong.parseLyric(xml("alsong_lyric7.xml")))
    }

    @Test fun alsongRequestsAndEnc() {
        assertEquals(Alsong.ENC_BUILTIN, Alsong.encOf(""))
        assertEquals(Alsong.ENC_BUILTIN, Alsong.encOf("  "))
        assertEquals("", Alsong.encOf("off"))
        assertEquals("abc", Alsong.encOf(" abc "))
        assertTrue(Alsong.lyricRequest("m", "E").contains("<ns1:GetLyric7><ns1:encData>E</ns1:encData><ns1:stQuery><ns1:strChecksum>m</ns1:strChecksum><ns1:strVersion>3.46</ns1:strVersion>"))
        assertTrue(Alsong.listRequest("제목", "가수", 1, "E").contains(
            "<ns1:GetResembleLyricList2><ns1:encData>E</ns1:encData><ns1:title>제목</ns1:title><ns1:artist>가수</ns1:artist><ns1:pageNo>1</ns1:pageNo>"))
        assertTrue(Alsong.byIdRequest("9002", "E").contains("<ns1:GetLyricByID2><ns1:encData>E</ns1:encData><ns1:lyricID>9002</ns1:lyricID>"))
        val r = Alsong.req("GetLyric7", "x")
        assertEquals("application/soap+xml; charset=utf-8; action=\"ALSongWebServer/GetLyric7\"", r.headers["Content-Type"])
        assertEquals("gSOAP/2.7", r.headers["User-Agent"])
        assertEquals("POST", r.method)
    }

    @Test fun alsongCleanLyric() {
        assertEquals("a\nb\nc\nd & e", Alsong.cleanLyric("a&lt;br&gt;b&amp;lt;br&amp;gt;c<br/>d &amp;amp; e\r\n"))
        assertEquals("가", Alsong.cleanLyric("&#44032;"))
    }

    /** 요청 함수 이름 → 고정 응답 */
    private fun soap(map: Map<String, String?>, log: MutableList<String>): Transport = { r ->
        log.add(r.label)
        val b = map[r.label]
        if (b == null) HttpRes(-1, null, 0, 1, NetErr.OFFLINE, "연결 안 됨") else HttpRes(200, b, b.length, 1)
    }

    @Test fun alsongPipelineResemble2() {
        val log = ArrayList<String>()
        val rep = ProvReport("alsong")
        Alsong.lookup(TrackQuery("좋은 날", "아이유", "Real", 233.0), null, Alsong.ENC_BUILTIN, 55,
            soap(mapOf("GetResembleLyric2" to xml("alsong_resemble2.xml")), log), rep)
        assertEquals(listOf("GetResembleLyric2"), log)
        assertTrue(rep.completed)
        val b = rep.best()!!
        assertEquals("좋은 날", b.title)
        assertTrue(b.score >= 55)
    }

    @Test fun alsongPipelineList2ById() {
        val log = ArrayList<String>()
        val rep = ProvReport("alsong")
        Alsong.lookup(TrackQuery("좋은 날", "아이유", "Real", 233.0), null, "E", 55,
            soap(mapOf("GetResembleLyric2" to xml("alsong_empty.xml"), "GetResembleLyricList2" to xml("alsong_list2.xml"),
                "GetLyricByID2" to xml("alsong_byid2.xml")), log), rep)
        assertEquals(listOf("GetResembleLyric2", "GetResembleLyricList2", "GetLyricByID2"), log)
        val b = rep.best()!!
        assertEquals("ByID2", b.via)
        assertEquals(233.0, b.durS, 1e-9)
        assertTrue(b.score >= 55)
        assertTrue(rep.steps.any { it.method == "GetLyricByID2" && it.items == 1 })
    }

    @Test fun alsongPipelineMd5First() {
        val log = ArrayList<String>()
        val rep = ProvReport("alsong")
        Alsong.lookup(TrackQuery("x", "y"), "abc", "E", 55, soap(mapOf("GetLyric7" to xml("alsong_lyric7.xml")), log), rep)
        assertEquals(listOf("GetLyric7"), log)
        assertEquals(100, rep.best()!!.score)
        // GetLyric7 가사 없음 → GetLyric5 → 검색
        val log2 = ArrayList<String>()
        val rep2 = ProvReport("alsong")
        Alsong.lookup(TrackQuery("좋은 날", "아이유"), "abc", "E", 55, soap(mapOf("GetLyric7" to "<a/>", "GetLyric5" to "<a/>",
            "GetResembleLyric2" to xml("alsong_resemble2.xml")), log2), rep2)
        assertEquals(listOf("GetLyric7", "GetLyric5", "GetResembleLyric2"), log2)
        // encData off → GetLyric5 만
        val log3 = ArrayList<String>()
        Alsong.lookup(TrackQuery("a", ""), "abc", "", 55, soap(mapOf("GetLyric5" to "<a/>", "GetResembleLyric2" to "<a/>",
            "GetResembleLyricList2" to "<a/>"), log3), ProvReport("alsong"))
        assertEquals(listOf("GetLyric5", "GetResembleLyric2", "GetResembleLyricList2"), log3)
    }

    @Test fun alsongOfflineStops() {
        val log = ArrayList<String>()
        val rep = ProvReport("alsong")
        Alsong.lookup(TrackQuery("좋은 날 (Good Day)", "아이유"), null, "E", 55, soap(emptyMap(), log), rep)
        assertEquals(1, log.size)                       // 연결 안 됨 → 다음 요청 안 보냄
        assertEquals(NetErr.OFFLINE, rep.err)
        assertFalse(rep.completed)
    }

    // ------------------------------------------------------------ L4 LRCLIB
    private val lrcObj = """{"id":1,"trackName":"Love Dive","artistName":"IVE","albumName":"LOVE DIVE","duration":177.0,
        "instrumental":false,"plainLyrics":"a\nb","syncedLyrics":"[00:01.00]a\n[00:02.00]b"}"""

    @Test fun lrclibParse() {
        val c = Lrclib.parseGet(lrcObj)!!
        assertEquals("Love Dive", c.title); assertEquals(177.0, c.durS, 1e-9); assertTrue(c.synced)
        val l = Lrclib.parseSearch("[$lrcObj, {\"trackName\":\"x\",\"syncedLyrics\":null,\"plainLyrics\":null}]", "search")
        assertEquals(1, l.size)
        assertTrue(Lrclib.parseSearch("not json", "q").isEmpty())
        assertFalse(Lrclib.getUrl("t", "a", 177.4).contains("album"))
        assertTrue(Lrclib.getUrl("t", "a", 177.6).endsWith("&duration=177"))
        assertTrue(Lrclib.qUrl("Love Dive", "IVE").endsWith("q=IVE+Love+Dive"))
    }

    @Test fun lrclibPipeline() {
        val urls = ArrayList<String>()
        val http: Transport = { r ->
            urls.add(r.label)
            when (r.label) {
                "get" -> HttpRes(404, "{\"message\":\"x\"}", 10, 1)
                "search" -> HttpRes(200, "[]", 2, 1)
                else -> HttpRes(200, "[$lrcObj]", 100, 1)
            }
        }
        val rep = ProvReport("lrclib")
        Lrclib.lookup(TrackQuery("Love Dive", "IVE", "", 177.0), 55, http, rep, "ua")
        assertEquals(listOf("get", "search", "q"), urls)
        assertTrue(rep.completed)
        assertEquals(NetErr.NONE, rep.err)
        assertTrue(rep.best()!!.score >= 55)
    }

    // ------------------------------------------------------------ L10 NetEase
    @Test fun neteaseParseAndMerge() {
        val s = NetEase.parseSearch("""{"result":{"songs":[{"id":186016,"name":"晴天","artists":[{"name":"周杰伦"},{"name":"B"}],
            "album":{"name":"叶惠美"},"duration":269000}],"songCount":1},"code":200}""")
        assertEquals(1, s.size)
        assertEquals("186016", s[0].id); assertEquals("周杰伦, B", s[0].artist); assertEquals("叶惠美", s[0].album)
        assertEquals(269.0, s[0].durS, 1e-9)
        val body = """{"lrc":{"version":1,"lyric":"[00:01.00]原文\n[00:02.50]二\n{\"t\":0,\"c\":[]}\n"},
            "tlyric":{"version":1,"lyric":"[00:01.00]번역\n[00:02.50]\n"},"code":200}"""
        assertEquals("[00:01.00]原文\n[00:01.00]번역\n[00:02.50]二", NetEase.parseLyric(body))
        val ly = Lrc.parse(NetEase.parseLyric(body))
        assertEquals(listOf("原文", "번역"), ly.blocks[0].lines)
        assertEquals("", NetEase.parseLyric("{\"code\":200}"))
        assertTrue(NetEase.searchUrl("a b").contains("type=1&limit=10"))
        assertTrue(NetEase.lyricUrl("1").endsWith("id=1&lv=1&tv=-1"))
    }

    // ------------------------------------------------------------ L5~L7 결정 · 사유 · 실패 기억
    private fun rep(src: String, score: Int?, err: NetErr = NetErr.NONE, done: Boolean = true) = ProvReport(src).apply {
        if (score != null) add(LyricCand(src, "t", "a", "", "[00:01.00]x", score = score))
        this.err = err; completed = done
    }

    @Test fun decide() {
        var d = Lookup.decide(listOf(rep("alsong", 40), rep("lrclib", 80)), 55)
        assertEquals("lrclib", d.best!!.source)
        assertEquals("LRCLIB · 80점", d.state.chip())
        d = Lookup.decide(listOf(rep("alsong", 40), rep("lrclib", null)), 55)
        assertNull(d.best); assertEquals(Reason.LOW_SCORE, d.state.reason); assertTrue(d.rememberNotFound)
        d = Lookup.decide(listOf(rep("alsong", null), rep("lrclib", null)), 55)
        assertEquals(Reason.NOT_FOUND, d.state.reason); assertTrue(d.rememberNotFound)
        d = Lookup.decide(listOf(rep("alsong", null, NetErr.OFFLINE, false), rep("lrclib", null, NetErr.OFFLINE, false)), 55)
        assertEquals(Reason.OFFLINE, d.state.reason); assertFalse(d.rememberNotFound)
        d = Lookup.decide(listOf(rep("alsong", null, NetErr.SERVER), rep("lrclib", null)), 55)
        assertEquals(Reason.SERVER_ERROR, d.state.reason); assertEquals("alsong", d.state.source); assertFalse(d.rememberNotFound)
        assertTrue(d.state.line().startsWith("알송 서버 응답 오류"))
        d = Lookup.decide(listOf(rep("alsong", null), rep("lrclib", null, done = false)), 55, timedOut = true)
        assertEquals(Reason.TIMEOUT, d.state.reason); assertFalse(d.rememberNotFound)
        d = Lookup.decide(emptyList(), 55)
        assertEquals(Reason.NO_PROVIDER, d.state.reason)
        // 같은 점수 → 공급자 순서 (알송 먼저)
        assertEquals("alsong", Lookup.decide(listOf(rep("alsong", 70), rep("lrclib", 70)), 55).best!!.source)
        assertEquals(listOf(70, 70), Lookup.ranked(listOf(rep("alsong", 70), rep("lrclib", 70))).map { it.score })
    }

    @Test fun statesAndNotFound() {
        assertEquals("가사 없음 (3일 전 확인) · 다시 찾기", LyricsState(Reason.REMEMBERED_NOT_FOUND, days = 3).line())
        assertTrue(LyricsState(Reason.REMEMBERED_NOT_FOUND).notFound)
        assertFalse(LyricsState(Reason.FOUND, "alsong", 92).notFound)
        assertEquals("알송 · 92점", LyricsState(Reason.FOUND, "alsong", 92).chip())
        assertEquals("직접 편집", LyricsState(Reason.FOUND, "user").chip())
        assertNull(LyricsState(Reason.NOT_FOUND).chip())
        val day = NotFound.DAY_MS
        assertTrue(NotFound.active(10 * day, 5 * day, 7))
        assertFalse(NotFound.active(13 * day, 5 * day, 7))
        assertFalse(NotFound.active(10 * day, 5 * day, 0))
        assertFalse(NotFound.active(10 * day, 0, 7))
        assertEquals(5, NotFound.daysAgo(10 * day + 5, 5 * day))
    }

    // ------------------------------------------------------------ L8 진단
    @Test fun diagReport() {
        val reps = listOf(rep("alsong", 92).apply {
            step("GetResembleLyric2", "좋은 날 / 아이유", HttpRes(200, "x", 1234, 321), "ST_GET_RESEMBLELYRIC2_RETURN", 2)
        }, rep("lrclib", null, NetErr.TIMEOUT, false))
        val q = TrackQuery("좋은 날", "아이유", "Real", 233.0)
        val txt = Diag.report("yAmp test", q, listOf("파일" to "/x.mp3"), Query.variants(q.title, q.artist), reps,
            Lookup.decide(reps, 55), 55, 6, 999, false)
        for (k in listOf("가사 진단", "좋은 날 / 아이유", "HTTP 200", "1234B", "ST_GET_RESEMBLELYRIC2_RETURN", "92점", "[LRCLIB]", "TIMEOUT", "선택: 알송 92점"))
            assertTrue(k, txt.contains(k))
    }

    // ------------------------------------------------------------ L9 단어 시각
    @Test fun wordTimesStripped() {
        val ly = Lrc.parse("[00:01.00]<00:01.00>Hello<00:01.50> world <00:02.00>again\n[00:03.00]<00:03.10>하나 <00:03.50>둘")
        assertEquals(listOf("Hello world again"), ly.blocks[0].lines)
        assertEquals(listOf("하나 둘"), ly.blocks[1].lines)
        assertEquals("a b", Lrc.stripWordTimes("a <01:02.345>b"))
        assertEquals("a <b>", Lrc.stripWordTimes("a <b>"))
    }

    // ------------------------------------------------------------ JSON
    @Test fun json() {
        val o = Json.obj(Json.parse("""{"a":[1,2.5,"x\"yé"],"b":{"c":null,"d":true},"e":-3e2}"""))!!
        assertEquals(listOf(1.0, 2.5, "x\"yé"), Json.arr(o["a"]))
        assertEquals("", Json.str(Json.obj(o["b"]), "c"))
        assertEquals("-300", Json.str(o, "e"))
        assertNotNull(Json.parse("[]"))
    }
}
