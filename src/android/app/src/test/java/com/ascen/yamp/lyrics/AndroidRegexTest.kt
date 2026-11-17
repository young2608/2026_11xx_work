package com.ascen.yamp.lyrics

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/**
 * vr0.1.0.013 — 앱 종료 원인 재발 방지: Android(ICU) 정규식은 Pattern.UNICODE_CHARACTER_CLASS 등 일부 플래그를 받지 않음
 *   (JVM 테스트는 통과해도 기기에서 IllegalArgumentException → 클래스 초기화 오류 → 앱 종료)
 */
class AndroidRegexTest {
    @Test fun reFallsBackInsteadOfThrowing() {
        val bad = Query.re("a", 0x40000000)                     // 어떤 엔진도 모르는 플래그 → 예외 대신 '아무것도 안 맞음'
        assertFalse(bad.containsMatchIn("a"))
        assertTrue(Query.re("\\s+", java.util.regex.Pattern.UNICODE_CHARACTER_CLASS).containsMatchIn("a b"))
    }

    @Test fun onlyQueryReUsesUnicodeCharacterClass() {
        val src = File(System.getProperty("user.dir") ?: ".").let { d ->
            listOf(d, d.parentFile, d.parentFile?.parentFile).firstNotNullOfOrNull { b ->
                b?.let { File(it, "app/src/main/java").takeIf { f -> f.isDirectory } ?: File(it, "android/app/src/main/java").takeIf { f -> f.isDirectory } }
            }
        } ?: return
        val bad = src.walkTopDown().filter { it.extension == "kt" }.flatMap { f ->
            f.readLines().mapIndexedNotNull { i, l ->
                if (("Pattern.compile(" in l && "UNICODE_CHARACTER_CLASS" in l && ".inv()" !in l) || "Pattern.CANON_EQ" in l) "${f.name}:${i + 1}" else null
            }
        }.toList()
        assertEquals("UNICODE_CHARACTER_CLASS/CANON_EQ 는 Query.re 로만: $bad", emptyList<String>(), bad)
    }

    @Test fun normStillWorks() {
        assertEquals("좋은날", Score.norm(" 좋은 날! "))
        assertEquals("ab", Score.norm("a{&}b$#%"))
    }
}
