package com.ascen.yamp.domain

import kotlin.math.ln
import kotlin.math.pow
import kotlin.random.Random

/**
 * 추천 엔진 (순수 Kotlin — android.* 없음, JVM 테스트 대상).
 * PC yamp/domain/recommend.py 와 **같은 규칙** — 공용 테스트 벡터 00__build/src/testdata/recommend_cases.txt
 *
 * 모든 데이터는 기기 안의 재생 기록에서 나옴 (외부 서버·AI 없음).
 *
 * 선호 점수   score = 3·liked + rating + ln(1+completed) − 1.5·ln(1+skipped)
 * 믹스
 *   favorites   좋아요 또는 최근 30일 완청 곡 — score + 2·ln(1+completed_recent) 순
 *   rediscover  완청 3회 이상 & 30일 이상 안 들은 곡 — score 순
 *   daily       오늘의 믹스 = 선호(3일 안 들은 곡) 50% + 다시 발견 30% + 새 곡(좋아하는 가수·장르, 미청취) 20%
 *   similar     기준 곡과 비슷한 곡 (같은 가수 3, 같은 앨범 2, 같은 장르 2, 같은 폴더 1, 같이 들은 곡 최대 3)
 *   mood        상황 믹스 (사용자 태그 우선, 없으면 장르 매핑)
 * 정렬 동점은 key 오름차순 (플랫폼 간 결과 일치). rng 를 주면 그룹 안에서 섞음 (테스트는 rng = null).
 */
data class TrackStat(
    val key: String,
    val artist: String = "",
    val album: String = "",
    val genre: String = "",
    val folder: String = "",
    val liked: Boolean = false,
    val rating: Int = 0,
    val completed: Int = 0,
    val skipped: Int = 0,
    val lastPlayed: Long = 0,        // epoch 초, 0 = 안 들음
    val addedAt: Long = 0,
    val completedRecent: Int = 0,    // 최근 30일 완청 수
    val tags: List<String> = emptyList(),
)

data class HomeCard(val id: String, val title: String, val keys: List<String>)

object Recommend {
    const val DAY = 86400L
    const val N_DEFAULT = 25

    /** id → (표시 이름, 장르 키워드)  — 순서 유지 (PC dict 순서와 같음) */
    val MOODS: LinkedHashMap<String, Pair<String, List<String>>> = linkedMapOf(
        "study" to ("공부·집중" to listOf("classical", "ambient", "piano", "lo-fi", "lofi", "jazz", "instrumental", "ost")),
        "workout" to ("운동" to listOf("dance", "edm", "electronic", "hip hop", "hip-hop", "rap", "rock", "k-pop", "kpop")),
        "drive" to ("드라이브" to listOf("pop", "rock", "k-pop", "kpop", "r&b", "indie")),
        "sleep" to ("수면·휴식" to listOf("classical", "ambient", "jazz", "ballad", "발라드", "new age", "piano")),
    )
    val MIX_TITLES = mapOf("daily" to "오늘의 믹스", "favorites" to "자주 듣는 곡 · 좋아요", "rediscover" to "다시 발견",
        "recent" to "최근 추가")

    fun score(t: TrackStat): Double =
        3.0 * (if (t.liked) 1 else 0) + t.rating + ln(1.0 + t.completed) - 1.5 * ln(1.0 + t.skipped)

    private fun daysSince(t: TrackStat, now: Long): Double =
        if (t.lastPlayed > 0) (now - t.lastPlayed).toDouble() / DAY else 1e9

    fun norm(s: String?): String = (s ?: "").trim().lowercase()

    /** Python round() — 반올림 시 짝수 쪽 (round(12.5) = 12, round(7.5) = 8) */
    fun pyRound(x: Double): Int = Math.rint(x).toInt()

    /** (-v, key) 정렬용 비교자 */
    private fun byDescThenKey(v: (TrackStat) -> Double): Comparator<TrackStat> =
        Comparator { a, b ->
            val va = v(a)
            val vb = v(b)
            if (va == vb) a.key.compareTo(b.key) else if (va > vb) -1 else 1   // Python 처럼 -0.0 == 0.0
        }

    fun favorites(tracks: List<TrackStat>, n: Int = N_DEFAULT): List<String> =
        tracks.filter { it.liked || it.completedRecent > 0 }
            .sortedWith(byDescThenKey { score(it) + 2.0 * ln(1.0 + it.completedRecent) })
            .take(n).map { it.key }

    fun rediscover(tracks: List<TrackStat>, now: Long, n: Int = N_DEFAULT): List<String> =
        tracks.filter { it.completed >= 3 && daysSince(it, now) >= 30 }
            .sortedWith(byDescThenKey { score(it) })
            .take(n).map { it.key }

    fun recentAdded(tracks: List<TrackStat>, n: Int = N_DEFAULT): List<String> =
        tracks.sortedWith(byDescThenKey { it.addedAt.toDouble() }).take(n).map { it.key }

    fun topArtistsGenres(tracks: List<TrackStat>, k: Int = 5): Pair<List<String>, List<String>> {
        val sa = LinkedHashMap<String, Double>()
        val sg = LinkedHashMap<String, Double>()
        for (t in tracks) {
            val s = score(t)
            if (s <= 0) continue
            val a = norm(t.artist)
            val g = norm(t.genre)
            if (a.isNotEmpty()) sa[a] = (sa[a] ?: 0.0) + s
            if (g.isNotEmpty()) sg[g] = (sg[g] ?: 0.0) + s
        }
        val cmp = Comparator<Map.Entry<String, Double>> { x, y ->
            val c = y.value.compareTo(x.value)
            if (c != 0) c else x.key.compareTo(y.key)
        }
        return sa.entries.sortedWith(cmp).take(k).map { it.key } to sg.entries.sortedWith(cmp).take(k).map { it.key }
    }

    /** 같은 가수가 maxRun 곡 넘게 연속되지 않게 (가능한 범위에서 뒤로 미룸, 안정적) */
    fun diversify(keys: List<String>, artistOf: (String) -> String, maxRun: Int = 2): List<String> {
        val out = ArrayList<String>()
        val pending = keys.toMutableList()
        while (pending.isNotEmpty()) {
            var picked = -1
            for ((i, k) in pending.withIndex()) {
                val a = norm(artistOf(k))
                var run = 0
                for (j in out.indices.reversed()) {
                    if (a.isNotEmpty() && norm(artistOf(out[j])) == a) run++ else break
                }
                if (run < maxRun) { picked = i; break }
            }
            if (picked < 0) picked = 0
            out.add(pending.removeAt(picked))
        }
        return out
    }

    fun daily(tracks: List<TrackStat>, now: Long, n: Int = N_DEFAULT, rng: Random? = null): List<String> {
        val by = tracks.associateBy { it.key }
        val fav = tracks.filter { score(it) > 0 && daysSince(it, now) >= 3 }.sortedWith(byDescThenKey { score(it) }).toMutableList()
        val red = rediscover(tracks, now, Int.MAX_VALUE).map { by.getValue(it) }.toMutableList()
        val (ta, tg) = topArtistsGenres(tracks)
        val new = tracks.filter {
            it.completed == 0 && it.skipped == 0 && (norm(it.artist) in ta || norm(it.genre) in tg)
        }.sortedWith(byDescThenKey { it.addedAt.toDouble() }).toMutableList()
        if (rng != null) for (g in listOf(fav, red, new)) g.shuffle(rng)
        val quota = listOf(fav to pyRound(n * 0.5), red to pyRound(n * 0.3), new to n)
        val out = ArrayList<String>()
        val seen = HashSet<String>()
        for ((group, q) in quota) {
            var cnt = 0
            for (t in group) {
                if (out.size >= n || cnt >= q) break
                if (seen.add(t.key)) { out.add(t.key); cnt++ }
            }
        }
        // 모자라면 선호 → 나머지 점수 순으로 채움
        val rest = tracks.sortedWith(byDescThenKey { score(it) })
        for (t in fav + rest) {
            if (out.size >= n) break
            if (seen.add(t.key)) out.add(t.key)
        }
        return diversify(out, { by[it]?.artist.orEmpty() })
    }

    fun similarity(seed: TrackStat, t: TrackStat, co: Map<Pair<String, String>, Int>): Int {
        var s = 0
        val sa = norm(seed.artist)
        if (sa.isNotEmpty() && sa == norm(t.artist)) s += 3
        if (norm(seed.album).isNotEmpty() && norm(seed.album) == norm(t.album) && sa == norm(t.artist)) s += 2
        if (norm(seed.genre).isNotEmpty() && norm(seed.genre) == norm(t.genre)) s += 2
        if (seed.folder.isNotEmpty() && seed.folder == t.folder) s += 1
        val c = (co[seed.key to t.key] ?: 0) + (co[t.key to seed.key] ?: 0)
        s += minOf(3, c)
        return s
    }

    /** co: (a, b) → 같이 들은 횟수, recent: 최근 1시간 재생 key (제외). 결과 = [seed] + 비슷한 곡 */
    fun similar(
        tracks: List<TrackStat>, seedKey: String, co: Map<Pair<String, String>, Int> = emptyMap(),
        recent: Collection<String> = emptyList(), n: Int = N_DEFAULT, rng: Random? = null,
    ): List<String> {
        val by = tracks.associateBy { it.key }
        val seed = by[seedKey] ?: return emptyList()
        val rec = recent.toHashSet()
        data class C(val sim: Int, val sc: Double, val key: String)
        val cand = ArrayList<C>()
        for (t in tracks) {
            if (t.key == seedKey || t.key in rec) continue
            val s = similarity(seed, t, co)
            if (s > 0) cand.add(C(s, score(t), t.key))
        }
        cand.sortWith(Comparator { a, b ->
            when {
                a.sim != b.sim -> b.sim.compareTo(a.sim)
                a.sc != b.sc -> b.sc.compareTo(a.sc)
                else -> a.key.compareTo(b.key)
            }
        })
        val top = cand.take(50)
        val keys: List<String> = if (rng == null) top.take(n).map { it.key } else {
            // 유사도 가중 무작위
            val pool = top.toMutableList()
            val out = ArrayList<String>()
            while (pool.isNotEmpty() && out.size < n) {
                val w = pool.map { maxOf(0.1, it.sim.toDouble()) }
                var r = rng.nextDouble() * w.sum()
                var pick = pool.size - 1
                for ((i, x) in w.withIndex()) {
                    r -= x
                    if (r < 0) { pick = i; break }
                }
                out.add(pool.removeAt(pick).key)
            }
            out
        }
        return listOf(seedKey) + diversify(keys, { by[it]?.artist.orEmpty() })
    }

    fun mood(tracks: List<TrackStat>, name: String, n: Int = N_DEFAULT, rng: Random? = null): List<String> {
        val m = MOODS[name]
        val label = m?.first ?: name
        val genres = m?.second ?: emptyList()
        val tagged = tracks.filter { name in it.tags || label in it.tags }
        val pool0 = if (tagged.isNotEmpty()) tagged else tracks.filter { t -> genres.any { g -> g in norm(t.genre) } }
        val pool = pool0.sortedWith(byDescThenKey { score(it) }).toMutableList()
        if (rng != null) pool.shuffle(rng)
        val by = tracks.associateBy { it.key }
        return diversify(pool.take(n).map { it.key }, { by[it]?.artist.orEmpty() })
    }

    /** 추천 홈 카드 목록 — 비어 있는 카드는 뺌 */
    fun buildHome(
        tracks: List<TrackStat>, now: Long, co: Map<Pair<String, String>, Int> = emptyMap(),
        lastKey: String? = null, recent: Collection<String> = emptyList(), rng: Random? = null,
    ): List<HomeCard> {
        val cards = mutableListOf(
            HomeCard("daily", MIX_TITLES.getValue("daily"), daily(tracks, now, rng = rng)),
            HomeCard("favorites", MIX_TITLES.getValue("favorites"), favorites(tracks)),
            HomeCard("rediscover", MIX_TITLES.getValue("rediscover"), rediscover(tracks, now)),
            HomeCard("recent", MIX_TITLES.getValue("recent"), recentAdded(tracks)),
        )
        if (!lastKey.isNullOrEmpty() && tracks.any { it.key == lastKey }) {
            cards.add(1, HomeCard("similar", "비슷한 곡 라디오 (마지막 재생 곡)", similar(tracks, lastKey, co, recent, rng = rng)))
        }
        for ((m, v) in MOODS) cards.add(HomeCard("mood:$m", "상황 믹스 · ${v.first}", mood(tracks, m, rng = rng)))
        return cards.filter { it.keys.isNotEmpty() }
    }

    // ---------------------------------------------------------------- ReplayGain (C1)
    private val NUM = Regex("""^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$""")

    /** "-6.52 dB" / "+1.2" → dB. 잘못되면 null */
    fun parseGain(s: String?): Double? {
        if (s == null) return null
        val txt = s.trim().lowercase().replace("db", "").replace(",", ".").replace("−", "-").trim()
        if (!NUM.matches(txt)) return null
        return txt.toDoubleOrNull()
    }

    /** 선형 배율 (1.0 = 그대로). peak 가 있으면 클리핑 방지 (배율 ≤ 1/peak). 범위 0.05 ~ 4.0 */
    fun gainFactor(gainDb: Double?, peak: Double? = null, preampDb: Double = 0.0): Double {
        if (gainDb == null) return 1.0
        var f = 10.0.pow((gainDb + preampDb) / 20.0)
        if (peak != null && peak > 0) f = minOf(f, 1.0 / peak)
        return f.coerceIn(0.05, 4.0)
    }
}
