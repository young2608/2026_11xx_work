package com.ascen.yamp.app

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import com.ascen.yamp.core.YLog
import com.ascen.yamp.domain.Dsp
import com.ascen.yamp.domain.SoundSettings
import com.ascen.yamp.playback.PlayerHolder
import com.ascen.yamp.playback.SoundEngine
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlin.math.abs

/**
 * 사운드 (vr0.1.0.006 — SoundEngine: 10밴드 EQ · 프리앰프 · 톤 · 밸런스 · 다이내믹) + 앱 볼륨 노브.
 * vr0.1.0.007: EQ 막대를 끄는 동안(초당 수십 번) 저장은 SAVE_DEBOUNCE_MS 뒤 한 번만, 같은 값이면 처리기를 다시 만들지 않음.
 */
class SoundController(private val core: AppCore) {
    private val store get() = core.store

    var sound by mutableStateOf(SoundSettings.fromText(store.sound)); private set
    /** 내 프리셋 (이름, SoundSettings 텍스트) */
    val userPresets = mutableStateListOf<Pair<String, String>>().apply { addAll(store.userPresets) }
    /** 앱 볼륨 노브 (PlayerHolder.applyVolume 에서 곱함) */
    var userVolume by mutableFloatStateOf(store.userVolume.coerceIn(0f, 1f)); private set

    private var saveJob: Job? = null

    /** 시작 시: 저장된 설정을 엔진 · 플레이어에 (서비스도 시작 시 같은 값을 읽음) */
    fun applyStored() {
        runCatching { SoundEngine.update(sound) }.onFailure { YLog.w("sound", "사운드 설정 적용 실패", it) }
        PlayerHolder.userVolume = userVolume
    }

    fun updateSound(s: SoundSettings) {
        val v = s.clamp()
        if (v == sound) return
        sound = v
        runCatching { SoundEngine.update(v) }.onFailure { YLog.e("sound", "사운드 설정 적용 실패", it) }
        saveJob?.cancel()
        saveJob = core.scope.launch {
            delay(SAVE_DEBOUNCE_MS)
            persist(v)
        }
    }

    private fun persist(v: SoundSettings) {
        runCatching { store.sound = v.toText() }.onFailure { YLog.e("sound", "사운드 설정 저장 실패", it) }
    }

    /** 대기 중인 저장을 바로 (onCleared) */
    fun flush() {
        if (saveJob?.isActive == true) { saveJob?.cancel(); persist(sound) }
        saveJob = null
    }

    /** EQ 밴드 하나 (-12..12 dB, 0.5 단위) */
    fun setBand(i: Int, db: Double) {
        if (i !in 0 until Dsp.EQ_FREQS.size) return
        val b = sound.bands.toMutableList()
        b[i] = Math.round(db * 2) / 2.0
        updateSound(sound.copy(bands = b, enabled = true))
    }

    fun applyPreset(name: String) {
        Dsp.PRESETS.firstOrNull { it.first == name }?.let { (n, bands) ->
            updateSound(sound.copy(bands = bands, enabled = true))
            YLog.i("sound", "프리셋 $n")
            return
        }
        userPresets.firstOrNull { it.first == name }?.let { (n, txt) ->
            val p = SoundSettings.fromText(txt)
            // 내 프리셋: EQ · 프리앰프 · 톤 (밸런스·다이내믹은 그대로)
            updateSound(sound.copy(enabled = true, preampDb = p.preampDb, bands = p.bands, bassDb = p.bassDb, trebleDb = p.trebleDb))
            YLog.i("sound", "내 프리셋 $n")
        }
    }

    /** 지금 EQ 값과 같은 프리셋 이름 (없으면 "") */
    fun presetNameOf(s: SoundSettings): String {
        Dsp.PRESETS.firstOrNull { (_, b) -> sameBands(b, s.bands) }?.let { return it.first }
        userPresets.firstOrNull { (_, t) ->
            val p = SoundSettings.fromText(t)
            sameBands(p.bands, s.bands) && same(p.preampDb, s.preampDb) && same(p.bassDb, s.bassDb) && same(p.trebleDb, s.trebleDb)
        }?.let { return it.first }
        return ""
    }

    fun saveUserPreset(name: String) {
        val n = name.trim().ifEmpty { "내 프리셋 ${userPresets.size + 1}" }
        val i = userPresets.indexOfFirst { it.first == n }
        val v = n to sound.toText()
        if (i >= 0) userPresets[i] = v else userPresets.add(v)
        store.userPresets = userPresets.toList()
        core.toast("프리셋 저장: $n")
        YLog.i("sound", "내 프리셋 저장 $n")
    }

    fun deleteUserPreset(name: String) {
        userPresets.removeAll { it.first == name }
        store.userPresets = userPresets.toList()
        core.toast("프리셋 삭제: $name")
    }

    fun resetSound() {
        updateSound(SoundSettings(enabled = sound.enabled))
        core.toast("사운드 초기화")
    }

    fun changeVolume(v: Float) {
        val x = v.coerceIn(0f, 1f)
        userVolume = x
        store.userVolume = x
        PlayerHolder.userVolume = x
        PlayerHolder.applyVolume()
    }

    companion object {
        /** 설정 저장 지연 (막대를 끄는 동안 SharedPreferences 쓰기를 모음) */
        const val SAVE_DEBOUNCE_MS = 400L
        /** 프리셋 비교 허용 오차 (dB) */
        private const val EPS_DB = 0.01

        private fun same(a: Double, b: Double) = abs(a - b) < EPS_DB
        private fun sameBands(a: List<Double>, b: List<Double>) = a.size <= b.size && a.indices.all { same(a[it], b[it]) }
    }
}
