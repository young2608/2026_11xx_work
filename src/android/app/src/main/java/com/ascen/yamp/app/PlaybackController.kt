package com.ascen.yamp.app

import android.content.ComponentName
import android.os.Bundle
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.media3.common.C
import androidx.media3.common.MediaItem
import androidx.media3.common.MediaMetadata
import androidx.media3.common.PlaybackException
import androidx.media3.common.PlaybackParameters
import androidx.media3.common.Player
import androidx.media3.session.MediaController
import androidx.media3.session.SessionToken
import com.ascen.yamp.core.YLog
import com.ascen.yamp.data.Track
import com.ascen.yamp.data.fmtTime
import com.ascen.yamp.domain.PlayMath
import com.ascen.yamp.domain.TickPolicy
import com.ascen.yamp.playback.FloatingLyricsService
import com.ascen.yamp.playback.PlaybackService
import com.ascen.yamp.playback.PlaybackTracker
import com.ascen.yamp.playback.PlayerHolder
import com.ascen.yamp.playback.SleepTimer
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.guava.await
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch

/**
 * 재생 제어: MediaController 연결 · 재생 목록(tracks) 거울 · 위치 폴링 · 재생 명령 · A-B · 속도/음정 · 슬립 · 오디오 설정.
 *
 * 위치 폴링 (vr0.1.0.007): 재생 중에만, 주기는 TickPolicy — 화면을 보는 중 50ms, 백그라운드 500ms
 *   (플로팅 가사 200ms, A-B 반복 100ms). 일시정지 · 정지면 폴링 없음.
 * 재생 오류 (vr0.1.0.008): 다음 곡으로 건너뛰기는 연속 ErrorSkip.MAX_IN_ROW 번까지 (전체 반복에서 끝없는 오류 고리 방지)
 * vr0.1.0.010 (A4): 재생 기록 · 오류 건너뛰기 · 마지막 곡/위치 저장 · 플로팅/위젯 가사 줄은 재생 서비스 쪽(PlaybackTracker)으로 옮김
 *   — 여기는 화면 표시(위치 · 상태 · A-B)와 명령만. 기록은 서비스 한 곳에서만 (중복 없음)
 */
class PlaybackController(private val core: AppCore) {
    private val store get() = core.store
    var controller: MediaController? = null; private set

    /** 재생 목록 (플레이어 목록과 같은 순서) — 편집은 PlaylistController */
    val tracks = mutableStateListOf<Track>()
    /** 현재 곡 index — PlaylistController 가 지우기/이동 때 맞춤 */
    var current by mutableIntStateOf(-1); internal set
    var isPlaying by mutableStateOf(false); private set
    var positionMs by mutableLongStateOf(0L); private set
    var durationMs by mutableLongStateOf(0L); private set
    var repeatMode by mutableIntStateOf(store.repeat); private set
    var shuffle by mutableStateOf(store.shuffle); private set
    var abA by mutableLongStateOf(-1L); private set            // A-B 반복 (-1 = 없음)
    var abB by mutableLongStateOf(-1L); private set
    var speed by mutableFloatStateOf(store.speed); private set
    var pitchSt by mutableFloatStateOf(store.pitchSt); private set
    /** V1 무음 건너뛰기 (vr0.1.0.010) */
    var skipSilence by mutableStateOf(store.skipSilence); private set
    /** V2 30분 넘는 파일 이어 듣기 (vr0.1.0.010) */
    var resumeLong by mutableStateOf(store.resumeLong); private set

    val currentTrack: Track? get() = tracks.getOrNull(current)
    val abActive: Boolean get() = abA >= 0 && abB > abA

    /** 곡이 바뀜 (old → new index): AppViewModel 이 대기열 · 가사 · 커버 · 좋아요 · 기록 시작을 연결 */
    var onTrackChanged: (old: Int, new: Int) -> Unit = { _, _ -> }
    /** 위치 갱신마다 (가사 줄 계산) */
    var onPosition: (Long) -> Unit = {}

    private var tickJob: Job? = null
    private var noticeJob: Job? = null
    /** 화면(Activity)이 보이는 중 — MainActivity onStart/onStop */
    private var uiVisible = true

    // ================================================= 연결
    suspend fun connect(onConnected: () -> Unit) {
        val ctx = core.app
        val token = SessionToken(ctx, ComponentName(ctx, PlaybackService::class.java))
        val future = MediaController.Builder(ctx, token).buildAsync()
        val c = try {
            future.await()
        } catch (e: CancellationException) {
            // 연결 중에 화면이 닫힘 → 나중에 연결이 끝나도 컨트롤러가 남지 않게
            MediaController.releaseFuture(future)
            throw e
        } catch (e: Exception) {
            YLog.w("app", "MediaController 연결 오류", e)
            null
        } ?: run {
            core.toast("재생 서비스 연결 실패")
            YLog.e("app", "MediaController 연결 실패")
            return
        }
        controller = c
        c.addListener(listener)
        c.repeatMode = repeatMode
        c.shuffleModeEnabled = shuffle
        if (c.mediaItemCount != tracks.size && tracks.isNotEmpty()) {
            // 서비스가 새로 시작됨 → 저장된 목록 복원
            val i = store.lastIndex.coerceIn(0, tracks.size - 1)
            c.setMediaItems(tracks.map(::mediaItemOf), i, if (store.resume) store.lastPos else 0L)
            c.prepare()
        }
        c.playbackParameters = PlaybackParameters(speed, PlayMath.pitchFactor(pitchSt))
        applyAudioConfig()
        // 서비스 쪽 알림 (오류 건너뛰기 멈춤 · 파일별 이어 듣기) → 화면 토스트
        noticeJob?.cancel()
        noticeJob = core.scope.launch {
            var seen = PlaybackTracker.notice.value.seq
            PlaybackTracker.notice.collect { n -> if (n.seq > seen) { seen = n.seq; if (n.text.isNotEmpty()) core.toast(n.text) } }
        }
        sync()
        onConnected()
    }

    /** onCleared: 연결 해제 (위치 저장은 서비스가 — PlaybackTracker) */
    fun release() {
        tickJob?.cancel()
        tickJob = null
        noticeJob?.cancel()
        noticeJob = null
        controller?.removeListener(listener)
        controller?.release()
        controller = null
    }

    private val listener = object : Player.Listener {
        override fun onMediaItemTransition(mediaItem: MediaItem?, reason: Int) { sync() }

        override fun onIsPlayingChanged(playing: Boolean) {
            isPlaying = playing
            if (playing) startTick() else { stopTick(); updatePos() }
        }

        override fun onPlaybackStateChanged(state: Int) {
            controller?.let { durationMs = it.duration.coerceAtLeast(0) }
        }

        // 다음 곡 건너뛰기(ErrorSkip)는 서비스(PlaybackTracker)가 — 화면은 알림만
        override fun onPlayerError(error: PlaybackException) {
            core.toast("재생 오류: ${error.message ?: error.errorCode}")
            YLog.w("player", "error ${error.errorCode} item=${controller?.currentMediaItem?.mediaId}", error)
        }
    }

    /** 플레이어 상태 → 화면 상태 (곡이 바뀌었으면 onTrackChanged) */
    fun sync() {
        val c = controller ?: return
        val idx = c.currentMediaItemIndex
        isPlaying = c.isPlaying
        durationMs = c.duration.coerceAtLeast(0)
        if (idx != current) {
            val old = current
            current = idx
            tracks.getOrNull(idx)?.let { YLog.i("player", "track $idx ${it.display}") }
            clearAB()
            onTrackChanged(old, idx)
        }
        updatePos()
        if (isPlaying) startTick()
    }

    // ================================================= 위치 폴링
    fun setUiVisible(visible: Boolean) {
        if (uiVisible == visible) return
        uiVisible = visible
        // 화면으로 돌아오면 바로 빠른 주기로 (백그라운드 주기 대기 없이)
        if (visible && isPlaying) { stopTick(); startTick() }
    }

    private fun startTick() {
        if (tickJob?.isActive == true) return
        tickJob = core.scope.launch {
            while (isActive) {
                updatePos()
                delay(TickPolicy.intervalMs(uiVisible, FloatingLyricsService.running, abActive))
            }
        }
    }

    private fun stopTick() { tickJob?.cancel(); tickJob = null }

    fun updatePos() {
        val c = controller ?: return
        positionMs = c.currentPosition.coerceAtLeast(0)
        if (durationMs <= 0) durationMs = c.duration.coerceAtLeast(0)
        // A-B 구간 반복 (되감기는 서비스 기록에서 탐색으로 보고 들은 시간에서 뺌 — PlayRecorder)
        PlayMath.abSeek(positionMs, abA, abB)?.let { a ->
            c.seekTo(a)
            positionMs = a
        }
        onPosition(positionMs)
    }

    // ================================================= 재생 명령
    fun playIndex(i: Int) {
        val c = controller ?: return
        if (i !in tracks.indices) return
        c.seekTo(i, 0)
        c.play()
    }

    fun toggle() {
        val c = controller ?: return
        if (c.mediaItemCount == 0) return
        if (c.isPlaying) c.pause() else {
            // 목록 끝 → 처음 곡 (셔플이면 셔플 순서의 첫 곡, A15). 새 기록은 서비스가 재생 시작 때
            if (c.playbackState == Player.STATE_ENDED) c.seekTo(firstIndex(c), 0)
            c.play()
        }
    }

    fun stop() {
        updatePos()
        controller?.run { pause(); seekTo(0) }
        PlaybackTracker.restartRecord()     // 지금 기록을 끝내고 새 기록 (서비스 쪽)
        updatePos()
    }

    fun next() {
        val c = controller ?: return
        if (c.hasNextMediaItem()) c.seekToNextMediaItem() else if (c.mediaItemCount > 0) c.seekTo(firstIndex(c), 0)
    }

    /** 재생 순서의 첫 곡 (셔플이면 셔플 순서, A15) */
    private fun firstIndex(c: Player): Int = c.currentTimeline.getFirstWindowIndex(c.shuffleModeEnabled).takeIf { it >= 0 } ?: 0

    fun prev() {
        val c = controller ?: return
        if (c.currentPosition > PREV_RESTART_MS || !c.hasPreviousMediaItem()) c.seekTo(0) else c.seekToPreviousMediaItem()
    }

    /** 음수 위치(가사 줄 누르기 + 싱크 보정)는 0 으로 (A10) */
    fun seek(ms: Long) {
        val m = ms.coerceAtLeast(0)
        controller?.seekTo(m); positionMs = m; updatePos()
    }

    fun cycleRepeat() {
        repeatMode = when (repeatMode) {
            Player.REPEAT_MODE_OFF -> Player.REPEAT_MODE_ALL
            Player.REPEAT_MODE_ALL -> Player.REPEAT_MODE_ONE
            else -> Player.REPEAT_MODE_OFF
        }
        store.repeat = repeatMode
        controller?.repeatMode = repeatMode
    }

    fun toggleShuffle() {
        shuffle = !shuffle
        store.shuffle = shuffle
        controller?.shuffleModeEnabled = shuffle
    }

    // ---- A-B 반복 (A5)
    fun cycleAB() {
        when {
            abA < 0 -> { abA = positionMs; core.toast("A 지점 %s".format(fmtTime(abA))) }
            abB < 0 -> {
                if (positionMs > abA + AB_MIN_MS) {
                    abB = positionMs
                    core.toast("구간 반복 %s ~ %s".format(fmtTime(abA), fmtTime(abB)))
                } else core.toast("B 지점은 A 보다 뒤여야 합니다")
            }
            else -> { clearAB(); core.toast("구간 반복 해제") }
        }
    }

    /** 구간 지정 (가사 줄 반복) */
    fun setAB(a: Long, b: Long) { abA = a; abB = b }

    fun clearAB() { abA = -1; abB = -1 }

    // ---- 속도 · 음정 (A6)
    fun setSpeedPitch(sp: Float, st: Float) {
        speed = (Math.round(sp * SPEED_STEPS) / SPEED_STEPS).coerceIn(SPEED_MIN, SPEED_MAX)
        pitchSt = st.coerceIn(-PITCH_MAX_ST, PITCH_MAX_ST)
        store.speed = speed
        store.pitchSt = pitchSt
        controller?.playbackParameters = PlaybackParameters(speed, PlayMath.pitchFactor(pitchSt))
    }

    // ---- 슬립 타이머 (A7) — 서비스 프로세스(같은 프로세스) 의 SleepTimer 사용
    fun startSleep(minutes: Int) {
        if (PlayerHolder.player == null) { core.toast("재생 서비스가 아직 준비되지 않았습니다"); return }
        if (minutes <= 0) SleepTimer.startEndOfTrack() else SleepTimer.start(minutes)
        core.toast(if (minutes <= 0) "곡이 끝나면 멈춥니다" else "${minutes}분 뒤 멈춥니다")
    }

    fun cancelSleep() { SleepTimer.cancel(); core.toast("슬립 타이머 해제") }

    // ---- 오디오 설정 (ReplayGain · 곡 전환 페이드 · 슬립 페이드)
    fun applyAudioConfig() {
        PlayerHolder.configure(store.replayGain, store.preampDb, store.crossfadeS, store.sleepFadeS)
    }

    fun setReplayGain(mode: String) { store.replayGain = mode; applyAudioConfig() }
    fun setPreamp(db: Int) { store.preampDb = db; applyAudioConfig() }
    fun setCrossfade(s: Int) { store.crossfadeS = s; applyAudioConfig() }
    fun setSleepFade(s: Int) { store.sleepFadeS = s; applyAudioConfig() }

    // ---- 음성 파일 (vr0.1.0.010): V1 무음 건너뛰기 · V2 파일별 이어 듣기 — 서비스 쪽 플레이어 · 기록에 바로
    fun changeSkipSilence(on: Boolean) {
        skipSilence = on
        store.skipSilence = on
        PlayerHolder.setSkipSilence(on)
        core.toast(if (on) "무음 건너뛰기 켬" else "무음 건너뛰기 끔")
    }

    fun changeResumeLong(on: Boolean) {
        resumeLong = on
        store.resumeLong = on
        PlaybackTracker.resumeLong = on
        if (!on) PlaybackTracker.clearResumeBook()
    }

    companion object {
        /** 이전 버튼: 이만큼 지났으면 곡 처음으로 (아니면 이전 곡) */
        const val PREV_RESTART_MS = 3000L
        /** A-B: B 는 A 보다 이만큼 뒤 */
        const val AB_MIN_MS = 300L
        const val SPEED_MIN = 0.5f
        const val SPEED_MAX = 2.0f
        /** 속도 0.05 단위 */
        const val SPEED_STEPS = 20f
        const val PITCH_MAX_ST = 6f
    }
}

/**
 * CUE 트랙: 실제 파일(mediaUri) + 구간(ClippingConfiguration). mediaId = 곡 uri (CUE 표시 포함, 목록에서 유일)
 * vr0.1.0.010: extras — 경로(서비스 쪽 .lrc 찾기, A4) · CUE ReplayGain(A12)
 */
fun mediaItemOf(t: Track): MediaItem {
    val extras = Bundle().apply {
        if (t.path.isNotEmpty()) putString(PlayerHolder.EXTRA_PATH, t.path)
        if (t.rg.isNotEmpty()) putString(PlayerHolder.EXTRA_RG, t.rg)
    }
    val b = MediaItem.Builder()
        .setUri(t.mediaUri).setMediaId(t.uri)
        .setMediaMetadata(MediaMetadata.Builder().setTitle(t.title).setArtist(t.artist).setAlbumTitle(t.album).setExtras(extras).build())
    t.clip?.let { c ->
        b.setClippingConfiguration(MediaItem.ClippingConfiguration.Builder()
            .setStartPositionMs(c.startMs.coerceAtLeast(0))      // v013: CUE 값이 이상해도 예외 없이
            .setEndPositionMs(if (c.endMs > c.startMs.coerceAtLeast(0)) c.endMs else C.TIME_END_OF_SOURCE)
            .build())
    }
    return b.build()
}
