package com.ascen.yamp.ui

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.graphics.Color

/**
 * 화면 색 묶음 (vr0.1.0.011, f19): 토큰 = testdata/themes.txt (ThemeTable) — PC ui/skin.py 와 같은 표.
 *   화면 코드는 고정 색 대신 LocalSkin.current.<토큰> 만 씀 (테마를 바꾸면 모두 바뀜).
 *   쓰는 규칙은 ThemeTable.kt 머리 설명 (노랑/주황 = 채움 전용, 채움 위 = onFill, 강조 글자 = accentText)
 */
class Skin(val def: ThemeDef) {
    val name: String get() = def.name
    val label: String get() = def.label
    /** 어두운 테마 (상태 막대 아이콘 · 빛 효과) */
    val dark: Boolean get() = def.dark

    private fun c(token: String) = Color(def.argb(token))

    val bg = c("bg")
    val surface = c("surface")
    val surface2 = c("surface2")
    val nav = c("nav")
    val line = c("line")
    val text = c("text")
    val dim = c("dim")
    val fill1 = c("fill1")
    val fill1Soft = c("fill1_soft")
    val fill2 = c("fill2")
    val accentText = c("accent_text")
    val onFill = c("on_fill")
    val lcdBg = c("lcd_bg")
    val lcdFg = c("lcd_fg")
    val wavePlayed = c("wave_played")
    val waveRest = c("wave_rest")
    val knob = c("knob")
    val knobRim = c("knob_rim")
    val graphBg = c("graph_bg")
    val graphGrid = c("graph_grid")
    val tooltipBg = c("tooltip_bg")
    val spectrumLo = c("spectrum_lo")
    val spectrumHi = c("spectrum_hi")
    val peak = c("peak")
    /** vr0.1.0.012 (f23): 상단 바 시세 — 상승 빨강 · 하락 파랑 (한국 표기) · 가격 바뀔 때 반짝 바탕 */
    val rise = c("rise")
    val fall = c("fall")
    val flashRise = c("flash_rise")
    val flashFall = c("flash_fall")
    /** EQ 막대 11색 (0 = 프리앰프, 1..10 = 밴드) */
    val bands: List<Color> = def.bands.map { Color(ThemeTable.argb(it)) }

    // ---- 예전 이름 (강조 '글자' 용도로만) — 채움에는 fill1/fill2/fill1Soft 를 직접 씀
    val accent: Color get() = accentText
    val panel: Color get() = surface
    val card2: Color get() = surface2
    val navBg: Color get() = nav
    val listBg: Color get() = surface
    val listFg: Color get() = text
    val listCur: Color get() = accentText
    val lyricCur: Color get() = accentText

    /**
     * 그림용 색 하나 (노브 호 · 좋아요 하트 등): 어두운 테마 = bands[i] (네온이면 예전 색 그대로),
     *   밝은 테마 = bands 진한 쪽 절반 (흰 바탕에서 옅은 노랑이 안 보이지 않게)
     */
    fun hue(i: Int): Color {
        val k = i.coerceIn(0, bands.size - 1)
        return if (dark) bands[k] else bands[bands.size / 2 + k % (bands.size - bands.size / 2)]
    }
}

/** 8 테마 (메뉴 순서) */
val SKINS: List<Skin> = ThemeTable.THEMES.map { Skin(it) }

private val SKIN_BY_NAME = SKINS.associateBy { it.name }

/** 이름 → 색 묶음 (옛 'light' → 클린 블루, 모르는 이름 → 써니) */
fun skinOf(name: String): Skin = SKIN_BY_NAME.getValue(ThemeTable.of(name).name)

val LocalSkin = staticCompositionLocalOf { skinOf(ThemeTable.DEFAULT) }

@Composable
fun YampTheme(s: Skin, content: @Composable () -> Unit) {
    // 대화상자 바탕(surfaceContainerHigh) = surface (밝은 테마에서 보라빛 회색 대신 흰색)
    // primary = 글자 버튼(TextButton) 글자색 → 흰 바탕에서도 보이는 accentText (노랑 글자 금지)
    val scheme = if (s.dark) darkColorScheme(primary = s.accentText, onPrimary = s.bg, background = s.bg, onBackground = s.text,
        surface = s.surface, onSurface = s.text, surfaceContainerHigh = s.surface)
    else lightColorScheme(primary = s.accentText, onPrimary = s.surface, background = s.bg, onBackground = s.text,
        surface = s.surface, onSurface = s.text, surfaceContainerHigh = s.surface)
    MaterialTheme(colorScheme = scheme) {
        androidx.compose.runtime.CompositionLocalProvider(LocalSkin provides s, content = content)
    }
}
