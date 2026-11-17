package com.ascen.yamp.lyrics

/**
 * LRC 파서 (순수 Kotlin — JVM 단위 테스트 대상). PC yamp/lyrics/lrc.py 와 같은 규칙.
 * - [mm:ss.xx] [mm:ss.xxx] [mm:ss:xx] [mm:ss], 한 줄 여러 타임스탬프
 * - [offset:+500] → 500ms 빨리
 * - 같은 시각의 여러 줄 = 한 블록 (원문/발음/번역)
 * - vr0.1.0.011 (f18 L9): 단어 시각 <mm:ss.xx> 는 표시 글에서 지움 (A2 확장 LRC)
 */
data class LrcBlock(val tMs: Long, val lines: List<String>)

data class Lyrics(
    val blocks: List<LrcBlock>,
    val synced: Boolean,
    val source: String = "",
    val meta: Map<String, String> = emptyMap(),
) {
    private val times: LongArray = LongArray(blocks.size) { blocks[it].tMs }

    /** posMs 에 표시할 블록 (첫 줄 이전 -1) */
    fun indexAt(posMs: Long): Int {
        if (!synced || blocks.isEmpty()) return -1
        var lo = 0
        var hi = times.size - 1
        var ans = -1
        while (lo <= hi) {
            val mid = (lo + hi) ushr 1
            if (times[mid] <= posMs) { ans = mid; lo = mid + 1 } else hi = mid - 1
        }
        return ans
    }

    fun isEmpty(): Boolean = blocks.none { b -> b.lines.any { it.isNotBlank() } }

    /**
     * 구간 잘라 쓰기 (vr0.1.0.010, A11): CUE 트랙이 앨범 전체 .lrc 를 읽을 때 그 트랙 구간 [startMs, endMs) 만, 시각은 구간 시작 기준.
     *   구간 시작 전에 이미 보이던 줄(시작 시각에 줄이 없으면)은 0ms 로 가져옴. endMs < 0 = 끝까지. 싱크 없는 가사는 그대로
     */
    fun slice(startMs: Long, endMs: Long): Lyrics {
        if (!synced || (startMs <= 0 && endMs < 0)) return this
        val s = maxOf(0L, startMs)
        val out = ArrayList<LrcBlock>()
        val before = blocks.lastOrNull { it.tMs < s }
        if (before != null && blocks.none { it.tMs == s }) out.add(LrcBlock(0, before.lines))
        for (b in blocks) if (b.tMs >= s && (endMs < 0 || b.tMs < endMs)) out.add(LrcBlock(b.tMs - s, b.lines))
        return copy(blocks = out)
    }

    fun toLrc(): String = buildString {
        for (b in blocks) for (l in b.lines) {
            if (synced) append(fmtTs(b.tMs))
            append(l).append('\n')
        }
    }
}

object Lrc {
    private val TS = Regex("""\[(\d{1,3}):(\d{1,2})(?:[.:](\d{1,3}))?]""")
    private val META = Regex("""^\[([a-zA-Z]+):(.*)]$""")
    /** 단어 시각 <mm:ss.xx> (L9) */
    private val WORD_TS = Regex("""\s*<\d{1,3}:\d{1,2}(?:[.:]\d{1,3})?>\s*""")

    /** 단어 시각 지우기: 앞뒤 공백은 한 칸으로 (단어 사이 공백 유지) */
    fun stripWordTimes(s: String): String {
        if (s.indexOf('<') < 0) return s
        return WORD_TS.replace(s) { m -> if (m.value.first().isWhitespace() || m.value.last().isWhitespace()) " " else "" }
            .replace(Regex(" {2,}"), " ").trim()
    }

    fun parse(text: String?, source: String = ""): Lyrics {
        val src = (text ?: "").replace("\r\n", "\n").replace('\r', '\n').removePrefix("﻿")
        val meta = HashMap<String, String>()
        data class T(val t: Long, val seq: Int, val body: String)
        val timed = ArrayList<T>()
        val plain = ArrayList<String>()
        var seq = 0
        for (raw in src.split('\n')) {
            val line = raw.trim()
            if (line.isEmpty()) { plain.add(""); continue }
            var pos = 0
            val stamps = ArrayList<Long>()
            while (true) {
                val m = TS.matchAt(line, pos) ?: break
                val (mm, ss, fr) = m.destructured
                stamps.add(mm.toLong() * 60000 + ss.toLong() * 1000 + fracMs(fr))
                pos = m.range.last + 1
            }
            if (stamps.isNotEmpty()) {
                val body = stripWordTimes(line.substring(pos).trim())
                for (t in stamps) timed.add(T(t, seq++, body))
                continue
            }
            val mm = META.find(line)
            if (mm != null) { meta[mm.groupValues[1].lowercase()] = mm.groupValues[2].trim(); continue }
            plain.add(line)
        }
        if (timed.isNotEmpty()) {
            val off = meta["offset"]?.replace("+", "")?.trim()?.toLongOrNull() ?: 0L
            timed.sortWith(compareBy<T>({ it.t }, { it.seq }))
            val blocks = ArrayList<LrcBlock>()
            val cur = ArrayList<String>()
            var curT = Long.MIN_VALUE
            for (x in timed) {
                val t = maxOf(0L, x.t - off)
                if (t == curT) {
                    if (x.body.isNotEmpty()) cur.add(x.body)
                } else {
                    if (curT != Long.MIN_VALUE) blocks.add(LrcBlock(curT, cur.toList()))
                    cur.clear()
                    if (x.body.isNotEmpty()) cur.add(x.body)
                    curT = t
                }
            }
            if (curT != Long.MIN_VALUE) blocks.add(LrcBlock(curT, cur.toList()))
            return Lyrics(blocks, true, source, meta)
        }
        while (plain.isNotEmpty() && plain.first().isEmpty()) plain.removeAt(0)
        while (plain.isNotEmpty() && plain.last().isEmpty()) plain.removeAt(plain.size - 1)
        return Lyrics(plain.map { LrcBlock(-1, listOf(it)) }, false, source, meta)
    }

    private fun fracMs(f: String): Long = if (f.isEmpty()) 0 else f.padEnd(3, '0').take(3).toLong()
}

fun fmtTs(ms: Long): String {
    val m = maxOf(0L, ms)
    return "[%02d:%02d.%02d]".format(m / 60000, m / 1000 % 60, m % 1000 / 10)
}
