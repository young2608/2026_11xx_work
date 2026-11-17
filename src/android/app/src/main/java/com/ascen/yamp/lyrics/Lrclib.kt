package com.ascen.yamp.lyrics

/**
 * LRCLIB (공개 무료 API, https://lrclib.net) — vr0.1.0.011 f18 L4. 순수 Kotlin (전송은 밖에서)
 *  검색어 변형마다: /api/get (제목+가수+길이, 앨범 빼고) → /api/search?track_name&artist_name → /api/search?q="가수 제목"
 *  후보는 길이(duration)를 가지고 Score 로 점수. minScore 이상이 나오면 멈춤 (all = false)
 */
object Lrclib {
    const val BASE = "https://lrclib.net/api"
    private const val SEARCH_MAX = 20

    fun req(url: String, label: String, ua: String): HttpReq = HttpReq(url, "GET", null, mapOf("User-Agent" to ua), label)

    fun getUrl(t: String, a: String, durS: Double): String =
        "$BASE/get?track_name=${Net.enc(t)}&artist_name=${Net.enc(a)}" + (if (durS >= 1) "&duration=${durS.toLong()}" else "")   // PC 와 같게 정수 (버림)

    fun searchUrl(t: String, a: String): String =
        "$BASE/search?track_name=${Net.enc(t)}" + (if (a.isNotBlank()) "&artist_name=${Net.enc(a)}" else "")

    fun qUrl(t: String, a: String): String = "$BASE/search?q=${Net.enc("$a $t".trim())}"

    /** 객체 하나 → 후보 (가사 없음 · 연주곡 → null). 싱크 가사 우선 */
    fun cand(o: Map<String, Any?>?, via: String): LyricCand? {
        if (o == null) return null
        val synced = Json.str(o, "syncedLyrics").takeIf { it.isNotBlank() }
        val txt = synced ?: Json.str(o, "plainLyrics").takeIf { it.isNotBlank() } ?: return null
        return LyricCand("lrclib", Json.str(o, "trackName"), Json.str(o, "artistName"), Json.str(o, "albumName"), txt,
            Json.num(o, "duration"), 0, via)
    }

    fun parseGet(body: String): LyricCand? = runCatching { cand(Json.obj(Json.parse(body)), "get") }.getOrNull()

    fun parseSearch(body: String, via: String): List<LyricCand> = runCatching {
        Json.arr(Json.parse(body)).orEmpty().take(SEARCH_MAX).mapNotNull { cand(Json.obj(it), via) }
    }.getOrDefault(emptyList())

    fun lookup(q: TrackQuery, minScore: Int, http: Transport, rep: ProvReport, ua: String,
               alive: () -> Boolean = { true }, all: Boolean = false, variants: List<Pair<String, String>>? = null) {
        val t0 = System.currentTimeMillis()
        try {
            fun scored(c: LyricCand) = c.copy(score = Score.score(q.title, q.artist, q.album, q.durS, c.title, c.artist, c.album, c.lyric, c.durS))
            fun done() = !all && (rep.best()?.score ?: -1) >= minScore
            fun bad(r: HttpRes) = r.err == NetErr.OFFLINE || r.err == NetErr.TIMEOUT
            for ((t, a) in variants ?: Query.variants(q.title, q.artist)) {
                if (a.isNotBlank()) {
                    if (!alive()) return
                    val r = http(req(getUrl(t, a, q.durS), "get", ua))
                    val c = if (r.ok && r.code == 200) parseGet(r.body!!) else null
                    rep.step("get", "$t / $a", r, if (r.code == 404) "404 없음" else "", if (c != null) 1 else 0)
                    if (bad(r)) return
                    c?.let { rep.add(scored(it)) }
                    if (done()) break
                }
                if (!alive()) return
                val r2 = http(req(searchUrl(t, a), "search", ua))
                val l2 = if (r2.ok && r2.code == 200) parseSearch(r2.body!!, "search") else emptyList()
                rep.step("search", "$t / $a", r2, "", l2.size)
                if (bad(r2)) return
                l2.forEach { rep.add(scored(it)) }
                if (done()) break
                if (a.isNotBlank()) {
                    if (!alive()) return
                    val r3 = http(req(qUrl(t, a), "q", ua))
                    val l3 = if (r3.ok && r3.code == 200) parseSearch(r3.body!!, "q") else emptyList()
                    rep.step("q", "$a $t", r3, "", l3.size)
                    if (bad(r3)) return
                    l3.forEach { rep.add(scored(it)) }
                    if (done()) break
                }
            }
            rep.completed = true
        } finally {
            rep.ms = System.currentTimeMillis() - t0
        }
    }
}
