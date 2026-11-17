package com.ascen.yamp.app

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import com.ascen.yamp.data.Store
import com.ascen.yamp.domain.VisMath
import com.ascen.yamp.playback.FloatingLyricsService
import com.ascen.yamp.playback.Fx
import com.ascen.yamp.playback.PlayerWidget
import com.ascen.yamp.ui.ThemePrefs
import com.ascen.yamp.ui.ThemeTable
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/**
 * 화면 설정 (테마 · 가사 글자 크기) + 스펙트럼(Visualizer).
 * vr0.1.0.007: 스펙트럼은 화면이 보일 때만 켬 — 백그라운드 · 화면 꺼짐에서는 Visualizer 를 해제 (초당 20번 FFT 콜백 중지)
 * vr0.1.0.010 (A8): 스펙트럼 켬/끔을 화면 상태(spectrumOn)로
 * vr0.1.0.011 (f19): 8 테마 · 기기 어두운 모드 따라가기 · D2 한 번만 써니로 바꾸기 · 위젯/플로팅 가사에 테마 알림
 */
class SettingsController(private val core: AppCore) {
    private val store get() = core.store

    private val prefs = core.app.getSharedPreferences(Store.PREFS, android.content.Context.MODE_PRIVATE)
    var theme by mutableStateOf(migrateTheme()); private set
    /** 기기 어두운 모드 따라가기 (config follow_system_dark) */
    var followSystemDark by mutableStateOf(store.cfg.bool("follow_system_dark")); private set
    var fontSp by mutableIntStateOf(store.fontSp); private set
    /** 스펙트럼 설정 (화면 상태 — A8: 마이크 권한 허용 뒤 스위치가 바로 켜짐으로 보이게) */
    var spectrumOn by mutableStateOf(store.spectrum); private set

    /** 소리 시각화 블럭 모드 (vr0.1.0.014, f26 D8): wave / bars / chart */
    var visMode by mutableStateOf(VisMath.parseMode(store.visMode)); private set
    /** 스펙트럼 막대 모양 (v027): round / led / mirror / reflex */
    var visBarStyle by mutableStateOf(VisMath.parseBarStyle(store.visBarStyle)); private set

    private val _levels = MutableStateFlow(FloatArray(Fx.BANDS))
    /** 스펙트럼 24밴드 0..1 (v026) */
    val levels: StateFlow<FloatArray> = _levels.asStateFlow()
    private var uiVisible = true

    init { ThemePrefs.save(core.app, theme, followSystemDark) }

    /**
     * D2 (이 버전 처음 실행 때 한 번): 저장된 테마가 이전 기본 'neon' 이면 'sunny' + 알림, 옛 'light' → 'clean_blue'.
     *   한 번 했다는 표시 = SharedPreferences theme_migrated (그 뒤 네온을 다시 골라도 유지)
     */
    private fun migrateTheme(): String {
        val stored = store.theme
        val m = ThemeTable.migrate(stored, prefs.getBoolean(ThemeTable.PREF_MIGRATED, false))
        if (m.theme != stored) store.theme = m.theme
        prefs.edit().putBoolean(ThemeTable.PREF_MIGRATED, true).apply()
        m.toast?.let { core.toast(it) }
        return m.theme
    }

    /** 테마 바꾸기 — 화면은 바로 (상태), 홈 위젯 · 플로팅 가사도 다시 칠함 */
    fun setThemeName(n: String) { theme = n; store.theme = n; themeChanged() }

    fun changeFollowSystemDark(on: Boolean) { followSystemDark = on; store.cfg.set("follow_system_dark", on); themeChanged() }

    private fun themeChanged() {
        ThemePrefs.save(core.app, theme, followSystemDark)
        PlayerWidget.refresh(core.app)
        if (FloatingLyricsService.running) FloatingLyricsService.restyle(core.app)
    }
    fun setFont(sp: Int) { fontSp = sp; store.fontSp = sp }
    /** v027: 이미 스펙트럼인데 스펙트럼을 또 고르면 막대 모양 바꾸기 (둥근 → LED → 미러 → 반사) */
    fun changeVisMode(m: String) {
        val v = VisMath.parseMode(m)
        if (v == VisMath.MODE_BARS && visMode == VisMath.MODE_BARS) {
            visBarStyle = VisMath.nextBarStyle(visBarStyle); store.visBarStyle = visBarStyle
            core.toast("막대 모양: " + VisMath.barStyleName(visBarStyle))
        }
        visMode = v; store.visMode = v
    }

    fun attachSpectrum() { Fx.onLevels = { _levels.value = it } }
    fun detachSpectrum() { Fx.onLevels = null; Fx.waveWanted = false; Fx.stopVisualizer() }

    fun setSpectrum(on: Boolean) {
        store.spectrum = on
        spectrumOn = on
        if (on) { if (!updateVisualizer()) core.toast("스펙트럼 시작 실패 (권한 확인)") } else Fx.stopVisualizer()
    }

    fun setUiVisible(visible: Boolean) {
        uiVisible = visible
        updateVisualizer()
    }

    /** 설정 켜짐 + 화면 보이는 중일 때만 Visualizer 동작. 반환: 켜야 할 때 켜졌는지 */
    fun updateVisualizer(): Boolean {
        val want = store.spectrum && uiVisible
        if (!want) { Fx.stopVisualizer(); return true }
        return Fx.startVisualizer()
    }
}
