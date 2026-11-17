package com.ascen.yamp.lyrics

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test
import java.io.ByteArrayInputStream
import java.security.MessageDigest

/** PC tests/test_core.py 와 같은 케이스 → 양쪽 결과 일치 확인 */
class LyricsTest {
    private val sample = """
        [ti:노래]
        [ar:가수]
        [offset:+200]
        [00:01.00]첫 줄
        [00:05.50][00:20.50]반복 줄
        [00:10.123]세 번째
        [00:10.123]third (번역)
        [00:15]초만
        [01:02:50]콜론 소수
    """.trimIndent()

    @Test fun parseBasic() {
        val ly = Lrc.parse(sample)
        assertTrue(ly.synced)
        assertEquals("노래", ly.meta["ti"])
        assertEquals(listOf(800L, 5300L, 9923L, 14800L, 20300L, 62300L), ly.blocks.map { it.tMs })
        assertEquals(listOf("세 번째", "third (번역)"), ly.blocks[2].lines)
    }

    @Test fun indexAt() {
        val ly = Lrc.parse("[00:01.00]a\n[00:02.00]b\n[00:03.00]c")
        assertEquals(-1, ly.indexAt(0))
        assertEquals(0, ly.indexAt(1000))
        assertEquals(1, ly.indexAt(2999))
        assertEquals(2, ly.indexAt(99999))
    }

    @Test fun fracVariants() {
        assertEquals(listOf(1500L, 2500L, 3500L), Lrc.parse("[00:01.5]a\n[00:02.50]b\n[00:03.500]c").blocks.map { it.tMs })
    }

    @Test fun plainAndEmpty() {
        val ly = Lrc.parse("\n\n가사 한 줄\n두 번째\n\n")
        assertTrue(!ly.synced && ly.blocks.size == 2 && ly.indexAt(5000) == -1)
        assertTrue(Lrc.parse("").isEmpty())
    }

    @Test fun roundTrip() {
        val ly = Lrc.parse("[00:01.00]a\n[00:01.00]b\n[00:02.30]c")
        assertEquals(ly.blocks, Lrc.parse(ly.toLrc()).blocks)
    }

    private fun fakeMp3(withId3: Boolean, junk: Int): Pair<ByteArray, ByteArray> {
        val body = byteArrayOf(0xFF.toByte(), 0xFB.toByte(), 0x90.toByte(), 0x64) + ByteArray(200000) { ((it * 7) % 256).toByte() }
        var head = ByteArray(0)
        if (withId3) {
            val size = 300
            head = "ID3".toByteArray() + byteArrayOf(3, 0, 0,
                ((size shr 21) and 0x7F).toByte(), ((size shr 14) and 0x7F).toByte(),
                ((size shr 7) and 0x7F).toByte(), (size and 0x7F).toByte()) + ByteArray(size)
        }
        return (head + ByteArray(junk) + body) to body
    }

    private fun md5(b: ByteArray, n: Int) = MessageDigest.getInstance("MD5").digest(b.copyOf(n)).joinToString("") { "%02x".format(it) }

    @Test fun alsongMd5SkipsId3() {
        val (file, body) = fakeMp3(true, 7)
        assertEquals(md5(body, Alsong.MD5_LEN), Alsong.audioMd5(ByteArrayInputStream(file)))
        val (f2, b2) = fakeMp3(false, 0)
        assertEquals(md5(b2, Alsong.MD5_LEN), Alsong.audioMd5(ByteArrayInputStream(f2)))
    }

    @Test fun alsongKnownOffset() {
        val head = "ID3".toByteArray() + byteArrayOf(4, 0, 0, 0, 0, 0, 10) + ByteArray(10) + byteArrayOf(0, 0, 0xFF.toByte(), 0xFB.toByte())
        assertEquals(22, Alsong.audioStartOffset(head))
    }

    @Test fun alsongRequests() {
        assertTrue(Alsong.lyricRequest("abc").contains("<ns1:GetLyric5><ns1:stQuery><ns1:strChecksum>abc</ns1:strChecksum>"))
        assertTrue(Alsong.lyricRequest("abc", "ENC").contains("<ns1:GetLyric7><ns1:encData>ENC</ns1:encData>"))
        assertTrue(Alsong.searchRequest("제목 & <x>", "가수").contains("제목 &amp; &lt;x&gt;"))
        assertTrue(Alsong.searchRequest("a", "b", 0, "ENC").contains("<ns1:GetResembleLyric2><ns1:encData>ENC</ns1:encData><ns1:stQuery>"))
    }

    private val resp = """<?xml version="1.0" encoding="utf-8"?><soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">
<soap:Body><GetLyric5Response xmlns="ALSongWebServer"><GetLyric5Result>true</GetLyric5Result>
<output><strInfoID>1</strInfoID><strTitle>노래</strTitle>
<strLyric>[00:01.00]첫 줄&lt;br&gt;[00:02.00]둘째 줄&lt;br&gt;[00:02.00]second</strLyric></output>
</GetLyric5Response></soap:Body></soap:Envelope>"""

    /** vr0.1.0.011: 검색 응답은 실제 태그 이름 (testdata/alsong_*.xml) 으로 LyricsSearchTest 에서 확인 */
    @Test fun alsongParse() {
        val ly = Lrc.parse(Alsong.parseLyric(resp))
        assertEquals(listOf("둘째 줄", "second"), ly.blocks[1].lines)
        assertNull(Alsong.parseLyric("<a><strLyric></strLyric></a>"))
    }

    // ------------------------------------------------ vr0.1.0.008: ID3 본문 건너뛰기 · 응답 크기 상한

    /** vr0.1.0.007 까지의 방법 (태그 전체를 읽음) — 새 audioMd5 와 같은 결과여야 함 */
    private fun oldMd5(file: ByteArray): String? {
        val ins = ByteArrayInputStream(file)
        val first = ins.readNBytesCompat(10)
        val sz = if (first.size >= 10 && first[0] == 'I'.code.toByte() && first[1] == 'D'.code.toByte() && first[2] == '3'.code.toByte())
            (((first[6].toInt() and 0x7F) shl 21) or ((first[7].toInt() and 0x7F) shl 14) or ((first[8].toInt() and 0x7F) shl 7) or
                (first[9].toInt() and 0x7F)) + if (first[5].toInt() and 0x10 != 0) 10 else 0 else -1
        val all = first + ins.readNBytesCompat((if (sz >= 0) 10 + sz else 0) + 65538 + Alsong.MD5_LEN - first.size)
        val start = Alsong.audioStartOffset(all)
        if (all.size - start < 1024) return null
        return MessageDigest.getInstance("MD5").digest(all.copyOfRange(start, start + minOf(Alsong.MD5_LEN, all.size - start)))
            .joinToString("") { "%02x".format(it) }
    }

    private fun id3(size: Int, footer: Boolean = false): ByteArray = "ID3".toByteArray() +
        byteArrayOf(4, 0, if (footer) 0x10 else 0, ((size shr 21) and 0x7F).toByte(), ((size shr 14) and 0x7F).toByte(),
            ((size shr 7) and 0x7F).toByte(), (size and 0x7F).toByte()) + ByteArray(size + if (footer) 10 else 0) { (it % 251).toByte() }

    /** skip() 이 늘 0 을 돌려주는 스트림 (일부 ContentResolver 스트림) */
    private class NoSkip(b: ByteArray) : java.io.InputStream() {
        private val d = ByteArrayInputStream(b)
        override fun read(): Int = d.read()
        override fun read(b: ByteArray, off: Int, len: Int): Int = d.read(b, off, len)
        override fun skip(n: Long): Long = 0
    }

    @Test fun alsongMd5SameAsFullRead() {
        val body = byteArrayOf(0, 0, 0xFF.toByte(), 0xFB.toByte(), 0x90.toByte(), 0x64) + ByteArray(300_000) { ((it * 13) % 256).toByte() }
        val cases = listOf(
            id3(3_000_000) + body,                  // 앨범아트가 큰 태그 (3MB) — 이제 메모리에 읽지 않음
            id3(500, footer = true) + ByteArray(5) + body,
            id3(0) + body,
            body,
            id3(2000) + ByteArray(500),             // 오디오가 짧음 → null
            id3(1_000_000).copyOf(5000),            // 태그 크기가 파일보다 큼 → null
            ByteArray(4),
        )
        for ((n, f) in cases.withIndex()) {
            val exp = oldMd5(f)
            assertEquals("case $n", exp, Alsong.audioMd5(ByteArrayInputStream(f)))
            assertEquals("case $n noskip", exp, Alsong.audioMd5(NoSkip(f)))
        }
        assertNull(oldMd5(cases[4]))
        assertNull(oldMd5(cases[5]))
    }

    @Test fun cappedRead() {
        val b = ByteArray(10_000) { it.toByte() }
        assertTrue(b.contentEquals(ByteArrayInputStream(b).readCapped(10_000)))
        assertTrue(ByteArrayInputStream(ByteArray(0)).readCapped(10).isEmpty())
        try {
            ByteArrayInputStream(b).readCapped(9_999)
            fail("상한을 넘으면 IOException")
        } catch (_: java.io.IOException) {
        }
        assertEquals(1234L, ByteArrayInputStream(b).skipFully(1234))
        assertEquals(10_000L, NoSkip(b).skipFully(20_000))
    }
}
