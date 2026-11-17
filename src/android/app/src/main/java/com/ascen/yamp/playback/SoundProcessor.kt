package com.ascen.yamp.playback

import android.content.Context
import androidx.annotation.OptIn
import androidx.media3.common.C
import androidx.media3.common.audio.AudioProcessor
import androidx.media3.common.audio.BaseAudioProcessor
import androidx.media3.common.util.UnstableApi
import androidx.media3.exoplayer.Renderer
import androidx.media3.exoplayer.RenderersFactory
import androidx.media3.exoplayer.audio.DefaultAudioSink
import androidx.media3.exoplayer.audio.MediaCodecAudioRenderer
import androidx.media3.exoplayer.mediacodec.MediaCodecSelector
import com.ascen.yamp.core.YLog
import com.ascen.yamp.domain.Dsp
import com.ascen.yamp.domain.SoundSettings
import java.nio.ByteBuffer
import kotlin.math.roundToInt

/**
 * 사운드 엔진 (vr0.1.0.006): 기기 EQ 대신 ExoPlayer 오디오 처리기에서 직접 처리 → 기기와 무관하게 같은 소리.
 *   10밴드 EQ · 프리앰프 · 베이스/트레블 · 밸런스 · 컴프레서 · 리미터 (계산 = domain/Dsp.kt, PC 와 같은 식)
 * 설정: SoundEngine.update(...) → 처리기가 다음 버퍼에서 새 설정으로 필터를 다시 만듦 (재생 끊김 없음)
 * 저장: Store "sound" (SoundSettings.toText) — AppViewModel 이 읽고 씀, 서비스 시작 시 PlaybackService 가 복원
 */
object SoundEngine {
    @Volatile var settings: SoundSettings = SoundSettings()
        private set
    @Volatile var version: Int = 0
        private set

    /** 같은 값이면 무시 (처리기를 다시 만들지 않음 — 필터 상태 유지) */
    fun update(s: SoundSettings) {
        val v = s.clamp()
        if (v == settings) return
        settings = v
        version++
    }

    /**
     * ExoPlayer 용 렌더러 팩토리: 오디오 렌더러 1개 (MediaCodec 디코더 + DefaultAudioSink + SoundProcessor).
     * 음악 전용 앱이라 영상·자막·메타데이터 렌더러는 만들지 않음.
     *   (DefaultRenderersFactory.buildAudioSink 를 오버라이드하는 방법은 media3 버전마다 인자가 달라
     *    — 1.0: 4개(enableOffload), 1.1+: 3개 — 버전에 상관없이 같은 RenderersFactory 인터페이스를 직접 구현)
     */
    @OptIn(UnstableApi::class)
    fun renderersFactory(ctx: Context): RenderersFactory {
        val app = ctx.applicationContext
        return RenderersFactory { handler, _, audioListener, _, _ ->
            val sink = DefaultAudioSink.Builder(app)
                .setAudioProcessors(arrayOf<AudioProcessor>(SoundProcessor()))
                .build()
            arrayOf<Renderer>(MediaCodecAudioRenderer(app, MediaCodecSelector.DEFAULT, handler, audioListener, sink))
        }
    }
}

/**
 * PCM 16bit / float, 1~2채널 처리. 다른 형식(다채널 등)은 처리하지 않음(NOT_SET → 비활성, 그대로 통과).
 * 한 번 설정되면 항상 활성 → EQ 켜기/끄기가 다시 설정(재생 끊김) 없이 바로 적용. 설정이 모두 꺼져 있으면 그대로 복사.
 */
@OptIn(UnstableApi::class)
class SoundProcessor : BaseAudioProcessor() {
    private var encoding = C.ENCODING_INVALID
    private var channels = 0
    private var sampleRate = 0
    private var proc: Dsp.Processor? = null
    private var builtVersion = -1
    private var tmp = DoubleArray(0)
    private var errLogged = false

    override fun onConfigure(inputAudioFormat: AudioProcessor.AudioFormat): AudioProcessor.AudioFormat {
        val enc = inputAudioFormat.encoding
        if ((enc != C.ENCODING_PCM_16BIT && enc != C.ENCODING_PCM_FLOAT) || inputAudioFormat.channelCount !in 1..2) {
            YLog.i("sound", "처리기 건너뜀 (encoding=$enc ch=${inputAudioFormat.channelCount}) — 원음 그대로")
            return AudioProcessor.AudioFormat.NOT_SET
        }
        encoding = enc
        channels = inputAudioFormat.channelCount
        sampleRate = inputAudioFormat.sampleRate
        proc = null
        builtVersion = -1
        YLog.d("sound", "처리기 설정 ${sampleRate}Hz ${channels}ch ${if (enc == C.ENCODING_PCM_FLOAT) "float" else "16bit"}")
        return inputAudioFormat
    }

    private fun current(): Dsp.Processor? {
        val v = SoundEngine.version
        if (proc == null || builtVersion != v) {
            builtVersion = v
            proc = runCatching { Dsp.Processor(SoundEngine.settings, sampleRate, channels) }
                .onFailure { if (!errLogged) { errLogged = true; YLog.e("sound", "처리기 만들기 실패", it) } }
                .getOrNull()
        }
        return proc
    }

    override fun queueInput(inputBuffer: ByteBuffer) {
        val remaining = inputBuffer.remaining()
        if (remaining == 0) return
        val out = replaceOutputBuffer(remaining)
        val p = current()
        if (p == null || !p.active) {
            out.put(inputBuffer)
            out.flip()
            return
        }
        val float = encoding == C.ENCODING_PCM_FLOAT
        val bps = if (float) 4 else 2
        val n = remaining / bps
        if (tmp.size < n) tmp = DoubleArray(n)
        val t = tmp
        if (float) for (i in 0 until n) t[i] = inputBuffer.getFloat().toDouble()
        else for (i in 0 until n) t[i] = inputBuffer.getShort() / PCM16_SCALE
        p.process(t, n - n % channels)
        if (float) {
            for (i in 0 until n) out.putFloat(t[i].toFloat())
        } else {
            for (i in 0 until n) {
                val v = (t[i] * PCM16_SCALE).roundToInt().coerceIn(Short.MIN_VALUE.toInt(), Short.MAX_VALUE.toInt())
                out.putShort(v.toShort())
            }
        }
        // 프레임 단위가 아닌 남은 바이트 (정상이면 없음)
        while (inputBuffer.hasRemaining()) out.put(inputBuffer.get())
        out.flip()
    }

    override fun onFlush() {
        // 탐색(seek) 등: 필터 상태 초기화
        proc = null
    }

    private companion object {
        /** 16bit PCM ↔ -1..1 */
        const val PCM16_SCALE = 32768.0
    }

    override fun onReset() {
        proc = null
        builtVersion = -1
        encoding = C.ENCODING_INVALID
        channels = 0
        sampleRate = 0
        tmp = DoubleArray(0)
    }
}
