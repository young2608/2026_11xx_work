package com.ascen.yamp.ui

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.provider.Settings
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.DialogProperties
import com.ascen.yamp.app.AppViewModel
import com.ascen.yamp.core.YLog
import com.ascen.yamp.data.fmtTime
import com.ascen.yamp.lyrics.LyricEditor
import com.ascen.yamp.playback.FloatingLyricsService

/** 가사 탭 대화상자 — 가사 없음 화면에서도 열 수 있게 LyricsTab 밖에서 */
@Composable
fun LyricsDialogs(vm: AppViewModel, showEdit: Boolean, showPick: Boolean, onEdit: () -> Unit, onPick: () -> Unit) {
    if (showEdit) LyricsEditDialog(vm, onEdit)
    if (showPick) LyricsPickDialog(vm, onPick)
}

/**
 * 가사 편집기 (A1): 텍스트 편집 + 싱크 찍기.
 *  - 텍스트: 현재 가사 줄 (시각 제거). 같은 순서의 줄은 시각 유지
 *  - 싱크 찍기: 깃발(현재 줄 찍기) = 재생 위치를 찍고 다음 줄, −0.1s/+0.1s, 줄 탭 = 선택 + 그 시각으로 이동
 */
@Composable
fun LyricsEditDialog(vm: AppViewModel, onDismiss: () -> Unit) {
    val s = LocalSkin.current
    val ed = remember { LyricEditor.fromLyrics(vm.lyrics) }
    var text by remember { mutableStateOf(ed.text()) }
    var syncMode by remember { mutableStateOf(false) }
    var ver by remember { mutableIntStateOf(0) }           // 편집기 내부 변경 → 다시 그리기
    val listState = rememberLazyListState()
    // 편집기(일반 객체) 상태를 ver 기준 스냅숏으로 → 바뀔 때마다 다시 그림
    val v = ver
    val rows = remember(v, syncMode) { ed.lines.map { it.copy() } }
    val curLine = remember(v, syncMode) { ed.cur }
    val stampedN = remember(v, syncMode) { ed.stamped() }
    LaunchedEffect(curLine, syncMode) { if (syncMode && rows.isNotEmpty()) listState.animateScrollToItem(maxOf(0, curLine - 2)) }
    AlertDialog(onDismissRequest = {}, properties = DialogProperties(usePlatformDefaultWidth = false),
        modifier = Modifier.padding(12.dp),
        title = { Text(if (syncMode) "싱크 찍기 ($stampedN/${rows.size})" else "가사 편집") },
        text = {
            Column {
                // vr0.1.0.009: 모드 · 명령은 아이콘만 (이름은 길게 누르기 팝업)
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    IconAction(YIcons.textMode, "ed_text", { syncMode = false }, framed = true, active = !syncMode, size = 40.dp, iconSize = 20.dp)
                    IconAction(YIcons.clock, "ed_sync", { ed.setText(text); syncMode = true; ver++ }, framed = true, active = syncMode,
                        size = 40.dp, iconSize = 20.dp)
                    IconAction(YIcons.clockOff, "ed_clear", { ed.clearTimes(); ver++ }, framed = true, size = 40.dp, iconSize = 20.dp)
                }
                Spacer(Modifier.height(6.dp))
                if (!syncMode) {
                    SkinField(text, { text = it; ed.setText(it) }, "가사를 입력하세요 (한 줄 = 한 가사 줄)",
                        Modifier.fillMaxWidth().heightIn(min = 200.dp, max = 380.dp), singleLine = false)
                } else {
                    PosText(vm, s.dim, 12.sp, prefix = "재생 ")
                    LazyColumn(state = listState, modifier = Modifier.fillMaxWidth().heightIn(max = 300.dp)) {
                        itemsIndexed(rows) { i, l ->
                            val sel = i == curLine
                            Row(Modifier.fillMaxWidth().background(if (sel) s.fill1Soft else s.surface)
                                .clickable {
                                    ed.select(i); ver++
                                    if (l.tMs >= 0) vm.seek(l.tMs)
                                }.padding(horizontal = 6.dp, vertical = 5.dp)) {
                                Text(if (l.tMs >= 0) fmtTime(l.tMs) + ".%d".format(l.tMs % 1000 / 100) else "--:--  ",
                                    color = s.dim, fontSize = 12.sp, modifier = Modifier.width(60.dp))
                                Text(l.text.ifEmpty { " " }, color = s.text, fontSize = 14.sp,
                                    maxLines = 1, overflow = TextOverflow.Ellipsis)
                            }
                        }
                    }
                    Spacer(Modifier.height(6.dp))
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                        IconAction(YIcons.nudgeBack, "ed_minus", { ed.nudge(-100); ver++ }, framed = true, size = 44.dp, iconSize = 22.dp)
                        IconAction(YIcons.nudgeFwd, "ed_plus", { ed.nudge(100); ver++ }, framed = true, size = 44.dp, iconSize = 22.dp)
                        IconAction(if (vm.isPlaying) YIcons.pause else YIcons.play, "ed_playpause", vm::toggle, framed = true, size = 44.dp,
                            iconSize = 22.dp, state = if (vm.isPlaying) "재생 중" else "멈춤")
                    }
                    Spacer(Modifier.height(6.dp))
                    WideIconAction(YIcons.stamp, "ed_stamp", { ed.stamp(vm.positionMs); ver++ }, Modifier.fillMaxWidth().height(56.dp))
                }
            }
        },
        confirmButton = {
            IconAction(YIcons.save, "ed_save", {
                if (!syncMode) ed.setText(text)
                vm.saveUserLyrics(ed.toLrc())
                onDismiss()
            }, tint = s.accentText)
        },
        dismissButton = { IconAction(YIcons.close, "ed_cancel", onDismiss) })
}

/** 다른 가사 찾기 (A2): 알송 유사검색 + LRCLIB 검색 → 선택 */
@Composable
fun LyricsPickDialog(vm: AppViewModel, onDismiss: () -> Unit) {
    val s = LocalSkin.current
    val t = vm.currentTrack
    var title by remember { mutableStateOf(t?.title.orEmpty()) }
    var artist by remember { mutableStateOf(t?.artist.orEmpty()) }
    LaunchedEffect(Unit) { vm.candidates.clear() }
    AlertDialog(onDismissRequest = onDismiss, properties = DialogProperties(usePlatformDefaultWidth = false),
        modifier = Modifier.padding(12.dp),
        title = { Text("다른 가사 찾기") },
        text = {
            Column {
                SkinField(title, { title = it }, "제목", Modifier.fillMaxWidth())
                Spacer(Modifier.height(4.dp))
                SkinField(artist, { artist = it }, "가수", Modifier.fillMaxWidth())
                Row(Modifier.padding(vertical = 6.dp), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    IconAction(YIcons.search, "search", { vm.searchCandidates(title, artist) }, framed = true, size = 40.dp, iconSize = 20.dp,
                        active = vm.candSearching, state = if (vm.candSearching) "검색 중" else null)
                }
                LazyColumn(Modifier.fillMaxWidth().heightIn(max = 380.dp)) {
                    itemsIndexed(vm.candidates.toList()) { _, c ->
                        Column(Modifier.fillMaxWidth().clickable { vm.chooseCandidate(c); onDismiss() }
                            .padding(vertical = 6.dp)) {
                            Text("${c.label} ${c.artist} - ${c.title}",     // vr0.1.0.011: 출처 · 싱크 · 점수 (점수 높은 순)
                                color = s.text, fontSize = 14.sp, fontWeight = FontWeight.Bold, maxLines = 1, overflow = TextOverflow.Ellipsis)
                            if (c.album.isNotBlank()) Text(c.album, color = s.dim, fontSize = 12.sp, maxLines = 1)
                            Text(c.preview, color = s.text, fontSize = 12.sp, maxLines = 3)
                        }
                    }
                }
            }
        },
        confirmButton = { IconAction(YIcons.close, "close", onDismiss) })
}

// ============================================================ 플로팅 가사 (A4) 권한·시작
object Floating {
    fun canDraw(ctx: Context): Boolean = Settings.canDrawOverlays(ctx)

    /** 켜기: 권한 없으면 설정 화면 열기 (돌아와서 다시 켜기) */
    fun set(ctx: Context, vm: AppViewModel, on: Boolean) {
        if (!on) {
            vm.store.floatingLyrics = false
            FloatingLyricsService.stop(ctx)
            return
        }
        if (!canDraw(ctx)) {
            YLog.i("float", "오버레이 권한 요청 → 설정 화면")
            vm.toast("'다른 앱 위에 표시'를 허용한 뒤 다시 켜 주세요")
            runCatching {
                ctx.startActivity(Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION, Uri.parse("package:${ctx.packageName}"))
                    .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
            }.onFailure { YLog.w("float", "권한 화면 열기 실패", it) }
            return
        }
        vm.store.floatingLyrics = true
        FloatingLyricsService.start(ctx)
    }
}
