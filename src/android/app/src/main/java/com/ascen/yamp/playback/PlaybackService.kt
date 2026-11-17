package com.ascen.yamp.playback

import android.app.PendingIntent
import android.content.Intent
import androidx.annotation.OptIn
import androidx.media3.common.AudioAttributes
import androidx.media3.common.C
import androidx.media3.common.MediaItem
import androidx.media3.common.MediaMetadata
import androidx.media3.common.Player
import androidx.media3.common.util.UnstableApi
import androidx.media3.common.util.Util
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.session.CacheBitmapLoader
import androidx.media3.session.MediaSession
import androidx.media3.session.MediaSessionService
import com.ascen.yamp.MainActivity
import com.ascen.yamp.core.ConfigTxt
import com.ascen.yamp.core.YLog
import com.ascen.yamp.data.Store
import com.ascen.yamp.domain.SoundSettings
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.launch
import java.io.File

/**
 * 백그라운드 재생: ExoPlayer + MediaSession.
 * 알림/잠금화면/블루투스 버튼은 media3 가 자동 처리.
 * vr0.1.0.004: PlayerHolder(볼륨·ReplayGain·페이드·슬립 타이머) 연결, 홈 위젯 갱신
 * vr0.1.0.006: SoundEngine (10밴드 EQ · 톤 · 밸런스 · 다이내믹) 오디오 처리기 연결
 * vr0.1.0.008: 알림 앨범아트 축소 디코딩 (CoverBitmapLoader)
 * vr0.1.0.010: PlaybackTracker (재생 기록 · 오류 건너뛰기 · 위치 저장 · 플로팅/위젯 가사 줄 · 파일별 이어 듣기) 연결 — 화면 없이도 동작,
 *              무음 건너뛰기(V1) config 적용
 */
class PlaybackService : MediaSessionService() {
    private var session: MediaSession? = null
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main)

    private val widgetListener = object : Player.Listener {
        override fun onIsPlayingChanged(isPlaying: Boolean) { updateWidget() }
        override fun onMediaItemTransition(mediaItem: MediaItem?, reason: Int) { updateWidget() }
        override fun onMediaMetadataChanged(mediaMetadata: MediaMetadata) { updateWidget() }
    }

    @OptIn(UnstableApi::class)
    override fun onCreate() {
        super.onCreate()
        val attrs = AudioAttributes.Builder().setUsage(C.USAGE_MEDIA).setContentType(C.AUDIO_CONTENT_TYPE_MUSIC).build()
        // 사운드 엔진 (vr0.1.0.006): 저장된 사운드 설정 복원 → 직접 만든 오디오 처리기를 넣은 렌더러
        runCatching {
            val sp = getSharedPreferences(Store.PREFS, android.content.Context.MODE_PRIVATE)
            SoundEngine.update(SoundSettings.fromText(sp.getString(Store.KEY_SOUND, "")))
            PlayerHolder.userVolume = sp.getFloat(Store.KEY_USER_VOLUME, 1f).coerceIn(0f, 1f)
        }.onFailure { YLog.w("sound", "사운드 설정 복원 실패", it) }
        val player = ExoPlayer.Builder(this, SoundEngine.renderersFactory(this))
            .setAudioAttributes(attrs, true)          // 오디오 포커스 처리
            .setHandleAudioBecomingNoisy(true)        // 이어폰 뽑으면 일시정지
            .setWakeMode(C.WAKE_MODE_LOCAL)
            .build()
        val sid = Util.generateAudioSessionIdV21(this)
        player.audioSessionId = sid
        Fx.attach(sid)          // 스펙트럼(Visualizer) 전용 — EQ 는 SoundEngine
        // 서비스만 살아 있을 때도 config.txt 값 적용 (화면이 열리면 AppViewModel 이 다시 configure)
        val ext = getExternalFilesDir(null) ?: filesDir
        runCatching {
            val cfg = ConfigTxt(File(ext, "config.txt"))
            PlayerHolder.configure(cfg.str("replaygain"), cfg.int("preamp_db"), cfg.int("crossfade_s"), cfg.int("sleep_fade_s"))
            PlayerHolder.setSkipSilence(cfg.bool("skip_silence"))
            PlaybackTracker.historyEnabled = cfg.bool("history_enabled")
            PlaybackTracker.resumeLong = cfg.bool("resume_long")
            PlaybackTracker.configureTiers(cfg.bool("lyric_show_pron"), cfg.bool("lyric_show_trans"))
        }.onFailure { YLog.w("app", "config.txt 읽기 실패 (서비스)", it) }
        PlayerHolder.attach(this, player)
        PlaybackTracker.attach(this, player)
        player.addListener(widgetListener)
        val pi = PendingIntent.getActivity(this, 0, Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        session = MediaSession.Builder(this, player).setSessionActivity(pi)
            // vr0.1.0.008: 알림 앨범아트를 줄여서 디코딩 (기본은 원본 크기 → 곡마다 수십 MB 비트맵)
            .setBitmapLoader(CacheBitmapLoader(CoverBitmapLoader(this)))
            .build()
        scope.launch { LyricsBus.lines.collectLatest { updateWidget() } }
    }

    private fun updateWidget() {
        val p = session?.player ?: return
        val md = p.mediaMetadata
        val title = listOfNotNull(md.artist?.toString()?.takeIf { it.isNotBlank() }, md.title?.toString())
            .joinToString(" - ")
        PlayerWidget.update(this, title, p.isPlaying, LyricsBus.lines.value.first)
    }

    override fun onGetSession(controllerInfo: MediaSession.ControllerInfo): MediaSession? = session

    override fun onTaskRemoved(rootIntent: Intent?) {
        val p = session?.player
        if (p == null || !p.playWhenReady || p.mediaItemCount == 0) stopSelf()
    }

    override fun onDestroy() {
        scope.cancel()
        PlaybackTracker.detach()
        PlayerHolder.detach()
        session?.run {
            player.removeListener(widgetListener)
            player.release()
            release()
        }
        session = null
        Fx.release()
        PlayerWidget.update(this, "", false, "")
        super.onDestroy()
    }
}
