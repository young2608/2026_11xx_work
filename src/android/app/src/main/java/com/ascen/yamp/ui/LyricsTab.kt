package com.ascen.yamp.ui

import android.content.ClipboardManager
import android.content.Context
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.background
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.ascen.yamp.app.AppViewModel
import com.ascen.yamp.lyrics.LyricTiers
import com.ascen.yamp.lyrics.LyricsState
import com.ascen.yamp.lyrics.Reason
import com.ascen.yamp.playback.FloatingLyricsService

// ============================================================ 가사
@OptIn(ExperimentalFoundationApi::class)
@Composable
fun LyricsTab(vm: AppViewModel) {
    val s = LocalSkin.current
    val ly = vm.lyrics
    val ctx = LocalContext.current
    // 화면 꺼짐 방지 (A8): 가사 탭을 보는 동안
    if (vm.store.keepScreenOnLyrics) {
        val view = LocalView.current
        DisposableEffect(Unit) {
            view.keepScreenOn = true
            onDispose { view.keepScreenOn = false }
        }
    }
    var showEdit by remember { mutableStateOf(false) }
    var showPick by remember { mutableStateOf(false) }
    var floating by remember { mutableStateOf(FloatingLyricsService.running) }
    var locked by remember { mutableStateOf(FloatingLyricsService.isLocked) }
    LyricsDialogs(vm, showEdit, showPick, { showEdit = false }, { showPick = false })
    // A1: 다시 찾기로 새 가사를 찾았는데 지금 가사가 직접 편집한 것 → 바꿀지 확인 (확인/취소는 글자 버튼 — D3)
    vm.pendingReplace?.let { f ->
        AlertDialog(onDismissRequest = { vm.confirmReplaceLyrics(false) },
            title = { Text("직접 편집한 가사") },
            text = {
                Text("새 가사를 찾았습니다 (${sourceLabel(f.source)}${if (f.lyrics.synced) " · 싱크" else ""}).\n" +
                    "지금 가사는 직접 편집한 것입니다. 새 가사로 바꿀까요?\n(편집본은 .user.bak 파일로 보관됩니다)")
            },
            confirmButton = { TextButton({ vm.confirmReplaceLyrics(true) }) { Text("바꾸기") } },
            dismissButton = { TextButton({ vm.confirmReplaceLyrics(false) }) { Text("편집 가사 유지") } })
    }
    Column(Modifier.fillMaxSize()) {
        // vr0.1.0.009: 명령은 아이콘만 한 줄 (이름은 길게 누르기 / 마우스 올리기 팝업), 보정값(데이터)만 글자
        val has = vm.currentTrack != null
        Row(Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()).padding(6.dp),
            horizontalArrangement = Arrangement.spacedBy(6.dp), verticalAlignment = Alignment.CenterVertically) {
            IconAction(YIcons.timeMinus, "lyric_offset_minus", { vm.adjustOffset(-500) }, framed = true, size = 38.dp, iconSize = 20.dp)
            Text("%+.1fs".format(vm.offsetMs / 1000.0), color = s.dim, fontSize = 12.sp)
            IconAction(YIcons.timePlus, "lyric_offset_plus", { vm.adjustOffset(500) }, framed = true, size = 38.dp, iconSize = 20.dp)
            IconAction(YIcons.refresh, "lyric_research", vm::researchLyrics, framed = true, size = 38.dp, iconSize = 20.dp)
            IconAction(YIcons.edit, "lyric_edit", { if (has) showEdit = true }, framed = true, size = 38.dp, iconSize = 20.dp, enabled = has)
            IconAction(YIcons.search, "lyric_pick", { if (has) showPick = true }, framed = true, size = 38.dp, iconSize = 20.dp, enabled = has)
            IconAction(YIcons.radio, "radio", { vm.currentTrack?.let { vm.radio(it) } }, framed = true, size = 38.dp, iconSize = 20.dp, enabled = has)
            IconAction(YIcons.floating, "floating", {
                Floating.set(ctx, vm, !floating)
                floating = vm.store.floatingLyrics && Floating.canDraw(ctx)
            }, framed = true, size = 38.dp, iconSize = 20.dp, active = floating, state = if (floating) "켬" else "끔", toggle = floating)
            // A19: 잠금 상태 표시 (강조 테두리 · 화면 읽기 "켬/끔")
            if (floating) IconAction(YIcons.lock, "floating_lock", {
                val on = !locked
                FloatingLyricsService.lock(ctx, on)
                locked = on
            }, framed = true, size = 38.dp, iconSize = 20.dp, active = locked, state = if (locked) "잠김 (터치 통과)" else "풀림", toggle = locked)
        }
        // vr0.1.0.011 (f18 L7): 사유 줄 + 찾은 출처 칩 "알송 · 92점"
        val lst = vm.lyricsState
        Row(Modifier.fillMaxWidth().padding(horizontal = 8.dp), verticalAlignment = Alignment.CenterVertically) {
            Text(vm.lyricsStatus, color = s.dim, fontSize = 12.sp, modifier = Modifier.weight(1f, fill = false))
            lst.chip()?.let { chip ->
                Spacer(Modifier.width(6.dp))
                Text(chip, color = s.accentText, fontSize = 11.sp,
                    modifier = Modifier.background(s.fill1Soft, RoundedCornerShape(8.dp)).padding(horizontal = 6.dp, vertical = 1.dp))
            }
        }
        if (ly == null) {
            Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Text(if (lst.reason == Reason.SEARCHING) "가사 찾는 중…" else lst.line() + "\n위의 다시 찾기 버튼을 눌러 보세요",
                        color = s.dim, textAlign = TextAlign.Center, modifier = Modifier.padding(horizontal = 16.dp))
                    // 못 찾음 → [다른 가사 찾기] [붙여넣기]
                    if (has && lst.notFound) Row(Modifier.padding(top = 8.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        TextButton({ showPick = true }) { Text("다른 가사 찾기", color = s.accentText) }
                        TextButton({
                            val cm = ctx.getSystemService(Context.CLIPBOARD_SERVICE) as? ClipboardManager
                            val clip = runCatching { cm?.primaryClip?.takeIf { it.itemCount > 0 }?.getItemAt(0)?.coerceToText(ctx)?.toString() }.getOrNull()
                            vm.pasteLyrics(clip)
                        }) { Text("붙여넣기", color = s.accentText) }
                    }
                }
            }
            return@Column
        }
        if (!ly.synced) {
            Text("싱크 없는 가사 — 편집(연필) → 싱크 찍기(시계) 로 시각을 넣을 수 있습니다", color = s.dim, fontSize = 11.sp,
                modifier = Modifier.padding(horizontal = 8.dp))
            Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(12.dp)) {
                ly.blocks.forEach { b ->
                    Text(LyricTiers.joined(b.lines, vm.showPron, vm.showTrans, "\n"), color = s.text, fontSize = vm.fontSp.sp, textAlign = TextAlign.Center,
                        modifier = Modifier.fillMaxWidth().padding(vertical = 3.dp))
                }
            }
            return@Column
        }
        val state = rememberLazyListState()
        var userScrollUntil by remember { mutableStateOf(0L) }
        BoxWithConstraints(Modifier.fillMaxSize()) {
            val half = with(LocalDensity.current) { (maxHeight / 2).roundToPx() }
            LaunchedEffect(vm.lyricIndex, ly) {
                if (System.currentTimeMillis() < userScrollUntil) return@LaunchedEffect
                // 현재 줄을 가운데로: 위에 빈 칸(item 0) 이 있으므로 index+1
                state.animateScrollToItem(vm.lyricIndex.coerceAtLeast(0) + 1, -half + 40)
            }
            LaunchedEffect(state.isScrollInProgress) {
                if (state.isScrollInProgress) userScrollUntil = System.currentTimeMillis() + 3000
            }
            LazyColumn(state = state, modifier = Modifier.fillMaxSize()) {
                item { Spacer(Modifier.height(maxHeight / 2)) }
                itemsIndexed(ly.blocks) { k, b ->
                    val cur = k == vm.lyricIndex
                    val inAb = vm.abActive && b.tMs - vm.offsetMs in vm.abA until vm.abB
                    // 3단 가사 (A3): 0 = 원문, 1 = 발음, 2 = 번역 (작고 흐리게)
                    Column(Modifier.fillMaxWidth()
                        .background(if (inAb) s.fill1Soft else androidx.compose.ui.graphics.Color.Transparent)
                        .combinedClickable(onClick = { userScrollUntil = 0; vm.seek(b.tMs - vm.offsetMs) },
                            onLongClick = { vm.repeatLine(k) })
                        .padding(horizontal = 10.dp, vertical = 6.dp),
                        horizontalAlignment = Alignment.CenterHorizontally) {
                        val vis = LyricTiers.visible(b.lines.ifEmpty { listOf("♪") }, vm.showPron, vm.showTrans)
                        vis.forEach { (line, tier) ->
                            val base = if (cur) s.accentText else s.text.copy(alpha = 0.65f)
                            Text(line,
                                color = if (tier == 0) base else base.copy(alpha = base.alpha * 0.7f),
                                fontSize = (if (tier == 0) (if (cur) vm.fontSp + 3 else vm.fontSp) else vm.fontSp - 3).sp,
                                fontWeight = if (cur && tier == 0) FontWeight.Bold else FontWeight.Normal,
                                textAlign = TextAlign.Center, modifier = Modifier.fillMaxWidth())
                        }
                    }
                }
                item { Spacer(Modifier.height(maxHeight / 2)) }
            }
        }
    }
}

/** 가사 출처 표시 이름 */
private fun sourceLabel(src: String): String = if (src == "local") "같은 폴더 .lrc" else LyricsState.sourceLabel(src)
