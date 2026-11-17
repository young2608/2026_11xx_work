package com.ascen.yamp.lyrics

import java.util.regex.Pattern
import kotlin.math.abs
import kotlin.math.floor

/**
 * 가사 후보 점수 (vr0.1.0.011, f18 L3) — 순수 Kotlin. PC yamp/lyrics/score.py 와 같은 식.
 * 공용 테스트: testdata/lyrics_score_cases.txt
 *
 *  제목 : 같음 45 · 포함 35 · 아니면 Dice 유사도 × 30 (floor(x+0.5))   — 검색 제목 이름들 중 최고
 *  가수 : 같음 30 · 포함 22 · 아니면 Dice × 18  (검색 가수가 비면 15)  — 가수 이름들 중 최고
 *  앨범 : 둘 다 있고 같음 10
 *  싱크 : 타임스탬프 1개 이상 +10, 10개 이상 +5
 *  길이 : 후보 길이 있음 → 차 ≤ 3초 +10, > 15초 −40 / 후보 길이 없음 + 싱크 → 마지막 시각 > 곡 길이 + 10초 −40
 */
object Score {
    const val MIN_SCORE = 55
    private val TS = Regex("""\[(\d{1,3}):(\d{1,2})(?:[.:](\d{1,3}))?]""")
    // vr0.1.0.013: Android(ICU) 에서도 되게 — 특수 문자는 모두 \ 로 (ICU 의 [] 안 & { } $ 같은 연산자 문제 방지),
    //   UNICODE_CHARACTER_CLASS 는 Android 에서 지원 안 함 → Query.re 가 빼고 다시 만듦 (앱 종료 원인 수정)
    private val NORM = Query.re("[\\s\\-_.,/\\\\()\\[\\]\\{\\}'\"`!?:;~\\^·\\&\\*\\+=\\|<>@#\\$%]+", Pattern.UNICODE_CHARACTER_CLASS)

    fun norm(s: String?): String = NORM.replace((s ?: "").lowercase(), "")

    private fun cps(s: String): IntArray = s.codePoints().toArray()

    fun dice(a0: String, b0: String): Double {
        val a = cps(norm(a0))
        val b = cps(norm(b0))
        if (a.isEmpty() || b.isEmpty()) return 0.0
        if (a.size < 2 || b.size < 2) return if (a.contentEquals(b)) 1.0 else 0.0
        val x = HashMap<Long, Int>()
        for (i in 0 until a.size - 1) { val k = (a[i].toLong() shl 32) or a[i + 1].toLong(); x[k] = (x[k] ?: 0) + 1 }
        var inter = 0
        for (i in 0 until b.size - 1) {
            val k = (b[i].toLong() shl 32) or b[i + 1].toLong()
            val c = x[k] ?: 0
            if (c > 0) { inter++; x[k] = c - 1 }
        }
        return 2.0 * inter / ((a.size - 1) + (b.size - 1))
    }

    private fun len(s: String) = s.codePointCount(0, s.length)

    private fun nameScore(cands: List<String>, value: String, eq: Int, contains: Int, sim: Int): Int {
        val v = norm(value)
        var best = 0
        for (c in cands) {
            val n = norm(c)
            if (n.isEmpty() || v.isEmpty()) continue
            val s = when {
                n == v -> eq
                (len(n) >= 2 && v.contains(n)) || (len(v) >= 2 && n.contains(v)) -> contains
                else -> floor(dice(n, v) * sim + 0.5).toInt()       // 반올림 (PC 와 같게)
            }
            best = maxOf(best, s)
        }
        return best
    }

    fun stamps(lyric: String?): List<Long> = TS.findAll(lyric ?: "").map { m ->
        val fr = m.groupValues[3].ifEmpty { "0" }
        m.groupValues[1].toLong() * 60000 + m.groupValues[2].toLong() * 1000 + fr.padEnd(3, '0').take(3).toLong()
    }.toList()

    fun score(qTitle: String, qArtist: String, qAlbum: String, qDurS: Double, cTitle: String, cArtist: String,
              cAlbum: String, cLyric: String, cDurS: Double = 0.0): Int {
        var s = nameScore(Query.titleNames(qTitle).ifEmpty { listOf(qTitle) }, cTitle, 45, 35, 30)
        val names = Query.artistNames(qArtist)
        s += if (names.isNotEmpty()) nameScore(names, cArtist, 30, 22, 18) else 15
        if (qAlbum.isNotEmpty() && cAlbum.isNotEmpty() && norm(qAlbum) == norm(cAlbum)) s += 10
        val ts = stamps(cLyric)
        if (ts.isNotEmpty()) s += 10 + if (ts.size >= 10) 5 else 0
        if (qDurS > 0) {
            if (cDurS > 0) {
                val d = abs(cDurS - qDurS)
                if (d <= 3) s += 10 else if (d > 15) s -= 40
            } else if (ts.isNotEmpty() && ts.max() / 1000.0 > qDurS + 10) s -= 40
        }
        return s
    }
}
