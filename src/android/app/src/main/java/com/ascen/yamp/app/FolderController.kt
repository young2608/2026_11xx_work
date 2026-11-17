package com.ascen.yamp.app

import android.content.Intent
import android.net.Uri
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import com.ascen.yamp.core.YLog
import com.ascen.yamp.data.CueRef
import com.ascen.yamp.data.FolderTree
import com.ascen.yamp.data.Formats
import com.ascen.yamp.data.MediaScanner
import com.ascen.yamp.data.SafFolders
import com.ascen.yamp.data.Track
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/**
 * 폴더 재생 (F1~F8): MediaStore + 추가한 SAF 폴더 → 폴더 트리 · 고정 · 폴더 재생
 * vr0.1.0.010:
 *   A6  읽는 중에 폴더를 추가/삭제 → 끝난 뒤 한 번 더 새로고침 (버리지 않음)
 *   A7  추가한 폴더(SAF)의 "추가일" 정렬 = 문서 수정 시각
 *   A16 폴더 추가 뒤 화면이 새 폴더로 (openRequest)
 *   A17 "폴더를 읽을 수 없습니다" 는 한 알림으로 모으고, 같은 폴더는 이번 실행에서 한 번만
 */
class FolderController(private val core: AppCore, private val playlist: PlaylistController) {
    private val store get() = core.store

    /** 폴더 탭 곡 전체 (MediaStore + 추가한 SAF 폴더). FolderTree.Item.idx = 이 목록 위치 */
    val folderTracks = mutableStateListOf<Track>()
    var folderRoot by mutableStateOf<FolderTree.Node?>(null); private set
    var folderLoading by mutableStateOf(false); private set
    val safTrees = mutableStateListOf<Pair<String, String>>().apply { addAll(store.safTrees) }
    val pinnedFolders = mutableStateListOf<String>().apply { addAll(store.pinnedFolders) }
    /** 폴더 화면이 열어야 할 폴더 (A16, "" = 없음) — FolderScreen 이 열고 consumeOpen() */
    var openRequest by mutableStateOf(""); private set

    /** 읽는 중에 들어온 새로고침 요청 (A6): null = 없음, true/false = MediaStore 포함 여부 */
    private var pendingRefresh: Boolean? = null
    /** 읽기 실패를 이미 알린 폴더 (A17) */
    private val warnedTrees = HashSet<String>()
    /** SAF 문서 수정 시각 (A7): 실제 파일 uri → ms */
    private var modified: Map<String, Long> = emptyMap()

    fun consumeOpen() { openRequest = "" }

    private fun safKey(i: Int) = "$SAF_PREFIX${i + 1}"

    /** withMediaStore = 음악 권한이 있을 때만 true (MainActivity 가 판단) */
    fun refreshFolders(withMediaStore: Boolean) {
        if (folderLoading) {
            // A6: 지금 읽기가 끝나면 다시 (MediaStore 요청은 합침)
            pendingRefresh = (pendingRefresh ?: false) || withMediaStore
            return
        }
        folderLoading = true
        val ctx = core.app
        val trees = safTrees.toList()
        core.scope.launch {
            var skipped = 0
            val all = ArrayList<Track>()
            val failed = ArrayList<String>()
            val mods = HashMap<String, Long>()
            if (withMediaStore) {
                val r = withContext(Dispatchers.IO) {
                    runCatching { MediaScanner.scan(ctx) }.onFailure { YLog.w("folder", "MediaStore 조회 실패", it) }.getOrNull()
                }
                if (r != null) { core.mediaStoreTracks = r.tracks; core.logSkipped(r, "MediaStore"); skipped += r.skipped.size }
            }
            all.addAll(core.mediaStoreTracks)
            trees.forEachIndexed { i, (u, label) ->
                val r = withContext(Dispatchers.IO) {
                    runCatching { SafFolders.scan(ctx, Uri.parse(u), safKey(i)) }
                        .onFailure { YLog.w("folder", "폴더 읽기 실패 $label ($u)", it) }.getOrNull()
                }
                if (r == null) { if (warnedTrees.add(u)) failed.add(label) }
                else { all.addAll(r.tracks); mods.putAll(r.modified); core.logSkipped(r, label); skipped += r.skipped.size; warnedTrees.remove(u) }
            }
            val labels = trees.mapIndexed { i, (_, label) -> safKey(i) to label }.toMap()
            val root = withContext(Dispatchers.Default) {
                FolderTree.build(all.mapIndexed { i, t -> FolderTree.Item(i, t.folder, Formats.ext(t.path.ifEmpty { t.title }), t.durationMs) }, labels)
            }
            folderTracks.clear()
            folderTracks.addAll(all)
            modified = mods
            folderRoot = root
            folderLoading = false
            // A17: 읽기 실패 · 건너뛴 형식을 한 알림으로 (곧바로 다른 알림에 덮이지 않게)
            val msgs = ArrayList<String>()
            if (failed.isNotEmpty()) msgs.add("폴더를 읽을 수 없습니다: ${failed.joinToString(", ")} (권한을 다시 주려면 폴더를 다시 추가하세요)")
            if (skipped > 0) msgs.add(core.skippedText(skipped))
            if (msgs.isNotEmpty()) core.toast(msgs.joinToString("\n"))
            YLog.i("folder", "폴더 ${root.children.size}개 루트 · ${all.size}곡 (MediaStore=${core.mediaStoreTracks.size}, SAF 폴더 ${trees.size}개)")
            pendingRefresh?.let { ms -> pendingRefresh = null; refreshFolders(ms) }
        }
    }

    fun addSafTree(uri: Uri) {
        runCatching { core.app.contentResolver.takePersistableUriPermission(uri, Intent.FLAG_GRANT_READ_URI_PERMISSION) }
            .onFailure { YLog.w("folder", "폴더 권한 유지 실패 $uri", it) }
        val s = uri.toString()
        if (safTrees.any { it.first == s }) { core.toast("이미 추가한 폴더입니다"); return }
        val label = SafFolders.label(uri)
        safTrees.add(s to label)
        store.safTrees = safTrees.toList()
        warnedTrees.remove(s)
        YLog.i("folder", "폴더 추가 $label ($s)")
        core.toast("폴더 추가: $label")
        val key = safKey(safTrees.size - 1)
        store.lastFolder = key
        openRequest = key            // A16: 읽기가 끝나 트리에 생기면 폴더 화면이 그 폴더로
        refreshFolders(withMediaStore = false)
    }

    fun removeSafTree(key: String) {
        val i = key.removePrefix(SAF_PREFIX).toIntOrNull()?.minus(1) ?: return
        if (i !in safTrees.indices) return
        val (u, label) = safTrees.removeAt(i)
        store.safTrees = safTrees.toList()
        runCatching { core.app.contentResolver.releasePersistableUriPermission(Uri.parse(u), Intent.FLAG_GRANT_READ_URI_PERMISSION) }
        // 번호가 당겨지므로 고정·마지막 폴더 중 saf: 항목은 정리
        pinnedFolders.removeAll { it.startsWith(SAF_PREFIX) }
        store.pinnedFolders = pinnedFolders.toSet()
        if (store.lastFolder.startsWith(SAF_PREFIX)) store.lastFolder = ""
        if (openRequest.startsWith(SAF_PREFIX)) openRequest = ""
        warnedTrees.remove(u)
        YLog.i("folder", "폴더 제거 $label")
        core.toast("폴더 목록에서 뺌: $label")
        refreshFolders(withMediaStore = false)
    }

    fun togglePin(path: String) {
        if (path in pinnedFolders) pinnedFolders.remove(path) else pinnedFolders.add(path)
        store.pinnedFolders = pinnedFolders.toSet()
    }

    fun rememberFolder(path: String) { store.lastFolder = path }

    /** ▶ 이 폴더 재생: 목록을 그 폴더 곡으로 바꾸고 첫 곡부터 */
    fun playFolder(path: String, includeSub: Boolean, shuffleList: Boolean, sort: String, startUri: String? = null) {
        val node = folderRoot?.find(path) ?: run { core.toast("폴더를 찾을 수 없습니다"); return }
        store.folderIncludeSub = includeSub
        store.folderShuffle = shuffleList
        store.folderSort = sort
        var list = node.items(includeSub).mapNotNull { folderTracks.getOrNull(it) }
        list = when {
            shuffleList -> list.shuffled()
            // 하위 포함: 폴더별로 묶은 채 폴더 안에서 정렬
            includeSub -> list.groupBy { it.folder }.values.flatMap { sort(it, sort) }
            else -> sort(list, sort)
        }
        val start = startUri?.let { u -> list.indexOfFirst { it.uri == u } }?.takeIf { it >= 0 } ?: 0
        store.lastFolder = path
        YLog.i("folder", "폴더 재생 ${node.label} (${list.size}곡, 하위=$includeSub, 셔플=$shuffleList, 정렬=$sort)")
        playlist.replacePlaylist(list, "폴더: ${node.label}", start)
    }

    /** 폴더 곡 정렬 (SAF 폴더 추가일 = 문서 수정 시각) */
    fun sort(list: List<Track>, sort: String): List<Track> {
        val mods = modified
        return sortFolderTracks(list, sort) { t -> mods[t.uri] ?: mods[CueRef.mediaUri(t.uri)] }
    }

    companion object {
        /** 추가한 SAF 폴더 경로 머리 (saf:1, saf:2 …) */
        const val SAF_PREFIX = "saf:"

        /**
         * 폴더 곡 정렬: name 파일명 / title 제목 / added 추가일 (최근 먼저)
         *   추가일: SAF 폴더 곡 = 문서 수정 시각 (addedAt, A7), MediaStore 곡 = id 큰 순 (나중에 등록된 것)
         *   같은 파일의 CUE 트랙은 트랙 번호 순
         */
        fun sortFolderTracks(list: List<Track>, sort: String, addedAt: (Track) -> Long? = { null }): List<Track> = when (sort) {
            "title" -> list.sortedWith(compareBy({ it.title.lowercase() }, { it.clip?.number ?: 0 }))
            "added" -> list.sortedWith(compareByDescending<Track> {
                addedAt(it) ?: CueRef.mediaUri(it.uri).substringAfterLast('/').toLongOrNull() ?: 0L
            }.thenBy { it.clip?.number ?: 0 })
            else -> list.sortedWith(compareBy({ it.folder.lowercase() }, { it.path.substringAfterLast('/').lowercase() }, { it.clip?.number ?: 0 }))
        }
    }
}
