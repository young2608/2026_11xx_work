package com.ascen.yamp.playback

import android.media.audiofx.Visualizer
import com.ascen.yamp.core.YLog
import com.ascen.yamp.domain.VisMath
import kotlin.math.hypot
import kotlin.math.min

/**
 * 스펙트럼(Visualizer). 서비스와 화면이 같은 프로세스 → 싱글턴으로 공유.
 * PlaybackService 가 고정 audioSessionId 로 attach. EQ · 베이스는 SoundEngine (기기 효과 안 씀, vr0.1.0.006~).
 * vr0.1.0.007: 화면이 보일 때만 켬 (SettingsController.updateVisualizer), FFT 크기 버퍼 재사용
 * vr0.1.0.014 (f26 D8): 같은 캡처에서 파형도 받음 → 소리 시각화 블럭 (파동 · 레벨 차트). 캡처 주기는 그대로
 */
object Fx {
    /** 스펙트럼 밴드 수 (로그 간격 50Hz~16kHz, v026: 19 → 24 — PC 와 같음) */
    const val BANDS = VisMath.VIS_BANDS
    private const val MAX_CAPTURE_SIZE = 1024
    /** 캡처 주기 상한 (mHz) = 20Hz */
    private const val MAX_RATE_MHZ = 20_000
    /** 표시 범위: -45 dB ~ 0 dB → 0..1 (8비트 FFT 라 PC 의 60 dB 보다 좁게) · 기준 크기 (바이트 FFT 최대 ≈ 128) */
    private const val RANGE_DB = 45.0
    private const val REF = 128.0

    var sessionId: Int = 0; private set
    private var vis: Visualizer? = null
    var onLevels: ((FloatArray) -> Unit)? = null
    /** FFT 크기 버퍼 (콜백 스레드 하나에서만 사용) */
    private var mags = FloatArray(0)

    // ---- 소리 시각화 블럭용 최근 파형 (콜백 스레드가 쓰고 화면이 읽음 → waveLock)
    private val waveLock = Any()
    private var waveBuf = ByteArray(0)
    private var waveLen = 0
    /** 시각화 블럭이 보일 때만 파형 복사 (안 보이면 콜백에서 바로 return) */
    @Volatile var waveWanted = false
    /** 최근 캡처의 RMS · 피크 0..1 */
    @Volatile var waveRms = 0f; private set
    @Volatile var wavePeak = 0f; private set
    /** 캡처 번호 (새 파형이 왔는지) */
    @Volatile var waveSeq = 0L; private set
    /** Visualizer 동작 중 (권한 · 화면 상태 반영) */
    val running: Boolean get() = vis != null

    fun attach(session: Int) {
        sessionId = session
    }

    /** 스펙트럼: RECORD_AUDIO 권한이 있어야 동작 */
    fun startVisualizer(): Boolean {
        if (vis != null) return true
        if (sessionId == 0) return false
        return runCatching {
            val v = Visualizer(sessionId)
            v.captureSize = Visualizer.getCaptureSizeRange()[1].coerceAtMost(MAX_CAPTURE_SIZE)
            val rate = Visualizer.getMaxCaptureRate()
            v.setDataCaptureListener(object : Visualizer.OnDataCaptureListener {
                override fun onWaveFormDataCapture(vz: Visualizer?, w: ByteArray?, sr: Int) {
                    if (w == null || !waveWanted) return
                    synchronized(waveLock) {
                        if (waveBuf.size < w.size) waveBuf = ByteArray(w.size)
                        System.arraycopy(w, 0, waveBuf, 0, w.size)
                        waveLen = w.size
                    }
                    waveRms = VisMath.rms(w)
                    wavePeak = VisMath.peak(w)
                    waveSeq++
                }
                override fun onFftDataCapture(vz: Visualizer?, fft: ByteArray?, samplingRate: Int) {
                    if (fft == null) return
                    val cb = onLevels ?: return
                    if (mags.size < fft.size / 2) mags = FloatArray(fft.size / 2)
                    cb(bandsFromFft(fft, samplingRate / 1000, BANDS, mags))
                }
            }, min(rate, MAX_RATE_MHZ), true, true)
            v.enabled = true
            vis = v
            YLog.d("fx", "스펙트럼 시작")
            true
        }.onFailure { YLog.w("fx", "visualizer: $it") }.getOrDefault(false)
    }

    fun stopVisualizer() {
        val v = vis ?: return
        runCatching { v.enabled = false; v.release() }
        vis = null
        synchronized(waveLock) { waveLen = 0 }
        waveRms = 0f; wavePeak = 0f
        onLevels?.invoke(FloatArray(BANDS))
        YLog.d("fx", "스펙트럼 중지")
    }

    /** 최근 파형 → out (-1..1, out.size 점). 반환: 캡처 번호 (0 = 아직 없음). 메모리 할당 없음 */
    fun readWave(out: FloatArray): Long {
        synchronized(waveLock) { VisMath.wavePoints(waveBuf, waveLen, out) }
        return waveSeq
    }

    /**
     * Visualizer FFT 바이트 → n밴드 0..1. v026 (f51): 계산 = VisMath.bandsFromMags (PC 와 같은 규칙 — 50 Hz~16 kHz 24밴드,
     *   낮은 밴드 보간 · RMS · +3 dB/옥타브). buf = 크기 계산용 재사용 버퍼 (fft.size/2 이상). sr = 표본율 Hz
     */
    fun bandsFromFft(fft: ByteArray, sr: Int, n: Int = BANDS, buf: FloatArray? = null): FloatArray {
        val bins = fft.size / 2
        val m0 = if (buf != null && buf.size >= bins) buf else FloatArray(bins)
        if (bins > 0) m0[0] = 0f
        for (k in 1 until bins) m0[k] = hypot(fft[2 * k].toFloat(), fft[2 * k + 1].toFloat())
        val out = FloatArray(n)
        if (bins < 2 || sr <= 0) return out
        VisMath.bandsFromMags(m0, bins, sr / 2.0 / bins, out, RANGE_DB, REF)
        return out
    }

    fun release() {
        stopVisualizer()
        sessionId = 0
    }
}
