package com.ascen.yamp.data

import android.content.Context
import android.media.MediaMetadataRetriever
import android.net.Uri
import android.provider.DocumentsContract
import com.ascen.yamp.core.YLog

/**
 * 폴더 추가 (F4): SAF 폴더 트리 (OpenDocumentTree + 읽기 권한 유지) → 하위 폴더까지 재귀 탐색.
 * SD카드·USB·MediaStore 에 안 잡히는 폴더도 재생. 곡 uri = content:// 문서 uri (ExoPlayer 가 그대로 재생).
 * 폴더 문자열 = "saf:<번호>/하위/폴더" (FolderTree 규칙). androidx.documentfile 없이 DocumentsContract 직접 사용.
 * 호출은 Dispatchers.IO 에서.
 */
object SafFolders {
    /** 곡 정보(제목·가수·길이)를 MediaMetadataRetriever 로 읽는 최대 파일 수 (넘으면 파일 이름만 — 스캔 시간 제한) */
    const val META_LIMIT = 300
    /** 한 폴더 트리에서 찾는 최대 파일 수 */
    const val FILE_LIMIT = 20000

    /** 표시 이름: 트리 문서 id "primary:Music/K-Pop" → "K-Pop" (루트면 "내장 저장소" / "SD …") */
    fun label(treeUri: Uri): String {
        val id = runCatching { DocumentsContract.getTreeDocumentId(treeUri) }.getOrNull() ?: return treeUri.lastPathSegment.orEmpty()
        val vol = id.substringBefore(':')
        val rel = id.substringAfter(':', "")
        val last = rel.trimEnd('/').substringAfterLast('/')
        if (last.isNotEmpty()) return last
        return if (vol == "primary") "내장 저장소" else "저장소 ($vol)"
    }

    private class Doc(val id: String, val name: String, val mime: String, val modified: Long)

    private fun children(ctx: Context, tree: Uri, parentId: String): List<Doc> {
        val uri = DocumentsContract.buildChildDocumentsUriUsingTree(tree, parentId)
        val proj = arrayOf(DocumentsContract.Document.COLUMN_DOCUMENT_ID, DocumentsContract.Document.COLUMN_DISPLAY_NAME,
            DocumentsContract.Document.COLUMN_MIME_TYPE, DocumentsContract.Document.COLUMN_LAST_MODIFIED)
        val out = ArrayList<Doc>()
        ctx.contentResolver.query(uri, proj, null, null, null)?.use { c ->
            while (c.moveToNext()) {
                val id = c.getString(0) ?: continue
                out.add(Doc(id, c.getString(1).orEmpty(), c.getString(2).orEmpty(), if (c.isNull(3)) 0L else c.getLong(3)))
            }
        }
        return out
    }

    /** rootKey = "saf:<번호>" */
    fun scan(ctx: Context, tree: Uri, rootKey: String): ScanResult {
        val rootId = DocumentsContract.getTreeDocumentId(tree)
        val skipped = ArrayList<String>()
        val result = ArrayList<Track>()
        var files = 0
        var meta = 0
        var cueFiles = 0
        val modified = HashMap<String, Long>()
        // (문서 id, 상대 경로) 너비 우선
        val queue = ArrayDeque<Pair<String, String>>()
        queue.add(rootId to "")
        while (queue.isNotEmpty() && files < FILE_LIMIT) {
            val (pid, rel) = queue.removeFirst()
            val folder = if (rel.isEmpty()) rootKey else "$rootKey/$rel"
            val kids = runCatching { children(ctx, tree, pid) }
                .onFailure { YLog.w("folder", "폴더 읽기 실패 $folder", it) }.getOrDefault(emptyList())
                .sortedBy { it.name.lowercase() }
            val audio = ArrayList<Pair<String, Track>>()
            val cues = ArrayList<List<Cue.CueTrack>>()
            for (d in kids) {
                if (d.mime == DocumentsContract.Document.MIME_TYPE_DIR) {
                    queue.add(d.id to (if (rel.isEmpty()) d.name else "$rel/${d.name}"))
                    continue
                }
                files++
                val docUri = DocumentsContract.buildDocumentUriUsingTree(tree, d.id)
                when (Formats.classify(d.name, d.mime)) {
                    Formats.Kind.AUDIO -> {
                        val t = if (meta < META_LIMIT) { meta++; withMeta(ctx, docUri, d.name, folder) } else plain(docUri, d.name, folder)
                        audio.add(d.name to t)
                        if (d.modified > 0) modified[t.uri] = d.modified
                    }
                    Formats.Kind.CUE -> runCatching {
                        ctx.contentResolver.openInputStream(docUri)?.use { Cue.parse(Cue.decode(it.readBytes()), "") }
                    }.getOrNull()?.takeIf { it.isNotEmpty() }?.let { cues.add(it) }
                    Formats.Kind.UNSUPPORTED -> skipped.add(d.name)
                    // 폴더 안 재생 목록 파일은 펼치지 않음 (파일 추가로 열면 안의 곡을 넣음 — LibraryController)
                    Formats.Kind.PLAYLIST, Formats.Kind.OTHER -> {}
                }
            }
            val (exp, n) = CueExpand.expand(audio, cues)
            cueFiles += n
            result.addAll(exp)
        }
        if (files >= FILE_LIMIT) YLog.w("folder", "파일이 너무 많아 $FILE_LIMIT 개까지만 읽음: $rootKey")
        return ScanResult(result, skipped, cueFiles, modified)
    }

    private fun plain(uri: Uri, name: String, folder: String): Track {
        var title = name.substringBeforeLast('.')
        var artist = ""
        if (title.contains(" - ")) {
            artist = title.substringBefore(" - ").trimStart('0', '1', '2', '3', '4', '5', '6', '7', '8', '9', '.', ' ').trim()
            title = title.substringAfter(" - ").trim()
        }
        return Track(uri.toString(), title, artist, "", 0, "$folder/$name", folder, "")
    }

    private fun withMeta(ctx: Context, uri: Uri, name: String, folder: String): Track {
        val base = plain(uri, name, folder)
        val r = MediaMetadataRetriever()
        return try {
            r.setDataSource(ctx, uri)
            val title = r.extractMetadata(MediaMetadataRetriever.METADATA_KEY_TITLE)?.takeIf { it.isNotBlank() }
            val artist = r.extractMetadata(MediaMetadataRetriever.METADATA_KEY_ARTIST)?.takeIf { it.isNotBlank() }
            base.copy(
                title = title ?: base.title,
                artist = artist ?: base.artist,
                album = r.extractMetadata(MediaMetadataRetriever.METADATA_KEY_ALBUM).orEmpty(),
                durationMs = r.extractMetadata(MediaMetadataRetriever.METADATA_KEY_DURATION)?.toLongOrNull() ?: 0,
                genre = r.extractMetadata(MediaMetadataRetriever.METADATA_KEY_GENRE).orEmpty(),
            )
        } catch (_: Exception) {
            base
        } finally {
            runCatching { r.release() }
        }
    }
}
