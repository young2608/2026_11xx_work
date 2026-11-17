package com.ascen.yamp.ui

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.expandVertically
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.shrinkVertically
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.ascen.yamp.data.Store

/** 카드 접기/펼치기 상태 저장소 (SharedPreferences "fold_<id>") — MainScreen 이 vm.store 를 넣음 */
val LocalFoldStore = staticCompositionLocalOf<Store?> { null }

val CardShape = RoundedCornerShape(22.dp)

/** 네온 카드 바탕: 둥근 22dp + 1dp 테두리 */
fun Modifier.neonCard(s: Skin): Modifier = this
    .fillMaxWidth()
    .clip(CardShape)
    .background(s.surface)
    .border(1.dp, s.line, CardShape)

/**
 * 접을 수 있는 카드 (vr0.1.0.006 — 모든 블록 공통).
 *   머리줄(제목 · 오른쪽 동작 · 꺾쇠) 을 누르면 몸통이 접히고/펼쳐짐. 상태는 id 별로 기억 (앱을 다시 열어도 유지).
 *   peek: 접혔을 때 머리줄 아래에 보일 짧은 내용 (예: 재생 버튼) — 없으면 머리줄만
 */
@Composable
fun CollapsibleCard(
    id: String,
    title: String,
    modifier: Modifier = Modifier,
    subtitle: String = "",
    contentPadding: PaddingValues = PaddingValues(start = 14.dp, end = 14.dp, bottom = 14.dp),
    actions: @Composable RowScope.() -> Unit = {},
    peek: (@Composable ColumnScope.() -> Unit)? = null,
    content: @Composable ColumnScope.() -> Unit,
) {
    val s = LocalSkin.current
    val fold = LocalFoldStore.current
    var expanded by rememberSaveable(id) { mutableStateOf(fold?.folded(id) != true) }
    Column(modifier.neonCard(s)) {
        Row(
            Modifier.fillMaxWidth()
                .clickable {
                    expanded = !expanded
                    fold?.setFolded(id, !expanded)
                }
                .padding(start = 14.dp, end = 8.dp, top = 8.dp, bottom = 6.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(Modifier.weight(1f)) {
                Text(title, color = s.dim, fontSize = 12.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
                if (subtitle.isNotEmpty()) Text(subtitle, color = s.dim.copy(alpha = 0.8f), fontSize = 11.sp, maxLines = 1,
                    overflow = TextOverflow.Ellipsis)
            }
            actions()
            Icon(if (expanded) YIcons.chevronUp else YIcons.chevronDown, if (expanded) "접기" else "펼치기",
                tint = s.dim, modifier = Modifier.padding(start = 4.dp).size(20.dp))
        }
        if (!expanded && peek != null) Column(Modifier.padding(contentPadding)) { peek() }
        AnimatedVisibility(visible = expanded, enter = expandVertically() + fadeIn(), exit = shrinkVertically() + fadeOut()) {
            Column(Modifier.fillMaxWidth().padding(contentPadding)) { content() }
        }
    }
}

/** 알약 버튼 (시안 .pill / .pill.on) */
@Composable
fun Pill(
    text: String,
    on: Boolean = false,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    icon: ImageVector? = null,
    small: Boolean = false,
) {
    val s = LocalSkin.current
    val shape = RoundedCornerShape(50)
    // 선택 = 채움(fill1) + 채움 위 글자색(onFill) — 시안 '가사' 탭 알약
    val fg = if (on) s.onFill else s.text
    Row(
        modifier
            .clip(shape)
            .background(if (on) s.fill1 else s.surface2)
            .border(1.dp, if (on) s.fill1 else s.line, shape)
            .clickable(onClick = onClick)
            .padding(horizontal = if (small) 10.dp else 14.dp, vertical = if (small) 4.dp else 7.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        if (icon != null) {
            Icon(icon, null, tint = fg, modifier = Modifier.size(if (small) 14.dp else 16.dp))
            if (text.isNotEmpty()) Spacer(Modifier.width(5.dp))
        }
        if (text.isNotEmpty()) Text(text, color = fg, fontSize = if (small) 11.sp else 13.sp, maxLines = 1)
    }
}

/** 큰 재생 버튼: fill1 → fill2 그라데이션 (써니 = 노랑 → 주황) + 빛, 아이콘 = onFill */
@Composable
fun BigPlayButton(playing: Boolean, onClick: () -> Unit, modifier: Modifier = Modifier, size: Dp = 70.dp) {
    val s = LocalSkin.current
    val glow = s.fill2
    // vr0.1.0.009: 길게 누르기 / 마우스 올리기 = 설명 팝업
    TipBox(if (playing) "pause" else "play", modifier) { Box(
        Modifier
            .shadow(18.dp, CircleShape, ambientColor = glow, spotColor = glow)
            .size(size)
            .clip(CircleShape)
            .background(Brush.radialGradient(listOf(s.fill1, s.fill2)))
            .clickable(onClick = onClick),
        contentAlignment = Alignment.Center,
    ) {
        Icon(if (playing) YIcons.pause else YIcons.play, Tips.of(if (playing) "pause" else "play").name,
            tint = s.onFill, modifier = Modifier.size(size * 0.4f))
    } }
}

/** 화면 머리줄: 굵은 제목 + 오른쪽 동작 */
@Composable
fun ScreenHeader(title: String, actions: @Composable RowScope.() -> Unit = {}) {
    val s = LocalSkin.current
    Row(Modifier.fillMaxWidth().padding(start = 4.dp, end = 2.dp, top = 2.dp, bottom = 10.dp), verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        Text(title, color = s.text, fontSize = 19.sp, fontWeight = FontWeight.Bold, maxLines = 1, modifier = Modifier.weight(1f))
        actions()
    }
}
