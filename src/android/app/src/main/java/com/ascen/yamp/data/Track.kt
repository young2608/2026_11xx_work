package com.ascen.yamp.data

import android.content.ContentUris
import android.content.Context
import android.media.MediaMetadataRetriever
import android.net.Uri
import android.os.Build
import android.provider.MediaStore
import android.provider.OpenableColumns
import java.io.File

/**
 * 스캔 결과: 곡 목록 + 재생할 수 없는 형식이라 건너뛴 파일 이름 + CUE 로 펼친 파일 수
 * modified (vr0.1.0.010, A7): 실제 파일 uri → 문서 수정 시각(ms) — SAF 폴더 "추가일" 정렬용 (MediaStore 는 비움, id 순)
 */
data class ScanResult(val tracks: List<Track>, val skipped: List<String> = emptyList(), val cueFiles: Int = 0,
                      val modified: Map<String, Long> = emptyMap())

object MediaScanner {
    /** 기기 전체 음악 (MediaStore). 폴더 → 파일명 순. 재생할 수 없는 형식(ape·wma·dsf …)은 건너뜀 */
    fun scan(ctx: Context): ScanResult {
        val out = ArrayList<Pair<String, Track>>()          // (파일 이름, 곡)
        val skipped = ArrayList<String>()
        val col = MediaStore.Audio.Media.EXTERNAL_CONTENT_URI
        @Suppress("DEPRECATION")
        val base = arrayOf(
            MediaStore.Audio.Media._ID, MediaStore.Audio.Media.TITLE, MediaStore.Audio.Media.ARTIST,
            MediaStore.Audio.Media.ALBUM, MediaStore.Audio.Media.DURATION, MediaStore.Audio.Media.DATA,
            MediaStore.Audio.Media.DISPLAY_NAME, MediaStore.Audio.Media.MIME_TYPE,
        )
        // 장르 열은 Android 11(API 30)+ 에서만 (그 이전은 빈 값)
        val hasGenre = Build.VERSION.SDK_INT >= 30
        val proj = if (hasGenre) base + MediaStore.Audio.AudioColumns.GENRE else base
        val sel = "${MediaStore.Audio.Media.IS_MUSIC} != 0 OR ${MediaStore.Audio.Media.DURATION} > 30000"
        ctx.contentResolver.query(col, proj, sel, null, null)?.use { c ->
            val iId = c.getColumnIndexOrThrow(proj[0])
            val iT = c.getColumnIndexOrThrow(proj[1])
            val iA = c.getColumnIndexOrThrow(proj[2])
            val iAl = c.getColumnIndexOrThrow(proj[3])
            val iD = c.getColumnIndexOrThrow(proj[4])
            val iP = c.getColumnIndexOrThrow(proj[5])
            val iN = c.getColumnIndexOrThrow(proj[6])
            val iM = c.getColumnIndex(proj[7])
            val iG = if (hasGenre) c.getColumnIndex(proj[8]) else -1
            while (c.moveToNext()) {
                val id = c.getLong(iId)
                val path = c.getString(iP).orEmpty()
                val name = c.getString(iN)?.takeIf { it.isNotBlank() } ?: File(path).name
                val mime = if (iM >= 0) c.getString(iM) else null
                when (Formats.classify(name.ifEmpty { path }, mime)) {
                    Formats.Kind.AUDIO -> {}
                    Formats.Kind.UNSUPPORTED -> { skipped.add(name); continue }
                    // 재생 목록 · CUE · 기타 (일부 기기는 m3u 를 오디오로 등록) — 건너뛴 형식으로 세지 않음
                    else -> continue
                }
                val artist = c.getString(iA).orEmpty().let { if (it == "<unknown>") "" else it }
                out.add(name to Track(
                    ContentUris.withAppendedId(col, id).toString(),
                    c.getString(iT)?.takeIf { it.isNotBlank() } ?: name,
                    artist, c.getString(iAl).orEmpty(), c.getLong(iD), path,
                    File(path).parent.orEmpty(),
                    if (iG >= 0) c.getString(iG).orEmpty() else "",
                ))
            }
        }
        // CUE (가능한 기기만): MediaStore 에 .cue 가 보이고 파일을 읽을 수 있을 때 → 폴더별로 펼침
        val cues = runCatching { cueSheets(ctx) }.getOrDefault(emptyMap())
        var cueFiles = 0
        val result = ArrayList<Track>()
        out.groupBy { it.second.folder }.forEach { (folder, list) ->
            val (exp, n) = CueExpand.expand(list, cues[folder].orEmpty())
            cueFiles += n
            result.addAll(exp)
        }
        val sorted = result.sortedWith(compareBy({ it.folder.lowercase() }, { File(it.path).name.lowercase() }, { it.clip?.number ?: 0 }))
        return ScanResult(sorted, skipped, cueFiles)
    }

    /** MediaStore.Files 의 .cue (폴더 → 파싱한 시트들). Android 11+ 는 보통 보이지 않음 → SAF 폴더 추가로 지원 */
    @Suppress("DEPRECATION")
    private fun cueSheets(ctx: Context): Map<String, List<List<Cue.CueTrack>>> {
        val out = HashMap<String, MutableList<List<Cue.CueTrack>>>()
        val uri = MediaStore.Files.getContentUri("external")
        val proj = arrayOf(MediaStore.Files.FileColumns.DATA)
        ctx.contentResolver.query(uri, proj, "${MediaStore.Files.FileColumns.DATA} LIKE ?", arrayOf("%.cue"), null)?.use { c ->
            while (c.moveToNext()) {
                val path = c.getString(0) ?: continue
                val f = File(path)
                val text = runCatching { Cue.decode(f.readBytes()) }.getOrNull() ?: continue
                val sheet = Cue.parse(text, "")
                if (sheet.isNotEmpty()) out.getOrPut(f.parent.orEmpty()) { ArrayList() }.add(sheet)
            }
        }
        return out
    }

    /** SAF 로 고른 파일 → Track (MediaMetadataRetriever) */
    fun fromUri(ctx: Context, uri: Uri): Track {
        var name = uri.lastPathSegment.orEmpty()
        runCatching {
            ctx.contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use {
                if (it.moveToFirst()) name = it.getString(0) ?: name
            }
        }
        var title = name.substringBeforeLast('.')
        var artist = ""
        var album = ""
        var dur = 0L
        var genre = ""
        val r = MediaMetadataRetriever()
        try {
            r.setDataSource(ctx, uri)
            r.extractMetadata(MediaMetadataRetriever.METADATA_KEY_TITLE)?.takeIf { it.isNotBlank() }?.let { title = it }
            artist = r.extractMetadata(MediaMetadataRetriever.METADATA_KEY_ARTIST).orEmpty()
            album = r.extractMetadata(MediaMetadataRetriever.METADATA_KEY_ALBUM).orEmpty()
            dur = r.extractMetadata(MediaMetadataRetriever.METADATA_KEY_DURATION)?.toLongOrNull() ?: 0
            genre = r.extractMetadata(MediaMetadataRetriever.METADATA_KEY_GENRE).orEmpty()
        } catch (_: Exception) {
        } finally {
            runCatching { r.release() }
        }
        if (artist.isBlank() && title.contains(" - ")) {
            artist = title.substringBefore(" - ").trimStart('0', '1', '2', '3', '4', '5', '6', '7', '8', '9', '.', ' ').trim()
            title = title.substringAfter(" - ").trim()
        }
        return Track(uri.toString(), title, artist, album, dur, "", "", genre)
    }

    /** 앨범아트 (재생 중인 곡만, 작은 크기) */
    fun cover(ctx: Context, uri: String): ByteArray? {
        val r = MediaMetadataRetriever()
        return try {
            r.setDataSource(ctx, Uri.parse(CueRef.mediaUri(uri)))
            r.embeddedPicture
        } catch (_: Exception) {
            null
        } finally {
            runCatching { r.release() }
        }
    }
}
