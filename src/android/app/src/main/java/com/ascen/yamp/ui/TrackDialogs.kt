package com.ascen.yamp.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Icon
import androidx.compose.material3.Slider
import androidx.compose.material3.SliderDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.ascen.yamp.app.AppViewModel
import com.ascen.yamp.data.Track

/** 한 줄 입력칸 (Winamp 스킨 색) */
@Composable
fun SkinField(value: String, onChange: (String) -> Unit, hint: String, modifier: Modifier = Modifier, singleLine: Boolean = true) {
    val s = LocalSkin.current
    Box(modifier.background(s.surface2).padding(8.dp)) {
        if (value.isEmpty()) Text(hint, color = s.dim, fontSize = 14.sp)
        BasicTextField(value, onChange, singleLine = singleLine, cursorBrush = SolidColor(s.accentText),
            textStyle = TextStyle(color = s.text, fontSize = 14.sp), modifier = Modifier.fillMaxWidth())
    }
}

@Composable
internal fun MenuItem(label: String, onClick: () -> Unit) {
    Text(label, fontSize = 16.sp, modifier = Modifier.fillMaxWidth().clickable(onClick = onClick).padding(vertical = 10.dp))
}

/**
 * 곡 길게 누르기 메뉴 (목록·라이브러리·추천 공용):
 * extra(앞쪽 항목) + 다음에 재생 · 대기열 끝에 추가 · 이 곡으로 라디오 · 좋아요 · 별점
 */
@Composable
fun TrackMenuDialog(vm: AppViewModel, t: Track, onDismiss: () -> Unit, extra: List<Pair<String, () -> Unit>> = emptyList()) {
    val s = LocalSkin.current
    val liked = if (t.uri == vm.currentTrack?.uri) vm.liked else vm.isLiked(t)
    val rating = if (t.uri == vm.currentTrack?.uri) vm.rating else vm.ratingOf(t)
    AlertDialog(onDismissRequest = onDismiss,
        title = { Text(t.display, maxLines = 2, overflow = TextOverflow.Ellipsis) },
        text = {
            Column {
                val items: List<Pair<String, () -> Unit>> = extra + listOf<Pair<String, () -> Unit>>(
                    "다음에 재생" to { vm.playNext(t) },
                    "대기열 끝에 추가" to { vm.enqueue(t) },
                    "이 곡으로 라디오" to { vm.radio(t) },
                    (if (liked) "좋아요 취소" else "좋아요") to { vm.toggleLike(t) },
                )
                items.forEach { (label, act) -> MenuItem(label) { act(); onDismiss() } }
                Text("별점", fontSize = 12.sp, modifier = Modifier.padding(top = 6.dp))
                Row(verticalAlignment = Alignment.CenterVertically) {
                    for (r in 1..5) {
                        IconAction(if (r <= rating) YIcons.star else YIcons.starOutline, "rate",
                            { vm.setTrackRating(t, if (r == rating) 0 else r); onDismiss() }, size = 38.dp, iconSize = 30.dp,
                            tint = if (r <= rating) s.accentText else s.dim,
                            state = "별 $r 개")
                    }
                }
            }
        },
        confirmButton = { IconAction(YIcons.close, "close", onDismiss) })
}

/** 재생 속도 · 음정 (A6) */
@Composable
fun SpeedDialog(vm: AppViewModel, onDismiss: () -> Unit) {
    val s = LocalSkin.current
    var sp by remember { mutableFloatStateOf(vm.speed) }
    var st by remember { mutableFloatStateOf(vm.pitchSt) }
    // 슬라이더: 채운 부분 fill1 · 빈 부분 waveRest · 손잡이 fill2 (노랑/주황 = 채움 전용)
    val colors = SliderDefaults.colors(thumbColor = s.fill2, activeTrackColor = s.fill1, inactiveTrackColor = s.waveRest)
    AlertDialog(onDismissRequest = onDismiss, title = { Text("재생 속도 · 음정") },
        text = {
            Column {
                Text("속도 %.2fx".format(sp))
                // 0.5 ~ 2.0, 0.05 단위 → 29 단계 (steps = 구간 수 - 1)
                Slider(sp, { sp = Math.round(it * 20) / 20f; vm.setSpeedPitch(sp, st) }, valueRange = 0.5f..2.0f, steps = 29, colors = colors)
                Text("음정 %+d 반음".format(st.toInt()))
                Slider(st, { st = Math.round(it).toFloat(); vm.setSpeedPitch(sp, st) }, valueRange = -6f..6f, steps = 11, colors = colors)
            }
        },
        confirmButton = { IconAction(YIcons.close, "close", onDismiss) },
        dismissButton = { IconAction(YIcons.reset, "reset", { sp = 1f; st = 0f; vm.setSpeedPitch(1f, 0f) }) })
}

/** 슬립 타이머 고르기 (분) */
private val SLEEP_CHOICES_MIN = listOf(15, 30, 45, 60, 90)

/** 슬립 타이머 (A7) */
@Composable
fun SleepDialog(vm: AppViewModel, remainingMin: Long, onDismiss: () -> Unit) {
    AlertDialog(onDismissRequest = onDismiss, title = { Text("슬립 타이머") },
        text = {
            Column {
                if (remainingMin >= 0) Text("남은 시간 약 ${remainingMin}분", fontWeight = FontWeight.Bold,
                    modifier = Modifier.padding(bottom = 6.dp))
                SLEEP_CHOICES_MIN.forEach { m -> MenuItem("${m}분") { vm.startSleep(m); onDismiss() } }
                MenuItem("곡 끝날 때") { vm.startSleep(0); onDismiss() }
                Text("마지막 ${vm.store.sleepFadeS}초 동안 소리를 줄인 뒤 멈춥니다 (앱을 닫아도 동작)", fontSize = 12.sp)
            }
        },
        confirmButton = { IconAction(YIcons.close, "close", onDismiss) },
        dismissButton = { if (remainingMin >= 0) IconAction(YIcons.trash, "sleep_cancel", { vm.cancelSleep(); onDismiss() }) })
}
