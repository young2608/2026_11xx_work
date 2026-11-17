package com.ascen.yamp.data

import android.content.Context
import android.media.MediaCodec
import android.media.MediaExtractor
import android.media.MediaFormat
import android.net.Uri
import android.os.Build
import com.ascen.yamp.core.YLog
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeoutOrNull
import java.io.File
import java.nio.ByteOrder
import kotlin.coroutines.coroutineContext

/**
 * 파형 시크바 (vr0.1.0.006): MediaExtractor + MediaCodec 으로 곡을 한 번 디코딩 → 피크 160개.
 *  - Dispatchers.Default, 곡이 바뀌면 호출한 쪽이 Job 취소 (디코딩 루프가 매번 취소 확인)
 *  - 20분 넘는 곡 / 15초 안에 못 끝나면 포기 → 화면은 일반 막대 (null)
 *  - 결과 캐시: filesDir/waveform/<key>.bin (1바이트 × 160)
 *  - vr0.1.0.008: 캐시가 없으면 그 곡에 SkipPolicy.WAVE_START_MS 머문 뒤에 디코딩 시작 (MediaInfoController)
 */
object Waveform {
    const val BUCKETS = 160
    private const val MAX_MS = 20 * 60_000L
    private const val TIMEOUT_MS = 15_000L
    /** 코덱 버퍼 대기 (µs) — 짧게 해서 취소 확인을 자주 */
    private const val DEQUEUE_US = 10_000L
    private const val ENC_PCM_16BIT = 2       // AudioFormat.ENCODING_PCM_16BIT
    private const val ENC_PCM_FLOAT = 4       // AudioFormat.ENCODING_PCM_FLOAT
    private const val DEFAULT_RATE = 44100
    private const val DEFAULT_CHANNELS = 2

    /** 결과 캐시 폴더 (Maintenance 가 파일 수 제한) */
    fun cacheDir(ctx: Context): File = File(ctx.filesDir, "waveform")

    private fun cacheFile(ctx: Context, key: String) = File(cacheDir(ctx).apply { mkdirs() }, "$key.bin")

    /** 캐시에 있는 파형만 (디코딩 없음). 호출은 IO 스레드 */
    fun cached(ctx: Context, key: String): FloatArray? {
        val f = cacheFile(ctx, key)
        if (!f.exists()) return null
        return runCatching { WavePeaks.decode(f.readBytes()) }.getOrNull()?.takeIf { it.size == BUCKETS }
    }

    suspend fun load(ctx: Context, t: Track, key: String): FloatArray? = withContext(Dispatchers.Default) {
        val f = cacheFile(ctx, key)
        cached(ctx, key)?.let { return@withContext it }
        if (t.durationMs > MAX_MS) return@withContext null
        val clip = t.clip
        val t0 = System.currentTimeMillis()
        val res = runCatching {
            withTimeoutOrNull(TIMEOUT_MS) {
                decode(ctx, Uri.parse(t.mediaUri), (clip?.startMs ?: 0L) * 1000, clip?.endMs?.takeIf { it > 0 }?.let { it * 1000 } ?: -1L)
            }
        }.onFailure { e ->
            if (e is kotlinx.coroutines.CancellationException) throw e
            YLog.w("wave", "파형 실패 ${t.display}: $e")
        }.getOrNull()
        if (res == null) {
            YLog.d("wave", "파형 없음 ${t.display} (${System.currentTimeMillis() - t0}ms)")
            return@withContext null
        }
        runCatching { f.writeBytes(WavePeaks.encode(res)) }
        YLog.d("wave", "파형 ${t.display} ${System.currentTimeMillis() - t0}ms")
        res
    }

    private suspend fun decode(ctx: Context, uri: Uri, startUs: Long, endUs: Long): FloatArray? {
        val ex = MediaExtractor()
        var codec: MediaCodec? = null
        try {
            ex.setDataSource(ctx, uri, null)
            var track = -1
            for (i in 0 until ex.trackCount) {
                if (ex.getTrackFormat(i).getString(MediaFormat.KEY_MIME)?.startsWith("audio/") == true) { track = i; break }
            }
            if (track < 0) return null
            val fmt = ex.getTrackFormat(track)
            val mime = fmt.getString(MediaFormat.KEY_MIME) ?: return null
            val fileDurUs = if (fmt.containsKey(MediaFormat.KEY_DURATION)) fmt.getLong(MediaFormat.KEY_DURATION) else 0L
            val stopUs = if (endUs > 0) endUs else fileDurUs
            val spanUs = stopUs - startUs
            if (spanUs <= 0 || spanUs > MAX_MS * 1000) return null
            ex.selectTrack(track)
            if (startUs > 0) ex.seekTo(startUs, MediaExtractor.SEEK_TO_PREVIOUS_SYNC)
            val c = MediaCodec.createDecoderByType(mime)
            codec = c
            c.configure(fmt, null, null, 0)
            c.start()
            val peaks = WavePeaks(BUCKETS, spanUs)
            var outFmt: MediaFormat = c.outputFormat
            val info = MediaCodec.BufferInfo()
            var inEos = false
            var shorts = ShortArray(0)
            var floats = FloatArray(0)
            while (true) {
                coroutineContext.ensureActive()
                if (!inEos) {
                    val ii = c.dequeueInputBuffer(DEQUEUE_US)
                    if (ii >= 0) {
                        val buf = c.getInputBuffer(ii)
                        val n = if (buf == null) -1 else ex.readSampleData(buf, 0)
                        val st = ex.sampleTime
                        if (n < 0 || (endUs > 0 && st > endUs)) {
                            c.queueInputBuffer(ii, 0, 0, 0, MediaCodec.BUFFER_FLAG_END_OF_STREAM)
                            inEos = true
                        } else {
                            c.queueInputBuffer(ii, 0, n, st, 0)
                            ex.advance()
                        }
                    }
                }
                val oi = c.dequeueOutputBuffer(info, DEQUEUE_US)
                if (oi == MediaCodec.INFO_OUTPUT_FORMAT_CHANGED) {
                    outFmt = c.outputFormat
                } else if (oi >= 0) {
                    val ob = c.getOutputBuffer(oi)
                    if (ob != null && info.size > 0 && info.presentationTimeUs >= startUs) {
                        ob.position(info.offset)
                        ob.limit(info.offset + info.size)
                        val bb = ob.slice().order(ByteOrder.nativeOrder())
                        val ch = if (outFmt.containsKey(MediaFormat.KEY_CHANNEL_COUNT)) outFmt.getInteger(MediaFormat.KEY_CHANNEL_COUNT) else DEFAULT_CHANNELS
                        val sr = if (outFmt.containsKey(MediaFormat.KEY_SAMPLE_RATE)) outFmt.getInteger(MediaFormat.KEY_SAMPLE_RATE) else DEFAULT_RATE
                        val enc = if (Build.VERSION.SDK_INT >= 24 && outFmt.containsKey(MediaFormat.KEY_PCM_ENCODING))
                            outFmt.getInteger(MediaFormat.KEY_PCM_ENCODING) else ENC_PCM_16BIT
                        val frameUs = 1_000_000.0 / sr.coerceAtLeast(1)
                        val tUs = info.presentationTimeUs - startUs
                        if (enc == ENC_PCM_FLOAT) {
                            val fb = bb.asFloatBuffer()
                            val n = fb.remaining()
                            if (floats.size < n) floats = FloatArray(n)
                            fb.get(floats, 0, n)
                            peaks.addFloat(floats, n, ch, tUs, frameUs)
                        } else if (enc == ENC_PCM_16BIT) {
                            val sb = bb.asShortBuffer()
                            val n = sb.remaining()
                            if (shorts.size < n) shorts = ShortArray(n)
                            sb.get(shorts, 0, n)
                            peaks.add16(shorts, n, ch, tUs, frameUs)
                        }
                    }
                    c.releaseOutputBuffer(oi, false)
                    if (info.flags and MediaCodec.BUFFER_FLAG_END_OF_STREAM != 0) break
                    if (endUs > 0 && info.presentationTimeUs > endUs) break
                }
            }
            return peaks.normalized()
        } finally {
            runCatching { codec?.stop() }
            runCatching { codec?.release() }
            runCatching { ex.release() }
        }
    }

    // ---------------------------------------------------------------- 형식 정보 (재생 화면 "FLAC 24bit/96kHz")
    data class FormatInfo(val mime: String, val sampleRate: Int, val channels: Int, val bits: Int) {
        fun label(name: String = ""): String = Formats.label(mime, bits, sampleRate, channels, name)
        val hiRes: Boolean get() = Formats.isHiRes(bits, sampleRate)
    }

    /** 첫 오디오 트랙 형식 (가벼움: 헤더만 읽음). 호출은 Dispatchers.IO */
    fun probe(ctx: Context, uri: String): FormatInfo? {
        val ex = MediaExtractor()
        return try {
            ex.setDataSource(ctx, Uri.parse(CueRef.mediaUri(uri)), null)
            var out: FormatInfo? = null
            for (i in 0 until ex.trackCount) {
                val f = ex.getTrackFormat(i)
                val mime = f.getString(MediaFormat.KEY_MIME) ?: continue
                if (!mime.startsWith("audio/")) continue
                fun int(k: String): Int = runCatching { if (f.containsKey(k)) f.getInteger(k) else 0 }.getOrDefault(0)
                var bits = int("bits-per-sample")
                if (bits == 0 && Build.VERSION.SDK_INT >= 24) bits = Formats.bitsOfPcmEncoding(int(MediaFormat.KEY_PCM_ENCODING))
                out = FormatInfo(mime, int(MediaFormat.KEY_SAMPLE_RATE), int(MediaFormat.KEY_CHANNEL_COUNT), bits)
                break
            }
            out
        } catch (e: Exception) {
            YLog.d("format", "형식 읽기 실패: $e")
            null
        } finally {
            runCatching { ex.release() }
        }
    }
}
