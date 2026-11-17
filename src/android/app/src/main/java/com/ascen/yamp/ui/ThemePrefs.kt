package com.ascen.yamp.ui

import android.content.Context
import android.content.res.Configuration
import com.ascen.yamp.data.Store

/**
 * 앱 화면 밖(홈 위젯 · 플로팅 가사)에서 쓰는 지금 테마 (vr0.1.0.011, f19).
 *   SettingsController 가 테마 이름 · 어두운 모드 따라가기를 SharedPreferences 에 같이 적어 둠 (config.txt 를 읽지 않음)
 */
object ThemePrefs {
    private fun prefs(ctx: Context) = ctx.getSharedPreferences(Store.PREFS, Context.MODE_PRIVATE)

    /** 기기 어두운 모드 */
    fun systemDark(ctx: Context): Boolean =
        (ctx.resources.configuration.uiMode and Configuration.UI_MODE_NIGHT_MASK) == Configuration.UI_MODE_NIGHT_YES

    /** 앱 설정 값 복사 (설정을 바꿀 때 · 시작할 때) */
    fun save(ctx: Context, theme: String, followSystemDark: Boolean) {
        prefs(ctx).edit().putString(ThemeTable.PREF_THEME, theme).putBoolean(ThemeTable.PREF_FOLLOW, followSystemDark).apply()
    }

    /** 지금 보일 테마 (어두운 모드 따라가기 반영) */
    fun current(ctx: Context): ThemeDef {
        val p = prefs(ctx)
        val name = p.getString(ThemeTable.PREF_THEME, ThemeTable.DEFAULT) ?: ThemeTable.DEFAULT
        return ThemeTable.of(ThemeTable.effective(name, p.getBoolean(ThemeTable.PREF_FOLLOW, false), systemDark(ctx)))
    }
}
