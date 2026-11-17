package com.ascen.yamp.playback

import android.content.Context
import android.net.Uri
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import androidx.annotation.OptIn
import androidx.media3.common.MediaItem
import androidx.media3.common.Player
import androidx.media3.common.util.UnstableApi
import androidx.media3.exoplayer.ExoPlayer
import com.ascen.yamp.core.ReplayGainTags
import com.ascen.yamp.core.RgTags
import com.ascen.yamp.core.YLog
import com.ascen.yamp.data.CueRef
import com.ascen.yamp.data.CueRg
import com.ascen.yamp.domain.LruMap
import com.ascen.yamp.domain.PlayMath
import com.ascen.yamp.domain.PollPolicy
import com.ascen.yamp.domain.Recommend
import java.util.concurrent.Executors

/**
 * 서비스 쪽 ExoPlayer 참조 + 볼륨 제어 (같은 프로세스 싱글턴). PlaybackService 가 attach / detach.
 *
 * 볼륨 = ReplayGain 배율 × 곡 전환 페이드 × 슬립 타이머 페이드 × 앱 볼륨 노브  →  applyVolume() 한 곳에서만 설정
 *   ExoPlayer volume 은 0.0 ~ 1.0 → ReplayGain 이 소리를 키우는 경우(배율 > 1)는 1.0 으로 잘림 (줄이는 보정만 적용)
 *
 * 곡 전환 페이드(crossfade_s): 플레이어 1개로 곡 시작 N초 페이드 인 + 끝 N초 페이드 아웃.
 *   두 곡이 겹쳐 재생되는 진짜 크로스페이드가 아님 (플레이어 2개 교대 방식은 D 단계).
 *   재생 중 위치를 확인 (메인 Looper Handler) — vr0.1.0.007: 페이드 구간 안 100ms, 밖은 최대 500ms (PollPolicy)
 * vr0.1.0.010:
 *   A12 CUE 트랙 = CUE 의 REM REPLAYGAIN 값 (MediaItem extras "yamp_rg") 우선, 없는 칸은 파일 태그.
 *       파일 태그는 실제 파일(mediaUri)마다 캐시 (같은 앨범 파일의 CUE 트랙을 넘길 때 다시 읽지 않음)
 *   V1 무음 건너뛰기 (ExoPlayer.setSkipSilenceEnabled — 서비스 쪽 플레이어에 직접)
 */
@OptIn(UnstableApi::class)
object PlayerHolder {
    @Volatile var player: ExoPlayer? = null; private set
    private var appCtx: Context? = null
    private val handler = Handler(Looper.getMainLooper())
    private val io = Executors.newSingleThreadExecutor { r -> Thread(r, "yamp-rg").apply { isDaemon = true } }

    // ---- 설정 (서비스 시작 시 Store, 설정 화면에서 바꾸면 AppViewModel 이 configure)
    var rgMode = "track"; private set
    var preampDb = 0; private set
    var fadeS = 0; private set
    var sleepFadeS = 30; private set

    /** 앱 볼륨 노브 (vr0.1.0.006, 0..1) — 기기 볼륨과 별개로 곱함 */
    @Volatile var userVolume = 1f

    private var rgTags: RgTags? = null
    private var rgUri: String? = null
    /** 파일 태그 캐시: 실제 파일 uri → 태그 (없음 = 빈 RgTags) */
    private val fileRg = LruMap<String, RgTags>(RG_CACHE_MAX)

    /** V1 무음 건너뛰기 (config skip_silence) */
    @Volatile var skipSilence = false; private set
    private var fade = 1f
    internal var sleepVol = 1f
    /** 곡 전환 번호 — RG 읽기 스레드가 이미 지난 곡이면 파일을 열지 않게 (vr0.1.0.008) */
    @Volatile private var seq = 0

    private val listener = object : Player.Listener {
        override fun onMediaItemTransition(mediaItem: MediaItem?, reason: Int) {
            fade = if (fadeS > 0) 0f else 1f
            loadRg(mediaItem)
            applyVolume()
            schedule()
        }

        override fun onIsPlayingChanged(isPlaying: Boolean) { schedule() }

        override fun onPositionDiscontinuity(oldPosition: Player.PositionInfo, newPosition: Player.PositionInfo, reason: Int) {
            schedule()      // 탐색 → 페이드 구간에 들어갔을 수 있음
        }

        override fun onPlayWhenReadyChanged(playWhenReady: Boolean, reason: Int) {
            if (reason == Player.PLAY_WHEN_READY_CHANGE_REASON_END_OF_MEDIA_ITEM) SleepTimer.onEndOfItemPause()
        }
    }

    fun attach(ctx: Context, p: ExoPlayer) {
        appCtx = ctx.applicationContext
        player = p
        p.addListener(listener)
        runCatching { p.skipSilenceEnabled = skipSilence }
        loadRg(p.currentMediaItem)
    }

    /** V1 무음 건너뛰기 켜기/끄기 (서비스 시작 때 config, 화면에서 바꾸면 바로) */
    fun setSkipSilence(on: Boolean) {
        skipSilence = on
        player?.let { p -> runCatching { p.skipSilenceEnabled = on }.onFailure { YLog.w("player", "무음 건너뛰기 설정 실패", it) } }
    }

    fun detach() {
        handler.removeCallbacks(poll)
        SleepTimer.cancel()
        player?.removeListener(listener)
        player = null
        appCtx = null
    }

    fun configure(mode: String, preamp: Int, fadeSec: Int, sleepFadeSec: Int) {
        rgMode = mode
        preampDb = preamp
        fadeS = fadeSec.coerceIn(0, MAX_FADE_S)
        sleepFadeS = sleepFadeSec.coerceIn(0, MAX_SLEEP_FADE_S)
        if (fadeS == 0) fade = 1f
        applyVolume()
        schedule()
    }

    // ---------------------------------------------------------- 볼륨
    private fun rgFactor(): Double {
        val t = rgTags ?: return 1.0
        val (g, pk) = t.pick(rgMode)
        return Recommend.gainFactor(g, pk, preampDb.toDouble())
    }

    fun applyVolume() {
        val p = player ?: return
        // ExoPlayer 최대 1.0 — 증폭(배율 > 1)은 잘림
        p.volume = (PlayMath.combineVolume(rgFactor(), fade, sleepVol) * userVolume.coerceIn(0f, 1f)).coerceIn(0f, 1f)
    }

    private fun loadRg(item: MediaItem?) {
        val uri = item?.mediaId?.takeIf { it.isNotEmpty() } ?: item?.localConfiguration?.uri?.toString()
        if (uri == null) { seq++; rgTags = null; rgUri = null; return }
        if (uri == rgUri) return
        val my = ++seq
        rgUri = uri
        // CUE 트랙의 REM REPLAYGAIN (Track.rg → MediaItem extras)
        val cue = item?.mediaMetadata?.extras?.getString(EXTRA_RG)?.takeIf { it.isNotBlank() }?.let { rg ->
            val (tg, tp, ag, ap) = CueRg.parts(rg)
            ReplayGainTags.fromStrings(tg, tp, ag, ap)
        }
        val media = CueRef.mediaUri(uri)
        val cached = fileRg[media]
        if (cached != null || (cue != null && !cue.isEmpty && cue.trackGain != null && cue.albumGain != null)) {
            // 파일을 다시 읽을 필요 없음
            rgTags = ReplayGainTags.merge(cue, cached)
            applyVolume()
            return
        }
        rgTags = cue
        val ctx = appCtx ?: return
        io.execute {
            // 곡을 빨리 넘기면 읽기 요청이 줄을 섬 → 이미 다른 곡이면 건너뜀 (파일 열기 · 태그 파싱 생략)
            if (my != seq) return@execute
            val tags = runCatching {
                ctx.contentResolver.openInputStream(Uri.parse(media))?.use { ReplayGainTags.read(it) }
            }.onFailure { YLog.d("rg", "태그 읽기 실패 $uri: $it") }.getOrNull()
            fileRg[media] = tags ?: RgTags()
            handler.post {
                if (my != seq) return@post
                val t = ReplayGainTags.merge(cue, tags)
                rgTags = t
                if (t != null && !t.isEmpty) YLog.d("rg", "track=${t.trackGain} album=${t.albumGain}${if (cue != null) " (CUE)" else ""} → x%.3f".format(rgFactor()))
                applyVolume()
            }
        }
    }

    // ---------------------------------------------------------- 폴링 (페이드 · 슬립 타이머) — 필요할 때만
    private val poll = object : Runnable {
        override fun run() {
            step()
            val d = nextPollMs()
            if (d > 0) handler.postDelayed(this, d)
        }
    }

    /** 다음 확인까지 (ms), -1 = 필요 없음 (재생 안 함 + 슬립 타이머 꺼짐) */
    private fun nextPollMs(): Long {
        val p = player ?: return -1
        var d = -1L
        if (p.isPlaying && fadeS > 0) d = PollPolicy.fadeDelayMs(p.currentPosition, p.duration, fadeS * 1000L)
        if (SleepTimer.active) {
            val s = SleepTimer.pollDelayMs(p)
            if (s > 0) d = if (d < 0) s else minOf(d, s)
        }
        return d
    }

    fun schedule() {
        handler.removeCallbacks(poll)
        handler.post(poll)
    }

    private const val MAX_FADE_S = 12
    /** 파일별 ReplayGain 태그 캐시 크기 */
    private const val RG_CACHE_MAX = 64
    /** MediaItem.mediaMetadata.extras 키 (app/PlaybackController.mediaItemOf 가 넣음) */
    const val EXTRA_PATH = "yamp_path"
    const val EXTRA_RG = "yamp_rg"
    private const val MAX_SLEEP_FADE_S = 120

    private fun step() {
        val p = player ?: return
        fade = if (fadeS > 0) PlayMath.transitionFade(p.currentPosition, p.duration, fadeS * 1000L) else 1f
        SleepTimer.step(p)
        applyVolume()
    }
}

/**
 * 슬립 타이머 (A7): 서비스 프로세스의 메인 Handler 에서 동작 → 화면(Activity)을 닫아도 계속.
 *   N분 후 / 곡 끝날 때. 마지막 sleep_fade_s 초 동안 볼륨을 서서히 줄인 뒤 일시정지, 볼륨 복원.
 */
@OptIn(UnstableApi::class)
object SleepTimer {
    private var endAt = 0L            // SystemClock.elapsedRealtime 기준, 0 = 꺼짐
    var endOfTrack = false; private set
    val active: Boolean get() = endAt > 0 || endOfTrack

    fun start(minutes: Int) {
        cancel()
        if (PlayerHolder.player == null) { YLog.w("sleep", "플레이어 없음 — 타이머 시작 안 함"); return }
        endAt = SystemClock.elapsedRealtime() + minutes * 60_000L
        YLog.i("sleep", "슬립 타이머 ${minutes}분")
        PlayerHolder.schedule()
    }

    fun startEndOfTrack() {
        cancel()
        val p = PlayerHolder.player ?: return
        endOfTrack = true
        p.setPauseAtEndOfMediaItems(true)
        YLog.i("sleep", "슬립 타이머: 곡 끝날 때")
        PlayerHolder.schedule()
    }

    fun cancel() {
        val was = active
        endAt = 0
        if (endOfTrack) PlayerHolder.player?.setPauseAtEndOfMediaItems(false)
        endOfTrack = false
        PlayerHolder.sleepVol = 1f
        PlayerHolder.applyVolume()
        if (was) YLog.i("sleep", "슬립 타이머 해제")
    }

    /** 남은 ms (-1 = 꺼짐) */
    fun remainingMs(): Long {
        if (endAt > 0) return maxOf(0L, endAt - SystemClock.elapsedRealtime())
        if (endOfTrack) {
            val p = PlayerHolder.player ?: return 0
            val d = p.duration
            return if (d > 0) maxOf(0L, d - p.currentPosition) else 0
        }
        return -1
    }

    internal fun step(p: ExoPlayer) {
        if (!active) { PlayerHolder.sleepVol = 1f; return }
        val fadeMs = PlayerHolder.sleepFadeS * 1000L
        if (endAt > 0) {
            val r = endAt - SystemClock.elapsedRealtime()
            if (r <= 0) {
                p.pause()
                YLog.i("sleep", "슬립 타이머 종료 → 일시정지")
                cancel()
                return
            }
            PlayerHolder.sleepVol = PlayMath.sleepFade(r, fadeMs)
        } else {
            val d = p.duration
            PlayerHolder.sleepVol = if (d > 0) PlayMath.sleepFade(d - p.currentPosition, fadeMs) else 1f
        }
    }

    /** PlayerHolder 폴링 간격: N분 뒤 = 시계 기준, 곡 끝날 때 = 재생 위치 기준 (일시정지 중이면 -1 = 다시 재생할 때까지 쉼) */
    internal fun pollDelayMs(p: ExoPlayer): Long {
        val fadeMs = PlayerHolder.sleepFadeS * 1000L
        if (endAt > 0) return PollPolicy.sleepDelayMs(endAt - SystemClock.elapsedRealtime(), fadeMs)
        if (!p.isPlaying) return -1
        val d = p.duration
        return if (d > 0) PollPolicy.trackEndDelayMs(d - p.currentPosition, fadeMs) else PollPolicy.SLOW_MS
    }

    /** pauseAtEndOfMediaItems 로 곡 끝에서 멈춤 */
    internal fun onEndOfItemPause() {
        if (!endOfTrack) return
        YLog.i("sleep", "곡 끝 → 일시정지")
        cancel()
    }
}
