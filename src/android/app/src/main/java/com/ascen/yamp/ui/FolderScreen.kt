package com.ascen.yamp.ui

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.ascen.yamp.app.AppViewModel
import com.ascen.yamp.data.FolderTree
import com.ascen.yamp.data.Formats
import com.ascen.yamp.data.fmtTime

private val SORTS = listOf("name" to "파일명", "title" to "제목", "added" to "추가일")
private const val SONG_LIMIT = 300

/**
 * ③ 폴더 지정 재생 (F1~F8, 시안 ③):
 *   경로(브레드크럼) · 현재 폴더 카드(형식별 곡 수 · 총 시간 · ▶ 이 폴더 재생 · 셔플 · 하위 폴더 포함 · 정렬 · ★ 고정)
 *   하위 폴더 카드 · 곡 목록. 처음 화면 = 저장소 / 추가한 폴더 / ★ 고정 폴더
 *   폴더 추가 = SAF 폴더 선택 (SD카드 · USB · MediaStore 에 안 잡히는 폴더)
 */
@Composable
fun FolderScreen(vm: AppViewModel, onAddFolder: () -> Unit, onRefresh: () -> Unit) {
    val s = LocalSkin.current
    LaunchedEffect(Unit) { if (vm.folderRoot == null && !vm.folderLoading) onRefresh() }
    val root = vm.folderRoot
    var path by rememberSaveable { mutableStateOf(vm.store.lastFolder) }
    var includeSub by rememberSaveable { mutableStateOf(vm.store.folderIncludeSub) }
    var shuffleList by rememberSaveable { mutableStateOf(vm.store.folderShuffle) }
    var sort by rememberSaveable { mutableStateOf(vm.store.folderSort) }
    var confirmRemove by remember { mutableStateOf("") }
    // A16: 폴더를 추가하면 읽기가 끝나 트리에 생긴 뒤 그 폴더로
    LaunchedEffect(vm.folderOpenRequest, root) {
        val req = vm.folderOpenRequest
        if (req.isNotEmpty() && root?.find(req) != null) { path = req; vm.consumeFolderOpen() }
    }
    val node: FolderTree.Node? = root?.let { r -> if (path.isEmpty()) r else r.find(path) ?: r }
    val parent = node?.parent
    BackHandler(enabled = parent != null) { path = parent?.path.orEmpty() }
    fun open(p: String) { path = p; vm.rememberFolder(p) }

    LazyColumn(Modifier.fillMaxSize(), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        item {
            ScreenHeader("폴더") {
                IconAction(YIcons.refresh, "folder_refresh", onRefresh, framed = true, size = 36.dp, iconSize = 18.dp,
                    active = vm.folderLoading, state = if (vm.folderLoading) "읽는 중" else null)
                IconAction(YIcons.plus, "folder_add", onAddFolder, framed = true, size = 36.dp, iconSize = 18.dp)
            }
        }
        // 브레드크럼: 전체 › 내장 저장소 › Music › K-Pop
        item {
            Row(Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()).padding(horizontal = 4.dp),
                verticalAlignment = Alignment.CenterVertically) {
                val crumbs = node?.crumbs().orEmpty()
                Text("전체", color = if (crumbs.isEmpty()) s.accentText else s.dim, fontSize = 12.sp,
                    modifier = Modifier.clickable { open("") }.padding(vertical = 4.dp))
                crumbs.forEachIndexed { i, c ->
                    Text("  ›  ", color = s.dim, fontSize = 12.sp)
                    Text(c.label, color = if (i == crumbs.size - 1) s.accentText else s.dim, fontSize = 12.sp, maxLines = 1,
                        modifier = Modifier.clickable { open(c.path) }.padding(vertical = 4.dp))
                }
            }
        }
        if (root == null || node == null) {
            item {
                Text(if (vm.folderLoading) "폴더를 읽는 중…" else "음악 권한을 허용하거나 + (폴더 추가) 버튼으로 폴더를 고르세요",
                    color = s.dim, textAlign = TextAlign.Center, modifier = Modifier.fillMaxWidth().padding(24.dp))
            }
        } else if (node.parent == null) {
            // ---- 처음 화면: ★ 고정 폴더 + 저장소/추가한 폴더
            val pins = vm.pinnedFolders.toList().mapNotNull { root.find(it) }
            if (pins.isNotEmpty()) item {
                CollapsibleCard("folder_pins", "고정 폴더 ${pins.size}", contentPadding = PaddingValues(start = 8.dp, end = 8.dp, bottom = 8.dp)) {
                    pins.forEach { n -> FolderRow(n, true, { open(n.path) }, { vm.playFolder(n.path, includeSub, shuffleList, sort) }) }
                }
            }
            item {
                CollapsibleCard("folder_roots", "저장소 · 추가한 폴더", contentPadding = PaddingValues(start = 8.dp, end = 8.dp, bottom = 8.dp)) {
                    if (root.children.isEmpty()) Text("음악이 있는 폴더가 없습니다.\n음악 권한을 허용하거나 + (폴더 추가) 버튼으로 SD카드·USB 폴더를 고르세요",
                        color = s.dim, fontSize = 12.sp, modifier = Modifier.padding(8.dp))
                    root.children.forEach { n -> FolderRow(n, n.path in vm.pinnedFolders, { open(n.path) }, { vm.playFolder(n.path, includeSub, shuffleList, sort) }) }
                }
            }
            item {
                Text("총 ${root.count}곡 · ${FolderTree.durationText(root.totalMs)}" +
                    (if (root.formats.isNotEmpty()) " · " + FolderTree.formatSummary(root.formats) else ""),
                    color = s.dim, fontSize = 11.sp, modifier = Modifier.padding(horizontal = 6.dp))
            }
        } else {
            // ---- 현재 폴더 카드
            item {
                CollapsibleCard("folder_current", node.label, subtitle = FolderTree.formatSummary(node.formats),
                    actions = {
                        val pinned = node.path in vm.pinnedFolders
                        IconAction(if (pinned) YIcons.star else YIcons.starOutline, "pin", { vm.togglePin(node.path) }, size = 34.dp, iconSize = 22.dp,
                            tint = if (pinned) s.accentText else s.dim, state = if (pinned) "고정됨" else null)
                    },
                    peek = {
                        IconAction(YIcons.play, "folder_play", { vm.playFolder(node.path, includeSub, shuffleList, sort) }, framed = true,
                            active = true, size = 40.dp, iconSize = 20.dp)
                    }) {
                    Text(FolderTree.summaryLine(node), color = s.dim, fontSize = 12.sp)
                    Row(Modifier.fillMaxWidth().padding(top = 12.dp).horizontalScroll(rememberScrollState()),
                        horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                        // vr0.1.0.009: 아이콘만 (켬/끔은 강조 테두리, 이름은 길게 누르기 팝업)
                        IconAction(YIcons.play, "folder_play", { vm.playFolder(node.path, includeSub, shuffleList, sort) }, framed = true,
                            active = true, size = 40.dp, iconSize = 20.dp)
                        IconAction(YIcons.shuffle, "folder_shuffle", { shuffleList = !shuffleList; vm.store.folderShuffle = shuffleList },
                            framed = true, active = shuffleList, size = 40.dp, iconSize = 20.dp, state = if (shuffleList) "켬" else "끔", toggle = shuffleList)
                        IconAction(YIcons.subfolder, "folder_sub", { includeSub = !includeSub; vm.store.folderIncludeSub = includeSub },
                            framed = true, active = includeSub, size = 40.dp, iconSize = 20.dp, state = if (includeSub) "켬" else "끔", toggle = includeSub)
                    }
                    Row(Modifier.fillMaxWidth().padding(top = 8.dp).horizontalScroll(rememberScrollState()),
                        horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                        Text("정렬", color = s.dim, fontSize = 12.sp)
                        SORTS.forEach { (k, label) -> Pill(label, on = sort == k, onClick = { sort = k; vm.store.folderSort = k }, small = true) }
                        IconAction(YIcons.up, "folder_up", { open(parent?.path.orEmpty()) }, framed = true, size = 32.dp, iconSize = 16.dp)
                        if (node.path.startsWith("saf:") && !node.path.contains('/'))
                            IconAction(YIcons.close, "folder_remove", { confirmRemove = node.path }, framed = true, size = 32.dp, iconSize = 16.dp)
                    }
                }
            }
            if (node.children.isNotEmpty()) item {
                CollapsibleCard("folder_sub", "하위 폴더 ${node.children.size}", contentPadding = PaddingValues(start = 8.dp, end = 8.dp, bottom = 8.dp)) {
                    node.children.forEach { n -> FolderRow(n, n.path in vm.pinnedFolders, { open(n.path) }, { vm.playFolder(n.path, includeSub, shuffleList, sort) }) }
                }
            }
            if (node.direct.isNotEmpty()) item {
                // 폴더 · 정렬이 바뀔 때만 정렬 (현재 곡 표시가 바뀌어도 다시 정렬하지 않음)
                val songs = remember(node, sort) { vm.sortFolderTracks(node.direct.mapNotNull { vm.folderTracks.getOrNull(it) }, sort) }
                CollapsibleCard("folder_songs", "이 폴더의 곡 ${songs.size}", contentPadding = PaddingValues(start = 6.dp, end = 6.dp, bottom = 8.dp)) {
                    songs.take(SONG_LIMIT).forEachIndexed { i, t ->
                        val cur = t.uri == vm.currentTrack?.uri
                        Row(Modifier.fillMaxWidth().clip(RoundedCornerShape(10.dp))
                            .clickable { vm.playFolder(node.path, includeSub, false, sort, startUri = t.uri) }
                            .padding(horizontal = 8.dp, vertical = 7.dp), verticalAlignment = Alignment.CenterVertically) {
                            Text("%02d. ".format(i + 1), color = s.dim, fontSize = 12.sp)
                            Text(t.display, color = if (cur) s.accentText else s.text, fontSize = 13.sp, maxLines = 1,
                                fontWeight = if (cur) FontWeight.Bold else FontWeight.Normal,
                                overflow = TextOverflow.Ellipsis, modifier = Modifier.weight(1f))
                            val fmt = if (t.clip != null) "CUE" else Formats.formatName(null, t.path.ifEmpty { t.title })
                            Text(fmt, color = s.dim, fontSize = 10.sp, modifier = Modifier.padding(horizontal = 6.dp))
                            if (t.durationMs > 0) Text(fmtTime(t.durationMs), color = s.dim, fontSize = 11.sp)
                        }
                    }
                    if (songs.size > SONG_LIMIT) Text("… ${songs.size - SONG_LIMIT}곡 더 (이 폴더 재생 버튼으로 모두 재생)", color = s.dim,
                        fontSize = 11.sp, modifier = Modifier.padding(8.dp))
                }
            }
        }
        item { Spacer(Modifier.height(8.dp)) }
    }
    if (confirmRemove.isNotEmpty()) AlertDialog(onDismissRequest = { confirmRemove = "" }, title = { Text("폴더 빼기") },
        text = { Text("추가한 폴더를 목록에서 뺄까요? (음악 파일은 지워지지 않습니다)") },
        confirmButton = { TextButton({ vm.removeSafTree(confirmRemove); confirmRemove = ""; open("") }) { Text("빼기") } },
        dismissButton = { TextButton({ confirmRemove = "" }) { Text("취소") } })
}

/** 폴더 한 줄 (시안 폴더 카드): 폴더 아이콘 · 이름 · 곡 수/하위 수 · ▶ */
@Composable
private fun FolderRow(n: FolderTree.Node, pinned: Boolean, onOpen: () -> Unit, onPlay: () -> Unit) {
    val s = LocalSkin.current
    Row(Modifier.fillMaxWidth().padding(vertical = 3.dp).clip(RoundedCornerShape(16.dp)).background(s.surface2)
        .clickable(onClick = onOpen).padding(horizontal = 12.dp, vertical = 10.dp), verticalAlignment = Alignment.CenterVertically) {
        Box(contentAlignment = Alignment.Center) {
            Icon(YIcons.folderFill, null, tint = s.fill1Soft, modifier = Modifier.size(30.dp))
            Icon(YIcons.folder, null, tint = s.accentText, modifier = Modifier.size(30.dp))
        }
        Spacer(Modifier.width(12.dp))
        Column(Modifier.weight(1f)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(n.label, color = s.text, fontSize = 14.sp, maxLines = 1, overflow = TextOverflow.Ellipsis, modifier = Modifier.weight(1f, fill = false))
                if (pinned) Icon(YIcons.star, "고정", tint = s.accentText, modifier = Modifier.padding(start = 4.dp).size(14.dp))
            }
            val sub = "${n.count}곡" + (if (n.children.isNotEmpty()) " · 하위 ${n.children.size}" else "") +
                (if (n.totalMs > 0) " · " + FolderTree.durationText(n.totalMs) else "")
            Text(sub, color = s.dim, fontSize = 11.sp, maxLines = 1)
        }
        IconAction(YIcons.play, "folder_play", onPlay, size = 34.dp, iconSize = 16.dp, tint = s.accentText)
    }
}
