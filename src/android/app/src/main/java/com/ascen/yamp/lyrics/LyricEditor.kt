package com.ascen.yamp.lyrics

/**
 * 가사 편집기 로직 (순수 Kotlin — JVM 테스트 대상). PC yamp/lyrics/editor.py 와 같은 동작.
 *
 * - 텍스트(줄) 불러오기: 기존 LRC 면 시각 유지, 일반 가사면 시각 없음(-1)
 * - stamp(pos): 현재 줄에 재생 위치를 찍고 다음 줄로 (빈 줄은 건너뜀)
 * - nudge(±ms): 선택 줄 시각 조정
 * - toLrc(): 시각 있는 줄만 [mm:ss.xx], 시각 없는 줄은 그대로 (일반 가사 줄)
 */
class LyricEditor(lines: List<EditLine> = emptyList()) {
    data class EditLine(var tMs: Long, var text: String)

    val lines: MutableList<EditLine> = lines.map { it.copy() }.toMutableList()
    var cur: Int = 0; private set

    companion object {
        fun fromLyrics(ly: Lyrics?): LyricEditor {
            val out = ArrayList<EditLine>()
            if (ly != null) for (b in ly.blocks) for (ln in b.lines.ifEmpty { listOf("") }) {
                out.add(EditLine(if (ly.synced) b.tMs else -1, ln))
            }
            return LyricEditor(out)
        }

        fun fromText(text: String?): LyricEditor = LyricEditor(splitLines(text).map { EditLine(-1, it) })

        private fun splitLines(text: String?): List<String> =
            (text ?: "").replace("\r\n", "\n").split('\n').map { it.trimEnd() }
    }

    /** 텍스트 수정 반영: 같은 순서의 줄은 기존 시각 유지 */
    fun setText(text: String) {
        val old = lines.toList()
        val new = splitLines(text)
        lines.clear()
        new.forEachIndexed { i, s -> lines.add(EditLine(if (i < old.size) old[i].tMs else -1, s)) }
        cur = minOf(cur, maxOf(0, lines.size - 1))
    }

    fun text(): String = lines.joinToString("\n") { it.text }

    fun select(i: Int) {
        if (lines.isNotEmpty()) cur = i.coerceIn(0, lines.size - 1)
    }

    /** 현재 줄에 시각 → 다음 (빈 줄은 건너뜀). 반환: 새 현재 줄 */
    fun stamp(posMs: Long): Int {
        if (lines.isEmpty()) return 0
        lines[cur].tMs = maxOf(0L, posMs)
        var i = cur + 1
        while (i < lines.size && lines[i].text.isBlank()) i++
        cur = minOf(i, lines.size - 1)
        return cur
    }

    fun nudge(deltaMs: Long, i: Int = cur) {
        if (i in lines.indices && lines[i].tMs >= 0) lines[i].tMs = maxOf(0L, lines[i].tMs + deltaMs)
    }

    fun clearTimes() {
        lines.forEach { it.tMs = -1 }
        cur = 0
    }

    fun stamped(): Int = lines.count { it.tMs >= 0 }

    fun toLrc(): String {
        val out = ArrayList<String>()
        for (l in lines) {
            if (l.tMs >= 0) out.add(fmtTs(l.tMs) + l.text)
            else if (l.text.isNotBlank()) out.add(l.text)
        }
        return out.joinToString("\n") + "\n"
    }
}

/**
 * 3단 가사 (A3): 블록의 0번째 = 원문, 1번째 = 발음, 2번째 = 번역.
 * 설정에 따라 숨김. 반환: (줄, 단계 0/1/2) — 3번째 이후 줄은 단계 2 와 같은 취급
 */
object LyricTiers {
    fun visible(lines: List<String>, showPron: Boolean, showTrans: Boolean): List<Pair<String, Int>> {
        if (lines.size < 2) return lines.map { it to 0 }
        val out = ArrayList<Pair<String, Int>>()
        lines.forEachIndexed { i, s ->
            val tier = minOf(i, 2)
            val keep = when (tier) { 0 -> true; 1 -> showPron; else -> showTrans }
            if (keep) out.add(s to tier)
        }
        return out
    }

    fun joined(lines: List<String>, showPron: Boolean, showTrans: Boolean, sep: String = " / "): String =
        visible(lines, showPron, showTrans).joinToString(sep) { it.first }
}

/**
 * 플로팅 가사 · 홈 위젯 용 (현재 줄, 다음 줄) — vr0.1.0.010 (A4): 재생 서비스 쪽(PlaybackTracker)에서 계산
 *   가사 없음 → ("", ""), 싱크 없음 → ("(싱크 없는 가사)", ""), 첫 줄 전 · 빈 줄 → "♪"
 */
object LyricLines {
    const val UNSYNCED = "(싱크 없는 가사)"

    fun of(ly: Lyrics?, index: Int, showPron: Boolean, showTrans: Boolean): Pair<String, String> {
        if (ly == null) return "" to ""
        if (!ly.synced) return UNSYNCED to ""
        val cur = ly.blocks.getOrNull(index)?.lines?.let { LyricTiers.joined(it, showPron, showTrans) }.orEmpty()
        val next = ly.blocks.getOrNull(index + 1)?.lines?.firstOrNull().orEmpty()
        return cur.ifEmpty { "♪" } to next
    }
}
