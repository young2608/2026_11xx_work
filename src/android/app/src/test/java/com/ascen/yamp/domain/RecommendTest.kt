package com.ascen.yamp.domain

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File
import kotlin.random.Random

/**
 * PC tests 와 같은 공용 벡터 (00__build/src/testdata/recommend_cases.txt) → 양쪽 결과 일치 확인.
 * 파일 위치: 작업 폴더에서 위로 올라가며 testdata/recommend_cases.txt 탐색 (Gradle cwd = android/app)
 */
class RecommendTest {
    private fun findCases(): File {
        System.getProperty("yamp.testdata")?.let { p -> File(p).takeIf { it.exists() }?.let { return it } }
        var d: File? = File("").absoluteFile
        while (d != null) {
            val f = File(d, "testdata/recommend_cases.txt")
            if (f.exists()) return f
            d = d.parentFile
        }
        error("testdata/recommend_cases.txt 를 찾을 수 없음 (cwd=${File("").absolutePath})")
    }

    private class Cases {
        var now = 0L
        val tracks = ArrayList<TrackStat>()
        val co = HashMap<Pair<String, String>, Int>()
        val recent = ArrayList<String>()
        val expect = ArrayList<Pair<String, List<String>>>()
        val scores = ArrayList<Pair<String, String>>()
        val gains = ArrayList<List<String>>()
    }

    private fun load(): Cases {
        val c = Cases()
        for (raw in findCases().readLines(Charsets.UTF_8)) {
            if (raw.isBlank()) continue
            val sp = raw.indexOf(' ')
            val kind = raw.substring(0, sp)
            val rest = raw.substring(sp + 1)
            val p = rest.split('|')
            when (kind) {
                "NOW" -> c.now = rest.trim().toLong()
                "T" -> c.tracks.add(TrackStat(p[0], p[1], p[2], p[3], p[4], p[5] == "1", p[6].toInt(), p[7].toInt(),
                    p[8].toInt(), p[9].toLong(), p[10].toLong(), p[11].toInt(),
                    p.getOrElse(12) { "" }.split(',').filter { it.isNotEmpty() }))
                "CO" -> c.co[p[0] to p[1]] = p[2].toInt()
                "RECENT" -> c.recent.add(rest.trim())
                "EXPECT" -> c.expect.add(p[0] to p.getOrElse(1) { "" }.split(',').filter { it.isNotEmpty() })
                "SCORE" -> c.scores.add(p[0] to p[1])
                "GAIN" -> c.gains.add(p)
                else -> error("알 수 없는 줄: $raw")
            }
        }
        return c
    }

    @Test fun sharedVectors() {
        val c = load()
        assertTrue(c.tracks.size >= 10 && c.expect.isNotEmpty() && c.scores.isNotEmpty() && c.gains.isNotEmpty())
        val by = c.tracks.associateBy { it.key }
        for ((k, v) in c.scores) assertEquals("SCORE $k", v, "%.6f".format(java.util.Locale.ROOT, Recommend.score(by.getValue(k))))
        for ((name, keys) in c.expect) {
            val got = when {
                name == "daily" -> Recommend.daily(c.tracks, c.now)
                name == "favorites" -> Recommend.favorites(c.tracks)
                name == "rediscover" -> Recommend.rediscover(c.tracks, c.now)
                name == "recent" -> Recommend.recentAdded(c.tracks, 5)
                name.startsWith("similar:") -> Recommend.similar(c.tracks, name.substringAfter(':'), c.co, c.recent)
                name.startsWith("mood:") -> Recommend.mood(c.tracks, name.substringAfter(':'))
                else -> error("알 수 없는 EXPECT: $name")
            }
            assertEquals("EXPECT $name", keys, got)
        }
        for (g in c.gains) {
            val f = Recommend.gainFactor(Recommend.parseGain(g[0]), g[1].toDoubleOrNull(), g[2].toDouble())
            assertEquals("GAIN ${g[0]}", g[3], "%.6f".format(java.util.Locale.ROOT, f))
        }
    }

    @Test fun pythonRounding() {
        assertEquals(12, Recommend.pyRound(25 * 0.5))
        assertEquals(8, Recommend.pyRound(25 * 0.3))   // 7.5 → 8
        assertEquals(2, Recommend.pyRound(2.5))
        assertEquals(4, Recommend.pyRound(3.5))
    }

    @Test fun diversifyLimitsRuns() {
        val art = mapOf("a" to "X", "b" to "X", "c" to "X", "d" to "Y", "e" to "")
        assertEquals(listOf("a", "b", "d", "c", "e"), Recommend.diversify(listOf("a", "b", "c", "d", "e"), { art.getValue(it) }))
    }

    @Test fun randomizedKeepsMembership() {
        val c = load()
        val r = Random(7)
        val d = Recommend.daily(c.tracks, c.now, rng = r)
        assertEquals(d.size, d.toSet().size)
        val s = Recommend.similar(c.tracks, "a01", c.co, c.recent, rng = r)
        assertEquals("a01", s.first())
        assertEquals(Recommend.similar(c.tracks, "a01", c.co, c.recent).toSet(), s.toSet())
        val home = Recommend.buildHome(c.tracks, c.now, c.co, "a01", c.recent)
        assertEquals("daily", home[0].id)
        assertEquals("similar", home[1].id)
        assertTrue(home.all { it.keys.isNotEmpty() })
        assertTrue(Recommend.buildHome(emptyList(), c.now).isEmpty())
    }

    @Test fun parseGainVariants() {
        assertEquals(-6.52, Recommend.parseGain("-6.52 dB")!!, 1e-9)
        assertEquals(1.2, Recommend.parseGain("+1,2 dB")!!, 1e-9)
        assertEquals(null, Recommend.parseGain("bad"))
        assertEquals(null, Recommend.parseGain(null))
        assertEquals(1.0, Recommend.gainFactor(null), 0.0)
    }
}
