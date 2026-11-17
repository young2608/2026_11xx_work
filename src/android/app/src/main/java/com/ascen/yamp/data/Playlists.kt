package com.ascen.yamp.data

/**
 * 재생 목록 파일 읽기 (vr0.1.0.010, R2 — 순수 Kotlin, JVM 테스트 대상): m3u · m3u8 · pls · xspf · wpl
 *   다른 플레이어(Winamp · VLC · foobar2000 · Windows Media Player)에서 만든 목록을 "파일 추가" 로 열면 안의 곡을 목록에 넣음.
 *   항목 위치 = 절대 경로 · 상대 경로 · file:// · content:// · http(s):// — 기기 곡과 맞추는 것은 resolve()
 *   글자 인코딩: Cue.decode 와 같음 (UTF-8(BOM) → CP949 → ISO-8859-1), m3u8 도 같은 함수 (UTF-8 이 먼저)
 */
object Playlists {
    /** 목록 항목: location = 파일 안의 글자 그대로, title · durationMs = 있으면 */
    data class Entry(val location: String, val title: String = "", val durationMs: Long = 0)

    /** 확장자로 형식 고르기 (모르면 내용으로: <?xml … xspf / smil → wpl, [playlist] → pls, 그 밖 m3u) */
    fun parse(name: String, text: String): List<Entry> {
        val t = text.removePrefix("\uFEFF")
        return when (Formats.ext(name)) {
            "pls" -> parsePls(t)
            "xspf" -> parseXspf(t)
            "wpl" -> parseWpl(t)
            "m3u", "m3u8" -> parseM3u(t)
            else -> {
                val head = t.trimStart().take(400).lowercase()
                when {
                    head.contains("<playlist") && head.contains("xspf") -> parseXspf(t)
                    head.contains("<smil") -> parseWpl(t)
                    head.startsWith("[playlist]") -> parsePls(t)
                    else -> parseM3u(t)
                }
            }
        }
    }

    private fun lines(t: String): List<String> = t.replace("\r\n", "\n").replace('\r', '\n').split('\n')

    // ---------------------------------------------------------------- m3u / m3u8
    /** #EXTINF:초,가수 - 제목 다음 줄 = 위치. # 로 시작하는 다른 줄은 무시 */
    fun parseM3u(text: String): List<Entry> {
        val out = ArrayList<Entry>()
        var title = ""
        var dur = 0L
        for (raw in lines(text)) {
            val l = raw.trim()
            if (l.isEmpty()) continue
            if (l.startsWith("#")) {
                if (l.startsWith("#EXTINF:", ignoreCase = true)) {
                    val body = l.substring(8)
                    val comma = body.indexOf(',')
                    val secs = (if (comma >= 0) body.substring(0, comma) else body).trim().substringBefore(' ').toDoubleOrNull()
                    dur = if (secs != null && secs > 0) (secs * 1000).toLong() else 0L
                    title = if (comma >= 0) body.substring(comma + 1).trim() else ""
                }
                continue
            }
            out.add(Entry(l, title, dur))
            title = ""
            dur = 0
        }
        return out
    }

    // ---------------------------------------------------------------- pls
    /** [playlist] FileN= · TitleN= · LengthN=(초, -1 = 모름). 번호 순서 */
    fun parsePls(text: String): List<Entry> {
        val files = java.util.TreeMap<Int, String>()
        val titles = HashMap<Int, String>()
        val lens = HashMap<Int, Long>()
        val key = Regex("""^(file|title|length)(\d+)$""", RegexOption.IGNORE_CASE)
        for (raw in lines(text)) {
            val l = raw.trim()
            val eq = l.indexOf('=')
            if (eq <= 0) continue
            val m = key.matchEntire(l.substring(0, eq).trim()) ?: continue
            val n = m.groupValues[2].toIntOrNull() ?: continue
            val v = l.substring(eq + 1).trim()
            when (m.groupValues[1].lowercase()) {
                "file" -> if (v.isNotEmpty()) files[n] = v
                "title" -> titles[n] = v
                "length" -> v.toDoubleOrNull()?.takeIf { it > 0 }?.let { lens[n] = (it * 1000).toLong() }
            }
        }
        return files.map { (n, f) -> Entry(f, titles[n].orEmpty(), lens[n] ?: 0) }
    }

    // ---------------------------------------------------------------- xspf (XML)
    private val TRACK = Regex("""<track\b[^>]*>(.*?)</track>""", setOf(RegexOption.DOT_MATCHES_ALL, RegexOption.IGNORE_CASE))

    private fun tag(body: String, name: String): String =
        Regex("""<$name\b[^>]*>(.*?)</$name>""", setOf(RegexOption.DOT_MATCHES_ALL, RegexOption.IGNORE_CASE))
            .find(body)?.groupValues?.get(1)?.let { xmlText(it) }.orEmpty()

    /** <track><location>…</location><title>…</title><creator>…</creator><duration>ms</duration></track> */
    fun parseXspf(text: String): List<Entry> = TRACK.findAll(text).mapNotNull { m ->
        val b = m.groupValues[1]
        val loc = tag(b, "location")
        if (loc.isEmpty()) return@mapNotNull null
        val title = tag(b, "title")
        val creator = tag(b, "creator")
        val name = if (creator.isNotEmpty() && title.isNotEmpty()) "$creator - $title" else title
        Entry(loc, name, tag(b, "duration").toLongOrNull()?.coerceAtLeast(0) ?: 0)
    }.toList()

    // ---------------------------------------------------------------- wpl (Windows Media Player, SMIL XML)
    private val MEDIA = Regex("""<media\b([^>]*?)/?>""", RegexOption.IGNORE_CASE)
    private val SRC = Regex("""\bsrc\s*=\s*("([^"]*)"|'([^']*)')""", RegexOption.IGNORE_CASE)

    /** <seq><media src="..\Music\a.mp3"/></seq> */
    fun parseWpl(text: String): List<Entry> = MEDIA.findAll(text).mapNotNull { m ->
        val s = SRC.find(m.groupValues[1]) ?: return@mapNotNull null
        val v = xmlText(s.groupValues[2].ifEmpty { s.groupValues[3] })
        if (v.isEmpty()) null else Entry(v)
    }.toList()

    /** XML 글자: CDATA · &amp; &lt; &gt; &quot; &apos; &#n; &#xh; */
    fun xmlText(s: String): String {
        var t = s.trim()
        if (t.startsWith("<![CDATA[") && t.endsWith("]]>")) return t.substring(9, t.length - 3).trim()
        t = Regex("""&#(x[0-9a-fA-F]+|\d+);""").replace(t) { m ->
            val v = m.groupValues[1]
            val cp = if (v.startsWith("x") || v.startsWith("X")) v.substring(1).toIntOrNull(16) else v.toIntOrNull()
            if (cp == null || cp !in 0..0x10FFFF) m.value else String(Character.toChars(cp))
        }
        return t.replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", "\"").replace("&apos;", "'").replace("&amp;", "&")
    }

    // ---------------------------------------------------------------- 위치 해석
    sealed class Loc {
        /** 그대로 재생할 수 있는 uri (http · https · content) */
        data class Direct(val uri: String) : Loc()
        /** 파일 경로 ('/' 구분, file:// 과 %XX 를 푼 것) — 기기 곡과 맞춰 봐야 함 */
        data class Path(val path: String) : Loc()
    }

    /** %XX 풀기 (UTF-8) — 잘못된 것은 그대로 */
    fun percentDecode(s: String): String {
        if (!s.contains('%')) return s
        val bytes = java.io.ByteArrayOutputStream()
        var i = 0
        while (i < s.length) {
            val c = s[i]
            if (c == '%' && i + 2 < s.length) {
                val h = s.substring(i + 1, i + 3).toIntOrNull(16)
                if (h != null) { bytes.write(h); i += 3; continue }
            }
            bytes.write(c.toString().toByteArray(Charsets.UTF_8))
            i++
        }
        return bytes.toString("UTF-8")
    }

    fun locate(location: String): Loc {
        val l = location.trim()
        val low = l.lowercase()
        if (low.startsWith("http://") || low.startsWith("https://") || low.startsWith("content://")) return Loc.Direct(l)
        var p = l
        if (low.startsWith("file:")) {
            p = percentDecode(l.substring(5))
            // file:///storage/… → /storage/… · file://localhost/… · file:///C:/… → C:/…
            if (p.startsWith("//")) p = p.substring(2).let { r -> if (r.startsWith("localhost/")) r.substring(9) else if (r.startsWith("/")) r else "/$r" }
            if (Regex("^/[A-Za-z]:/").containsMatchIn(p)) p = p.substring(1)
        }
        return Loc.Path(p.replace('\\', '/'))
    }

    /** 비교용 경로 조각: 소문자, '/' 구분, 빈 조각 · "." · ".." · 드라이브 문자 제거 */
    fun segments(path: String): List<String> = path.replace('\\', '/').split('/')
        .filter { it.isNotEmpty() && it != "." && it != ".." && !Regex("^[A-Za-z]:$").matches(it) }
        .map { it.lowercase() }

    /**
     * 경로 항목 → 기기 곡 (없으면 null). candidates 의 Track.path 와 맞춤:
     *   1) 같은 절대 경로  2) 뒤쪽 조각이 가장 많이 같은 곡 (파일 이름은 반드시 같아야, 같은 점수가 여럿이면 앞의 것)
     *   SAF 곡 path = "saf:N/하위/이름" → 뒤쪽 조각 비교로 맞춤. CUE 트랙(같은 파일 여러 곡)은 맞추지 않음
     */
    fun resolve(path: String, candidates: List<Track>): Track? {
        val want = segments(path)
        if (want.isEmpty()) return null
        val name = want.last()
        var best: Track? = null
        var bestScore = 0
        for (t in candidates) {
            if (t.clip != null || t.path.isEmpty()) continue
            if (t.path.equals(path, ignoreCase = true)) return t
            val have = segments(if (t.path.startsWith("saf:")) t.path.substringAfter('/', "") else t.path)
            if (have.isEmpty() || have.last() != name) continue
            var n = 1
            while (n < want.size && n < have.size && want[want.size - 1 - n] == have[have.size - 1 - n]) n++
            if (n > bestScore) { best = t; bestScore = n }
        }
        return best
    }
}
