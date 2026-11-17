package com.ascen.yamp.app

import android.content.Intent
import android.net.Uri
import android.provider.OpenableColumns
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import com.ascen.yamp.core.YLog
import com.ascen.yamp.data.Cue
import com.ascen.yamp.data.Formats
import com.ascen.yamp.data.Playlists
import com.ascen.yamp.data.LibraryDb
import com.ascen.yamp.data.MediaScanner
import com.ascen.yamp.data.ScanResult
import com.ascen.yamp.data.Track
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/**
 * 라이브러리 (C2): DB 곡 목록 · 좋아요/별점 (B1) · 음악 스캔 · 파일 추가
 * vr0.1.0.010:
 *   R2 파일 추가로 재생 목록 파일(m3u · m3u8 · pls · xspf · wpl)을 열면 안의 곡을 기기 곡과 맞춰 넣음 (data/Playlists.kt)
 *   A3 "열기"(다른 앱에서 보낸 파일)처럼 영구 권한을 못 받은 파일은 알림 + 목록 파일에 저장하지 않음
 */
class LibraryController(
    private val core: AppCore,
    private val playback: PlaybackController,
    private val playlist: PlaylistController,
) {
    private val db get() = core.db

    val library = mutableStateListOf<LibraryDb.Row>()
    /** key → 행 (메인 스레드에서만 읽고 씀) */
    private var libByKey = HashMap<String, LibraryDb.Row>()
    var historyCount by mutableIntStateOf(0); private set
    var scanning by mutableStateOf(false); private set
    /** 현재 곡 좋아요 · 별점 */
    var liked by mutableStateOf(false); private set
    var rating by mutableIntStateOf(0); private set

    /** 재생 목록 파일 항목을 맞춰 볼 곡 (폴더 탭 곡 — AppViewModel 이 연결) */
    var extraCandidates: () -> List<Track> = { emptyList() }

    fun trackOfKey(k: String): Track? = libByKey[k]?.track
    fun hasKey(k: String): Boolean = k in libByKey
    val isEmpty: Boolean get() = libByKey.isEmpty()

    // ================================================= DB → 화면
    suspend fun refreshNow() {
        val rows = core.io("library", "DB 읽기 실패", emptyList()) { db.rows() }
        val cnt = core.io("library", "기록 수 읽기 실패", 0) { db.playCount() }
        libByKey = rows.associateByTo(HashMap(rows.size * 2)) { it.key }
        library.clear()
        library.addAll(rows)
        historyCount = cnt
    }

    fun refresh() { core.scope.launch { refreshNow() } }

    /** 설정 화면용: 기록 건수만 (곡 목록 전체를 다시 읽지 않음) */
    fun refreshHistoryCount() {
        core.scope.launch { historyCount = core.io("library", "기록 수 읽기 실패", historyCount) { db.playCount() } }
    }

    // ================================================= 좋아요 · 별점 (B1)
    fun refreshLike() {
        val t = playback.currentTrack ?: run { liked = false; rating = 0; return }
        val k = core.keyOf(t)
        core.scope.launch {
            val (l, r) = core.io("library", "좋아요 읽기 실패", false to 0) { db.likeRating(k) }
            if (playback.currentTrack?.uri == t.uri) { liked = l; rating = r }
        }
    }

    private fun isCurrent(t: Track) = t.uri == playback.currentTrack?.uri

    fun isLiked(t: Track): Boolean = libByKey[core.keyOf(t)]?.liked ?: false
    fun ratingOf(t: Track): Int = libByKey[core.keyOf(t)]?.rating ?: 0

    fun toggleLike(t: Track?) {
        val tr = t ?: return
        val k = core.keyOf(tr)
        val now = if (isCurrent(tr)) !liked else !isLiked(tr)
        if (isCurrent(tr)) liked = now
        core.scope.launch {
            core.io("library", "좋아요 저장 실패", Unit) { db.upsert(listOf(tr)); db.setLiked(k, now) }
            core.toast(if (now) "좋아요" else "좋아요 취소")
            patchRow(k) { it.copy(liked = now) }
        }
    }

    fun setRating(t: Track, r: Int) {
        val k = core.keyOf(t)
        if (isCurrent(t)) rating = r
        core.scope.launch {
            core.io("library", "별점 저장 실패", Unit) { db.upsert(listOf(t)); db.setRating(k, r.coerceIn(0, 5)) }
            core.toast(if (r > 0) "별점 $r / 5" else "별점 지움")
            patchRow(k) { it.copy(rating = r.coerceIn(0, 5)) }
        }
    }

    /**
     * 화면 목록에서 한 곡만 바꿈 (vr0.1.0.008): 좋아요·별점마다 DB 전체(1만 곡+)를 다시 읽고 목록을 통째로 바꾸지 않게.
     * 목록에 없던 곡(방금 DB 에 등록됨)이면 전체 다시 읽기
     */
    private suspend fun patchRow(k: String, change: (LibraryDb.Row) -> LibraryDb.Row) {
        val old = libByKey[k]
        val i = if (old == null) -1 else library.indexOfFirst { it.key == k }
        if (old == null || i < 0) { refreshNow(); return }
        val row = change(old)
        library[i] = row
        libByKey[k] = row
    }

    // ================================================= 음악 스캔 · 파일 추가
    fun scanAll() {
        if (scanning) return
        scanning = true
        core.scope.launch {
            val r = core.io("library", "스캔 실패", ScanResult(emptyList())) { MediaScanner.scan(core.app) }
            val found = r.tracks
            core.mediaStoreTracks = found
            val added = core.register(found)
            YLog.i("library", "스캔 ${found.size}곡 (새 곡 $added)")
            core.logSkipped(r, "스캔")
            scanning = false
            val known = playback.tracks.mapTo(HashSet()) { it.uri }
            playlist.addTracks(found.filter { f -> f.uri !in known })
            core.appendSkipped(r.skipped.size)
            refreshNow()
        }
    }

    fun addUris(uris: List<Uri>) {
        libByKeySnapshot = libByKey.values.map { it.track }
        playbackSnapshot = playback.tracks.toList()
        extraSnapshot = runCatching { extraCandidates() }.getOrDefault(emptyList())
        core.scope.launch {
            val ctx = core.app
            var skipped = 0
            var notPersisted = 0
            val transient = ArrayList<String>()
            val playlists = ArrayList<Pair<Uri, String>>()
            val list = withContext(Dispatchers.IO) {
                uris.mapNotNull { u ->
                    val name = runCatching {
                        ctx.contentResolver.query(u, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use {
                            if (it.moveToFirst()) it.getString(0) else null
                        }
                    }.getOrNull() ?: u.lastPathSegment.orEmpty()
                    val mime = runCatching { ctx.contentResolver.getType(u) }.getOrNull()
                    when (Formats.classify(name, mime)) {
                        Formats.Kind.AUDIO -> {}
                        Formats.Kind.UNSUPPORTED -> {
                            skipped++
                            YLog.i("library", "재생할 수 없는 형식 건너뜀: $name ($mime)")
                            return@mapNotNull null
                        }
                        // .cue 는 '폴더 추가' 로 (같은 폴더의 음원과 함께 읽어야 함)
                        Formats.Kind.CUE -> { YLog.i("library", "CUE 파일은 폴더 추가로 열어 주세요: $name"); return@mapNotNull null }
                        // 재생 목록 파일 → 아래에서 안의 곡으로 펼침
                        Formats.Kind.PLAYLIST -> { playlists.add(u to name); return@mapNotNull null }
                        // 형식을 모름 (MIME 없음) → 일단 시도 (이전 버전과 같음), 오디오가 아닌 것이 확실하면 건너뜀
                        Formats.Kind.OTHER -> if (mime != null) { YLog.i("library", "오디오 아님 건너뜀: $name ($mime)"); return@mapNotNull null }
                    }
                    // A3: "열기" 로 받은 임시 권한은 영구로 바꿀 수 없음 → 다시 시작하면 재생 오류 → 목록 파일에 저장하지 않음
                    val kept = runCatching { ctx.contentResolver.takePersistableUriPermission(u, Intent.FLAG_GRANT_READ_URI_PERMISSION) }
                        .onFailure { YLog.i("library", "영구 권한 없음 (이번 실행만): $name — $it") }.isSuccess
                    if (!kept) { notPersisted++; transient.add(u.toString()) }
                    MediaScanner.fromUri(ctx, u)
                }
            }
            val fromLists = ArrayList<Track>()
            var missing = 0
            if (playlists.isNotEmpty()) {
                val (found, miss) = withContext(Dispatchers.IO) { importPlaylists(playlists) }
                fromLists.addAll(found)
                missing = miss
            }
            val all = list + fromLists
            if (all.isEmpty()) {
                if (playlists.isNotEmpty()) core.toast("재생 목록에서 이 기기의 곡을 찾지 못했습니다" + if (missing > 0) " (${missing}곡)" else "")
                else core.toastSkipped(skipped)
                return@launch
            }
            core.register(all)
            val start = playback.tracks.size
            playlist.markTransient(transient)
            playlist.addTracks(all)
            if (fromLists.isNotEmpty()) core.appendToast(" (재생 목록 ${playlists.size}개" + (if (missing > 0) " · 못 찾은 곡 $missing" else "") + ")")
            core.appendSkipped(skipped)
            if (notPersisted > 0) core.appendToast(" · ${notPersisted}곡은 임시 권한이라 앱을 다시 시작하면 목록에서 빠집니다")
            refreshNow()
            if (!playback.isPlaying) playback.playIndex(start)
        }
    }

    /**
     * 재생 목록 파일 → 곡 (IO 스레드). 항목 위치를 기기 곡(MediaStore · 추가한 폴더 · 라이브러리 · 지금 목록)과 맞춤,
     * http(s) · content 는 그대로. 반환: (곡, 못 찾은 항목 수)
     */
    private fun importPlaylists(files: List<Pair<Uri, String>>): Pair<List<Track>, Int> {
        val ctx = core.app
        if (core.mediaStoreTracks.isEmpty()) {
            // 음악 권한이 있으면 기기 곡 목록 (없으면 SecurityException → 건너뜀)
            runCatching { MediaScanner.scan(ctx) }.getOrNull()?.let { core.mediaStoreTracks = it.tracks }
        }
        val cands = ArrayList<Track>()
        cands.addAll(core.mediaStoreTracks)
        cands.addAll(extraSnapshot)
        cands.addAll(libByKeySnapshot)
        cands.addAll(playbackSnapshot)
        val out = ArrayList<Track>()
        var missing = 0
        for ((u, name) in files) {
            val text = runCatching { ctx.contentResolver.openInputStream(u)?.use { Cue.decode(it.readBytes()) } }
                .onFailure { YLog.w("library", "재생 목록 읽기 실패 $name", it) }.getOrNull() ?: continue
            val entries = Playlists.parse(name, text)
            var ok = 0
            for (e in entries) {
                val t = when (val loc = Playlists.locate(e.location)) {
                    is Playlists.Loc.Direct -> Track(loc.uri, e.title.ifBlank { loc.uri.substringAfterLast('/') }, durationMs = e.durationMs)
                    is Playlists.Loc.Path -> Playlists.resolve(loc.path, cands)
                }
                if (t == null) { missing++; continue }
                out.add(t)
                ok++
            }
            YLog.i("library", "재생 목록 $name: ${entries.size}곡 중 ${ok}곡 찾음")
        }
        return out to missing
    }

    /** IO 스레드에서 읽을 복사본 (메인 스레드 상태를 직접 읽지 않게 — addUris 시작 때 갱신) */
    @Volatile private var libByKeySnapshot: List<Track> = emptyList()
    @Volatile private var playbackSnapshot: List<Track> = emptyList()
    @Volatile private var extraSnapshot: List<Track> = emptyList()
}
