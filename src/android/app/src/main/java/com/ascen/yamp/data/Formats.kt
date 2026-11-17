package com.ascen.yamp.data

/**
 * 음원 형식 판별 (순수 Kotlin — JVM 테스트 대상).
 * Android 는 ExoPlayer 기본 추출기·기기 디코더만 사용 (FFmpeg 확장 없음, f08 결정 (a)).
 * vr0.1.0.010: 공용 형식 표 testdata/formats.txt 와 똑같이 (확장자 → 분류 · Android 재생 가능) — FormatsTableTest 가 모든 줄 확인
 *   재생 목록 파일(m3u · m3u8 · pls · xspf · wpl)은 Kind.PLAYLIST → 파일 추가 때 안의 곡으로 펼침 (data/Playlists.kt)
 */
object Formats {
    enum class Kind { AUDIO, UNSUPPORTED, CUE, PLAYLIST, OTHER }

    /** 형식 표 한 줄: 분류 (music voice book web bigwav hires movie tracker playlist cue) · Android 재생 가능 */
    data class Row(val category: String, val android: Boolean)

    /** testdata/formats.txt 의 Android 열 그대로 (1 = 재생 목록에 넣음, 0 = 빼고 알림) */
    val TABLE: Map<String, Row> = linkedMapOf(
        "mp3" to Row("music", true), "mp2" to Row("music", false), "flac" to Row("music", true),
        "ogg" to Row("music", true), "oga" to Row("music", true), "opus" to Row("music", true),
        "m4a" to Row("music", true), "mp4" to Row("music", true), "aac" to Row("music", true),
        "adts" to Row("music", true), "alac" to Row("music", false), "wav" to Row("music", true),
        "aif" to Row("music", false), "aiff" to Row("music", false), "aifc" to Row("music", false),
        "wma" to Row("music", false), "ape" to Row("music", false), "wv" to Row("music", false),
        "tta" to Row("music", false), "dsf" to Row("hires", false), "dff" to Row("hires", false),
        "mka" to Row("music", true), "mpc" to Row("music", false), "caf" to Row("music", false),
        "spx" to Row("voice", false), "tak" to Row("hires", false),
        "3gp" to Row("voice", true), "3ga" to Row("voice", true), "amr" to Row("voice", true),
        "awb" to Row("voice", true), "qcp" to Row("voice", false), "gsm" to Row("voice", false),
        "au" to Row("voice", false), "snd" to Row("voice", false), "voc" to Row("voice", false),
        "m4b" to Row("book", true), "m4r" to Row("book", true),
        "webm" to Row("web", true), "weba" to Row("web", true),
        "w64" to Row("bigwav", false), "rf64" to Row("bigwav", false), "bwf" to Row("bigwav", true),
        "ac3" to Row("movie", false), "eac3" to Row("movie", false), "dts" to Row("movie", false),
        "thd" to Row("movie", false), "mlp" to Row("movie", false), "ra" to Row("movie", false), "rm" to Row("movie", false),
        "mod" to Row("tracker", false), "xm" to Row("tracker", false), "it" to Row("tracker", false), "s3m" to Row("tracker", false),
        "m3u" to Row("playlist", true), "m3u8" to Row("playlist", true), "pls" to Row("playlist", true),
        "xspf" to Row("playlist", true), "wpl" to Row("playlist", true),
        "cue" to Row("cue", true),
    )

    private val AUDIO_CATS = setOf("music", "voice", "book", "web", "bigwav", "hires", "movie", "tracker")
    val SUPPORTED: Set<String> = TABLE.filter { it.value.category in AUDIO_CATS && it.value.android }.keys
    val UNSUPPORTED: Set<String> = TABLE.filter { it.value.category in AUDIO_CATS && !it.value.android }.keys
    val PLAYLISTS: Set<String> = TABLE.filter { it.value.category == "playlist" }.keys

    private val BAD_MIME = setOf("audio/x-ms-wma", "audio/x-ape", "audio/ape", "audio/x-monkeys-audio", "audio/aiff",
        "audio/x-aiff", "audio/x-wavpack", "audio/wavpack", "audio/x-tta", "audio/x-dsf", "audio/x-dff", "audio/dsd",
        "audio/ac3", "audio/vnd.dts", "audio/x-musepack", "audio/x-caf", "audio/eac3", "audio/x-gsm", "audio/basic",
        "audio/qcelp", "audio/x-realaudio", "audio/vnd.rn-realaudio", "audio/x-pn-realaudio", "audio/x-mod", "audio/x-xm",
        "audio/x-it", "audio/x-s3m", "audio/x-voc", "audio/x-w64", "audio/vnd.dolby.mlp", "audio/true-hd")
    /** 재생 목록 MIME (확장자 없는 SAF 문서) */
    val PLAYLIST_MIME = setOf("audio/x-mpegurl", "audio/mpegurl", "application/x-mpegurl", "application/vnd.apple.mpegurl",
        "audio/x-scpls", "application/pls+xml", "application/xspf+xml", "application/vnd.ms-wpl")

    fun ext(name: String): String {
        val n = name.substringAfterLast('/')
        val i = n.lastIndexOf('.')
        return if (i <= 0 || i == n.length - 1) "" else n.substring(i + 1).lowercase()
    }

    /** 형식 표의 분류 (모르는 확장자 null) */
    fun category(name: String): String? = TABLE[ext(name)]?.category

    /** 파일 이름 + (있으면) MIME 으로 분류. 확장자가 우선, 모르는 확장자는 MIME 으로 */
    fun classify(name: String, mime: String? = null): Kind {
        val e = ext(name)
        if (e == "cue") return Kind.CUE
        if (e in PLAYLISTS) return Kind.PLAYLIST
        if (e in SUPPORTED) return Kind.AUDIO
        if (e in UNSUPPORTED) return Kind.UNSUPPORTED
        val m = mime?.lowercase()?.substringBefore(';')?.trim().orEmpty()
        if (m in PLAYLIST_MIME) return Kind.PLAYLIST
        if (m in BAD_MIME) return Kind.UNSUPPORTED
        if (m.startsWith("audio/") && e.isEmpty()) return Kind.AUDIO      // 확장자 없는 문서(SAF) — MIME 만 믿음
        if (m.startsWith("audio/")) return if (e in setOf("mid", "midi", "kar", "xmf", "imy", "ota", "rtttl")) Kind.OTHER else Kind.AUDIO
        return Kind.OTHER
    }

    fun isSupported(name: String, mime: String? = null): Boolean = classify(name, mime) == Kind.AUDIO

    /** 표시용 형식 이름: MIME 우선, 없으면 확장자 */
    fun formatName(mime: String?, name: String = ""): String {
        val m = mime?.lowercase().orEmpty()
        val byMime = when {
            m.contains("flac") -> "FLAC"
            m == "audio/mpeg" || m.contains("mp3") || m == "audio/mpeg-l3" -> "MP3"
            m.contains("mp4a") || m.contains("aac") || m == "audio/mp4" -> "AAC"
            m.contains("opus") -> "Opus"
            m.contains("vorbis") || m == "audio/ogg" -> "Ogg"
            m.contains("raw") || m.contains("wav") || m.contains("pcm") -> "WAV"
            m.contains("alac") -> "ALAC"
            m.contains("amr") -> "AMR"
            m.contains("matroska") -> "MKA"
            m.contains("webm") -> "WebM"
            else -> ""
        }
        if (byMime.isNotEmpty()) return byMime
        return when (val e = ext(name)) {
            "m4a", "mp4", "m4b", "m4r", "aac", "adts" -> "AAC"     // m4b 오디오북 · m4r 벨소리 = AAC
            "bwf" -> "WAV"                                          // 방송용 WAV
            "webm", "weba" -> "WebM"                                // 코덱(Opus/Vorbis)은 MIME 으로
            "oga", "ogg" -> "Ogg"
            "opus" -> "Opus"
            "3gp", "3ga", "awb", "amr" -> "AMR"
            "" -> "?"
            else -> e.uppercase()
        }
    }

    /** 형식 표시: "FLAC 24bit/96kHz", "MP3 44.1kHz", "AAC 48kHz · 모노". bits/rate 0 = 모름 */
    fun label(mime: String?, bits: Int, sampleRate: Int, channels: Int = 0, name: String = ""): String {
        val sb = StringBuilder(formatName(mime, name))
        val kHz = if (sampleRate > 0) {
            val k = sampleRate / 1000.0
            if (sampleRate % 1000 == 0) "${sampleRate / 1000}kHz" else "%.1fkHz".format(java.util.Locale.ROOT, k)
        } else ""
        when {
            bits > 0 && kHz.isNotEmpty() -> sb.append(" ${bits}bit/").append(kHz)
            kHz.isNotEmpty() -> sb.append(' ').append(kHz)
            bits > 0 -> sb.append(" ${bits}bit")
        }
        if (channels == 1) sb.append(" · 모노") else if (channels > 2) sb.append(" · ${channels}ch")
        return sb.toString()
    }

    /** Hi-Res 배지 (24bit 이상 또는 48kHz 초과) */
    fun isHiRes(bits: Int, sampleRate: Int): Boolean = bits >= 24 || sampleRate > 48000

    /** PCM 인코딩 상수(android.media.AudioFormat ENCODING_*) → 비트 수 */
    fun bitsOfPcmEncoding(enc: Int): Int = when (enc) {
        2 -> 16      // ENCODING_PCM_16BIT
        3 -> 8       // ENCODING_PCM_8BIT
        4 -> 32      // ENCODING_PCM_FLOAT
        21 -> 24     // ENCODING_PCM_24BIT_PACKED
        22 -> 32     // ENCODING_PCM_32BIT
        else -> 0
    }
}

/**
 * CUE 트랙 = 한 파일의 구간. 목록·DB 에서 서로 다른 곡으로 다루기 위해 uri 뒤에 표시를 붙임:
 *   <실제 uri>#yampcue=<번호>:<시작ms>:<끝ms>   (끝 -1 = 파일 끝까지)
 * 재생·태그·앨범아트는 mediaUri (표시를 뗀 실제 uri) 사용.
 */
object CueRef {
    const val TAG = "#yampcue="

    data class Clip(val number: Int, val startMs: Long, val endMs: Long)

    fun make(base: String, number: Int, startMs: Long, endMs: Long): String = "$base$TAG$number:$startMs:$endMs"

    fun mediaUri(uri: String): String {
        val i = uri.indexOf(TAG)
        return if (i < 0) uri else uri.substring(0, i)
    }

    fun clip(uri: String): Clip? {
        val i = uri.indexOf(TAG)
        if (i < 0) return null
        val p = uri.substring(i + TAG.length).split(':')
        if (p.size < 3) return null
        val n = p[0].toIntOrNull() ?: return null
        val s = p[1].toLongOrNull() ?: return null
        val e = p[2].toLongOrNull() ?: return null
        return Clip(n, s, e)
    }

    fun isCue(uri: String): Boolean = uri.contains(TAG)
}
