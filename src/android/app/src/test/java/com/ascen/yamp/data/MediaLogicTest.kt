package com.ascen.yamp.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/** CUE (PC 공용 벡터) · 형식 판별 · 폴더 트리 · 파형 피크 */
class MediaLogicTest {
    private fun find(name: String): File {
        var d: File? = File("").absoluteFile
        while (d != null) {
            val f = File(d, "testdata/$name")
            if (f.exists()) return f
            d = d.parentFile
        }
        error("testdata/$name 를 찾을 수 없음")
    }

    // ------------------------------------------------------------ CUE
    @Test fun cueMatchesPcVectors() {
        val tracks = Cue.parse(Cue.decode(find("cue_sample.cue").readBytes()), "")
        val exp = find("cue_cases.txt").readLines(Charsets.UTF_8).filter { it.startsWith("CUE ") }
        assertEquals(exp.size, tracks.size)
        exp.forEachIndexed { i, l ->
            val p = l.removePrefix("CUE ").split("|")
            val t = tracks[i]
            assertEquals(p[0].toInt(), t.number)
            assertEquals(p[1], t.file)
            assertEquals(p[2], t.title)
            assertEquals(p[3], t.performer)
            assertEquals(p[4], t.album)
            assertEquals(p[5].toLong(), t.startMs)
            assertEquals(p[6].toLong(), t.endMs)
            assertEquals(p[7], t.genre)
            assertEquals(p[8], t.date)
        }
    }

    @Test fun cueDecodeAndBase() {
        assertEquals(240000L + 435986L - 240000L, Cue.indexMs("07:15:74"))
        assertEquals(0L, Cue.indexMs("bad"))
        // BOM + CRLF
        val bom = byteArrayOf(0xEF.toByte(), 0xBB.toByte(), 0xBF.toByte()) + "TITLE \"앨범\"\r\nFILE \"a.wav\" WAVE\r\nTRACK 01 AUDIO\r\nINDEX 01 00:01:00\r\n".toByteArray()
        val t = Cue.parse(Cue.decode(bom), "/m/x")
        assertEquals(1, t.size)
        assertEquals("/m/x/a.wav", t[0].file)
        assertEquals("앨범", t[0].album)
        assertEquals("Track 01", t[0].title)
        assertEquals(1000L, t[0].startMs)
        // 잘못된 UTF-8 → CP949 (있으면) 또는 latin-1 — 예외 없이 글자
        val cp = byteArrayOf(0xC7.toByte(), 0xD1.toByte(), 0xB1.toByte(), 0xDB.toByte())     // "한글" (CP949)
        val s = Cue.decode(cp)
        assertTrue(s == "한글" || s.length == 4)
    }

    // ------------------------------------------------------------ 형식
    @Test fun formats() {
        assertEquals(Formats.Kind.AUDIO, Formats.classify("a.FLAC"))
        assertEquals(Formats.Kind.AUDIO, Formats.classify("/x/y/b.opus"))
        assertEquals(Formats.Kind.UNSUPPORTED, Formats.classify("c.ape"))
        assertEquals(Formats.Kind.UNSUPPORTED, Formats.classify("d.wma", "audio/x-ms-wma"))
        assertEquals(Formats.Kind.UNSUPPORTED, Formats.classify("e.aiff"))
        assertEquals(Formats.Kind.CUE, Formats.classify("album.cue"))
        assertEquals(Formats.Kind.OTHER, Formats.classify("cover.jpg", "image/jpeg"))
        assertEquals(Formats.Kind.OTHER, Formats.classify("x.lrc"))
        assertEquals(Formats.Kind.AUDIO, Formats.classify("noext", "audio/flac"))
        assertEquals(Formats.Kind.UNSUPPORTED, Formats.classify("noext", "audio/x-ape"))
        assertTrue(Formats.isSupported("song.m4a"))
        assertFalse(Formats.isSupported("song.dsf"))
        assertEquals("", Formats.ext("README"))
        assertEquals("FLAC 24bit/96kHz", Formats.label("audio/flac", 24, 96000))
        assertEquals("MP3 44.1kHz", Formats.label("audio/mpeg", 0, 44100))
        assertEquals("AAC 48kHz · 모노", Formats.label("audio/mp4a-latm", 0, 48000, 1))
        assertEquals("WAV 16bit/44.1kHz", Formats.label("audio/raw", 16, 44100, 2))
        assertEquals("OPUS", Formats.label(null, 0, 0, 0, "x.opus").uppercase())
        assertTrue(Formats.isHiRes(24, 44100))
        assertFalse(Formats.isHiRes(16, 48000))
        assertEquals(24, Formats.bitsOfPcmEncoding(21))
    }

    @Test fun cueRef() {
        val u = CueRef.make("content://media/external/audio/media/7", 2, 240000, -1)
        assertEquals("content://media/external/audio/media/7", CueRef.mediaUri(u))
        assertEquals(CueRef.Clip(2, 240000, -1), CueRef.clip(u))
        assertTrue(CueRef.isCue(u))
        assertNull(CueRef.clip("content://x/1"))
        assertEquals("content://x/1", CueRef.mediaUri("content://x/1"))
    }

    @Test fun cueExpand() {
        val sheet = Cue.parse(Cue.decode(find("cue_sample.cue").readBytes()), "")
        val album = Track("content://m/1", "album", "가수", "앨범", 600_000, "/m/a/album.flac", "/m/a")
        val other = Track("content://m/2", "solo", "", "", 1000, "/m/a/solo.mp3", "/m/a")
        val (out, n) = CueExpand.expand(listOf("Album.FLAC" to album, "solo.mp3" to other), listOf(sheet))
        assertEquals(1, n)                                   // bonus.wav 는 폴더에 없음 → 무시
        assertEquals(4, out.size)                            // CUE 3곡 + solo
        assertEquals("첫 곡", out[0].title)
        assertEquals("content://m/1", out[0].mediaUri)
        assertEquals(CueRef.Clip(1, 426, 240000), out[0].clip)
        assertEquals(240000L - 426L, out[0].durationMs)
        assertEquals("피처링 가수", out[1].artist)
        assertEquals(600_000L - 435986L, out[2].durationMs)  // 마지막 곡 = 파일 끝까지
        assertEquals("solo", out[3].title)
        assertEquals(out[1], Track.decode(out[1].encode()))  // 목록 저장 왕복
        assertEquals(listOf(other), CueExpand.expand(listOf("solo.mp3" to other), emptyList()).first)
    }

    // ------------------------------------------------------------ 폴더 트리
    @Test fun folderTree() {
        val items = listOf(
            FolderTree.Item(0, "/storage/emulated/0/Music/K-Pop", "flac", 200_000),
            FolderTree.Item(1, "/storage/emulated/0/Music/K-Pop/발라드", "mp3", 100_000),
            FolderTree.Item(2, "/storage/emulated/0/Music/K-Pop/발라드", "flac", 100_000),
            FolderTree.Item(3, "/storage/emulated/0/Music/K-Pop/댄스", "wav", 60_000),
            FolderTree.Item(4, "/storage/1234-ABCD/Music", "mp3", 3_600_000),
            FolderTree.Item(5, "saf:1/Albums/OST", "opus", 1000),
            FolderTree.Item(6, "", "mp3", 0),
        )
        val root = FolderTree.build(items, mapOf("saf:1" to "USB 음악"))
        assertEquals(listOf("(폴더 없음)", "SD·USB (1234-ABCD)", "USB 음악", "내장 저장소"), root.children.map { it.label })
        val kpop = root.find("/storage/emulated/0/Music/K-Pop")
        assertNotNull(kpop)
        kpop!!
        assertEquals(4, kpop.count)
        assertEquals(listOf(0), kpop.items(false))
        assertEquals(listOf(0, 3, 1, 2), kpop.items(true))            // 이 폴더 → 댄스 → 발라드 (이름 순)
        assertEquals(mapOf("FLAC" to 2, "MP3" to 1, "WAV" to 1), kpop.formats)
        assertEquals(listOf("내장 저장소", "Music", "K-Pop"), kpop.crumbs().map { it.label })
        assertEquals("하위 폴더 2 · 4곡 · 8분", FolderTree.summaryLine(kpop))
        assertEquals(listOf(5), root.find("saf:1/Albums")!!.items(true))
        assertEquals("1시간 0분", FolderTree.durationText(3_600_000))
        assertEquals("FLAC 2 · MP3 1 · 기타 1", FolderTree.formatSummary(kpop.formats, 2))
        assertEquals(7, root.count)
        assertNull(root.find("/nope"))
    }

    // ------------------------------------------------------------ 파형
    @Test fun wavePeaks() {
        val w = WavePeaks(4, 4_000_000)          // 4초, 버킷 1초
        val pcm = ShortArray(8) { if (it == 4) 16384 else 100 }      // 스테레오 4프레임, 1초 간격
        w.add16(pcm, pcm.size, 2, 0, 1_000_000.0)
        assertEquals(0.5f, w.peaks[2], 1e-4f)
        val n = w.normalized()
        assertEquals(1f, n[2], 1e-6f)
        val enc = WavePeaks.decode(WavePeaks.encode(n))
        assertEquals(4, enc.size)
        assertEquals(1f, enc[2], 1e-6f)
        w.addFloat(floatArrayOf(2f), 1, 1, 3_500_000, 1.0)
        assertEquals(1f, w.peaks[3], 1e-6f)
    }
}
