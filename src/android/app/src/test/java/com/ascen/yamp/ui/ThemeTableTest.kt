package com.ascen.yamp.ui

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File
import kotlin.math.pow

/** vr0.1.0.011 (f19): 테마 색 표 = testdata/themes.txt · 대비 규칙 (WCAG) · 화면 코드에 고정 색 없음 · D2/D3 규칙 */
class ThemeTableTest {
    private fun find(rel: String): File {
        var d: File? = File("").absoluteFile
        while (d != null) {
            val f = File(d, rel)
            if (f.exists()) return f
            d = d.parentFile
        }
        error("$rel 를 찾을 수 없음")
    }

    private fun rows(name: String): List<List<String>> = find("testdata/$name").readLines(Charsets.UTF_8)
        .map { it.trim() }.filter { it.isNotEmpty() && !it.startsWith("#") }.map { it.split("|") }

    // ------------------------------------------------------------ WCAG 2.x 대비
    private fun lum(hex: String): Double {
        val v = ThemeTable.argb(hex)
        fun ch(shift: Int): Double {
            val c = ((v shr shift) and 0xFF) / 255.0
            return if (c <= 0.03928) c / 12.92 else ((c + 0.055) / 1.055).pow(2.4)
        }
        return 0.2126 * ch(16) + 0.7152 * ch(8) + 0.0722 * ch(0)
    }

    private fun contrast(a: String, b: String): Double {
        val x = lum(a)
        val y = lum(b)
        return (maxOf(x, y) + 0.05) / (minOf(x, y) + 0.05)
    }

    @Test fun contrastFormulaKnownValues() {
        assertEquals(21.0, contrast("#000000", "#FFFFFF"), 1e-9)
        assertEquals(1.0, contrast("#C2410C", "#C2410C"), 1e-9)
        assertEquals(5.18, contrast("#C2410C", "#FFFFFF"), 0.02)
    }

    // ------------------------------------------------------------ 공용 표와 같은지
    @Test fun tableEqualsTestdata() {
        val file = rows("themes.txt")
        val expected = file.map { Triple(it[0], it[1], it[2]) }
        val actual = ThemeTable.THEMES.flatMap { t ->
            listOf(Triple(t.name, "label", t.label), Triple(t.name, "dark", if (t.dark) "1" else "0")) +
                t.tokens.map { (k, v) -> Triple(t.name, k, v) } + Triple(t.name, "bands", t.bands.joinToString(","))
        }
        assertEquals(expected, actual)
        assertEquals(listOf("sunny", "clean_blue", "mint", "cherry", "night_sunny", "neon", "dark", "classic") +
            (1..5).map { "light$it" } + (1..5).map { "dark$it" }, ThemeTable.THEMES.map { it.name })
    }

    @Test fun everyThemeHasAllTokensAndBands() {
        val header = find("testdata/themes.txt").readLines(Charsets.UTF_8).first { it.startsWith("# 토큰:") }
        assertEquals(header.removePrefix("# 토큰:").trim().split(" "), ThemeTable.TOKENS)
        ThemeTable.THEMES.forEach { t ->
            assertEquals(t.name, ThemeTable.TOKENS, t.tokens.keys.toList())
            assertEquals(t.name, 11, t.bands.size)
            (t.tokens.values + t.bands).forEach { assertTrue("${t.name} $it", Regex("#[0-9A-F]{6}").matches(it)) }
        }
    }

    @Test fun contrastRulesPassForEveryTheme() {
        val rules = rows("theme_contrast.txt")
        assertTrue(rules.size >= 10)
        val bad = mutableListOf<String>()
        ThemeTable.THEMES.forEach { t ->
            rules.forEach { (fg, bg, min) ->
                val c = contrast(t.hex(fg), t.hex(bg))
                if (c < min.toDouble()) bad += "${t.name} $fg/$bg = ${"%.2f".format(c)} < $min"
            }
        }
        assertEquals(emptyList<String>(), bad)
    }

    @Test fun argbParsesHex() {
        assertEquals(0xFFC2410C.toInt(), ThemeTable.argb("#C2410C"))
        assertEquals(0x80FFFFFF.toInt(), ThemeTable.argb("#ffffff", 128))
        assertEquals(0xFFFFC72C.toInt(), ThemeTable.of("sunny").argb("fill1"))
    }

    // ------------------------------------------------------------ 이름 · D3 어두운 모드 따라가기 · D2 이전
    @Test fun namesAndLegacy() {
        assertEquals("sunny", ThemeTable.DEFAULT)
        assertEquals("clean_blue", ThemeTable.of("light").name)
        assertEquals("sunny", ThemeTable.of("없는테마").name)
        assertEquals("neon", ThemeTable.of("neon").name)
        assertEquals("써니", ThemeTable.of("sunny").label)
        assertFalse(ThemeTable.of("sunny").dark)
        assertTrue(ThemeTable.of("night_sunny").dark)
    }

    @Test fun followSystemDark() {
        assertEquals("sunny", ThemeTable.effective("sunny", followSystemDark = false, systemDark = true))
        assertEquals("sunny", ThemeTable.effective("sunny", followSystemDark = true, systemDark = false))
        assertEquals("night_sunny", ThemeTable.effective("sunny", followSystemDark = true, systemDark = true))
        for (n in listOf("clean_blue", "mint", "cherry", "light")) assertEquals(n, "dark", ThemeTable.effective(n, true, true))
        for (i in 1..5) {                                   // v024: 라이트 n단계 ↔ 다크 n단계
            assertEquals("dark$i", ThemeTable.effective("light$i", true, true))
            assertEquals("dark$i", ThemeTable.effective("dark$i", true, true))
            assertEquals("light$i", ThemeTable.effective("light$i", true, false))
        }
        for (n in listOf("night_sunny", "neon", "dark", "classic")) assertEquals(n, n, ThemeTable.effective(n, true, true))
        assertEquals("clean_blue", ThemeTable.effective("light", true, false))
    }

    @Test fun migrationD2() {
        val first = ThemeTable.migrate("neon", migrated = false)
        assertEquals("sunny", first.theme)
        assertEquals(ThemeTable.MIGRATE_TOAST, first.toast)
        assertTrue(first.toast!!.contains("네온"))
        // 이미 한 번 함 → 네온 다시 고른 사람은 그대로
        assertEquals(ThemeTable.Migration("neon", null), ThemeTable.migrate("neon", migrated = true))
        // 다른 테마를 고른 적 있으면 유지, 옛 light → clean_blue (알림 없음)
        assertEquals(ThemeTable.Migration("dark", null), ThemeTable.migrate("dark", migrated = false))
        assertEquals(ThemeTable.Migration("clean_blue", null), ThemeTable.migrate("light", migrated = false))
        assertEquals(ThemeTable.Migration("clean_blue", null), ThemeTable.migrate("light", migrated = true))
        assertEquals(ThemeTable.Migration("sunny", null), ThemeTable.migrate("sunny", migrated = false))
    }

    // ------------------------------------------------------------ 화면 코드에 고정 색 없음 (T4)
    @Test fun noHardcodedColorsInUi() {
        val dir = find("app/src/main/java/com/ascen/yamp/ui").takeIf { it.isDirectory }
            ?: find("src/main/java/com/ascen/yamp/ui")
        val files = dir.listFiles { f -> f.name.endsWith(".kt") }!!.filter { it.name !in setOf("Theme.kt", "ThemeTable.kt") }
        assertTrue(files.size > 10)
        val pat = Regex("""\bNeon\.|Color\(\s*0x|parseColor|Color\.(Black|White|Red|Green|Blue|Yellow|Gray|DarkGray|LightGray|Cyan|Magenta)\b""")
        val bad = files.flatMap { f ->
            f.readLines().mapIndexedNotNull { i, ln ->
                // Icons.kt: 벡터 아이콘 모양용 검정 (tint 로 칠해짐)
                if (f.name == "Icons.kt" && ln.contains("SolidColor(Color.Black)")) null
                else if (pat.containsMatchIn(ln)) "${f.name}:${i + 1}: ${ln.trim()}" else null
            }
        }
        assertEquals(emptyList<String>(), bad)
    }

    @Test fun noNeonObjectLeft() {
        val theme = find("src/main/java/com/ascen/yamp/ui/Theme.kt").readText()
        assertFalse(theme.contains("object Neon"))
        assertNull(Regex("""Color\(\s*0x""").find(theme))
    }
}
