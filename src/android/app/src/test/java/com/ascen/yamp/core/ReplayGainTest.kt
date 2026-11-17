package com.ascen.yamp.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream

/** 합성 ID3 / FLAC 바이트로 ReplayGain 태그 읽기 확인 */
class ReplayGainTest {
    private fun ss(n: Int) = byteArrayOf(((n shr 21) and 0x7F).toByte(), ((n shr 14) and 0x7F).toByte(),
        ((n shr 7) and 0x7F).toByte(), (n and 0x7F).toByte())
    private fun be(n: Int) = byteArrayOf((n ushr 24).toByte(), (n ushr 16).toByte(), (n ushr 8).toByte(), n.toByte())
    private fun le(n: Int) = byteArrayOf(n.toByte(), (n ushr 8).toByte(), (n ushr 16).toByte(), (n ushr 24).toByte())

    private fun txxx(enc: Int, desc: String, value: String): ByteArray {
        val o = ByteArrayOutputStream()
        o.write(enc)
        when (enc) {
            0 -> { o.write(desc.toByteArray(Charsets.ISO_8859_1)); o.write(0); o.write(value.toByteArray(Charsets.ISO_8859_1)) }
            1 -> {
                o.write(byteArrayOf(0xFF.toByte(), 0xFE.toByte())); o.write(desc.toByteArray(Charsets.UTF_16LE)); o.write(0); o.write(0)
                o.write(byteArrayOf(0xFF.toByte(), 0xFE.toByte())); o.write(value.toByteArray(Charsets.UTF_16LE))
            }
            else -> { o.write(desc.toByteArray(Charsets.UTF_8)); o.write(0); o.write(value.toByteArray(Charsets.UTF_8)) }
        }
        return o.toByteArray()
    }

    private fun id3(ver: Int, frames: List<Pair<String, ByteArray>>, padding: Int = 64): ByteArray {
        val body = ByteArrayOutputStream()
        for ((id, data) in frames) {
            body.write(id.toByteArray(Charsets.ISO_8859_1))
            body.write(if (ver == 4) ss(data.size) else be(data.size))
            body.write(byteArrayOf(0, 0))
            body.write(data)
        }
        body.write(ByteArray(padding))
        val b = body.toByteArray()
        return "ID3".toByteArray() + byteArrayOf(ver.toByte(), 0, 0) + ss(b.size) + b +
            byteArrayOf(0xFF.toByte(), 0xFB.toByte(), 0x90.toByte(), 0x64) + ByteArray(1000)
    }

    @Test fun id3v24Utf8AndLatin1() {
        val f = id3(4, listOf(
            "TIT2" to byteArrayOf(3) + "제목".toByteArray(),
            "TXXX" to txxx(3, "REPLAYGAIN_TRACK_GAIN", "-6.52 dB"),
            "TXXX" to txxx(0, "replaygain_track_peak", "0.988"),
            "TXXX" to txxx(3, "REPLAYGAIN_ALBUM_GAIN", "-7.10 dB"),
        ))
        val r = ReplayGainTags.read(ByteArrayInputStream(f))
        assertEquals(-6.52, r.trackGain!!, 1e-9)
        assertEquals(0.988, r.trackPeak!!, 1e-9)
        assertEquals(-7.10, r.albumGain!!, 1e-9)
        assertNull(r.albumPeak)
        assertEquals(-7.10 to 0.988, r.pick("album"))
        assertEquals(null to null, r.pick("off"))
    }

    @Test fun id3v23Utf16() {
        // 2.3 = 일반 크기: 200 바이트 이상 프레임으로 syncsafe 와 차이 나게
        val big = txxx(1, "COMMENTISH", "x".repeat(150))
        val f = id3(3, listOf("TXXX" to big, "TXXX" to txxx(1, "REPLAYGAIN_TRACK_GAIN", "+3.10 dB"),
            "TXXX" to txxx(1, "REPLAYGAIN_TRACK_PEAK", "0.95")))
        val r = ReplayGainTags.parse(f)
        assertEquals(3.10, r.trackGain!!, 1e-9)
        assertEquals(0.95, r.trackPeak!!, 1e-9)
        assertEquals(3.10 to 0.95, r.pick("album"))   // album 없음 → track
    }

    private fun flac(comments: List<String>, withPadFirst: Boolean = true): ByteArray {
        val o = ByteArrayOutputStream()
        o.write("fLaC".toByteArray())
        // STREAMINFO (34 바이트)
        o.write(byteArrayOf(0, 0, 0, 34)); o.write(ByteArray(34))
        if (withPadFirst) { o.write(byteArrayOf(1, 0, 0, 8)); o.write(ByteArray(8)) }
        val vc = ByteArrayOutputStream()
        val vendor = "reference libFLAC".toByteArray()
        vc.write(le(vendor.size)); vc.write(vendor)
        vc.write(le(comments.size))
        for (c in comments) { val b = c.toByteArray(Charsets.UTF_8); vc.write(le(b.size)); vc.write(b) }
        val v = vc.toByteArray()
        o.write(byteArrayOf((0x80 or 4).toByte(), (v.size shr 16).toByte(), (v.size shr 8).toByte(), v.size.toByte()))
        o.write(v)
        o.write(ByteArray(100))
        return o.toByteArray()
    }

    @Test fun flacVorbisComment() {
        val r = ReplayGainTags.parse(flac(listOf("TITLE=노래", "replaygain_track_gain=-1.00 dB",
            "REPLAYGAIN_TRACK_PEAK=1.2", "Replaygain_Album_Gain=−8 dB", "REPLAYGAIN_ALBUM_PEAK=0.5")))
        assertEquals(-1.0, r.trackGain!!, 1e-9)
        assertEquals(1.2, r.trackPeak!!, 1e-9)
        assertEquals(-8.0, r.albumGain!!, 1e-9)
        assertEquals(0.5, r.albumPeak!!, 1e-9)
        // ID3 가 앞에 붙은 FLAC
        val withId3 = "ID3".toByteArray() + byteArrayOf(4, 0, 0) + ss(20) + ByteArray(20) + flac(listOf("REPLAYGAIN_TRACK_GAIN=2"), false)
        assertEquals(2.0, ReplayGainTags.parse(withId3).trackGain!!, 1e-9)
    }

    @Test fun noTagsAndGarbage() {
        assertTrue(ReplayGainTags.parse(ByteArray(0)).isEmpty)
        assertTrue(ReplayGainTags.parse(ByteArray(5000) { (it * 31).toByte() }).isEmpty)
        // 잘린 ID3 (크기가 실제보다 큼)
        val cut = id3(4, listOf("TXXX" to txxx(3, "REPLAYGAIN_TRACK_GAIN", "-3 dB"))).copyOf(30)
        assertTrue(ReplayGainTags.parse(cut).isEmpty)
        assertTrue(ReplayGainTags.read(ByteArrayInputStream(id3(4, emptyList())), 16).isEmpty)
    }
}
