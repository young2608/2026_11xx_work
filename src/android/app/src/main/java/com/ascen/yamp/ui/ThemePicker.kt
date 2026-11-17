package com.ascen.yamp.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

/** 견본 칩 모양 */
private val SwatchShape = RoundedCornerShape(12.dp)

/**
 * 설정 → 화면 → 테마 (vr0.1.0.011, f19): 색 견본 칩 18개 (2열, v024: 기본 8 · 라이트 5단계 · 다크 5단계 묶음). 견본 3칸 = 그 테마의 bg · fill1 · fill2.
 *   누르면 바로 적용 (onPick). 고른 칩 = fill2 굵은 테두리 + 굵은 이름 (시안 테마 목록)
 */
@Composable
fun ThemePicker(current: String, onPick: (String) -> Unit) {
    val s = LocalSkin.current
    val sel = ThemeTable.of(current).name
    // v024: 기본 8 테마 · 라이트 5단계 · 다크 5단계 묶음 (각 묶음 2열 — 라이트++++ 와 다크가 한 줄에 섞이지 않게)
    val groups = listOf(
        null to SKINS.filter { !it.name.startsWith("light") && !it.name.matches(Regex("dark\\d")) },
        "라이트 5단계 (+ = 덜 눈부시게)" to SKINS.filter { it.name.startsWith("light") },
        "다크 5단계 (+ = 더 어둡게)" to SKINS.filter { it.name.matches(Regex("dark\\d")) },
    )
    Column(Modifier.fillMaxWidth().padding(vertical = 6.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        groups.forEach { (title, list) ->
        if (title != null && list.isNotEmpty()) {
            Text(title, color = s.dim, fontSize = 12.sp, fontWeight = FontWeight.Bold, modifier = Modifier.padding(top = 4.dp))
        }
        list.chunked(2).forEach { row ->
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                row.forEach { k ->
                    val on = k.name == sel
                    Column(
                        Modifier.weight(1f).clip(SwatchShape).background(s.surface)
                            .border(if (on) 2.dp else 1.dp, if (on) s.fill2 else s.line, SwatchShape)
                            .clickable { onPick(k.name) },
                    ) {
                        Row(Modifier.fillMaxWidth().height(26.dp)) {
                            Box(Modifier.weight(1f).fillMaxHeight().background(k.bg))
                            Box(Modifier.weight(1f).fillMaxHeight().background(k.fill1))
                            Box(Modifier.weight(1f).fillMaxHeight().background(k.fill2))
                        }
                        Text(if (k.name == ThemeTable.DEFAULT) "${k.label} (기본)" else k.label, color = s.text, fontSize = 12.sp,
                            fontWeight = if (on) FontWeight.Bold else FontWeight.Normal, maxLines = 1, overflow = TextOverflow.Ellipsis,
                            modifier = Modifier.padding(horizontal = 8.dp, vertical = 5.dp))
                    }
                }
                if (row.size == 1) Spacer(Modifier.weight(1f))
            }
        }
        }
    }
}
