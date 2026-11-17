package com.ascen.yamp.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.RichTooltip
import androidx.compose.material3.Text
import androidx.compose.material3.TooltipBox
import androidx.compose.material3.TooltipDefaults
import androidx.compose.material3.rememberTooltipState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Shape
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

/*
 * 글자 없는 아이콘 버튼 + 설명 팝업 (vr0.1.0.009, D7).
 *
 * 설명 팝업 = material3 TooltipBox (1.3.x, @ExperimentalMaterial3Api) + RichTooltip
 *   - 터치/펜: 길게 누르기 (longPressTimeout) → 팝업. 이때 손을 뗀 이벤트는 TooltipBox 가 먹으므로 버튼 클릭은 일어나지 않음
 *   - 마우스 (ChromeOS · DeX · 블루투스 마우스): 올리면(Enter) 팝업, 벗어나면(Exit) 닫힘
 *   - 접근성: TooltipBox 가 onLongClick 의미(semantics)를 붙임 + 아이콘 contentDescription = 설명 이름
 *   - isPersistent = false → 약 1.5초 뒤 저절로 닫힘. 한 번에 팝업 하나 (전역 MutatorMutex)
 *   - focusable = false: 마우스로 팝업이 떠 있는 동안 버튼을 눌러도 첫 클릭이 팝업 닫기로 먹히지 않게
 * 주의: TooltipBox 의 modifier 는 안쪽 Box 에 붙으므로 weight · align 같은 부모용 modifier 는 바깥 Box(여기 TipBox 의 modifier)에 둠
 */

/** 설명 팝업 모양 */
private val TipShape = RoundedCornerShape(12.dp)

/**
 * 설명 팝업 감싸개: content 를 길게 누르거나 마우스를 올리면 Tips[tipKey] 를 보여 줌.
 *   modifier = 바깥 자리 (weight · padding · size), anchorModifier = 실제 누르는 영역 (예: fillMaxSize)
 *   state = 지금 상태 한 줄 (예: "켬", "남은 12분") — 없으면 null
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun TipBox(
    tipKey: String,
    modifier: Modifier = Modifier,
    state: String? = null,
    anchorModifier: Modifier = Modifier,
    contentAlignment: Alignment = Alignment.Center,
    content: @Composable () -> Unit,
) {
    val s = LocalSkin.current
    val tip = Tips.of(tipKey)
    val tipState = rememberTooltipState()
    Box(modifier, contentAlignment = contentAlignment) {
        TooltipBox(
            positionProvider = TooltipDefaults.rememberPlainTooltipPositionProvider(6.dp),
            tooltip = {
                // 팝업이 보일 때만 구성됨 → 여기서 한 번 진동 (버튼마다 코루틴을 돌리지 않음)
                val haptic = LocalHapticFeedback.current
                LaunchedEffect(Unit) { haptic.performHapticFeedback(HapticFeedbackType.LongPress) }
                RichTooltip(
                    modifier = Modifier.border(1.dp, s.line, TipShape),
                    title = { Text(tip.name, color = s.text, fontSize = 14.sp, fontWeight = FontWeight.Bold, maxLines = 1) },
                    shape = TipShape,
                    colors = TooltipDefaults.richTooltipColors(containerColor = s.tooltipBg, contentColor = s.dim, titleContentColor = s.text),
                ) {
                    Column {
                        if (!state.isNullOrEmpty()) Text("지금: $state", color = s.accentText, fontSize = 12.sp, maxLines = 1)
                        if (tip.desc.isNotEmpty()) Text(tip.desc, color = s.text.copy(alpha = 0.8f), fontSize = 12.sp, maxLines = 3)
                        if (tip.shortcut.isNotEmpty()) Text(tip.shortcut, color = s.dim, fontSize = 11.sp, maxLines = 2,
                            modifier = Modifier.padding(top = 2.dp))
                    }
                }
            },
            state = tipState,
            modifier = anchorModifier,
            focusable = false,
        ) { content() }
    }
}

/**
 * 아이콘만 있는 명령 버튼 (원형 물결). active = 강조색(켜짐 표시), framed = 둥근 바탕 + 테두리 (재생 버튼 줄 모양).
 *   tint 를 주면 active 색보다 우선. enabled = false 면 흐리게 + 누르기 안 됨 (설명 팝업은 그대로)
 * vr0.1.0.010 (A19 접근성): toggle = 켜고 끄는 버튼이면 지금 켜짐 여부 → 화면 읽기 프로그램에 "스위치 · 켬/끔" 으로 알림
 *   (Role.Switch + stateDescription), state 가 있으면 그 글을 상태 설명으로 (예: "남은 12분")
 */
@Composable
fun IconAction(
    icon: ImageVector,
    tipKey: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    tint: Color? = null,
    active: Boolean = false,
    enabled: Boolean = true,
    state: String? = null,
    size: Dp = 40.dp,
    iconSize: Dp = size * 0.5f,
    framed: Boolean = false,
    toggle: Boolean? = null,
) {
    val s = LocalSkin.current
    val stateText = state?.takeIf { it.isNotEmpty() } ?: toggle?.let { if (it) "켬" else "끔" }
    val fg = when {
        !enabled -> s.dim.copy(alpha = 0.4f)
        tint != null -> tint
        active -> s.accentText
        else -> s.text
    }
    TipBox(tipKey, modifier, state) {
        Box(
            Modifier.size(size).clip(CircleShape)
                .actionBackground(s, framed, active, CircleShape)
                .clickable(enabled = enabled, role = if (toggle != null) Role.Switch else Role.Button, onClick = onClick)
                .semantics { if (stateText != null) stateDescription = stateText },
            contentAlignment = Alignment.Center,
        ) {
            Icon(icon, Tips.of(tipKey).name, tint = fg, modifier = Modifier.size(iconSize))
        }
    }
}

/** 넓은 아이콘 버튼 (가사 편집기 '현재 줄 찍기' 처럼 가로로 꽉 차는 것): modifier 로 크기, 모서리 둥근 사각 */
@Composable
fun WideIconAction(
    icon: ImageVector,
    tipKey: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    active: Boolean = true,
    iconSize: Dp = 28.dp,
) {
    val s = LocalSkin.current
    val shape = RoundedCornerShape(14.dp)
    TipBox(tipKey, modifier, anchorModifier = Modifier.fillMaxSize()) {
        Box(
            Modifier.fillMaxSize().clip(shape).actionBackground(s, true, active, shape).clickable(onClick = onClick),
            contentAlignment = Alignment.Center,
        ) {
            Icon(icon, Tips.of(tipKey).name, tint = if (active) s.accentText else s.text, modifier = Modifier.size(iconSize))
        }
    }
}

/** 버튼 바탕: framed = surface2 + line 테두리 (켜짐 = 연노랑 fill1Soft + fill1 테두리), 아니면 켜짐일 때만 fill1Soft */
private fun Modifier.actionBackground(s: Skin, framed: Boolean, active: Boolean, shape: Shape): Modifier = when {
    framed -> this.background(if (active) s.fill1Soft else s.surface2, shape)
        .border(1.dp, if (active) s.fill1 else s.line, shape)
    active -> this.background(s.fill1Soft, shape)
    else -> this
}
