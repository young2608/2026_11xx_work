package com.ascen.yamp.data

import java.nio.ByteBuffer
import java.nio.charset.CharacterCodingException
import java.nio.charset.Charset
import java.nio.charset.CodingErrorAction

/**
 * CUE 시트 파서 (순수 Kotlin). PC yamp/data/cue.py 와 같은 규칙. 공용 테스트: testdata/cue_sample.cue, cue_cases.txt
 *
 * 지원: FILE / TRACK nn AUDIO / TITLE / PERFORMER / INDEX 01 mm:ss:ff (ff = 1/75초) / REM GENRE·DATE
 *       vr0.1.0.010: REM REPLAYGAIN_ALBUM_GAIN·PEAK (첫 TRACK 앞 = 앨범) · REM REPLAYGAIN_TRACK_GAIN·PEAK (TRACK 안 = 그 트랙)
 *         값은 글자 그대로 ("-6.50 dB", "0.988123", 없으면 "") — PC cue.py rg_track_gain · rg_track_peak · rg_album_gain · rg_album_peak
 *         트랙은 앨범 값을 album 칸에만 물려받음 (track 칸은 그 TRACK 안의 REM 만)
 *  - 앨범 TITLE·PERFORMER 는 트랙에 값이 없을 때 사용
 *  - 트랙 끝 = 같은 FILE 의 다음 트랙 INDEX 01, 마지막 트랙은 끝까지(-1)
 *  - 글자 인코딩: UTF-8(BOM) → CP949(MS949) → ISO-8859-1 순서로 시도
 */
object Cue {
    data class CueTrack(
        val number: Int,
        val file: String,           // base 가 있으면 base/이름, 없으면 이름 그대로
        val title: String,
        val performer: String,
        val album: String,
        val startMs: Long,
        val endMs: Long,            // -1 = 파일 끝까지
        val genre: String = "",
        val date: String = "",
        val rgTrackGain: String = "",   // PC rg_track_gain
        val rgTrackPeak: String = "",   // PC rg_track_peak
        val rgAlbumGain: String = "",   // PC rg_album_gain
        val rgAlbumPeak: String = "",   // PC rg_album_peak
    ) {
        /** ReplayGain 값이 하나라도 있음 */
        val hasRg: Boolean get() = rgTrackGain.isNotEmpty() || rgAlbumGain.isNotEmpty()
    }

    private val INDEX = Regex("""(\d+):(\d{1,2}):(\d{1,2})""")
    private val WS = Regex("""\s+""")

    private fun splitWs(s: String): List<String> = s.trim().split(WS).filter { it.isNotEmpty() }

    /** Python line.split(None, 1)[1] 처럼 첫 단어 뒤 나머지 */
    private fun rest(line: String): String {
        val t = line.trim()
        val i = t.indexOfFirst { it.isWhitespace() }
        return if (i < 0) "" else t.substring(i).trim()
    }

    private fun arg(line: String): String {
        val r = rest(line)
        if (r.startsWith("\"")) {
            val end = r.indexOf('"', 1)
            return if (end > 0) r.substring(1, end) else r.substring(1)
        }
        return splitWs(r).firstOrNull() ?: ""
    }

    fun indexMs(text: String): Long {
        val m = INDEX.find(text) ?: return 0
        val (mm, ss, ff) = m.destructured
        return mm.toLong() * 60000 + ss.toLong() * 1000 + (ff.toLong() * 1000) / 75
    }

    /** CP949 계열 문자셋 (JVM: MS949 / x-windows-949, Android ICU: windows-949 등). 없으면 null */
    private val korean: Charset? by lazy {
        listOf("MS949", "x-windows-949", "windows-949", "CP949", "EUC-KR").firstNotNullOfOrNull { n ->
            runCatching { if (Charset.isSupported(n)) Charset.forName(n) else null }.getOrNull()
        }
    }

    private fun strict(raw: ByteArray, cs: Charset): String? = try {
        cs.newDecoder().onMalformedInput(CodingErrorAction.REPORT).onUnmappableCharacter(CodingErrorAction.REPORT)
            .decode(ByteBuffer.wrap(raw)).toString()
    } catch (_: CharacterCodingException) {
        null
    }

    fun decode(raw: ByteArray): String {
        strict(raw, Charsets.UTF_8)?.let { return it.removePrefix("﻿") }
        korean?.let { k -> strict(raw, k)?.let { return it } }
        return String(raw, Charsets.ISO_8859_1)
    }

    private class Tmp(val number: Int, val file: String) {
        var title = ""
        var performer = ""
        var start: Long? = null
        var rgGain = ""
        var rgPeak = ""
    }

    /** REM 값: 앞뒤 공백 · 따옴표 제거 */
    private fun remValue(v: String): String = v.trim().trim('"').trim()

    fun parse(text: String, baseDir: String = ""): List<CueTrack> {
        var album = ""
        var performer = ""
        var genre = ""
        var date = ""
        var albumGain = ""
        var albumPeak = ""
        var curFile = ""
        val tracks = ArrayList<Tmp>()
        var t: Tmp? = null
        for (raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")) {
            val line = raw.trim()
            if (line.isEmpty()) continue
            val parts = splitWs(line)
            when (parts[0].uppercase()) {
                "FILE" -> {
                    val name = arg(line)
                    curFile = if (baseDir.isNotEmpty() && !name.startsWith("/") && !Regex("^[A-Za-z]:[\\\\/]").containsMatchIn(name))
                        baseDir.trimEnd('/') + "/" + name else name
                }
                "TRACK" -> {
                    if (parts.size >= 3 && parts[2].uppercase() != "AUDIO") { t = null; continue }
                    val num = if (parts.size > 1 && parts[1].isNotEmpty() && parts[1].all { it.isDigit() }) parts[1].toInt() else tracks.size + 1
                    val n = Tmp(num, curFile)
                    tracks.add(n)
                    t = n
                }
                "TITLE" -> { val cur = t; if (cur == null) album = arg(line) else cur.title = arg(line) }
                "PERFORMER" -> { val cur = t; if (cur == null) performer = arg(line) else cur.performer = arg(line) }
                "INDEX" -> {
                    val cur = t
                    if (cur != null && parts.size >= 3 && parts[1] == "01") cur.start = indexMs(parts[2])
                }
                "REM" -> {
                    // Python line.split(None, 2): REM KEY 나머지
                    val after = rest(line)
                    val key = splitWs(after).firstOrNull()?.uppercase()
                    val value = rest(after)
                    val cur = t
                    if (key != null && value.isNotEmpty()) {
                        if (cur == null) when (key) {
                            "GENRE" -> genre = remValue(value)
                            "DATE" -> date = remValue(value)
                            "REPLAYGAIN_ALBUM_GAIN" -> albumGain = remValue(value)
                            "REPLAYGAIN_ALBUM_PEAK" -> albumPeak = remValue(value)
                        } else when (key) {
                            "REPLAYGAIN_TRACK_GAIN" -> cur.rgGain = remValue(value)
                            "REPLAYGAIN_TRACK_PEAK" -> cur.rgPeak = remValue(value)
                        }
                    }
                }
            }
        }
        val valid = tracks.filter { it.start != null }
        return valid.mapIndexed { i, x ->
            val nxt = valid.getOrNull(i + 1)
            val end = if (nxt != null && nxt.file == x.file) nxt.start!! else -1L
            CueTrack(x.number, x.file, x.title.ifEmpty { "Track %02d".format(x.number) },
                x.performer.ifEmpty { performer }, album, x.start!!, end, genre, date,
                x.rgGain, x.rgPeak, albumGain, albumPeak)
        }
    }
}
