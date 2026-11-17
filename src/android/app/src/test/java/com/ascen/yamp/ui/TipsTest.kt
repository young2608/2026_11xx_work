package com.ascen.yamp.ui

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/**
 * vr0.1.0.009 (D7): 글자 없는 아이콘 버튼의 설명 표(Tips) 검사.
 *   - ui 폴더의 .kt 소스에서 쓰는 모든 tipKey 가 Tips.ALL 에 있어야 함 (없으면 팝업에 키 이름이 그대로 보임)
 *   - 모든 Tip 의 name · desc 는 비어 있지 않아야 함
 * 소스는 디스크에서 직접 읽음 (작업 폴더에서 위로 올라가며 src/main/java/com/ascen/yamp/ui 를 찾음)
 */
class TipsTest {
    private fun uiDir(): File {
        System.getProperty("yamp.uidir")?.let { p -> File(p).takeIf { it.isDirectory }?.let { return it } }
        var d: File? = File("").absoluteFile
        while (d != null) {
            for (rel in listOf("src/main/java/com/ascen/yamp/ui", "app/src/main/java/com/ascen/yamp/ui")) {
                val f = File(d, rel)
                if (f.isDirectory) return f
            }
            d = d.parentFile
        }
        error("ui 소스 폴더를 찾을 수 없음 (cwd=${File("").absolutePath})")
    }

    /** name( 뒤의 괄호 짝까지 (문자열 · 문자 리터럴 안의 괄호는 무시) — 인자 전체 글을 돌려줌 */
    private fun callArgs(src: String, open: Int): String {
        var depth = 0
        var i = open
        while (i < src.length) {
            val c = src[i]
            when {
                c == '"' -> {                         // 문자열 건너뛰기 ("""…""" 는 ui 명령 인자에 쓰지 않음)
                    i++
                    while (i < src.length && src[i] != '"') { if (src[i] == '\\') i++; i++ }
                }
                c == '\'' -> {
                    i++
                    while (i < src.length && src[i] != '\'') { if (src[i] == '\\') i++; i++ }
                }
                c == '(' -> depth++
                c == ')' -> { depth--; if (depth == 0) return src.substring(open + 1, i) }
            }
            i++
        }
        return src.substring(open + 1)
    }

    /** 괄호 깊이 0 인 부분만 남김 (안쪽 괄호 내용은 공백으로) — 문자열 안의 괄호는 무시 */
    private fun topLevel(args: String): String {
        val sb = StringBuilder()
        var depth = 0
        var i = 0
        while (i < args.length) {
            val c = args[i]
            if (c == '"') {
                val st = i
                i++
                while (i < args.length && args[i] != '"') { if (args[i] == '\\') i++; i++ }
                if (depth == 0) sb.append(args, st, minOf(i + 1, args.length)) else sb.append(' ')
            } else {
                if (c == '(') depth++
                if (depth == 0) sb.append(c) else sb.append(' ')
                if (c == ')') depth--
            }
            i++
        }
        return sb.toString()
    }

    private val keyLit = Regex("\"([a-z][a-z0-9_]*)\"")

    /** 소스 하나에서 쓰는 팁 키 모으기 */
    private fun keysIn(src: String): Set<String> {
        val out = linkedSetOf<String>()
        // 1) IconAction( / WideIconAction( / TipBox( / Tips.of( 호출 인자 안의 영문 소문자 문자열 리터럴
        //    (상태 문구 · 데이터는 한글/기호라 걸리지 않음). 선언(fun IconAction(...)) 은 제외
        for (m in Regex("(?<![A-Za-z_.])(IconAction|WideIconAction|TipBox|Tips\\.of)\\(").findAll(src)) {
            val before = src.substring(maxOf(0, m.range.first - 4), m.range.first)
            if (before.endsWith("fun ")) continue
            val args = callArgs(src, m.range.last)
            // 안쪽 호출 괄호 (예: { vm.play("x") }) 속 문자열은 빼고, 이 호출의 바로 인자 수준 문자열만
            //   (if (p) "pause" else "play" · when (m) { A -> "repeat_one" } 은 포함)
            keyLit.findAll(topLevel(args)).forEach { out += it.groupValues[1] }
        }
        // 2) tip = "x" / tipKey = "x" (NavItem 등)
        Regex("\\btip(Key)?\\s*=\\s*\"([a-z][a-z0-9_]*)\"").findAll(src).forEach { out += it.groupValues[2] }
        // 3) 도움말 목록: "x" to YIcons.y
        Regex("\"([a-z][a-z0-9_]*)\"\\s+to\\s+YIcons\\.").findAll(src).forEach { out += it.groupValues[1] }
        return out
    }

    @Test fun everyTipHasNameAndDesc() {
        assertTrue("Tips.ALL 이 너무 적음", Tips.ALL.size >= 40)
        for ((k, t) in Tips.ALL) {
            assertTrue("키 형식: $k", Regex("[a-z][a-z0-9_]*").matches(k))
            assertTrue("name 비어 있음: $k", t.name.isNotBlank())
            assertTrue("desc 비어 있음: $k", t.desc.isNotBlank())
        }
    }

    @Test fun everyReferencedKeyExists() {
        val files = uiDir().listFiles { f -> f.name.endsWith(".kt") && f.name != "Tips.kt" }.orEmpty().sortedBy { it.name }
        assertTrue("ui 소스가 없음", files.isNotEmpty())
        val used = linkedMapOf<String, MutableSet<String>>()     // 키 → 파일들
        for (f in files) keysIn(f.readText()).forEach { used.getOrPut(it) { linkedSetOf() } += f.name }
        val missing = used.filterKeys { it !in Tips.ALL }
        assertEquals("Tips.ALL 에 없는 키: $missing", emptyMap<String, Set<String>>(), missing)
        // 추출이 실제로 동작하는지 (0개면 정규식이 깨진 것)
        assertTrue("찾은 키가 너무 적음: ${used.keys}", used.size >= 40)
        for (k in listOf("play", "pause", "prev", "next", "shuffle", "repeat_off", "repeat_all", "repeat_one", "nav_play", "ed_stamp", "help"))
            assertTrue("코드에서 쓰는 키에 $k 가 없음", k in used)
    }

    @Test fun keyExtractionSamples() {
        val src = """
            IconAction(YIcons.play, "folder_play", { vm.play("not_a_key") }, framed = true)
            IconAction(when (m) { 1 -> YIcons.repeatOne; else -> YIcons.repeat }, when (m) { 1 -> "repeat_one"; else -> "repeat_all" }, f)
            IconAction(if (p) YIcons.pause else YIcons.play, if (p) "pause" else "play", vm::toggle, state = "켬")
            fun IconAction(icon: ImageVector, tipKey: String = "decl_skip") {}
            NavItem(tip = "nav_x", YIcons.list)
            val l = listOf("help_y" to YIcons.help)
        """
        assertEquals(setOf("folder_play", "repeat_one", "repeat_all", "pause", "play", "nav_x", "help_y"), keysIn(src))
    }
}
