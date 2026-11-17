package com.ascen.yamp.data

import com.ascen.yamp.core.ReplayGainTags
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/**
 * vr0.1.0.010 (R2 · A12): 공용 형식 표 (testdata/formats.txt) · 재생 목록 파일 읽기 (m3u · pls · xspf · wpl) · CUE REM REPLAYGAIN
 */
class FormatsPlaylistTest {
    private fun find(name: String): File {
        var d: File? = File("").absoluteFile
        while (d != null) {
            val f = File(d, "testdata/$name")
            if (f.exists()) return f
            d = d.parentFile
        }
        error("testdata/$name 를 찾을 수 없음")
    }

    // ------------------------------------------------------------ 공용 형식 표
    @Test fun formatsTableMatchesSharedFile() {
        val rows = find("formats.txt").readLines(Charsets.UTF_8).map { it.trim() }
            .filter { it.isNotEmpty() && !it.startsWith("#") }.map { it.split('|') }
        assertTrue("형식 표가 너무 적음", rows.size >= 50)
        val seen = HashSet<String>()
        for (r in rows) {
            assertEquals("열 4개: $r", 4, r.size)
            val (ext, cat, _, android) = r
            assertTrue("중복 확장자 $ext", seen.add(ext))
            val expected = when {
                cat == "cue" -> Formats.Kind.CUE
                cat == "playlist" -> Formats.Kind.PLAYLIST
                android == "1" -> Formats.Kind.AUDIO
                else -> Formats.Kind.UNSUPPORTED
            }
            assertEquals("classify(.$ext)", expected, Formats.classify("곡.$ext"))
            assertEquals("대문자 .$ext", expected, Formats.classify("/x/Y.${ext.uppercase()}"))
            assertEquals("분류 .$ext", cat, Formats.category("a.$ext"))
            assertEquals("TABLE .$ext", Formats.Row(cat, android == "1"), Formats.TABLE[ext])
        }
        // 표에 없는 확장자가 코드 표에 있으면 안 됨 (두 표가 같아야)
        assertEquals(seen, Formats.TABLE.keys)
    }

    @Test fun formatNamesForNewFormats() {
        assertEquals("AAC", Formats.formatName(null, "/b/book.m4b"))
        assertEquals("AAC", Formats.formatName(null, "ring.m4r"))
        assertEquals("WAV", Formats.formatName(null, "news.bwf"))
        assertEquals("WebM", Formats.formatName(null, "web.weba"))
        assertEquals("Opus", Formats.formatName("audio/opus", "web.webm"))        // 코덱은 MIME 으로
        assertEquals("Ogg", Formats.formatName("audio/vorbis", "web.weba"))
        assertEquals("WebM", Formats.formatName("audio/webm", "noext"))
        assertEquals(Formats.Kind.PLAYLIST, Formats.classify("noext", "audio/x-mpegurl"))
        assertEquals(Formats.Kind.UNSUPPORTED, Formats.classify("noext", "audio/x-gsm"))
        assertEquals(Formats.Kind.OTHER, Formats.classify("song.mid", "audio/midi"))
    }

    // ------------------------------------------------------------ 재생 목록 파일
    @Test fun m3u() {
        val t = "\uFEFF#EXTM3U\r\n#EXTINF:215,가수 - 첫 곡\r\nMusic/01 첫 곡.mp3\r\n\r\n# 주석\r\n/storage/emulated/0/Music/b.flac\r\nhttp://radio.example/stream\r\n"
        val e = Playlists.parse("list.m3u8", t)
        assertEquals(3, e.size)
        assertEquals(Playlists.Entry("Music/01 첫 곡.mp3", "가수 - 첫 곡", 215_000), e[0])
        assertEquals(Playlists.Entry("/storage/emulated/0/Music/b.flac"), e[1])
        assertEquals("http://radio.example/stream", e[2].location)
    }

    @Test fun pls() {
        val t = "[playlist]\nFile2=C:\\Music\\b.mp3\nTitle2=B\nFile1=a.ogg\nTitle1=A\nLength1=61.5\nLength2=-1\nNumberOfEntries=2\nVersion=2\n"
        val e = Playlists.parse("x.pls", t)
        assertEquals(listOf(Playlists.Entry("a.ogg", "A", 61_500), Playlists.Entry("C:\\Music\\b.mp3", "B", 0)), e)
    }

    @Test fun xspf() {
        val t = """<?xml version="1.0" encoding="UTF-8"?>
            <playlist version="1" xmlns="http://xspf.org/ns/0/">
              <trackList>
                <track><location>file:///storage/emulated/0/Music/%EA%B0%80%20b.mp3</location><title>T &amp; U</title><creator>가수</creator><duration>1000</duration></track>
                <track>
                  <location><![CDATA[file:///C:/Music/c.flac]]></location>
                </track>
                <track><title>위치 없음</title></track>
              </trackList>
            </playlist>"""
        val e = Playlists.parse("p.xspf", t)
        assertEquals(2, e.size)
        assertEquals(Playlists.Entry("file:///storage/emulated/0/Music/%EA%B0%80%20b.mp3", "가수 - T & U", 1000), e[0])
        assertEquals(Playlists.Loc.Path("/storage/emulated/0/Music/가 b.mp3"), Playlists.locate(e[0].location))
        assertEquals(Playlists.Loc.Path("C:/Music/c.flac"), Playlists.locate(e[1].location))
    }

    @Test fun wpl() {
        val t = """<?wpl version="1.0"?><smil><head><title>목록</title></head><body><seq>
            <media src="..\Music\a &amp; b.mp3" tid="{1}"/>
            <media src='D:\x\c.wma'/>
            </seq></body></smil>"""
        val e = Playlists.parse("w.wpl", t)
        assertEquals(listOf(Playlists.Entry("..\\Music\\a & b.mp3"), Playlists.Entry("D:\\x\\c.wma")), e)
        assertEquals(Playlists.Loc.Path("../Music/a & b.mp3"), Playlists.locate(e[0].location))
    }

    @Test fun parseByContentWhenExtUnknown() {
        assertEquals(1, Playlists.parse("noext", "[playlist]\nFile1=a.mp3\n").size)
        assertEquals("a.mp3", Playlists.parse("noext", "<smil><media src=\"a.mp3\"/></smil>")[0].location)
        assertEquals("a.mp3", Playlists.parse("noext", "a.mp3\n")[0].location)
    }

    @Test fun locateAndResolve() {
        assertEquals(Playlists.Loc.Direct("content://x/1"), Playlists.locate("content://x/1"))
        assertEquals(Playlists.Loc.Direct("https://a/b.mp3"), Playlists.locate("https://a/b.mp3"))
        assertEquals(Playlists.Loc.Path("/sd/a b.mp3"), Playlists.locate("file:///sd/a%20b.mp3"))
        assertEquals(Playlists.Loc.Path("/sd/a.mp3"), Playlists.locate("file://localhost/sd/a.mp3"))
        assertEquals("100%", Playlists.percentDecode("100%"))
        val ms1 = Track("content://media/1", "a", path = "/storage/emulated/0/Music/K/a.mp3", folder = "/storage/emulated/0/Music/K")
        val ms2 = Track("content://media/2", "a", path = "/storage/emulated/0/Other/a.mp3", folder = "/storage/emulated/0/Other")
        val saf = Track("content://doc/3", "c", path = "saf:1/Album/c.flac", folder = "saf:1/Album")
        val cue = Track(CueRef.make("content://media/9", 1, 0, 1000), "t1", path = "/storage/emulated/0/Music/K/album.flac")
        val c = listOf(ms2, ms1, saf, cue)
        assertEquals(ms1, Playlists.resolve("/storage/emulated/0/Music/K/a.mp3", c))         // 같은 절대 경로
        assertEquals(ms1, Playlists.resolve("C:/Users/me/Music/K/A.MP3", c))                  // 뒤쪽 조각이 더 많이 같은 곡
        assertEquals(ms2, Playlists.resolve("a.mp3", c))                                      // 이름만 → 앞의 것
        assertEquals(saf, Playlists.resolve("../Album/c.flac", c))
        assertNull(Playlists.resolve("album.flac", c))                                        // CUE 트랙은 맞추지 않음
        assertNull(Playlists.resolve("없는곡.mp3", c))
    }

    // ------------------------------------------------------------ CUE REM REPLAYGAIN (A12, PC cue.py 와 같은 규칙)
    @Test fun cueReplayGain() {
        val text = """
            REM GENRE Pop
            REM REPLAYGAIN_ALBUM_GAIN -7.10 dB
            REM REPLAYGAIN_ALBUM_PEAK 0.998
            REM REPLAYGAIN_TRACK_GAIN -1.00 dB
            TITLE "앨범"
            FILE "album.flac" WAVE
              TRACK 01 AUDIO
                TITLE "하나"
                REM REPLAYGAIN_TRACK_GAIN -6.50 dB
                REM REPLAYGAIN_TRACK_PEAK 0.988123
                REM REPLAYGAIN_ALBUM_GAIN +3 dB
                INDEX 01 00:00:00
              TRACK 02 AUDIO
                TITLE "둘"
                INDEX 01 03:00:00
        """.trimIndent()
        val t = Cue.parse(text)
        assertEquals(2, t.size)
        // 트랙 1: 트랙 값 = 그 TRACK 안, 앨범 값 = 첫 TRACK 앞 (TRACK 안의 ALBUM 은 무시)
        assertEquals("-6.50 dB", t[0].rgTrackGain)
        assertEquals("0.988123", t[0].rgTrackPeak)
        assertEquals("-7.10 dB", t[0].rgAlbumGain)
        assertEquals("0.998", t[0].rgAlbumPeak)
        // 트랙 2: 트랙 값 없음 (앨범 앞 TRACK_GAIN 은 물려받지 않음), 앨범 값은 물려받음
        assertEquals("", t[1].rgTrackGain)
        assertEquals("", t[1].rgTrackPeak)
        assertEquals("-7.10 dB", t[1].rgAlbumGain)
        assertEquals("Pop", t[1].genre)
        // Track.rg 로 → PlayerHolder 가 읽는 값
        assertEquals("-6.50 dB;0.988123;-7.10 dB;0.998", CueRg.text(t[0]))
        val (tg, tp, ag, ap) = CueRg.parts(CueRg.text(t[1]))
        val rg = ReplayGainTags.fromStrings(tg, tp, ag, ap)
        assertNull(rg.trackGain)
        assertEquals(-7.1, rg.albumGain!!, 1e-9)
        assertEquals(0.998, rg.albumPeak!!, 1e-9)
        assertEquals("", CueRg.text(Cue.parse("FILE \"a.wav\" WAVE\nTRACK 01 AUDIO\nINDEX 01 00:00:00\n")[0]))
        // 펼친 CUE 트랙에 실림 + 목록 저장 왕복
        val album = Track("content://m/1", "album", path = "/m/a/album.flac", folder = "/m/a", durationMs = 400_000)
        val (out, _) = CueExpand.expand(listOf("album.flac" to album), listOf(t))
        assertEquals("-6.50 dB;0.988123;-7.10 dB;0.998", out[0].rg)
        assertEquals(out[0], Track.decode(out[0].encode()))
        assertEquals(8, album.encode().split('\t').size)          // 일반 곡은 이전 형식 그대로
    }

    @Test fun rgMerge() {
        val file = ReplayGainTags.fromStrings("-3 dB", "0.9", "-4 dB", "0.95")
        val cue = ReplayGainTags.fromStrings("-6.5 dB", "0.98", "", "")
        val m = ReplayGainTags.merge(cue, file)!!
        assertEquals(-6.5, m.trackGain!!, 1e-9)
        assertEquals(0.98, m.trackPeak!!, 1e-9)
        assertEquals(-4.0, m.albumGain!!, 1e-9)
        assertEquals(0.95, m.albumPeak!!, 1e-9)
        assertEquals(file, ReplayGainTags.merge(null, file))
        assertEquals(cue, ReplayGainTags.merge(cue, null))
    }
}
