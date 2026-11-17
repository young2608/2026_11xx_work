package com.ascen.yamp.app

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import com.ascen.yamp.core.YLog
import com.ascen.yamp.data.Formats
import com.ascen.yamp.data.MediaScanner
import com.ascen.yamp.data.Track
import com.ascen.yamp.data.Waveform
import com.ascen.yamp.domain.ImageMath
import com.ascen.yamp.domain.LruMap
import com.ascen.yamp.domain.SkipPolicy
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

/**
 * 현재 곡 부가 정보: 앨범아트 · 형식 표시("FLAC 24bit/96kHz") · 파형 시크바 (vr0.1.0.006).
 * vr0.1.0.007: 앨범아트는 크기를 먼저 읽고 짧은 변 ~600px 로 줄여 디코딩 (큰 그림 → 수십 MB 방지),
 *              형식 정보 캐시는 크기 제한(LRU) — 오래 켜 두어도 늘지 않음.
 * vr0.1.0.008: 파형 디코딩은 캐시가 없을 때 곡 넘김 대기(SkipPolicy.WAVE_START_MS) 뒤 — 연달아 넘기면 디코딩이 쌓이지 않음
 */
class MediaInfoController(private val core: AppCore, private val playback: PlaybackController) {
    var cover by mutableStateOf<Bitmap?>(null); private set
    var formatLabel by mutableStateOf(""); private set
    var formatHiRes by mutableStateOf(false); private set
    var wave by mutableStateOf<FloatArray?>(null); private set

    private var coverJob: Job? = null
    private var waveJob: Job? = null
    private val formatCache = LruMap<String, Waveform.FormatInfo>(FORMAT_CACHE_MAX)

    private fun isCurrent(t: Track) = playback.currentTrack?.uri == t.uri

    /** 곡이 바뀜 (t = null 이면 지움) */
    fun load(t: Track?) {
        if (t == null) { clear(); return }
        loadCover(t)
        loadFormatAndWave(t)
    }

    fun clear() {
        coverJob?.cancel(); waveJob?.cancel()
        cover = null; wave = null; formatLabel = ""; formatHiRes = false
    }

    private fun loadCover(t: Track) {
        coverJob?.cancel()
        coverJob = core.scope.launch {
            val bm = core.io("cover", "앨범아트 읽기 실패", null) {
                MediaScanner.cover(core.app, t.uri)?.let(::decodeCover)
            }
            if (isCurrent(t)) cover = bm
        }
    }

    private fun loadFormatAndWave(t: Track) {
        val ctx = core.app
        val key = core.keyOf(t)
        formatLabel = ""
        formatHiRes = false
        wave = null
        waveJob?.cancel()
        waveJob = core.scope.launch {
            val fi = formatCache[t.mediaUri] ?: core.io("format", "형식 읽기 실패", null) { Waveform.probe(ctx, t.mediaUri) }
            if (!isCurrent(t)) return@launch
            if (fi != null) {
                formatCache[t.mediaUri] = fi
                formatLabel = fi.label(t.path.ifEmpty { t.title })
                formatHiRes = fi.hiRes
            } else {
                formatLabel = Formats.formatName(null, t.path)
            }
            if (!core.store.waveform) return@launch
            val w = try {
                core.io("wave", "파형 캐시 읽기 실패", null) { Waveform.cached(ctx, key) } ?: run {
                    // 곡을 빨리 넘기는 중이면 디코딩을 시작하지 않음 (대기 중 곡이 바뀌면 이 Job 이 취소됨)
                    delay(SkipPolicy.WAVE_START_MS)
                    if (!isCurrent(t)) return@launch
                    Waveform.load(ctx, t, key)
                }
            } catch (e: CancellationException) { throw e } catch (e: Exception) {
                YLog.w("wave", "파형 실패", e); null
            }
            if (isCurrent(t)) wave = w
        }
    }

    fun setWaveformEnabled(on: Boolean) {
        core.store.waveform = on
        if (on) playback.currentTrack?.let { loadFormatAndWave(it) } else { waveJob?.cancel(); wave = null }
    }

    companion object {
        /** 형식 정보 캐시 최대 곡 수 */
        const val FORMAT_CACHE_MAX = 256

        /** 크기만 먼저 읽고 → 줄여서 디코딩 */
        fun decodeCover(b: ByteArray): Bitmap? {
            val o = BitmapFactory.Options().apply { inJustDecodeBounds = true }
            BitmapFactory.decodeByteArray(b, 0, b.size, o)
            val opts = BitmapFactory.Options().apply { inSampleSize = ImageMath.sampleSize(o.outWidth, o.outHeight) }
            return BitmapFactory.decodeByteArray(b, 0, b.size, opts)
        }
    }
}
