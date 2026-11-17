package com.ascen.yamp.ui

import android.app.Activity
import androidx.compose.runtime.Composable
import androidx.compose.runtime.SideEffect
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.platform.LocalView
import androidx.core.view.WindowCompat

/**
 * 상태 막대 · 내비 막대 (vr0.1.0.011, f19): 밝은 테마 = 어두운 아이콘, 어두운 테마 = 밝은 아이콘.
 *   막대 색 = 테마 bg / nav (Android 15 미만 — 15+ 는 edge-to-edge 라 막대가 투명하고 화면 bg 가 비침)
 */
@Suppress("DEPRECATION")
@Composable
fun SystemBars(s: Skin) {
    val view = LocalView.current
    SideEffect {
        val win = (view.context as? Activity)?.window ?: return@SideEffect
        runCatching {
            win.statusBarColor = s.bg.toArgb()
            win.navigationBarColor = s.nav.toArgb()
        }
        val ctl = WindowCompat.getInsetsController(win, view)
        ctl.isAppearanceLightStatusBars = !s.dark
        ctl.isAppearanceLightNavigationBars = !s.dark
    }
}
