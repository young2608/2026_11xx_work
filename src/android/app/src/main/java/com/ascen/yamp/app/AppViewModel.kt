package com.ascen.yamp.app

import android.app.Application
import android.net.Uri
import android.os.SystemClock
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.ascen.yamp.BuildConfig
import com.ascen.yamp.core.YLog
import com.ascen.yamp.data.Track
import com.ascen.yamp.domain.MaintPolicy
import com.ascen.yamp.domain.SoundSettings
import com.ascen.yamp.lyrics.LyricsRepo
import com.ascen.yamp.playback.LyricsBus
import com.ascen.yamp.playback.PlaybackTracker
import kotlinx.coroutines.launch

/**
 * 화면(UI) 용 얇은 창구 (vr0.1.0.007 모듈화): 상태 · 명령은 기능별 컨트롤러가 갖고, 여기서는 연결과 전달만.
 *
 *   AppCore              공용 (Store · LibraryDb · LyricsRepo · 알림 메시지)
 *   PlaybackController   연결 · 재생 명령 · 위치 폴링 · A-B · 속도/음정 · 슬립 · 오디오 설정
 *   PlaylistController   목록 편집 · 대기열 · 믹스 · 목록 교체
 *   (재생 기록 · 오류 건너뛰기 · 위치 저장 · 플로팅/위젯 가사 줄 = 재생 서비스 쪽 playback/PlaybackTracker, vr0.1.0.010)
 *   LibraryController    라이브러리 · 좋아요/별점 · 음악 스캔 · 파일 추가
 *   HomeController       추천 홈 · 라디오 · 기록 지우기
 *   FolderController     폴더 재생
 *   LyricsController     가사
 *   MediaInfoController  앨범아트 · 형식 · 파형
 *   SoundController      사운드 엔진 · 프리셋 · 앱 볼륨
 *   SettingsController   테마 · 글자 크기 · 스펙트럼
 *   TickerController     상단 바 업비트 시세 · KST 시계 (vr0.1.0.012, 화면이 보일 때만)
 */
class AppViewModel(app: Application) : AndroidViewModel(app) {
    // vr0.1.0.013: 기능 하나의 코루틴 오류가 앱 전체를 종료시키지 않게 (로그 남기고 계속) — viewModelScope 는 SupervisorJob
    private val core = AppCore(app, kotlinx.coroutines.CoroutineScope(viewModelScope.coroutineContext +
        kotlinx.coroutines.CoroutineExceptionHandler { _, e -> YLog.e("app", "작업 오류: ${com.ascen.yamp.core.CrashReport.summary(e)}", e) }))
    private val playback = PlaybackController(core)
    private val playlist = PlaylistController(core, playback)
    private val lib = LibraryController(core, playback, playlist)
    private val home = HomeController(core, playback, playlist, lib)
    private val folders = FolderController(core, playlist)
    private val lyricsCtl = LyricsController(core, playback)
    private val media = MediaInfoController(core, playback)
    private val soundCtl = SoundController(core)
    private val settings = SettingsController(core)
    private val ticker = TickerController(core)

    val store get() = core.store

    // ================================================= 화면 수명 (MainActivity onStart / onStop)
    /** 화면이 보이는지: 위치 폴링 주기 · 스펙트럼 on/off */
    fun setUiVisible(visible: Boolean) {
        playback.setUiVisible(visible)
        settings.setUiVisible(visible)
        ticker.setUiVisible(visible)
        if (!visible) YLog.flush()
    }

    // ================================================= 재생
    val tracks get() = playback.tracks
    val current get() = playback.current
    val currentTrack: Track? get() = playback.currentTrack
    val isPlaying get() = playback.isPlaying
    val positionMs get() = playback.positionMs
    val durationMs get() = playback.durationMs
    val repeatMode get() = playback.repeatMode
    val shuffle get() = playback.shuffle
    val abA get() = playback.abA
    val abB get() = playback.abB
    val abActive: Boolean get() = playback.abActive
    val speed get() = playback.speed
    val pitchSt get() = playback.pitchSt

    fun playIndex(i: Int) = playback.playIndex(i)
    fun toggle() = playback.toggle()
    fun stop() = playback.stop()
    fun next() = playback.next()
    fun prev() = playback.prev()
    fun seek(ms: Long) = playback.seek(ms)
    fun cycleRepeat() = playback.cycleRepeat()
    fun toggleShuffle() = playback.toggleShuffle()
    fun cycleAB() = playback.cycleAB()
    fun clearAB() = playback.clearAB()
    fun setSpeedPitch(sp: Float, st: Float) = playback.setSpeedPitch(sp, st)
    fun startSleep(minutes: Int) = playback.startSleep(minutes)
    fun cancelSleep() = playback.cancelSleep()
    fun applyAudioConfig() = playback.applyAudioConfig()
    fun setReplayGain(mode: String) = playback.setReplayGain(mode)
    fun setPreamp(db: Int) = playback.setPreamp(db)
    fun setCrossfade(s: Int) = playback.setCrossfade(s)
    fun setSleepFade(s: Int) = playback.setSleepFade(s)
    val skipSilence get() = playback.skipSilence
    val resumeLong get() = playback.resumeLong
    fun setSkipSilence(on: Boolean) = playback.changeSkipSilence(on)
    fun setResumeLong(on: Boolean) = playback.changeResumeLong(on)

    // ================================================= 목록 · 대기열
    val queued get() = playlist.queued
    fun addTracks(list: List<Track>) = playlist.addTracks(list)
    fun remove(i: Int) = playlist.remove(i)
    fun move(i: Int, j: Int) = playlist.move(i, j)
    fun clear() = playlist.clear()
    fun playNext(t: Track) = playlist.playNext(t)
    fun enqueue(t: Track) = playlist.enqueue(t)
    fun clearQueue() = playlist.clearQueue()
    fun playMix(list: List<Track>, label: String, startNow: Boolean = true) = playlist.playMix(list, label, startNow)
    fun replacePlaylist(list: List<Track>, label: String, startIndex: Int = 0) = playlist.replacePlaylist(list, label, startIndex)

    // ================================================= 라이브러리 · 좋아요 · 스캔
    val library get() = lib.library
    val historyCount get() = lib.historyCount
    val scanning get() = lib.scanning
    val liked get() = lib.liked
    val rating get() = lib.rating
    fun keyOf(t: Track): String = core.keyOf(t)
    fun trackOfKey(k: String): Track? = lib.trackOfKey(k)
    fun isLiked(t: Track): Boolean = lib.isLiked(t)
    fun ratingOf(t: Track): Int = lib.ratingOf(t)
    fun toggleLike(t: Track? = currentTrack) = lib.toggleLike(t)
    fun setTrackRating(t: Track, r: Int) = lib.setRating(t, r)
    fun refreshLibrary() = lib.refresh()
    fun refreshHistoryCount() = lib.refreshHistoryCount()
    fun scanAll() = lib.scanAll()
    fun addUris(uris: List<Uri>) = lib.addUris(uris)
    fun setHistoryEnabled(on: Boolean) {
        core.store.historyEnabled = on
        PlaybackTracker.historyEnabled = on
    }

    // ================================================= 추천 · 라디오
    val homeCards get() = home.homeCards
    val homeLoading get() = home.homeLoading
    fun refreshHome(force: Boolean = false) = home.refreshHome(force)
    fun playMixKeys(keys: List<String>, label: String) = home.playMixKeys(keys, label)
    fun radio(seed: Track) = home.radio(seed)
    fun clearHistory() = home.clearHistory()

    // ================================================= 폴더
    val folderTracks get() = folders.folderTracks
    val folderRoot get() = folders.folderRoot
    val folderLoading get() = folders.folderLoading
    val folderOpenRequest get() = folders.openRequest
    fun consumeFolderOpen() = folders.consumeOpen()
    val safTrees get() = folders.safTrees
    val pinnedFolders get() = folders.pinnedFolders
    fun refreshFolders(withMediaStore: Boolean) = folders.refreshFolders(withMediaStore)
    fun addSafTree(uri: Uri) = folders.addSafTree(uri)
    fun removeSafTree(key: String) = folders.removeSafTree(key)
    fun togglePin(path: String) = folders.togglePin(path)
    fun rememberFolder(path: String) = folders.rememberFolder(path)
    fun sortFolderTracks(list: List<Track>, sort: String): List<Track> = folders.sort(list, sort)
    fun playFolder(path: String, includeSub: Boolean, shuffleList: Boolean, sort: String, startUri: String? = null) =
        folders.playFolder(path, includeSub, shuffleList, sort, startUri)

    // ================================================= 가사
    val lyrics get() = lyricsCtl.lyrics
    val lyricsStatus get() = lyricsCtl.lyricsStatus
    val lyricIndex get() = lyricsCtl.lyricIndex
    val offsetMs get() = lyricsCtl.offsetMs
    val showPron get() = lyricsCtl.showPron
    val showTrans get() = lyricsCtl.showTrans
    val candidates get() = lyricsCtl.candidates
    val candSearching get() = lyricsCtl.candSearching
    /** A1: 다시 찾기로 새 가사를 찾았는데 지금 가사가 직접 편집한 것 → 바꿀지 물어봄 (null = 묻지 않음) */
    val pendingReplace get() = lyricsCtl.pendingReplace
    fun researchLyrics() = lyricsCtl.research()
    fun confirmReplaceLyrics(replace: Boolean) = lyricsCtl.confirmReplace(replace)
    fun adjustOffset(delta: Long?) = lyricsCtl.adjustOffset(delta)
    fun setTiers(pron: Boolean, trans: Boolean) = lyricsCtl.setTiers(pron, trans)
    fun repeatLine(blockIndex: Int) = lyricsCtl.repeatLine(blockIndex)
    fun saveUserLyrics(lrc: String) = lyricsCtl.saveUserLyrics(lrc)
    fun searchCandidates(title: String, artist: String) = lyricsCtl.searchCandidates(title, artist)
    fun chooseCandidate(c: LyricsRepo.Candidate) = lyricsCtl.chooseCandidate(c)
    /** vr0.1.0.011 (f18): L7 상태 사유 · 붙여넣기 · L8 가사 진단 */
    val lyricsState get() = lyricsCtl.state
    fun pasteLyrics(text: String?) = lyricsCtl.pasteLyrics(text)
    val lyricsDiagText get() = lyricsCtl.diagText
    val lyricsDiagRunning get() = lyricsCtl.diagRunning
    val lyricsDiagFile get() = lyricsCtl.diagFile
    fun runLyricsDiag() = lyricsCtl.runDiag()
    fun closeLyricsDiag() = lyricsCtl.closeDiag()

    // ================================================= 앨범아트 · 형식 · 파형
    val cover get() = media.cover
    val formatLabel get() = media.formatLabel
    val formatHiRes get() = media.formatHiRes
    val wave get() = media.wave
    fun setWaveformEnabled(on: Boolean) = media.setWaveformEnabled(on)

    // ================================================= 사운드 · 앱 볼륨
    val sound: SoundSettings get() = soundCtl.sound
    val userPresets get() = soundCtl.userPresets
    val userVolume: Float get() = soundCtl.userVolume
    fun updateSound(s: SoundSettings) = soundCtl.updateSound(s)
    fun setBand(i: Int, db: Double) = soundCtl.setBand(i, db)
    fun applyPreset(name: String) = soundCtl.applyPreset(name)
    fun presetNameOf(s: SoundSettings): String = soundCtl.presetNameOf(s)
    fun saveUserPreset(name: String) = soundCtl.saveUserPreset(name)
    fun deleteUserPreset(name: String) = soundCtl.deleteUserPreset(name)
    fun resetSound() = soundCtl.resetSound()
    fun setUserVolume(v: Float) = soundCtl.changeVolume(v)

    // ================================================= 화면 설정 · 알림
    val theme get() = settings.theme
    val followSystemDark get() = settings.followSystemDark
    val fontSp get() = settings.fontSp
    val levels get() = settings.levels
    val spectrumOn get() = settings.spectrumOn
    val visMode get() = settings.visMode
    val visBarStyle get() = settings.visBarStyle
    fun setVisMode(m: String) = settings.changeVisMode(m)
    val message get() = core.message
    fun setThemeName(n: String) = settings.setThemeName(n)
    fun setFollowSystemDark(on: Boolean) = settings.changeFollowSystemDark(on)
    fun setFont(sp: Int) = settings.setFont(sp)
    fun setSpectrum(on: Boolean) = settings.setSpectrum(on)
    fun toast(m: String) = core.toast(m)
    fun consumeMessage() = core.consumeMessage()

    // ================================================= 상단 바 시세 · KST 시계 (vr0.1.0.012, f23)
    val tickerOn get() = ticker.tickerOn
    val clockOn get() = ticker.clockOn
    val clockSeconds get() = ticker.clockSeconds
    val tickerMarkets get() = ticker.markets
    val tickerQuotes get() = ticker.quotes
    val tickerStale: Boolean get() = ticker.stale
    val tickerError get() = ticker.error
    val tickerFlashSeq get() = ticker.flashSeq
    val tickerFlashMarket get() = ticker.flashMarket
    val tickerFlashUp get() = ticker.flashUp
    /** 화면이 보이는 중 (시계 1초 갱신 · 마켓 번갈아 표시는 이때만) */
    val uiVisible get() = ticker.visible
    fun tickerDetail(market: String): String = ticker.detail(market)
    fun setTickerOn(on: Boolean) = ticker.changeTicker(on)
    fun setClockOn(on: Boolean) = ticker.changeClock(on)
    fun setClockSeconds(on: Boolean) = ticker.changeClockSeconds(on)
    fun setTickerMarket(text: String) = ticker.changeMarket(text)

    // ================================================= 연결 (곡 변경 → 기능 모듈)
    private fun onTrackChanged(old: Int, new: Int) {
        playlist.onTrackMoved(old, new)
        val t = playback.currentTrack
        media.load(t)
        lyricsCtl.load(t)
        lib.refreshLike()
        maintainIfDue()
    }

    /** 마지막 정리 시각 (elapsedRealtime, 0 = 아직) */
    private var lastMaintMs = 0L
    private var maintRunning = false

    /**
     * 장시간 운용 정리 (vr0.1.0.008): 시작 때 + 앱을 며칠 켜 둘 때 하루 한 번 (곡이 바뀔 때 확인)
     *   — 계속 재생하면 가사 · 파형 캐시와 재생 기록이 다음 시작 때까지 무한히 늘던 것 방지
     */
    private fun maintainIfDue() {
        val now = SystemClock.elapsedRealtime()
        if (maintRunning || !MaintPolicy.due(now, lastMaintMs)) return
        maintRunning = true
        lastMaintMs = now
        core.scope.launch {
            try { core.io("maint", "정리 실패", Unit) { Maintenance.run(core.app, core.db) } } finally { maintRunning = false }
        }
    }

    init {
        val st = core.store
        YLog.init(st.logDir, st.cfg)
        YLog.i("app", "===== start ${BuildConfig.APP_NAME} ${BuildConfig.VERSION_NAME}__${BuildConfig.BUILD_TIME} =====")
        YLog.i("app", "config: ${st.cfg.file}  log: ${st.logDir}")
        st.cfg.warnings.forEach { YLog.w("config", it) }
        if (core.safeMode) {
            YLog.w("app", "safe mode start")
            core.toast("안전 모드로 시작: 테마 · 상단 바 시세 · 플로팅 가사 · 스펙트럼을 끄고 재생 목록을 백업했습니다 (playlist.tsv.safe_bak)")
        }
        st.cleanupLegacy()
        playback.onTrackChanged = ::onTrackChanged
        playback.onPosition = lyricsCtl::onPosition
        playlist.onEmptied = { lyricsCtl.clear(); media.clear() }
        lib.extraCandidates = { folders.folderTracks.toList() }
        settings.attachSpectrum()
        soundCtl.applyStored()
        LyricsBus.setTiers(lyricsCtl.showPron, lyricsCtl.showTrans)
        core.scope.launch {
            // vr0.1.0.010 (A13): 목록 파일(만 곡 = 수 MB)은 IO 스레드에서 읽고, 다 읽은 뒤 재생 서비스에 연결 (연결 때 목록 복원)
            val saved = core.io("playlist", "목록 읽기 실패", emptyList()) { st.loadPlaylist() }
            playback.tracks.addAll(saved)
            launch { playback.connect { settings.updateVisualizer() } }
            // 이전 버전 목록도 라이브러리 DB 에 등록 (재생 기록 · 좋아요 대상)
            core.register(playback.tracks.toList())
            refreshHome()
            // 장시간 운용: 캐시 폴더 · 재생 기록 크기 제한 (시작 때, 그 뒤 하루 한 번 — maintainIfDue)
            maintainIfDue()
        }
    }

    override fun onCleared() {
        // 재생 기록 · 위치 저장은 서비스(PlaybackTracker)가 계속 — 화면은 연결만 해제
        playlist.flush()
        playback.release()
        soundCtl.flush()
        settings.detachSpectrum()
        ticker.stop()
        YLog.i("app", "viewmodel cleared")
        YLog.flush()
        super.onCleared()
    }
}
