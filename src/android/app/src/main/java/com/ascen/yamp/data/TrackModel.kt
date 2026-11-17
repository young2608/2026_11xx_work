package com.ascen.yamp.data

/**
 * 곡 모델 (순수 Kotlin — JVM 테스트 대상). vr0.1.0.006: Track.kt 에서 분리 (MediaScanner 는 Track.kt 에 남음)
 * CUE 트랙은 uri = CueRef.make(실제 uri, 번호, 시작, 끝) → mediaUri 로 실제 파일, clip 으로 구간
 */
data class Track(
    val uri: String,
    val title: String,
    val artist: String = "",
    val album: String = "",
    val durationMs: Long = 0,
    val path: String = "",          // MediaStore DATA (있을 때만, .lrc 탐색용)
    val folder: String = "",
    val genre: String = "",         // 라이브러리·추천용 (vr0.1.0.004)
    /** vr0.1.0.010 (A12): CUE 의 REM REPLAYGAIN 값 "트랙gain;트랙peak;앨범gain;앨범peak" (CueRg.text) — 일반 곡은 "" */
    val rg: String = "",
) {
    val display: String get() = if (artist.isNotBlank()) "$artist - $title" else title
    /** 재생·태그·앨범아트용 실제 uri (CUE 표시 제거) */
    val mediaUri: String get() = CueRef.mediaUri(uri)
    /** CUE 구간 (일반 곡은 null) */
    val clip: CueRef.Clip? get() = CueRef.clip(uri)
    /** 탭 구분자로 한 줄 저장 (rg 는 있을 때만 9번째 칸 — 일반 곡은 이전 버전과 같은 줄) */
    fun encode(): String = (listOf(uri, title, artist, album, durationMs.toString(), path, folder, genre) +
        (if (rg.isNotEmpty()) listOf(rg) else emptyList()))
        .joinToString("\t") { it.replace('\t', ' ').replace('\n', ' ') }

    companion object {
        fun decode(line: String): Track? {
            val p = line.split('\t')
            if (p.size < 2 || p[0].isBlank()) return null
            return Track(p[0], p[1], p.getOrElse(2) { "" }, p.getOrElse(3) { "" },
                p.getOrElse(4) { "0" }.toLongOrNull() ?: 0, p.getOrElse(5) { "" }, p.getOrElse(6) { "" }, p.getOrElse(7) { "" },
                p.getOrElse(8) { "" })
        }
    }
}

fun fmtTime(ms: Long): String {
    if (ms < 0) return "--:--"
    val s = ms / 1000
    return if (s >= 3600) "%d:%02d:%02d".format(s / 3600, s / 60 % 60, s % 60) else "%d:%02d".format(s / 60, s % 60)
}

/** CUE 시트 펼치기: 같은 폴더의 오디오 파일 중 CUE 의 FILE 과 이름이 같은 파일을 CUE 트랙들로 바꿈 */
object CueExpand {
    /**
     * audio: (파일 이름, 곡) — 한 폴더. cues: 그 폴더의 CUE 들 (Cue.parse(text, "") — file = 이름만)
     * 반환: (펼친 목록, 바뀐 오디오 파일 수). CUE 가 가리키는 파일은 목록에서 빠지고 그 자리에 트랙들이 들어감
     */
    fun expand(audio: List<Pair<String, Track>>, cues: List<List<Cue.CueTrack>>): Pair<List<Track>, Int> {
        if (cues.isEmpty()) return audio.map { it.second } to 0
        val byName = HashMap<String, Int>()
        audio.forEachIndexed { i, (n, _) -> byName[n.lowercase()] = i }
        val repl = HashMap<Int, MutableList<Track>>()
        for (sheet in cues) for (ct in sheet) {
            val name = ct.file.replace('\\', '/').substringAfterLast('/').lowercase()
            val i = byName[name] ?: continue
            val src = audio[i].second
            val dur = if (ct.endMs > 0) ct.endMs - ct.startMs else (src.durationMs - ct.startMs).coerceAtLeast(0)
            repl.getOrPut(i) { ArrayList() }.add(Track(
                CueRef.make(src.uri, ct.number, ct.startMs, ct.endMs), ct.title,
                ct.performer.ifBlank { src.artist }, ct.album.ifBlank { src.album }, dur, src.path, src.folder,
                ct.genre.ifBlank { src.genre }, CueRg.text(ct)))
        }
        val out = ArrayList<Track>()
        audio.forEachIndexed { i, (_, t) -> val r = repl[i]; if (r == null) out.add(t) else out.addAll(r) }
        return out to repl.size
    }
}

/**
 * CUE ReplayGain (vr0.1.0.010, A12): Cue.CueTrack 의 REM REPLAYGAIN 글자 4개 ↔ Track.rg 한 칸.
 *   "트랙gain;트랙peak;앨범gain;앨범peak" (예 "-6.50 dB;0.98;-7.10 dB;1.0"), 값이 하나도 없으면 ""
 */
object CueRg {
    fun text(ct: Cue.CueTrack): String = if (!ct.hasRg) "" else
        listOf(ct.rgTrackGain, ct.rgTrackPeak, ct.rgAlbumGain, ct.rgAlbumPeak).joinToString(";") { it.replace(';', ' ') }

    /** (트랙gain, 트랙peak, 앨범gain, 앨범peak) 글자 — 빈 값은 "" */
    fun parts(rg: String): List<String> {
        if (rg.isBlank()) return listOf("", "", "", "")
        val p = rg.split(';')
        return List(4) { p.getOrElse(it) { "" }.trim() }
    }
}
