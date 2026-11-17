package com.ascen.yamp.ui

import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.background
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.derivedStateOf
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.ascen.yamp.app.AppViewModel
import com.ascen.yamp.data.fmtTime

// ============================================================ 목록
@OptIn(ExperimentalFoundationApi::class)
@Composable
fun PlaylistTab(vm: AppViewModel, onScanAll: () -> Unit, onPickFiles: () -> Unit) {
    val s = LocalSkin.current
    var query by remember { mutableStateOf("") }
    var menuFor by remember { mutableIntStateOf(-1) }
    var confirmClear by remember { mutableStateOf(false) }
    val listState = rememberLazyListState()
    val q = query.trim().lowercase()
    // 목록 · 검색어가 바뀔 때만 다시 계산 (현재 곡 · 대기열 표시가 바뀌어도 필터를 다시 돌리지 않음)
    val rows: List<Int> by remember(q) {
        derivedStateOf {
            val list = vm.tracks
            if (q.isEmpty()) list.indices.toList()
            else list.indices.filter { list[it].display.lowercase().contains(q) || list[it].album.lowercase().contains(q) }
        }
    }
    LaunchedEffect(vm.current) {
        val r = rows.indexOf(vm.current)
        if (r >= 0 && listState.layoutInfo.visibleItemsInfo.none { it.index == r }) listState.animateScrollToItem(maxOf(0, r - 2))
    }
    Column(Modifier.fillMaxSize()) {
        // vr0.1.0.009: 아이콘만 (이름은 길게 누르기 팝업)
        Row(Modifier.fillMaxWidth().padding(6.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            IconAction(YIcons.scan, "scan", onScanAll, framed = true, size = 38.dp, iconSize = 20.dp, active = vm.scanning,
                state = if (vm.scanning) "스캔 중" else null)
            IconAction(YIcons.addFile, "add_files", onPickFiles, framed = true, size = 38.dp, iconSize = 20.dp)
            IconAction(YIcons.trash, "list_clear", { confirmClear = true }, framed = true, size = 38.dp, iconSize = 20.dp)
        }
        Box(Modifier.fillMaxWidth().padding(horizontal = 6.dp).background(s.surface2).padding(8.dp)) {
            if (query.isEmpty()) Text("검색", color = s.dim, fontSize = 14.sp)
            BasicTextField(query, { query = it }, singleLine = true, cursorBrush = SolidColor(s.accentText),
                textStyle = TextStyle(color = s.text, fontSize = 14.sp), modifier = Modifier.fillMaxWidth())
        }
        // 대기열 (B5): 현재 곡 뒤에 끼워 넣은 곡
        if (vm.queued > 0 && vm.current >= 0) {
            Row(Modifier.fillMaxWidth().padding(horizontal = 8.dp, vertical = 4.dp), verticalAlignment = Alignment.CenterVertically) {
                Text("다음 재생 ${vm.queued}곡", color = s.accentText, fontSize = 13.sp, fontWeight = FontWeight.Bold,
                    modifier = Modifier.weight(1f))
                IconAction(YIcons.trash, "queue_clear", vm::clearQueue, framed = true, size = 32.dp, iconSize = 16.dp)
            }
        }
        if (vm.tracks.isEmpty()) {
            Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Text("위의 스캔 버튼으로 기기의 음악을 불러오거나\n파일 추가 버튼으로 곡을 고르세요", color = s.dim, textAlign = TextAlign.Center)
            }
            return@Column
        }
        LazyColumn(state = listState, modifier = Modifier.fillMaxSize()) {
            itemsIndexed(rows, key = { _, i -> vm.tracks.getOrNull(i)?.uri?.let { "$it#$i" } ?: "x$i" }) { _, i ->
                val t = vm.tracks.getOrNull(i) ?: return@itemsIndexed
                val cur = i == vm.current
                val inQueue = vm.current >= 0 && i in (vm.current + 1)..(vm.current + vm.queued)
                Row(Modifier.fillMaxWidth().background(if (cur) s.fill1Soft else if (inQueue) s.surface2 else androidx.compose.ui.graphics.Color.Transparent)
                    .combinedClickable(onClick = { vm.playIndex(i) }, onLongClick = { menuFor = i })
                    .padding(horizontal = 8.dp, vertical = 7.dp)) {
                    Text("${i + 1}. ${t.display}", color = if (cur) s.accentText else s.text,
                        fontWeight = if (cur) FontWeight.Bold else FontWeight.Normal, fontSize = 14.sp,
                        maxLines = 1, overflow = TextOverflow.Ellipsis, modifier = Modifier.weight(1f))
                    if (t.durationMs > 0) Text(fmtTime(t.durationMs), color = s.dim, fontSize = 12.sp)
                }
            }
        }
    }
    if (menuFor >= 0) {
        val i = menuFor
        val t = vm.tracks.getOrNull(i)
        if (t == null) menuFor = -1
        else TrackMenuDialog(vm, t, { menuFor = -1 }, extra = listOf<Pair<String, () -> Unit>>(
            "재생" to { vm.playIndex(i) }, "위로 이동" to { vm.move(i, i - 1) },
            "아래로 이동" to { vm.move(i, i + 1) }, "목록에서 삭제" to { vm.remove(i) }))
    }
    if (confirmClear) {
        AlertDialog(onDismissRequest = { confirmClear = false }, title = { Text("목록 비우기") },
            text = { Text("플레이리스트를 모두 지울까요? (음악 파일은 지워지지 않습니다)") },
            confirmButton = { TextButton({ vm.clear(); confirmClear = false }) { Text("비우기") } },
            dismissButton = { TextButton({ confirmClear = false }) { Text("취소") } })
    }
}
