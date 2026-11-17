package com.ascen.yamp.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.sizeIn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

/** 선택 알약 (데이터 · 선택지용 — 가수/앨범 등). 명령 버튼은 IconAction (vr0.1.0.009: SkinButton · SkinIconButton 삭제) */
@Composable
fun Chip(text: String, selected: Boolean, onClick: () -> Unit, modifier: Modifier = Modifier) {
    val s = LocalSkin.current
    // vr0.1.0.011: 선택 = 옅은 채움(fill1Soft) + fill1 테두리 + 강조 글자(accentText) — 시안 칩
    val shape = RoundedCornerShape(50)
    Box(
        modifier
            .clip(shape)
            .background(if (selected) s.fill1Soft else s.surface2, shape)
            .border(1.dp, if (selected) s.fill1 else s.line, shape)
            .clickable(onClick = onClick)
            .padding(horizontal = 12.dp, vertical = 6.dp),
    ) {
        Text(text, color = if (selected) s.accentText else s.text, fontSize = 13.sp, maxLines = 1)
    }
}
