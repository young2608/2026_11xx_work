package com.ascen.yamp.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawing
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.ascen.yamp.BuildConfig
import com.ascen.yamp.app.AppViewModel

/** 규칙 9: 버전__빌드시각 */
val VERSION_LABEL = "${BuildConfig.VERSION_NAME}__${BuildConfig.BUILD_TIME}"

/** 하단 내비 5개 (vr0.1.0.006, 상단 칩 탭 대체) — vr0.1.0.009: 아이콘만, 이름은 길게 누르기 팝업 (tip = Tips 키) */
private data class NavItem(val tip: String, val icon: ImageVector)
private val NAV = listOf(
    NavItem(tip = "nav_play", YIcons.playCircle), NavItem(tip = "nav_sound", YIcons.eq), NavItem(tip = "nav_folder", YIcons.folder),
    NavItem(tip = "nav_reco", YIcons.starOutline), NavItem(tip = "nav_list", YIcons.list),
)
private const val NAV_PLAY = 0
private const val NAV_LIST = 4

/** 목록·가사 안의 작은 탭 (아이콘만) */
private val SUBS = listOf(NavItem(tip = "sub_list", YIcons.list), NavItem(tip = "sub_library", YIcons.library),
    NavItem(tip = "sub_lyrics", YIcons.lyrics), NavItem(tip = "sub_settings", YIcons.settings))
private const val SUB_LYRICS = 2

@Composable
fun MainScreen(
    vm: AppViewModel,
    onScanAll: () -> Unit,
    onPickFiles: () -> Unit,
    onSpectrum: (Boolean) -> Unit,
    onAddFolder: () -> Unit = {},
    onRefreshFolders: () -> Unit = {},
) {
    // vr0.1.0.011 (f19 D3): 기기 어두운 모드 따라가기 — 켜져 있고 어두우면 짝 테마 (써니 → 나이트 써니, 밝은 테마 → 다크 블루)
    val skin = skinOf(ThemeTable.effective(vm.theme, vm.followSystemDark, isSystemInDarkTheme()))
    SystemBars(skin)
    YampTheme(skin) {
        CompositionLocalProvider(LocalFoldStore provides vm.store) {
            val s = LocalSkin.current
            var nav by rememberSaveable { mutableIntStateOf(vm.store.navTab.coerceIn(0, NAV.size - 1)) }
            var sub by rememberSaveable { mutableIntStateOf(vm.store.listSub.coerceIn(0, SUBS.size - 1)) }
            fun go(n: Int, sb: Int = -1) {
                nav = n; vm.store.navTab = n
                if (sb >= 0) { sub = sb; vm.store.listSub = sb }
            }
            var showHelp by rememberSaveable { mutableStateOf(!vm.store.helpShown) }
            if (showHelp) HelpDialog(nav) { showHelp = false; vm.store.helpShown = true }
            val ctx = LocalContext.current
            LaunchedEffect(vm.message) {
                if (vm.message.isNotEmpty()) {
                    android.widget.Toast.makeText(ctx, vm.message, android.widget.Toast.LENGTH_SHORT).show()
                    vm.consumeMessage()
                }
            }
            // 플로팅 가사: 마지막 상태 기억 (권한이 있을 때만 다시 시작)
            LaunchedEffect(Unit) {
                if (vm.store.floatingLyrics && Floating.canDraw(ctx)) com.ascen.yamp.playback.FloatingLyricsService.start(ctx)
            }
            // safeDrawing = 상태바 · 내비바 · 카메라 구멍(컷아웃) 모두 피함 (Android 15 edge-to-edge 에서 제목 잘림 방지)
            Column(Modifier.fillMaxSize().background(s.bg).windowInsetsPadding(WindowInsets.safeDrawing)) {
                // 상단 바: [앱 이름] [업비트 시세] [KST 시각] [버전] [?] (vr0.1.0.012, f23 — TopBar.kt), 왼쪽 16dp 여백
                TopBar(vm, onHelp = { showHelp = true },
                    modifier = Modifier.padding(start = 16.dp, end = 16.dp, top = 10.dp, bottom = 8.dp))
                Box(Modifier.weight(1f).fillMaxWidth().padding(horizontal = 14.dp)) {
                    when (nav) {
                        NAV_PLAY -> PlayScreen(vm, onOpenLyrics = { go(NAV_LIST, SUB_LYRICS) })
                        1 -> SoundScreen(vm)
                        2 -> FolderScreen(vm, onAddFolder, onRefreshFolders)
                        3 -> RecommendScreen(vm)
                        else -> ListLyricsScreen(vm, sub, { go(NAV_LIST, it) }, onScanAll, onPickFiles, onSpectrum)
                    }
                }
                if (nav != NAV_PLAY) MiniPlayer(vm, { go(NAV_PLAY) }, Modifier.padding(horizontal = 14.dp, vertical = 6.dp))
                BottomNav(nav) { go(it) }
            }
        }
    }
}

@Composable
private fun BottomNav(sel: Int, onSelect: (Int) -> Unit) {
    val s = LocalSkin.current
    Column(Modifier.fillMaxWidth().background(s.nav)) {
        Box(Modifier.fillMaxWidth().height(1.dp).background(s.line))
        Row(Modifier.fillMaxWidth().height(56.dp), horizontalArrangement = Arrangement.SpaceAround, verticalAlignment = Alignment.CenterVertically) {
            NAV.forEachIndexed { i, item ->
                val on = i == sel
                // weight 는 바깥 Box(TipBox modifier) 에 — TooltipBox 의 modifier 는 안쪽에 붙어 weight 가 듣지 않음
                TipBox(item.tip, Modifier.weight(1f).fillMaxHeight(), anchorModifier = Modifier.fillMaxSize()) {
                    Column(Modifier.fillMaxSize().clickable { onSelect(i) }, horizontalAlignment = Alignment.CenterHorizontally,
                        verticalArrangement = Arrangement.Center) {
                        Icon(item.icon, Tips.of(item.tip).name, tint = if (on) s.accentText else s.dim, modifier = Modifier.size(24.dp))
                        // 선택 표시: 작은 막대 (글자 대신) — 채움 fill2 (써니 = 주황 밑줄)
                        Box(Modifier.padding(top = 5.dp).size(width = 18.dp, height = 3.dp).clip(RoundedCornerShape(50))
                            .background(if (on) s.fill2 else androidx.compose.ui.graphics.Color.Transparent))
                    }
                }
            }
        }
    }
}

/** 도움말: 지금 화면 + 공통 주요 버튼의 아이콘 · 이름 · 설명 (간단한 목록 대화상자) */
@Composable
private fun HelpDialog(nav: Int, onDismiss: () -> Unit) {
    val s = LocalSkin.current
    val play = listOf("play" to YIcons.play, "prev" to YIcons.prev, "next" to YIcons.next, "shuffle" to YIcons.shuffle,
        "repeat_all" to YIcons.repeat, "like" to YIcons.heart, "sleep" to YIcons.moon, "ab" to YIcons.ab, "more" to YIcons.more,
        "vis_bars" to YIcons.visBars, "vis_wave" to YIcons.visWave, "vis_radial" to YIcons.visRadial, "vis_gram" to YIcons.visGram,
        "vis_chart" to YIcons.visChart)
    val navs = NAV.map { it.tip to it.icon }
    // 지금 화면이 재생 화면이면 재생 버튼부터, 아니면 내비부터
    val items = if (nav == NAV_PLAY) play + navs + SUBS.map { it.tip to it.icon } else navs + SUBS.map { it.tip to it.icon } + play
    AlertDialog(onDismissRequest = onDismiss,
        title = { Text("도움말 — 버튼 안내") },
        text = {
            Column(Modifier.heightIn(max = 460.dp).verticalScroll(rememberScrollState())) {
                Text("버튼은 아이콘만 있습니다. 버튼을 길게 누르거나 마우스를 올리면 이름과 설명이 뜹니다.",
                    color = s.dim, fontSize = 12.sp, modifier = Modifier.padding(bottom = 8.dp))
                items.forEach { (k, ic) ->
                    val tip = Tips.of(k)
                    Row(Modifier.fillMaxWidth().padding(vertical = 5.dp), verticalAlignment = Alignment.CenterVertically) {
                        Icon(ic, null, tint = s.accentText, modifier = Modifier.size(22.dp))
                        Column(Modifier.padding(start = 12.dp)) {
                            Text(tip.name, color = s.text, fontSize = 14.sp, fontWeight = FontWeight.Bold, maxLines = 1)
                            Text(tip.desc, color = s.dim, fontSize = 12.sp)
                        }
                    }
                }
            }
        },
        confirmButton = { IconAction(YIcons.check, "close", onDismiss, tint = s.accentText) })
}

/** ④ 추천 (기존 추천 홈을 카드 스타일로) */
@Composable
private fun RecommendScreen(vm: AppViewModel) {
    Column(Modifier.fillMaxSize()) {
        ScreenHeader("추천") {
            IconAction(YIcons.refresh, "reco_refresh", { vm.refreshHome(force = true) }, framed = true, size = 36.dp, iconSize = 18.dp,
                active = vm.homeLoading, state = if (vm.homeLoading) "계산 중" else null)
        }
        HomeTab(vm)
    }
}

/** ⑤ 목록·가사: 작은 분할 버튼(목록 · 라이브러리 · 가사 · 설정) + 기존 화면 */
@Composable
private fun ListLyricsScreen(
    vm: AppViewModel, sub: Int, onSub: (Int) -> Unit,
    onScanAll: () -> Unit, onPickFiles: () -> Unit, onSpectrum: (Boolean) -> Unit,
) {
    val s = LocalSkin.current
    Column(Modifier.fillMaxSize()) {
        Row(Modifier.fillMaxWidth().padding(bottom = 10.dp).clip(RoundedCornerShape(50)).background(s.surface2)
            .border(1.dp, s.line, RoundedCornerShape(50)).padding(3.dp)) {
            SUBS.forEachIndexed { i, item ->
                val on = i == sub
                TipBox(item.tip, Modifier.weight(1f), anchorModifier = Modifier.fillMaxWidth()) {
                    // 선택 = 채움 fill1 + onFill 아이콘 (시안 '가사' 알약)
                    Box(Modifier.fillMaxWidth().clip(RoundedCornerShape(50)).background(if (on) s.fill1 else s.surface2)
                        .clickable { onSub(i) }.padding(vertical = 6.dp), contentAlignment = Alignment.Center) {
                        Icon(item.icon, Tips.of(item.tip).name, tint = if (on) s.onFill else s.text, modifier = Modifier.size(20.dp))
                    }
                }
            }
        }
        if (sub >= SUBS.size - 1) {
            // 설정: 섹션마다 접는 카드
            Box(Modifier.weight(1f).fillMaxWidth()) { SettingsTab(vm, onSpectrum) }
        } else {
            Box(Modifier.weight(1f).fillMaxWidth().neonCard(s)) {
                when (sub) {
                    0 -> PlaylistTab(vm, onScanAll, onPickFiles)
                    1 -> LibraryTab(vm, onScanAll)
                    else -> LyricsTab(vm)
                }
            }
        }
    }
}
