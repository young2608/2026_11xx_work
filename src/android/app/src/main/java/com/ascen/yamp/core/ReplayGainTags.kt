package com.ascen.yamp.core

import com.ascen.yamp.domain.Recommend
import java.io.InputStream
import java.nio.charset.Charset

/** ReplayGain 태그 값 (없으면 null). gain = dB, peak = 선형 (1.0 = 0 dBFS) */
data class RgTags(
    val trackGain: Double? = null,
    val trackPeak: Double? = null,
    val albumGain: Double? = null,
    val albumPeak: Double? = null,
) {
    val isEmpty: Boolean get() = trackGain == null && albumGain == null

    /** mode: off / track / album (album 이 없으면 track 으로) → (gain, peak) */
    fun pick(mode: String): Pair<Double?, Double?> = when (mode) {
        "off" -> null to null
        "album" -> if (albumGain != null) albumGain to (albumPeak ?: trackPeak) else trackGain to trackPeak
        else -> trackGain to trackPeak
    }
}

/**
 * ReplayGain 태그 읽기 (순수 Kotlin — JVM 테스트 대상). 파일 앞부분만 읽음 (기본 512KB).
 *   - ID3v2.3 / 2.4 TXXX 프레임 (설명 REPLAYGAIN_TRACK_GAIN 등, 인코딩 0 ISO-8859-1 · 1 UTF-16 BOM · 2 UTF-16BE · 3 UTF-8)
 *     2.4 = syncsafe 프레임 크기, 2.3 = 일반 크기
 *   - FLAC "fLaC" METADATA_BLOCK_VORBIS_COMMENT (리틀 엔디언 길이), 키 대소문자 무시
 * 그 밖의 형식(APEv2, MP4, Ogg)은 미지원 → 빈 RgTags
 */
object ReplayGainTags {
    const val MAX_READ = 512 * 1024

    fun read(input: InputStream, maxBytes: Int = MAX_READ): RgTags =
        input.use { parse(readUpTo(it, maxBytes)) }

    fun parse(b: ByteArray): RgTags {
        val kv = HashMap<String, String>()
        var pos = 0
        if (b.size >= 10 && b[0] == 'I'.code.toByte() && b[1] == 'D'.code.toByte() && b[2] == '3'.code.toByte()) {
            pos = parseId3(b, kv)
        }
        // FLAC (앞에 ID3 가 붙은 경우도)
        if (b.size >= pos + 4 && String(b, pos, 4, Charsets.ISO_8859_1) == "fLaC") parseFlac(b, pos + 4, kv)
        return RgTags(
            Recommend.parseGain(kv["REPLAYGAIN_TRACK_GAIN"]), peak(kv["REPLAYGAIN_TRACK_PEAK"]),
            Recommend.parseGain(kv["REPLAYGAIN_ALBUM_GAIN"]), peak(kv["REPLAYGAIN_ALBUM_PEAK"]),
        )
    }

    /**
     * 글자 값 4개 → RgTags (vr0.1.0.010: CUE 의 REM REPLAYGAIN_* 값, 형식은 태그와 같음 "-6.50 dB" · "0.988").
     * 빈 글자 · 못 읽는 값은 null
     */
    fun fromStrings(trackGain: String?, trackPeak: String?, albumGain: String?, albumPeak: String?): RgTags = RgTags(
        Recommend.parseGain(trackGain?.takeIf { it.isNotBlank() }), peak(trackPeak?.takeIf { it.isNotBlank() }),
        Recommend.parseGain(albumGain?.takeIf { it.isNotBlank() }), peak(albumPeak?.takeIf { it.isNotBlank() }),
    )

    /** CUE 값이 있는 칸은 CUE 를, 없는 칸은 파일 태그를 (CUE 트랙 = 한 파일의 구간 → 파일 태그는 앨범 전체 값인 경우가 많음) */
    fun merge(cue: RgTags?, file: RgTags?): RgTags? {
        if (cue == null || cue.isEmpty) return file
        if (file == null) return cue
        return RgTags(cue.trackGain ?: file.trackGain, if (cue.trackGain != null) cue.trackPeak else file.trackPeak,
            cue.albumGain ?: file.albumGain, if (cue.albumGain != null) cue.albumPeak else file.albumPeak)
    }

    private fun peak(s: String?): Double? = s?.trim()?.replace(',', '.')?.toDoubleOrNull()?.takeIf { it > 0 }

    private fun readUpTo(ins: InputStream, n: Int): ByteArray {
        val buf = ByteArray(n)
        var off = 0
        while (off < n) {
            val r = ins.read(buf, off, n - off)
            if (r < 0) break
            off += r
        }
        return if (off == n) buf else buf.copyOf(off)
    }

    private fun u8(b: ByteArray, i: Int) = b[i].toInt() and 0xFF
    private fun syncsafe(b: ByteArray, i: Int) =
        ((u8(b, i) and 0x7F) shl 21) or ((u8(b, i + 1) and 0x7F) shl 14) or ((u8(b, i + 2) and 0x7F) shl 7) or (u8(b, i + 3) and 0x7F)
    private fun be32(b: ByteArray, i: Int) = (u8(b, i) shl 24) or (u8(b, i + 1) shl 16) or (u8(b, i + 2) shl 8) or u8(b, i + 3)
    private fun le32(b: ByteArray, i: Int) = u8(b, i) or (u8(b, i + 1) shl 8) or (u8(b, i + 2) shl 16) or (u8(b, i + 3) shl 24)

    /** 반환: 태그 끝 위치 (헤더+본문+footer) */
    private fun parseId3(b: ByteArray, kv: MutableMap<String, String>): Int {
        val ver = u8(b, 3)
        val flags = u8(b, 5)
        val size = syncsafe(b, 6)
        val end = minOf(b.size, 10 + size)
        val tagEnd = 10 + size + if (ver >= 4 && flags and 0x10 != 0) 10 else 0
        if (ver != 3 && ver != 4) return tagEnd     // 2.2 등 미지원
        var p = 10
        if (flags and 0x40 != 0 && p + 4 <= end) {  // 확장 헤더
            p += if (ver == 4) syncsafe(b, p) else be32(b, p) + 4
        }
        while (p + 10 <= end) {
            if (b[p].toInt() == 0) break            // padding
            val id = String(b, p, 4, Charsets.ISO_8859_1)
            if (!id.all { it in 'A'..'Z' || it in '0'..'9' }) break
            // 2.4 = syncsafe. 일부 프로그램이 2.4 에 일반 크기를 쓰므로 최상위 비트가 켜져 있으면 일반 크기로
            val fs = if (ver == 4 && (0..3).none { u8(b, p + 4 + it) and 0x80 != 0 }) syncsafe(b, p + 4) else be32(b, p + 4)
            val ds = p + 10
            if (fs <= 0 || ds + fs > end) break
            if (id == "TXXX") parseTxxx(b, ds, fs)?.let { (k, v) -> kv.putIfAbsent(k.uppercase(), v) }
            p = ds + fs
        }
        return tagEnd
    }

    private fun parseTxxx(b: ByteArray, start: Int, len: Int): Pair<String, String>? {
        if (len < 2) return null
        val enc = u8(b, start)
        val body = b.copyOfRange(start + 1, start + len)
        val wide = enc == 1 || enc == 2
        // 설명 끝(종료 문자) 찾기
        var cut = -1
        if (wide) {
            var i = 0
            while (i + 1 < body.size) {
                if (body[i].toInt() == 0 && body[i + 1].toInt() == 0) { cut = i; break }
                i += 2
            }
        } else cut = body.indexOf(0)
        if (cut < 0) return null
        val term = if (wide) 2 else 1
        val desc = decode(body.copyOfRange(0, cut), enc, null)
        val valueBytes = body.copyOfRange(cut + term, body.size)
        // UTF-16(1) 의 값은 자체 BOM 을 가짐. BOM 이 없으면 설명의 BOM 순서를 따름
        val value = decode(valueBytes, enc, bomOf(body))
        return desc.trim() to value.trimEnd('\u0000').trim()
    }

    private fun bomOf(b: ByteArray): Charset? =
        if (b.size >= 2 && u8(b, 0) == 0xFF && u8(b, 1) == 0xFE) Charsets.UTF_16LE
        else if (b.size >= 2 && u8(b, 0) == 0xFE && u8(b, 1) == 0xFF) Charsets.UTF_16BE else null

    private fun decode(raw: ByteArray, enc: Int, fallback16: Charset?): String = when (enc) {
        0 -> String(raw, Charsets.ISO_8859_1)
        1 -> {
            val bom = bomOf(raw)
            if (bom != null) String(raw, 2, raw.size - 2, bom) else String(raw, fallback16 ?: Charsets.UTF_16LE)
        }
        2 -> String(raw, Charsets.UTF_16BE)
        else -> String(raw, Charsets.UTF_8)
    }.trimEnd('\u0000')

    private fun parseFlac(b: ByteArray, start: Int, kv: MutableMap<String, String>) {
        var p = start
        while (p + 4 <= b.size) {
            val h = u8(b, p)
            val last = h and 0x80 != 0
            val type = h and 0x7F
            val len = (u8(b, p + 1) shl 16) or (u8(b, p + 2) shl 8) or u8(b, p + 3)
            val ds = p + 4
            if (type == 4 && ds + len <= b.size) { parseVorbis(b, ds, ds + len, kv); return }
            if (last) return
            p = ds + len
        }
    }

    private fun parseVorbis(b: ByteArray, start: Int, end: Int, kv: MutableMap<String, String>) {
        var p = start
        if (p + 4 > end) return
        val vlen = le32(b, p)
        p += 4
        if (vlen < 0 || p + vlen + 4 > end) return
        p += vlen
        val n = le32(b, p)
        p += 4
        for (i in 0 until n) {
            if (p + 4 > end) return
            val l = le32(b, p)
            p += 4
            if (l < 0 || p + l > end) return
            val s = String(b, p, l, Charsets.UTF_8)
            p += l
            val eq = s.indexOf('=')
            if (eq > 0) kv.putIfAbsent(s.substring(0, eq).trim().uppercase(), s.substring(eq + 1))
        }
    }
}
