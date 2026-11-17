package com.ascen.yamp.domain

import com.ascen.yamp.core.ConfigTxt
import com.ascen.yamp.lyrics.LyricLines
import com.ascen.yamp.lyrics.Lrc
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File
import java.nio.file.Files
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit

/** vr0.1.0.010: V2 파일별 이어 듣기 · 대기열 순서 바꾸기(A14) · 오류 건너뛰기(서비스) · 가사 구간(A11) · 위젯/플로팅 줄 · config 비동기 쓰기(A13) */
class VoiceTest {
    private val H = 60 * 60_000L

    @Test fun resumeBookRules() {
        val b = ResumeBook()
        assertFalse(b.put("short", 10 * 60_000, 20 * 60_000))     // 30분 이하 = 기억 안 함
        assertNull(b.get("short"))
        assertTrue(b.put("book", 12 * 60_000, H))
        assertEquals(12 * 60_000L, b.resumeAt("book", H))
        assertNull(b.resumeAt("book", 20 * 60_000))                // 길이가 짧게 보이면 이동 안 함
        assertFalse(b.put("book", 12 * 60_000, H))                 // 같은 값 → 바뀜 없음
        assertTrue(b.put("book", H - 5_000, H))                    // 끝 10초 안 = 다 들음 → 지움
        assertNull(b.get("book"))
        b.put("x", 3_000, H)                                       // 앞 5초 안 = 기억할 것 없음
        assertNull(b.get("x"))
        b.put("y", 40 * 60_000, H)
        assertNull(b.resumeAt("y", 40 * 60_000 + 9_000))           // 저장 위치가 (새) 끝 10초 안 → 처음부터
        assertNull(b.get("y"))
    }

    @Test fun resumeBookLruAndText() {
        val b = ResumeBook(maxEntries = 3)
        b.put("a", 60_000, H); b.put("b", 60_000, H); b.put("c", 60_000, H)
        b.resumeAt("a", H)                                         // a 를 최근으로
        b.put("d", 60_000, H)                                      // 가장 오래 안 쓴 b 가 빠짐
        assertNull(b.get("b"))
        assertEquals(3, b.size())
        val c = ResumeBook(maxEntries = 3)
        c.load(b.toText() + "\n잘못된 줄\n")
        assertEquals(b.toText(), c.toText())
        assertEquals(ResumeBook.MAX_ENTRIES, ResumeBook().maxEntries)
        assertEquals(200, ResumeBook.MAX_ENTRIES)
    }

    @Test fun queuedAfterReorder() {
        // 목록 0..7, 현재 2, 대기열 3·4
        assertEquals(2 to 1, PlayMath.queuedAfterReorder(2, 2, 3, 6, 8))   // 대기열 곡을 밖으로 → 하나 줄어듦
        assertEquals(2 to 3, PlayMath.queuedAfterReorder(2, 2, 6, 3, 8))   // 밖의 곡을 대기열 안으로 → 하나 늘어남
        assertEquals(2 to 2, PlayMath.queuedAfterReorder(2, 2, 6, 5, 8))   // 대기열 끝 바로 뒤 = 대기열 아님
        assertEquals(2 to 2, PlayMath.queuedAfterReorder(2, 2, 4, 3, 8))   // 대기열 안에서 순서만
        assertEquals(1 to 3, PlayMath.queuedAfterReorder(2, 2, 0, 3, 8))   // 앞의 곡을 대기열로 (현재 곡이 당겨짐)
        assertEquals(3 to 2, PlayMath.queuedAfterReorder(2, 2, 7, 0, 8))   // 뒤의 곡을 맨 앞으로 (현재 곡이 밀림)
        assertEquals(4 to 0, PlayMath.queuedAfterReorder(2, 2, 2, 4, 8))   // 현재 곡을 대기열 뒤로 → 남는 대기열 없음
        assertEquals(0 to 0, PlayMath.queuedAfterReorder(2, 2, 2, 0, 8))   // 현재 곡을 맨 앞으로 → 바로 뒤가 대기열 곡이 아님
        assertEquals(-1 to 0, PlayMath.queuedAfterReorder(-1, 0, 1, 2, 8))
        assertEquals(2 to 2, PlayMath.queuedAfterReorder(2, 2, 1, 1, 8))
    }

    @Test fun errorSkipOnService() {
        // 5곡 목록: 연속 오류 4번까지 건너뛰고 5번째에 멈춤 (곡 수만큼)
        var n = 0
        val acts = ArrayList<ErrorSkip.Action>()
        repeat(5) { val d = ErrorSkip.onError(n, 5, true); n = d.count; acts.add(d.action) }
        assertEquals(List(4) { ErrorSkip.Action.SKIP } + ErrorSkip.Action.STOP, acts)
        assertEquals(0, n)                                           // 멈춘 뒤 0 부터 다시
        assertEquals(ErrorSkip.Decision(ErrorSkip.Action.NONE, 1), ErrorSkip.onError(0, 5, false))   // 마지막 곡 (반복 끔)
        assertEquals(ErrorSkip.Action.STOP, ErrorSkip.onError(0, 1, true).action)                    // 1곡 목록
        n = 0
        var skips = 0
        while (true) { val d = ErrorSkip.onError(n, 100, true); n = d.count; if (d.action == ErrorSkip.Action.SKIP) skips++ else break }
        assertEquals(ErrorSkip.MAX_IN_ROW - 1, skips)               // 큰 목록은 최대 10번째 오류에서 멈춤
    }

    @Test fun lyricsSliceForCue() {
        val ly = Lrc.parse("[00:10.00]a\n[01:00.00]b\n[02:00.00]c\n[03:00.00]d\n")
        val s = ly.slice(90_000, 180_000)          // 1:30 ~ 3:00
        assertEquals(listOf(0L, 30_000L), s.blocks.map { it.tMs })
        assertEquals(listOf("b", "c"), s.blocks.map { it.lines[0] })
        val s2 = ly.slice(60_000, -1)              // 시작 시각에 줄이 있으면 앞 줄을 가져오지 않음
        assertEquals(listOf(0L, 60_000L, 120_000L), s2.blocks.map { it.tMs })
        val plain = Lrc.parse("가사\n둘")
        assertEquals(plain, plain.slice(1000, 2000))
    }

    @Test fun lyricLinesForWidget() {
        val ly = Lrc.parse("[00:01.00]원문\n[00:01.00]발음\n[00:01.00]번역\n[00:05.00]다음\n")
        assertEquals("원문 / 발음 / 번역" to "다음", LyricLines.of(ly, 0, true, true))
        assertEquals("원문" to "다음", LyricLines.of(ly, 0, false, false))
        assertEquals("♪" to "원문", LyricLines.of(ly, -1, true, true))
        assertEquals("" to "", LyricLines.of(null, 0, true, true))
        assertEquals(LyricLines.UNSYNCED to "", LyricLines.of(Lrc.parse("plain"), 0, true, true))
    }

    @Test fun configAsyncWriteAndNewKeys() {
        val f = File(Files.createTempDirectory("ump").toFile(), "config.txt")
        val ex = Executors.newSingleThreadExecutor()
        val c = ConfigTxt(f, ex)
        assertFalse(c.bool("skip_silence"))
        assertTrue(c.bool("resume_long"))
        c.set("skip_silence", true)
        c.set("resume_long", false)
        assertTrue(c.bool("skip_silence"))                         // 값은 바로
        ex.shutdown()
        assertTrue(ex.awaitTermination(5, TimeUnit.SECONDS))
        val c2 = ConfigTxt(f)
        assertTrue(c2.bool("skip_silence"))
        assertFalse(c2.bool("resume_long"))
        assertTrue(c2.warnings.isEmpty())
    }
}
