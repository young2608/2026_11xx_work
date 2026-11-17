package com.ascen.yamp.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File
import java.nio.file.Files

class CrashReportTest {
    private fun boom(): Throwable = try {
        try { listOf<Int>()[1] } catch (e: Exception) { throw IllegalStateException("상단 바 실패", e) }
        error("unreachable")
    } catch (e: Throwable) { e }

    @Test fun fileNameAndKst() {
        assertEquals("crash_20261109_185607.txt", CrashReport.fileName(1794218167000L))
        assertEquals("2026-11-09 18:56:07 KST", CrashReport.kst(1794218167000L))
    }

    @Test fun summaryUsesRootCause() {
        val s = CrashReport.summary(boom())
        assertTrue(s, s.startsWith("IndexOutOfBoundsException") || s.startsWith("ArrayIndexOutOfBoundsException"))
        assertTrue(s, s.contains(" @ "))
    }

    @Test fun buildHasAllSections() {
        val env = CrashReport.Env("yMp3Player", "vr0.1.0.013", "2026-11-11 05:30", "samsung SM-S928N (e3q)", "15 (API 35)", "com.ascen.yamp")
        val r = CrashReport.build(env, "main", boom(), 1794218167000L, 1234, "log a\nlog b", "")
        for (k in listOf("비정상 종료 보고서", "시각     : 2026-11-09 18:56:07 KST  (시작 후 1.234초)", "버전     : vr0.1.0.013__2026-11-11 05:30",
                "기기     : samsung", "Android  : 15 (API 35)", "요약     : ", "---- 예외 (전체) ----", "Caused by:", "상단 바 실패",
                "---- 최근 앱 로그 ----", "log b", "(읽지 못함)")) assertTrue(k, r.contains(k))
    }

    @Test fun shareTruncates() {
        val long = "x".repeat(100_000)
        val s = CrashReport.forShare(long, 1000)
        assertTrue(s.length <= 1000 && s.endsWith("전체는 파일 참고)"))
        assertEquals("짧음", CrashReport.forShare("짧음"))
    }

    @Test fun streakAndSafeMode() {
        assertEquals(1, CrashReport.nextStreak(0, 3_000))
        assertEquals(2, CrashReport.nextStreak(1, 14_999))
        assertEquals(0, CrashReport.nextStreak(2, 60_000))
        assertFalse(CrashReport.suggestSafeMode(1))
        assertTrue(CrashReport.suggestSafeMode(2))
    }

    @Test fun listTrimAndTail() {
        val d = Files.createTempDirectory("crash").toFile()
        for (i in 10..24) File(d, "crash_202611${i}_000000.txt").writeText("r$i")
        File(d, "other.txt").writeText("x")
        assertEquals(15, CrashReport.list(d).size)
        assertEquals("crash_20261124_000000.txt", CrashReport.list(d).first().name)
        CrashReport.trim(d, 10)
        assertEquals(10, CrashReport.list(d).size)
        assertTrue(File(d, "other.txt").exists())
        val f = File(d, "log.txt"); f.writeText((1..10).joinToString("\n") { "줄$it" })
        assertEquals("줄9\n줄10", CrashReport.tail(f, 2))
        assertEquals("", CrashReport.tail(File(d, "없음"), 2))
    }
}
