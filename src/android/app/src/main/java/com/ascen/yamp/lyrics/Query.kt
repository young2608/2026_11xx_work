package com.ascen.yamp.lyrics

import java.util.regex.Pattern

/**
 * 가사 검색어 정리 · 변형 (vr0.1.0.011, f18 L2) — 순수 Kotlin. PC yamp/lyrics/query.py 와 같은 규칙.
 * 공용 테스트: testdata/lyrics_query_cases.txt
 *
 * cleanTitle : 앞 번호 "01. " 제거 → 괄호 속 군더더기(feat·prod·MV·remaster·live …) 제거 → " - Remastered 2011" 같은
 *              꼬리 제거 → 괄호 없는 "feat. X" 꼬리 제거 → 공백 정리
 * splitAlt   : "좋은 날 (Good Day)" → ("좋은 날", "Good Day")   "IU(아이유)" → ("IU", "아이유")
 * mainArtist : "아이유, 김창완" / "A & B" / "A x B" / "A feat. B" / "A/B" → 첫 가수
 * variants   : (원본) → 정리 제목 × 가수 이름들 — 중복 빼고 최대 4개
 * ※ Python re 와 같게: 유니코드 \s \d \b, 대소문자 무시는 유니코드
 */
object Query {
    const val MAX_VARIANTS = 4
    private const val U = Pattern.UNICODE_CHARACTER_CLASS
    private const val I = Pattern.CASE_INSENSITIVE or Pattern.UNICODE_CASE or U
    private const val KW = "feat|ft|featuring|prod|produced|remaster|remastered|mv|m/v|official|audio|video|live|inst|instrumental" +
        "|ver|version|lyric|lyrics|explicit|clean|radio edit|edit|mono|stereo|bonus|hq|hd|4k|visualizer|teaser|full"

    /**
     * vr0.1.0.013 (앱 종료 원인 수정): Android 의 정규식(ICU)은 UNICODE_CHARACTER_CLASS 플래그를 지원하지 않아
     *   IllegalArgumentException("Unsupported flags") → Query 를 처음 쓰는 순간(가사 검색) 앱 종료.
     *   ICU 는 원래 \s \d \b 가 유니코드 기준이라 플래그를 빼도 같은 결과. JVM(테스트)에서는 플래그 사용.
     *   그래도 안 되면 아무것도 맞지 않는 정규식으로 (가사 검색이 덜 똑똑해질 뿐, 앱은 살아 있음)
     */
    internal fun re(p: String, f: Int): Regex = try {
        Pattern.compile(p, f).toRegex()
    } catch (e: IllegalArgumentException) {
        try { Pattern.compile(p, f and Pattern.UNICODE_CHARACTER_CLASS.inv()).toRegex() } catch (e2: IllegalArgumentException) { Regex("(?!)") }
    }

    private val KEEP_RE = re("remix|\\bmix\\b|acoustic|cover|unplugged|piano|orchestra|demo|sped up|slowed|english|japanese|korean|chinese|\\bjp\\b|\\beng\\b|\\bkor\\b", I)
    private val BR = re("\\s*[\\(\\[\\{【]([^\\)\\]\\}】]*)[\\)\\]\\}】]", U)
    private val KW_RE = re("(?:^|[\\s.\\-_/])(?:$KW)(?:$|[\\s.\\-_/:0-9])", I)
    private val TAIL_DASH = re("\\s+[-–—]\\s+[^-–—]*?(?:$KW)[^-–—]*$", I)
    private val TAIL_FEAT = re("\\s+(?:feat\\.?|ft\\.?|featuring)\\s+.*$", I)
    private val NUM = re("^\\s*\\d{1,3}\\s*[.\\-_)]\\s*(?=\\S)", U)
    private val ART_SEP = re("\\s*(?:,|&|/|;|\\s+x\\s+|\\s+with\\s+|\\s+feat\\.?\\s+|\\s+ft\\.?\\s+|\\s+featuring\\s+)\\s*", I)
    private val SPACES = re("\\s+", U)
    private val ALT = re("^(.*?)\\s*[\\(\\[]([^\\)\\]]+)[\\)\\]]\\s*$", U)

    fun ws(s: String?): String = SPACES.replace(s ?: "", " ").trim()

    private fun isKw(inner: String): Boolean = KW_RE.containsMatchIn(" $inner ")

    fun cleanTitle(t: String): String {
        var s = ws(t)
        val n = NUM.replace(s, "")
        if (n.isNotBlank()) s = n
        s = BR.replace(s) { m -> if (isKw(m.groupValues[1])) "" else m.value }
        s = TAIL_DASH.replace(s, "")
        s = TAIL_FEAT.replace(s, "")
        s = ws(s)
        return s.ifEmpty { ws(t) }
    }

    /** 바깥 이름, 괄호 속 다른 이름 (없으면 "") */
    fun splitAlt(s0: String): Pair<String, String> {
        val s = ws(s0)
        val m = ALT.find(s)
        if (m != null && m.groupValues[1].isNotBlank() && !isKw(m.groupValues[2]) && !KEEP_RE.containsMatchIn(m.groupValues[2]))
            return ws(m.groupValues[1]) to ws(m.groupValues[2])
        return s to ""
    }

    fun mainArtist(a0: String): String {
        val a = ws(a0)
        val parts = ART_SEP.split(a).filter { it.isNotBlank() }
        return if (parts.isNotEmpty()) ws(parts[0]) else a
    }

    /** 가수 이름 후보: 첫 가수 바깥 이름, 괄호 속 이름 */
    fun artistNames(a: String): List<String> {
        val out = ArrayList<String>()
        val (m, alt) = splitAlt(mainArtist(a))
        for (x in listOf(m, alt)) if (x.isNotEmpty() && x !in out) out.add(x)
        return out
    }

    fun titleNames(t: String): List<String> {
        val c = cleanTitle(t)
        val (m, alt) = splitAlt(c)
        val out = ArrayList<String>()
        for (x in listOf(c, m, alt)) if (x.isNotEmpty() && x !in out) out.add(x)
        return out
    }

    /** 검색에 쓸 (제목, 가수) 목록 — 첫 항목은 원본 (공백 정리) */
    fun variants(title: String, artist: String): List<Pair<String, String>> {
        val out = ArrayList<Pair<String, String>>()
        fun add(t: String, a: String) {
            val p = ws(t) to ws(a)
            if (p.first.isNotEmpty() && p !in out && out.size < MAX_VARIANTS) out.add(p)
        }
        add(title, artist)
        val ts = titleNames(title)
        val arts = artistNames(artist).ifEmpty { listOf("") }
        // 정리 제목 + 첫 가수 → 바깥 제목 + 첫 가수 → 정리 제목 + 다른 이름 → 괄호 속 제목 + 첫 가수 …
        for (t in ts.drop(1).take(1) + ts.take(1) + ts.drop(2)) add(t, arts[0])
        for (a in arts.drop(1)) for (t in ts) add(t, a)
        return out
    }
}
