package com.ascen.yamp.lyrics

/**
 * NetEase 클라우드 뮤직 (비공식 웹 API) — vr0.1.0.011 f18 L10, 기본 꺼짐 (config lyrics_netease). 순수 Kotlin (전송은 밖에서)
 *  검색: /api/search/get/web?s=<검색어>&type=1&limit=10 → result.songs[] (id · name · artists[].name · album.name · duration ms)
 *  가사: /api/song/lyric?id=<id>&lv=1&tv=-1 → lrc.lyric (+ tlyric.lyric 번역 → 같은 시각 둘째 줄)
 */
object NetEase {
    const val BASE = "https://music.163.com/api"
    private const val UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    private val HEADERS = mapOf("User-Agent" to UA, "Referer" to "https://music.163.com/")
    private val TS = Regex("""\[(\d{1,3}):(\d{1,2})(?:[.:](\d{1,3}))?]""")

    data class Song(val id: String, val title: String, val artist: String, val album: String, val durS: Double)

    fun searchUrl(q: String): String = "$BASE/search/get/web?s=${Net.enc(q)}&type=1&limit=10"
    fun lyricUrl(id: String): String = "$BASE/song/lyric?id=${Net.enc(id)}&lv=1&tv=-1"
    fun req(url: String, label: String) = HttpReq(url, "GET", null, HEADERS, label)

    fun parseSearch(body: String): List<Song> = runCatching {
        val songs = Json.arr(Json.obj(Json.obj(Json.parse(body))?.get("result"))?.get("songs")).orEmpty()
        songs.mapNotNull { s ->
            val o = Json.obj(s) ?: return@mapNotNull null
            val id = Json.str(o, "id").ifEmpty { return@mapNotNull null }
            val arts = Json.arr(o["artists"]).orEmpty().mapNotNull { Json.obj(it)?.let { a -> Json.str(a, "name") } }.filter { it.isNotBlank() }
            Song(id, Json.str(o, "name"), arts.joinToString(", "), Json.str(Json.obj(o["album"]), "name"), Json.num(o, "duration") / 1000.0)
        }
    }.getOrDefault(emptyList())

    /** 가사 응답 → LRC (번역 합침). 가사 없음 → "" */
    fun parseLyric(body: String): String = runCatching {
        val o = Json.obj(Json.parse(body))
        merge(Json.str(Json.obj(o?.get("lrc")), "lyric"), Json.str(Json.obj(o?.get("tlyric")), "lyric"))
    }.getOrDefault("")

    private fun stampMs(m: MatchResult): Long {
        val fr = m.groupValues[3].ifEmpty { "0" }
        return m.groupValues[1].toLong() * 60000 + m.groupValues[2].toLong() * 1000 + fr.padEnd(3, '0').take(3).toLong()
    }

    /** 줄 앞 타임스탬프들 (원래 글자, ms) 과 본문 */
    private fun split(line: String): Pair<List<Pair<String, Long>>, String> {
        val st = ArrayList<Pair<String, Long>>()
        var pos = 0
        while (true) {
            val m = TS.matchAt(line, pos) ?: break
            st.add(m.value to stampMs(m))
            pos = m.range.last + 1
        }
        return st to line.substring(pos).trim()
    }

    /**
     * 원문 LRC + 번역 LRC → 같은 시각에 번역 줄을 하나 더 (알송처럼 블록 둘째 줄).
     * JSON 줄({"t":…}) 은 버림. 번역이 원문과 같거나 비면 넣지 않음
     */
    fun merge(lrc: String, tlyric: String): String {
        fun lines(s: String) = s.replace("\r\n", "\n").replace('\r', '\n').split('\n').map { it.trim() }
            .filter { it.isNotEmpty() && !it.startsWith("{") }
        val trans = HashMap<Long, String>()
        for (l in lines(tlyric)) {
            val (st, body) = split(l)
            if (body.isNotEmpty()) for ((_, ms) in st) trans.putIfAbsent(ms, body)
        }
        val out = StringBuilder()
        for (l in lines(lrc)) {
            val (st, body) = split(l)
            if (st.isEmpty()) { out.append(l).append('\n'); continue }
            for ((raw, ms) in st) {
                out.append(raw).append(body).append('\n')
                val tr = trans[ms]
                if (body.isNotEmpty() && tr != null && tr != body) out.append(raw).append(tr).append('\n')
            }
        }
        return out.toString().trim()
    }

    fun lookup(q: TrackQuery, minScore: Int, http: Transport, rep: ProvReport,
               alive: () -> Boolean = { true }, all: Boolean = false, variants: List<Pair<String, String>>? = null) {
        val t0 = System.currentTimeMillis()
        try {
            fun bad(r: HttpRes) = r.err == NetErr.OFFLINE || r.err == NetErr.TIMEOUT
            for ((t, a) in variants ?: Query.variants(q.title, q.artist)) {
                if (!alive()) return
                val qs = "$t $a".trim()
                val r = http(req(searchUrl(qs), "search"))
                val songs = if (r.ok && r.code == 200) parseSearch(r.body!!) else emptyList()
                rep.step("search", qs, r, "", songs.size)
                if (bad(r)) return
                // 가사 없이 먼저 점수 → 높은 곡부터 가사 받기 (자동: 1곡, 다른 가사 찾기: 3곡)
                val top = songs.sortedByDescending { Score.score(q.title, q.artist, q.album, q.durS, it.title, it.artist, it.album, "", it.durS) }
                    .take(if (all) 3 else 1)
                for (s in top) {
                    if (!alive()) return
                    val r2 = http(req(lyricUrl(s.id), "lyric"))
                    val ly = if (r2.ok && r2.code == 200) parseLyric(r2.body!!) else ""
                    rep.step("lyric", s.id, r2, "", if (ly.isNotEmpty()) 1 else 0)
                    if (bad(r2)) return
                    if (ly.isNotEmpty()) rep.add(LyricCand("netease", s.title, s.artist, s.album, ly, s.durS,
                        Score.score(q.title, q.artist, q.album, q.durS, s.title, s.artist, s.album, ly, s.durS), "lyric"))
                }
                if (!all && (rep.best()?.score ?: -1) >= minScore) break
            }
            rep.completed = true
        } finally {
            rep.ms = System.currentTimeMillis() - t0
        }
    }
}
