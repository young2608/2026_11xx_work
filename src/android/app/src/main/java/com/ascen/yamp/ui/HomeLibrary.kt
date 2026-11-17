package com.ascen.yamp.ui

import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.derivedStateOf
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.ascen.yamp.app.AppViewModel
import com.ascen.yamp.data.LibraryDb
import com.ascen.yamp.data.Track
import com.ascen.yamp.data.fmtTime
import java.io.File

// ============================================================ 추천 (홈, B2)
@OptIn(ExperimentalFoundationApi::class)
@Composable
fun HomeTab(vm: AppViewModel) {
    val s = LocalSkin.current
    var open by rememberSaveable { mutableStateOf("") }        // 모든 곡을 펼친 카드 id
    var menuFor by remember { mutableStateOf<Track?>(null) }
    LaunchedEffect(Unit) { vm.refreshHome() }
    Column(Modifier.fillMaxSize()) {
        Text("기기 안 재생 기록 기반 · 카드 머리줄을 누르면 접기/펼치기", color = s.dim, fontSize = 11.sp,
            modifier = Modifier.padding(start = 4.dp, bottom = 8.dp))
        val cards by remember { derivedStateOf { vm.homeCards.toList() } }
        if (cards.isEmpty()) {
            Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Text(if (vm.homeLoading) "추천 만드는 중…" else "음악을 몇 곡 들으면 추천이 만들어집니다\n(좋아요를 누르면 더 빨리 만들어져요)",
                    color = s.dim, textAlign = TextAlign.Center)
            }
            return@Column
        }
        LazyColumn(Modifier.fillMaxSize(), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            items(cards, key = { it.id }) { card ->
                val list = remember(card, vm.library.size) { card.keys.mapNotNull { vm.trackOfKey(it) } }
                val all = open == card.id
                CollapsibleCard("rec_${card.id}", card.title, subtitle = "${list.size}곡",
                    actions = { IconAction(YIcons.play, "mix_play", { vm.playMix(list, card.title) }, framed = true, active = true, size = 36.dp, iconSize = 16.dp) }) {
                    val shown = if (all) list else list.take(4)
                    shown.forEachIndexed { i, t ->
                        Text("${i + 1}. ${t.display}", color = if (t.uri == vm.currentTrack?.uri) s.accentText else s.text, fontSize = 13.sp,
                            maxLines = 1, overflow = TextOverflow.Ellipsis,
                            modifier = Modifier.fillMaxWidth().combinedClickable(
                                // A18: 곡 하나 = 그 곡만 (묶음 전체는 ▶ 추천 재생 버튼)
                                onClick = { vm.playMix(listOf(t), card.title) },
                                onLongClick = { menuFor = t }).padding(vertical = 6.dp))
                    }
                    if (list.size > 4) Row(Modifier.fillMaxWidth().clickable { open = if (all) "" else card.id }.padding(vertical = 4.dp),
                        verticalAlignment = Alignment.CenterVertically) {
                        Text(if (all) "접기" else "${list.size - 4}곡 더 보기", color = s.dim, fontSize = 12.sp)
                        Icon(if (all) YIcons.chevronUp else YIcons.chevronDown, null, tint = s.dim, modifier = Modifier.size(16.dp))
                    }
                }
            }
        }
    }
    menuFor?.let { t -> TrackMenuDialog(vm, t, { menuFor = null }) }
}

// ============================================================ 라이브러리 (C2)
private enum class Group(val label: String) { ARTIST("가수"), ALBUM("앨범"), GENRE("장르"), FOLDER("폴더") }

private fun groupName(g: Group, r: LibraryDb.Row): String = when (g) {
    Group.ARTIST -> r.track.artist.ifBlank { "(가수 없음)" }
    Group.ALBUM -> r.track.album.ifBlank { "(앨범 없음)" }
    Group.GENRE -> r.track.genre.ifBlank { "(장르 없음)" }
    Group.FOLDER -> r.track.folder.ifBlank { "(폴더 없음)" }
}

@OptIn(ExperimentalFoundationApi::class)
@Composable
fun LibraryTab(vm: AppViewModel, onScanAll: () -> Unit) {
    val s = LocalSkin.current
    var groupBy by rememberSaveable { mutableStateOf(Group.ARTIST.name) }
    var query by remember { mutableStateOf("") }
    var open by remember { mutableStateOf("") }
    var menuFor by remember { mutableStateOf<Track?>(null) }
    LaunchedEffect(Unit) { vm.refreshLibrary() }
    val g = Group.valueOf(groupBy)
    val q = query.trim().lowercase()
    // 라이브러리 · 검색어가 바뀔 때만 다시 거름 → groups 의 remember 가 실제로 재사용됨 (매번 새 목록이면 매번 정렬)
    val rows: List<LibraryDb.Row> by remember(q) {
        derivedStateOf {
            val all = vm.library.toList()
            if (q.isEmpty()) all else all.filter { r ->
                val t = r.track
                t.title.lowercase().contains(q) || t.artist.lowercase().contains(q) || t.album.lowercase().contains(q) ||
                    t.genre.lowercase().contains(q) || t.folder.lowercase().contains(q)
            }
        }
    }
    val groups = remember(rows, g) {
        // (대소문자만 다른 이름은 별도 그룹 — toSortedMap(CASE_INSENSITIVE) 는 합쳐 버리므로 쓰지 않음)
        rows.groupBy { groupName(g, it) }.toList().sortedWith(compareBy({ it.first.lowercase() }, { it.first }))
    }
    Column(Modifier.fillMaxSize()) {
        Row(Modifier.fillMaxWidth().padding(6.dp), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            Group.entries.forEach { e -> Chip(e.label, g == e, { groupBy = e.name; open = "" }) }
        }
        SkinField(query, { query = it }, "검색 (제목·가수·앨범·장르·폴더)", Modifier.fillMaxWidth().padding(horizontal = 6.dp))
        if (vm.library.isEmpty()) {
            Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Text("라이브러리가 비어 있습니다.\n아래 스캔 버튼(또는 목록 탭의 파일 추가)으로 곡을 불러오세요", color = s.dim, textAlign = TextAlign.Center)
                    Spacer(Modifier.padding(6.dp))
                    IconAction(YIcons.scan, "scan", onScanAll, framed = true, size = 48.dp, iconSize = 24.dp, active = vm.scanning,
                        state = if (vm.scanning) "스캔 중" else null)
                }
            }
            return@Column
        }
        LazyColumn(Modifier.fillMaxSize()) {
            groups.forEach { (name, list) ->
                val expanded = open == name
                item(key = "g:$name") {
                    Row(Modifier.fillMaxWidth().clickable { open = if (expanded) "" else name }
                        .background(if (expanded) s.surface2 else s.surface).padding(horizontal = 8.dp, vertical = 8.dp),
                        verticalAlignment = Alignment.CenterVertically) {
                        val label = if (g == Group.FOLDER) File(name).name.ifEmpty { name } else name
                        Icon(if (expanded) YIcons.chevronDown else YIcons.chevronRight, null, tint = s.dim, modifier = Modifier.size(18.dp))
                        Text(label, color = s.text, fontSize = 14.sp,
                            fontWeight = FontWeight.Bold, maxLines = 1, overflow = TextOverflow.Ellipsis, modifier = Modifier.weight(1f).padding(start = 4.dp))
                        Text("${list.size}", color = s.dim, fontSize = 12.sp, modifier = Modifier.padding(horizontal = 6.dp))
                        if (expanded) IconAction(YIcons.play, "group_play", { vm.playMix(list.map { it.track }, "${g.label}: $name") },
                            framed = true, active = true, size = 32.dp, iconSize = 16.dp)
                    }
                }
                if (expanded) items(list, key = { "t:$name:${it.key}" }) { r ->
                    val t = r.track
                    val cur = t.uri == vm.currentTrack?.uri
                    Row(Modifier.fillMaxWidth().combinedClickable(
                        // A18: 곡 하나 = 그 곡만 (묶음 전체는 ▶ 전체 재생 버튼)
                        onClick = { vm.playMix(listOf(t), "${g.label}: $name") },
                        onLongClick = { menuFor = t }).padding(start = 22.dp, end = 8.dp, top = 6.dp, bottom = 6.dp),
                        verticalAlignment = Alignment.CenterVertically) {
                        if (r.liked) Icon(YIcons.heart, "좋아요", tint = likeColor(s), modifier = Modifier.padding(end = 4.dp).size(14.dp))
                        Text(t.display, color = if (cur) s.accentText else s.text,
                            fontWeight = if (cur) FontWeight.Bold else FontWeight.Normal, fontSize = 13.sp,
                            maxLines = 1, overflow = TextOverflow.Ellipsis, modifier = Modifier.weight(1f))
                        if (r.rating > 0) {
                            Icon(YIcons.star, "별점", tint = s.accentText, modifier = Modifier.size(12.dp))
                            Text("${r.rating} ", color = s.accentText, fontSize = 11.sp)
                        }
                        if (t.durationMs > 0) Text(fmtTime(t.durationMs), color = s.dim, fontSize = 12.sp)
                    }
                }
            }
        }
    }
    menuFor?.let { t -> TrackMenuDialog(vm, t, { menuFor = null }) }
}
