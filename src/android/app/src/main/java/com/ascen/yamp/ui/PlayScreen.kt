package com.ascen.yamp.ui

import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.basicMarquee
import androidx.compose.foundation.clickable
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
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.runtime.withFrameNanos
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Shadow
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.media3.common.Player
import com.ascen.yamp.app.AppViewModel
import com.ascen.yamp.data.fmtTime
import com.ascen.yamp.lyrics.LyricTiers
import com.ascen.yamp.playback.SleepTimer
import kotlinx.coroutines.delay
import kotlin.math.roundToInt

/**
 * ① 재생 화면 (vr0.1.0.006, 시안 mock_v006 ①):
 *   아트·스펙트럼 카드 → 파형 시크바 카드 → 비주얼라이저 카드 (vr0.1.0.014 → v026 이름) → 3줄 가사 카드 → 재생 버튼 줄(항상 보임) → 노브 카드(볼륨·속도·좋아요·슬립·A-B·더보기)
 *   카드는 모두 접기/펼치기 (상태 기억)
 */
@Composable
fun PlayScreen(vm: AppViewModel, onOpenLyrics: () -> Unit) {
    val s = LocalSkin.current
    var showSpeed by remember { mutableStateOf(false) }
    var showSleep by remember { mutableStateOf(false) }
    var showMore by remember { mutableStateOf(false) }
    // 슬립 타이머 남은 분 (서비스 쪽 SleepTimer 를 1초마다 확인 — 값은 분 단위라 화면은 1분에 한 번만 다시 구성)
    //   withFrameNanos: 화면이 안 보이면(백그라운드) 프레임이 없으므로 여기서 멈춤
    var sleepMin by remember { mutableLongStateOf(-1L) }
    LaunchedEffect(Unit) {
        while (true) {
            withFrameNanos { }
            sleepMin = sleepMinutes(SleepTimer.remainingMs())
            delay(SLEEP_POLL_MS)
        }
    }
    val t = vm.currentTrack
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        ArtCard(vm)
        WaveCard(vm, sleepMin)
        VisCard(vm)             // vr0.1.0.014 (f26 D8) → v026 (f51): 비주얼라이저 (스펙트럼 · 웨이브 · 레벨)
        LyricCard(vm, onOpenLyrics)
        // 재생 버튼 줄 — 접지 않음 (큰 재생 버튼은 항상 누를 수 있게)
        Row(Modifier.fillMaxWidth().padding(horizontal = 6.dp), horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically) {
            // vr0.1.0.009: 글자 없는 아이콘 버튼 — 길게 누르기 / 마우스 올리기 = 설명 팝업 (Tips)
            IconAction(YIcons.shuffle, "shuffle", vm::toggleShuffle, framed = true, size = 46.dp, iconSize = 20.dp,
                active = vm.shuffle, tint = if (vm.shuffle) s.accentText else s.dim, state = if (vm.shuffle) "켬" else "끔", toggle = vm.shuffle)
            IconAction(YIcons.prev, "prev", vm::prev, framed = true, size = 46.dp, iconSize = 20.dp)
            BigPlayButton(vm.isPlaying, vm::toggle)
            IconAction(YIcons.next, "next", vm::next, framed = true, size = 46.dp, iconSize = 20.dp)
            val rep = vm.repeatMode != Player.REPEAT_MODE_OFF
            IconAction(
                when (vm.repeatMode) { Player.REPEAT_MODE_ONE -> YIcons.repeatOne; Player.REPEAT_MODE_ALL -> YIcons.repeat; else -> YIcons.repeatOff },
                when (vm.repeatMode) { Player.REPEAT_MODE_ONE -> "repeat_one"; Player.REPEAT_MODE_ALL -> "repeat_all"; else -> "repeat_off" },
                vm::cycleRepeat, framed = true, size = 46.dp, iconSize = 20.dp, active = rep, tint = if (rep) s.accentText else s.dim)
        }
        CollapsibleCard("play_knobs", "볼륨 · 속도 · 더보기", contentPadding = PaddingValues(start = 6.dp, end = 6.dp, bottom = 12.dp)) {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceAround, verticalAlignment = Alignment.CenterVertically) {
                Knob(vm.userVolume, { vm.setUserVolume(it) }, 0f..1f, 1f, s.hue(5), "볼륨",
                    "${(vm.userVolume * 100).roundToInt()}%", size = 60.dp, step = 0.01f)
                Knob(vm.speed, { vm.setSpeedPitch(it, vm.pitchSt) }, 0.5f..2.0f, 1f, s.hue(7), "속도",
                    "%.2fx".format(vm.speed), size = 60.dp, step = 0.05f)
                // 노브 옆 명령: 아이콘만 (이름 · 상태는 길게 누르기 / 마우스 올리기 팝업)
                IconAction(if (vm.liked) YIcons.heart else YIcons.heartOutline, "like", { vm.toggleLike() }, size = 44.dp, iconSize = 28.dp,
                    tint = if (vm.liked) likeColor(s) else s.dim, state = if (vm.liked) "좋아요 함" else null)
                IconAction(YIcons.moon, "sleep", { showSleep = true }, size = 44.dp, iconSize = 26.dp,
                    tint = if (sleepMin >= 0) (if (s.dark) s.hue(9) else s.accentText) else s.dim, state = if (sleepMin >= 0) "남은 ${sleepMin}분" else null)
                IconAction(YIcons.ab, "ab", vm::cycleAB, size = 44.dp, iconSize = 26.dp,
                    tint = if (vm.abA >= 0) s.accentText else s.dim, active = vm.abActive,
                    state = when { vm.abActive -> "구간 반복 중 (누르면 해제)"; vm.abA >= 0 -> "A 지점 찍음 (누르면 B)"; else -> null })
                IconAction(YIcons.more, "more", { if (t != null) showMore = true }, size = 44.dp, iconSize = 26.dp,
                    tint = s.dim, enabled = t != null)
            }
        }
        Spacer(Modifier.height(8.dp))
    }
    if (showSpeed) SpeedDialog(vm) { showSpeed = false }
    if (showSleep) SleepDialog(vm, sleepMin) { showSleep = false }
    if (showMore && t != null) TrackMenuDialog(vm, t, { showMore = false }, extra = listOf<Pair<String, () -> Unit>>(
        "정지" to { vm.stop() },
        "속도 · 음정 자세히" to { showSpeed = true },
        // vr0.1.0.010 V1: 녹음 · 강의의 긴 무음 건너뛰기 (메뉴 항목은 글자 유지 — D3)
        (if (vm.skipSilence) "무음 건너뛰기 끄기" else "무음 건너뛰기 켜기") to { vm.setSkipSilence(!vm.skipSilence) },
        "가사 보기" to onOpenLyrics,
    ))
}

// ------------------------------------------------------------ 아트 · 스펙트럼
@OptIn(ExperimentalFoundationApi::class)
@Composable
private fun ArtCard(vm: AppViewModel) {
    val s = LocalSkin.current
    val t = vm.currentTrack
    var remaining by rememberSaveable { mutableStateOf(false) }
    val spectrumOn = vm.spectrumOn
    CollapsibleCard("play_art", "앨범아트 · 스펙트럼", contentPadding = PaddingValues(start = 10.dp, end = 10.dp, bottom = 10.dp),
        peek = {
            Text(t?.display ?: "재생할 곡이 없습니다", color = s.text, fontSize = 14.sp, maxLines = 1,
                overflow = TextOverflow.Ellipsis)
        }) {
        // 아트 바탕: 연한 채움 → 면 (써니 = 연노랑 → 크림, 어두운 테마 = fill1Soft → bg). 글자는 text (대비 검사 text|fill1_soft)
        Box(Modifier.fillMaxWidth().height(196.dp).clip(RoundedCornerShape(16.dp))
            .background(Brush.radialGradient(listOf(s.fill1Soft, if (s.dark) s.bg else s.surface2))),
        ) {
            vm.cover?.let { bm ->
                val img = remember(bm) { bm.asImageBitmap() }
                Image(img, null, Modifier.fillMaxSize(), contentScale = ContentScale.Crop, alpha = 0.45f)
            }
            VmSpectrum(vm, spectrumOn, Modifier.fillMaxWidth().height(150.dp).padding(horizontal = 10.dp, vertical = 8.dp))
            if (!spectrumOn) Text("스펙트럼: 설정 → 화면 → 스펙트럼 켜기 (마이크 권한)", color = s.text.copy(alpha = 0.45f), fontSize = 10.sp,
                modifier = Modifier.align(Alignment.TopStart).padding(12.dp))
            Column(Modifier.align(Alignment.BottomStart).padding(start = 14.dp, end = 120.dp, bottom = 12.dp)) {
                Text(t?.title ?: "yMp3Player", color = s.text, fontSize = 19.sp, fontWeight = FontWeight.Bold, maxLines = 1,
                    overflow = TextOverflow.Clip, modifier = Modifier.basicMarquee(iterations = Int.MAX_VALUE),
                    style = if (s.dark) TextStyle(shadow = Shadow(s.bg, Offset(0f, 2f), 8f)) else TextStyle())
                val sub = listOf(t?.artist.orEmpty(), t?.album.orEmpty(), vm.formatLabel).filter { it.isNotBlank() }.joinToString(" · ")
                Text(if (t == null) "목록·가사 → 목록 또는 폴더 탭에서 음악을 추가하세요" else sub, color = s.text.copy(alpha = 0.78f), fontSize = 11.sp,
                    maxLines = 1, overflow = TextOverflow.Ellipsis)
                if (vm.formatHiRes) Text("Hi-Res", color = s.accentText, fontSize = 10.sp, fontWeight = FontWeight.Bold)
            }
            // LCD 시간 (탭 → 경과/남은 시간) — 위치를 읽는 곳은 LcdClock 안만
            LcdClock(vm, remaining, { remaining = !remaining }, Modifier.align(Alignment.BottomEnd).padding(end = 14.dp, bottom = 10.dp))
        }
    }
}

// ------------------------------------------------------------ 파형 시크바
@Composable
private fun WaveCard(vm: AppViewModel, sleepMin: Long) {
    val s = LocalSkin.current
    CollapsibleCard("play_wave", "파형 시크바", contentPadding = PaddingValues(start = 14.dp, end = 14.dp, bottom = 10.dp),
        peek = {
            Row(Modifier.fillMaxWidth()) {
                PosText(vm, s.dim, 11.sp)
                Spacer(Modifier.weight(1f))
                Text(fmtTime(vm.durationMs), color = s.dim, fontSize = 11.sp)
            }
        }) {
        WaveSeekBar(vm.wave, { vm.positionMs }, vm.durationMs, if (vm.abA >= 0) vm.abA else -1L, if (vm.abActive) vm.abB else -1L,
            { vm.seek(it) }, Modifier.fillMaxWidth().height(40.dp))
        Row(Modifier.fillMaxWidth().padding(top = 4.dp), verticalAlignment = Alignment.CenterVertically) {
            PosText(vm, s.dim, 11.sp)
            Spacer(Modifier.weight(1f))
            // A-B: 아이콘 버튼 + 구간 시각(데이터)만 글자로
            IconAction(YIcons.ab, "ab", vm::cycleAB, size = 30.dp, iconSize = 16.dp, active = vm.abA >= 0,
                tint = if (vm.abA >= 0) s.accentText else s.dim)
            if (vm.abA >= 0) Text(if (vm.abActive) "${fmtTime(vm.abA)}~${fmtTime(vm.abB)}" else "${fmtTime(vm.abA)}~",
                color = s.accentText, fontSize = 11.sp, maxLines = 1)
            if (sleepMin >= 0) {
                Spacer(Modifier.width(6.dp))
                Pill("${sleepMin}분", on = true, onClick = {}, icon = YIcons.moon, small = true)
            }
            if (vm.speed != 1f || vm.pitchSt != 0f) {
                Spacer(Modifier.width(6.dp))
                Pill("%.2fx".format(vm.speed), on = true, onClick = {}, small = true)
            }
            if (vm.skipSilence) {
                Spacer(Modifier.width(6.dp))
                Pill("무음 건너뛰기", on = true, onClick = { vm.setSkipSilence(false) }, small = true)
            }
            Spacer(Modifier.weight(1f))
            Text(fmtTime(vm.durationMs), color = s.dim, fontSize = 11.sp)
        }
    }
}

// ------------------------------------------------------------ 3줄 가사
@Composable
private fun LyricCard(vm: AppViewModel, onOpen: () -> Unit) {
    val s = LocalSkin.current
    val ly = vm.lyrics
    val i = vm.lyricIndex
    fun line(k: Int): String = ly?.blocks?.getOrNull(k)?.lines?.firstOrNull().orEmpty()
    val cur: String
    val sub: String
    when {
        ly == null -> { cur = vm.lyricsStatus.ifEmpty { " " }; sub = "" }
        !ly.synced -> { cur = "(싱크 없는 가사 — 목록·가사 → 가사)"; sub = "" }
        i in ly.blocks.indices -> {
            val vis = LyricTiers.visible(ly.blocks[i].lines.ifEmpty { listOf("♪") }, vm.showPron, vm.showTrans)
            cur = vis.firstOrNull { it.second == 0 }?.first ?: "♪"
            sub = vis.filter { it.second > 0 }.joinToString(" · ") { it.first }
        }
        else -> { cur = "♪"; sub = "" }
    }
    CollapsibleCard("play_lyrics", "가사", peek = {
        Text(cur, color = s.accentText, fontSize = 14.sp, maxLines = 1, overflow = TextOverflow.Ellipsis,
            textAlign = TextAlign.Center, modifier = Modifier.fillMaxWidth())
    }) {
        Column(Modifier.fillMaxWidth().clickable(onClick = onOpen), horizontalAlignment = Alignment.CenterHorizontally) {
            val synced = ly != null && ly.synced
            Text(if (synced) line(i - 1).ifEmpty { " " } else " ", color = s.dim.copy(alpha = 0.7f), fontSize = 12.sp, maxLines = 1,
                overflow = TextOverflow.Ellipsis, textAlign = TextAlign.Center)
            Text(cur, color = s.accentText, fontSize = (vm.fontSp).sp, fontWeight = FontWeight.Bold, maxLines = 2,
                overflow = TextOverflow.Ellipsis, textAlign = TextAlign.Center, modifier = Modifier.padding(vertical = 4.dp),
                style = if (s.dark) TextStyle(shadow = Shadow(s.accentText.copy(alpha = 0.5f), Offset.Zero, 12f)) else TextStyle())
            if (sub.isNotEmpty()) Text(sub, color = s.accentText.copy(alpha = 0.75f), fontSize = 12.sp, maxLines = 2,
                overflow = TextOverflow.Ellipsis, textAlign = TextAlign.Center)
            Text(if (synced) line(i + 1).ifEmpty { " " } else " ", color = s.dim.copy(alpha = 0.7f), fontSize = 12.sp, maxLines = 1,
                overflow = TextOverflow.Ellipsis, textAlign = TextAlign.Center)
        }
    }
}

/** 슬립 타이머 확인 주기 */
private const val SLEEP_POLL_MS = 1000L

/** 남은 ms → 올림 분 (-1 = 꺼짐) */
private fun sleepMinutes(ms: Long): Long = if (ms < 0) -1 else (ms + 59_999) / 60_000

/** 좋아요 하트 색: 어두운 테마 = 분홍 계열 (bands 끝), 밝은 테마 = 강조 글자색 (흰 바탕 대비) */
fun likeColor(s: Skin) = if (s.dark) s.hue(10) else s.accentText
