package com.ascen.yamp.lyrics

import java.io.IOException
import java.io.InputStream
import java.security.MessageDigest

/**
 * 알송 가사 (비공식 SOAP). PC yamp/lyrics/providers/alsong.py 와 같은 규칙.
 * ⚠ ESTsoft 공식 공개 API 아님 — 개인 사용 용도. 실패 시 다음 공급자로.
 * 순수 Kotlin(네트워크 제외) — JVM 단위 테스트 대상.
 * vr0.1.0.011 (f18 L1): 검색 응답 태그를 실제 이름(ST_GET_RESEMBLELYRIC2_RETURN)으로 고침 — 이전에는 검색이 늘 0건 (C1),
 *   encData 기본 내장 토큰 (C2·C3), 0건이면 GetResembleLyricList2 → GetLyricByID2, 후보 점수는 Score (L3), 전송은 Net (상태 사유 · 진단)
 */
object Alsong {
    const val URL_SVC = "http://lyrics.alsong.co.kr/alsongwebservice/service1.asmx"
    const val MD5_LEN = 163840

    private const val HEAD = "<?xml version=\"1.0\" encoding=\"UTF-8\"?>" +
        "<SOAP-ENV:Envelope xmlns:SOAP-ENV=\"http://www.w3.org/2003/05/soap-envelope\" " +
        "xmlns:SOAP-ENC=\"http://www.w3.org/2003/05/soap-encoding\" " +
        "xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" " +
        "xmlns:xsd=\"http://www.w3.org/2001/XMLSchema\" " +
        "xmlns:ns2=\"ALSongWebServer/Service1Soap\" xmlns:ns1=\"ALSongWebServer\" " +
        "xmlns:ns3=\"ALSongWebServer/Service1Soap12\"><SOAP-ENV:Body>"
    private const val TAIL = "</SOAP-ENV:Body></SOAP-ENV:Envelope>"

    // ---------------------------------------------------------- MD5
    private fun id3Size(h: ByteArray): Int {
        if (h.size < 10 || h[0] != 'I'.code.toByte() || h[1] != 'D'.code.toByte() || h[2] != '3'.code.toByte()) return -1
        val s = ((h[6].toInt() and 0x7F) shl 21) or ((h[7].toInt() and 0x7F) shl 14) or
            ((h[8].toInt() and 0x7F) shl 7) or (h[9].toInt() and 0x7F)
        return s + if (h[5].toInt() and 0x10 != 0) 10 else 0
    }

    /** ID3v2 를 건너뛴 뒤 첫 프레임 동기(0xFFEx) 위치 */
    fun audioStartOffset(head: ByteArray): Int {
        val sz = id3Size(head)
        return syncFrom(head, if (sz >= 0) 10 + sz else 0)
    }

    /**
     * vr0.1.0.008: ID3v2 본문(앨범아트 포함, 수 MB 일 수 있음)은 메모리에 읽지 않고 건너뜀 → 곡마다 큰 배열이 생기지 않음.
     * 결과는 이전(태그까지 모두 읽고 audioStartOffset)과 같음: 태그 뒤 위치부터 같은 범위에서 동기를 찾음
     */
    fun audioMd5(input: InputStream): String? {
        input.use { ins ->
            val first = ins.readNBytesCompat(10)
            val sz = id3Size(first)
            val body: ByteArray
            if (sz >= 0) {
                // 태그 본문 건너뛰기 → 남은 부분은 태그 없이 시작 (id3Size 다시 보지 않게 offset 0 부터 찾음)
                if (ins.skipFully(sz.toLong()) < sz) return null
                body = ins.readNBytesCompat(65538 + MD5_LEN)
            } else {
                body = first + ins.readNBytesCompat(65538 + MD5_LEN - first.size)
            }
            val start = if (sz >= 0) syncFrom(body, 0) else audioStartOffset(body)
            if (body.size - start < 1024) return null
            val md = MessageDigest.getInstance("MD5")
            md.update(body, start, minOf(MD5_LEN, body.size - start))
            return md.digest().joinToString("") { "%02x".format(it) }
        }
    }

    /** pos 부터 65536 바이트 안의 첫 프레임 동기 (없으면 pos) — audioStartOffset 과 같은 규칙 */
    private fun syncFrom(head: ByteArray, pos: Int): Int {
        val end = minOf(head.size - 1, pos + 65536)
        var i = pos
        while (i < end) {
            if (head[i] == 0xFF.toByte() && (head[i + 1].toInt() and 0xE0) == 0xE0) return i
            i++
        }
        return pos
    }

    // ---------------------------------------------------------- SOAP (vr0.1.0.011 L1 — 실제 응답 태그 이름으로 수정)
    /**
     * 기본 encData — 공개 오픈소스 alsong-lyrics (npm, MIT) 에 실린 고정 토큰 (D1-a).
     * config alsong_enc_data: 빈 값 = 이 토큰 / "off" = encData 없이 (옛 GetLyric5) / 그 밖 = 그 값
     */
    const val ENC_BUILTIN = "7c2d15b8f51ac2f3b2a37d7a445c3158455defb8a58d621eb77a3ff8ae4921318e49cefe24e515f79892a4c29c9a3e204358698c1cfe79c151c04f9561e945096ccd1d1c0a8d8f265a2f3fa7995939b21d8f663b246bbc433c7589da7e68047524b80e16f9671b6ea0faaf9d6cde1b7dbcf1b89aa8a1d67a8bbc566664342e12"

    fun encOf(cfg: String?): String {
        val v = cfg?.trim().orEmpty()
        return when {
            v.isEmpty() -> ENC_BUILTIN
            v.equals("off", ignoreCase = true) -> ""
            else -> v
        }
    }

    fun esc(s: String) = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        .replace("\"", "&quot;")

    private fun encTag(encData: String) = if (encData.isNotEmpty()) "<ns1:encData>${esc(encData)}</ns1:encData>" else ""

    /** MD5 조회: encData 있으면 GetLyric7, 없으면 GetLyric5 */
    fun lyricRequest(md5: String, encData: String = ""): String {
        val q = "<ns1:stQuery><ns1:strChecksum>${esc(md5)}</ns1:strChecksum>" +
            "<ns1:strVersion>3.46</ns1:strVersion><ns1:strMACAddress>00ff667f9a08</ns1:strMACAddress>" +
            "<ns1:strIPAddress>192.168.0.2</ns1:strIPAddress></ns1:stQuery>"
        val body = if (encData.isNotEmpty()) "<ns1:GetLyric7>${encTag(encData)}$q</ns1:GetLyric7>"
        else "<ns1:GetLyric5>$q</ns1:GetLyric5>"
        return HEAD + body + TAIL
    }

    /** 제목·가수 검색 (가사 포함): GetResembleLyric2 → ST_GET_RESEMBLELYRIC2_RETURN */
    fun searchRequest(title: String, artist: String, page: Int = 0, encData: String = ""): String =
        HEAD + "<ns1:GetResembleLyric2>${encTag(encData)}<ns1:stQuery>" +
            "<ns1:strTitle>${esc(title)}</ns1:strTitle><ns1:strArtistName>${esc(artist)}</ns1:strArtistName>" +
            "<ns1:nCurPage>$page</ns1:nCurPage></ns1:stQuery></ns1:GetResembleLyric2>" + TAIL

    /** 목록 검색 (가사 없음): GetResembleLyricList2 → ST_SEARCHLYRIC_LIST (lyricID …) */
    fun listRequest(title: String, artist: String, page: Int = 1, encData: String = ""): String =
        HEAD + "<ns1:GetResembleLyricList2>${encTag(encData)}<ns1:title>${esc(title)}</ns1:title>" +
            "<ns1:artist>${esc(artist)}</ns1:artist><ns1:pageNo>$page</ns1:pageNo></ns1:GetResembleLyricList2>" + TAIL

    /** 목록 항목 가사: GetLyricByID2 → output/lyric */
    fun byIdRequest(id: String, encData: String = ""): String =
        HEAD + "<ns1:GetLyricByID2>${encTag(encData)}<ns1:lyricID>${esc(id)}</ns1:lyricID></ns1:GetLyricByID2>" + TAIL

    private val NUM_ENT = Regex("&#(\\d{1,7});")
    private val HEX_ENT = Regex("&#[xX]([0-9a-fA-F]{1,6});")

    fun unescape(s: String): String {
        var r = s.replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", "\"").replace("&apos;", "'")
        r = NUM_ENT.replace(r) { m -> m.groupValues[1].toIntOrNull()?.let { cp -> runCatching { String(Character.toChars(cp)) }.getOrNull() } ?: m.value }
        r = HEX_ENT.replace(r) { m -> m.groupValues[1].toIntOrNull(16)?.let { cp -> runCatching { String(Character.toChars(cp)) }.getOrNull() } ?: m.value }
        return r.replace("&amp;", "&")
    }

    private val BR = Regex("<br\\s*/?>|&lt;br\\s*/?&gt;", RegexOption.IGNORE_CASE)

    /** 가사 글 정리: XML 엔티티 → <br> · &lt;br&gt; (이중 이스케이프 포함) → 줄바꿈 → 남은 엔티티 → \r\n */
    fun cleanLyric(raw: String): String {
        var s = unescape(raw)               // XML 한 겹
        s = BR.replace(s, "\n")             // <br> / (이중 이스케이프였던) &lt;br&gt;
        s = unescape(s)                     // 가사 글 안의 엔티티
        s = BR.replace(s, "\n")
        return s.replace("\r\n", "\n").replace('\r', '\n').trim()
    }

    private fun tagText(xml: String, tag: String): String? =
        Regex("<(?:\\w+:)?$tag(?:\\s[^>]*?)?(?<!/)>(.*?)</(?:\\w+:)?$tag>", RegexOption.DOT_MATCHES_ALL).find(xml)?.groupValues?.get(1)

    private fun blocks(xml: String, tag: String): List<String> =
        Regex("<(?:\\w+:)?$tag(?:\\s[^>]*?)?(?<!/)>(.*?)</(?:\\w+:)?$tag>", RegexOption.DOT_MATCHES_ALL).findAll(xml).map { it.groupValues[1] }.toList()

    /** 응답 가사: strLyric (GetLyric7/5 · Resemble2) 또는 output 안의 lyric (GetLyricByID2) */
    fun parseLyric(xml: String): String? {
        val raw = tagText(xml, "strLyric") ?: tagText(xml, "output")?.let { tagText(it, "lyric") } ?: tagText(xml, "lyric")
        return raw?.let(::cleanLyric)?.takeIf { it.isNotEmpty() }
    }

    /** 응답 안의 요소 이름들 (진단용, 처음 나온 순서) */
    fun tagNames(xml: String, max: Int = 16): String {
        val names = LinkedHashSet<String>()
        for (m in Regex("<([A-Za-z_][\\w.-]*:)?([A-Za-z_][\\w.-]*)[\\s/>]").findAll(xml)) {
            val n = m.groupValues[2]
            if (n != "xml" && n != "Envelope" && n != "Body") names.add(n)
            if (names.size >= max) break
        }
        return names.joinToString(",")
    }

    data class Item(val title: String, val artist: String, val album: String, val lyric: String,
                    val id: String = "", val durS: Double = 0.0)

    /** GetResembleLyric2 응답: ST_GET_RESEMBLELYRIC2_RETURN (+ 옛 ST_SEARCHLYRIC_LIST 중 strLyric 있는 것) */
    fun parseSearch(xml: String): List<Item> =
        (blocks(xml, "ST_GET_RESEMBLELYRIC2_RETURN") + blocks(xml, "ST_SEARCHLYRIC_LIST")).mapNotNull { b ->
            val ly = tagText(b, "strLyric")?.let(::cleanLyric).orEmpty()
            if (ly.isEmpty()) null else Item(
                unescape(tagText(b, "strTitle").orEmpty()).trim(), unescape(tagText(b, "strArtistName").orEmpty()).trim(),
                unescape(tagText(b, "strAlbumName").orEmpty()).trim(), ly, tagText(b, "strInfoID").orEmpty().trim())
        }

    /** GetResembleLyricList2 응답: ST_SEARCHLYRIC_LIST (lyricID · title · artist · album · playtime ms) — 가사 없음 */
    fun parseList(xml: String): List<Item> = blocks(xml, "ST_SEARCHLYRIC_LIST").mapNotNull { b ->
        val id = tagText(b, "lyricID")?.trim().orEmpty()
        if (id.isEmpty()) null else Item(
            unescape(tagText(b, "title").orEmpty()).trim(), unescape(tagText(b, "artist").orEmpty()).trim(),
            unescape(tagText(b, "album").orEmpty()).trim(), "", id,
            (tagText(b, "playtime")?.trim()?.toDoubleOrNull() ?: 0.0) / 1000.0)
    }

    // ---------------------------------------------------------- 요청 · 찾기 (전송은 밖에서 — 테스트는 고정 응답)
    fun req(method: String, body: String): HttpReq = HttpReq(URL_SVC, "POST", body, mapOf(
        "Content-Type" to "application/soap+xml; charset=utf-8; action=\"ALSongWebServer/$method\"",
        "User-Agent" to "gSOAP/2.7"), method)

    /**
     * 알송 찾기 (L1): ① mp3 MD5 → GetLyric7 (없으면 GetLyric5)  ② 검색어 변형마다 GetResembleLyric2
     *   ③ ② 가 0건이면 GetResembleLyricList2 → 최고점 항목 GetLyricByID2.  후보는 Score 로 점수.
     *   all = false: minScore 이상 후보가 나오면 멈춤 / true: 변형 모두 (다른 가사 찾기)
     *   alive = false 가 되면 (곡 넘김 · 시간 초과) 다음 요청을 보내지 않음
     */
    fun lookup(q: TrackQuery, md5: String?, encData: String, minScore: Int, http: Transport, rep: ProvReport,
               alive: () -> Boolean = { true }, all: Boolean = false, variants: List<Pair<String, String>>? = null) {
        val t0 = System.currentTimeMillis()
        try {
            fun net(r: HttpRes) = r.err == NetErr.OFFLINE || r.err == NetErr.TIMEOUT
            if (md5 != null) {
                val methods = if (encData.isNotEmpty()) listOf("GetLyric7", "GetLyric5") else listOf("GetLyric5")
                for (m in methods) {
                    if (!alive()) return
                    val r = http(req(m, lyricRequest(md5, if (m == "GetLyric7") encData else "")))
                    val ly = if (r.ok) parseLyric(r.body!!) else null
                    rep.step(m, md5, r, r.body?.let { tagNames(it) }.orEmpty(), if (ly != null) 1 else 0)
                    if (net(r)) return
                    if (ly != null) {
                        val b = r.body!!
                        rep.add(LyricCand("alsong", unescape(tagText(b, "strTitle").orEmpty()).ifEmpty { q.title },
                            unescape(tagText(b, "strArtist").orEmpty()).ifEmpty { q.artist },
                            unescape(tagText(b, "strAlbum").orEmpty()), ly, 0.0, 100, "MD5 $m"))
                        if (!all) { rep.completed = true; return }
                        break
                    }
                }
            }
            for ((t, a) in variants ?: Query.variants(q.title, q.artist)) {
                if (!alive()) return
                val r = http(req("GetResembleLyric2", searchRequest(t, a, 0, encData)))
                val items = if (r.ok) parseSearch(r.body!!) else emptyList()
                rep.step("GetResembleLyric2", "$t / $a", r, r.body?.let { tagNames(it) }.orEmpty(), items.size)
                if (net(r)) return
                for (i in items) rep.add(LyricCand("alsong", i.title, i.artist, i.album, i.lyric, 0.0,
                    Score.score(q.title, q.artist, q.album, q.durS, i.title, i.artist, i.album, i.lyric), "Resemble2"))
                if (items.isEmpty()) {
                    if (!alive()) return
                    val r2 = http(req("GetResembleLyricList2", listRequest(t, a, 1, encData)))
                    val list = if (r2.ok) parseList(r2.body!!) else emptyList()
                    rep.step("GetResembleLyricList2", "$t / $a", r2, r2.body?.let { tagNames(it) }.orEmpty(), list.size)
                    if (net(r2)) return
                    val pick = list.maxByOrNull { Score.score(q.title, q.artist, q.album, q.durS, it.title, it.artist, it.album, "", it.durS) }
                    if (pick != null) {
                        if (!alive()) return
                        val r3 = http(req("GetLyricByID2", byIdRequest(pick.id, encData)))
                        val ly = if (r3.ok) parseLyric(r3.body!!) else null
                        rep.step("GetLyricByID2", pick.id, r3, r3.body?.let { tagNames(it) }.orEmpty(), if (ly != null) 1 else 0)
                        if (net(r3)) return
                        if (ly != null) rep.add(LyricCand("alsong", pick.title, pick.artist, pick.album, ly, pick.durS,
                            Score.score(q.title, q.artist, q.album, q.durS, pick.title, pick.artist, pick.album, ly, pick.durS), "ByID2"))
                    }
                }
                if (!all && (rep.best()?.score ?: -1) >= minScore) break
            }
            rep.completed = true
        } finally {
            rep.ms = System.currentTimeMillis() - t0
        }
    }
}

/** API 26 호환 readNBytes */
fun InputStream.readNBytesCompat(n: Int): ByteArray {
    if (n <= 0) return ByteArray(0)
    val buf = ByteArray(n)
    var off = 0
    while (off < n) {
        val r = read(buf, off, n - off)
        if (r < 0) break
        off += r
    }
    return if (off == n) buf else buf.copyOf(off)
}

/** 건너뛰기 (skip 이 0 을 돌려주면 read 로) — 반환: 실제로 건너뛴 바이트 */
fun InputStream.skipFully(n: Long): Long {
    var left = n
    var buf: ByteArray? = null
    while (left > 0) {
        val s = skip(left)
        if (s > 0) { left -= s; continue }
        val b = buf ?: ByteArray(8192).also { buf = it }
        val r = read(b, 0, minOf(left, b.size.toLong()).toInt())
        if (r < 0) break
        left -= r
    }
    return n - left
}

/** 응답 읽기 (vr0.1.0.008): max 바이트를 넘으면 IOException — 잘못된 서버 응답으로 메모리가 튀지 않게 */
fun InputStream.readCapped(max: Int): ByteArray {
    val out = java.io.ByteArrayOutputStream()
    val buf = ByteArray(8192)
    var total = 0
    while (true) {
        val r = read(buf)
        if (r < 0) break
        total += r
        if (total > max) throw IOException("응답이 너무 큼 (> $max bytes)")
        out.write(buf, 0, r)
    }
    return out.toByteArray()
}
