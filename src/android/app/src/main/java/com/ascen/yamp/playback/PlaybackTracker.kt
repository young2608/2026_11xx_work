package com.ascen.yamp.playback

import android.content.Context
import android.content.SharedPreferences
import android.os.Handler
import android.os.Looper
import androidx.annotation.OptIn
import androidx.media3.common.MediaItem
import androidx.media3.common.PlaybackException
import androidx.media3.common.Player
import androidx.media3.common.util.UnstableApi
import androidx.media3.common.util.Util
import androidx.media3.exoplayer.ExoPlayer
import com.ascen.yamp.core.YLog
import com.ascen.yamp.data.LibraryDb
import com.ascen.yamp.data.PlayRecorder
import com.ascen.yamp.data.Store
import com.ascen.yamp.data.Track
import com.ascen.yamp.data.fmtTime
import com.ascen.yamp.domain.ErrorSkip
import com.ascen.yamp.domain.ResumeBook
import com.ascen.yamp.domain.TickPolicy
import com.ascen.yamp.lyrics.LyricLines
import com.ascen.yamp.lyrics.Lyrics
import com.ascen.yamp.lyrics.LyricsRepo
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.util.concurrent.Executors

/**
 * 재생 서비스 쪽 기록 · 가사 줄 · 오류 건너뛰기 · 위치 저장 (vr0.1.0.010, A4 · D4).
 *
 * 화면(AppViewModel)에만 있던 일을 PlaybackService 의 ExoPlayer 리스너로 옮김 → 최근 앱에서 앱을 밀어 닫아도
 * (음악은 계속, 화면 · ViewModel 은 없음) 아래가 계속 동작:
 *   - 재생 기록 (PlayRecorder → LibraryDb) — 기록하는 곳은 여기 하나 (화면은 기록하지 않음, 중복 없음)
 *   - 재생 오류 → 다음 곡 건너뛰기 (ErrorSkip, 연속 10번까지)
 *   - 마지막 곡 번호 · 위치 저장 (시작 시 이어 듣기)
 *   - 플로팅 가사 · 홈 위젯 가사 줄 (LyricsBus.post) — 가사는 곡이 바뀌면 여기서 캐시 · 같은 폴더 .lrc 로 읽음 (네트워크 없음),
 *     화면이 네트워크로 찾거나 편집한 가사는 LyricsBus.publish 로 받음
 *   - V2 파일별 이어 듣기 (30분 넘는 파일, ResumeBook)
 * 위치 확인: 재생 중에만 메인 Handler 로 (플로팅 가사가 떠 있으면 200ms, 아니면 500ms — PlayRecorder 2초 간격 조건보다 짧게)
 * 같은 프로세스 싱글턴 (PlayerHolder 처럼). PlaybackService 가 attach / detach.
 */
@OptIn(UnstableApi::class)
object PlaybackTracker {
    /** 화면에 보여 줄 알림 (같은 문구도 다시 보이게 seq) */
    data class Notice(val seq: Long, val text: String)

    private val _notice = MutableStateFlow(Notice(0, ""))
    val notice: StateFlow<Notice> = _notice.asStateFlow()

    // ---- 설정 (서비스 시작 때 config.txt, 화면에서 바꾸면 바로)
    @Volatile var historyEnabled = true
    @Volatile var resumeLong = true

    private var player: ExoPlayer? = null
    private var appCtx: Context? = null
    private var prefs: SharedPreferences? = null
    private var scope: CoroutineScope? = null
    private val handler = Handler(Looper.getMainLooper())
    private val io = Executors.newSingleThreadExecutor { r -> Thread(r, "yamp-tracker").apply { isDaemon = true } }

    private val recorder = PlayRecorder()
    private var errorsInRow = 0

    // ---- 지금 곡 (메인 스레드)
    private var curId: String? = null
    private var lastPos = 0L
    private var lastDur = 0L
    private var lastSaveAt = 0L

    // ---- V2
    private val book = ResumeBook()
    private var pendingResume: String? = null

    // ---- 가사 (서비스 쪽)
    @Volatile private var store: Store? = null
    @Volatile private var repo: LyricsRepo? = null
    private var ly: Lyrics? = null
    private var lyOffset = 0L
    private var lyFromUi = false
    private var pron = true
    private var trans = true
    private var lyJob: Job? = null

    // ================================================================ 연결
    fun attach(ctx: Context, p: ExoPlayer) {
        appCtx = ctx.applicationContext
        player = p
        val sp = ctx.getSharedPreferences(Store.PREFS, Context.MODE_PRIVATE)
        prefs = sp
        runCatching { book.load(sp.getString(Store.KEY_RESUME_BOOK, "").orEmpty()) }
        val sc = CoroutineScope(SupervisorJob() + Dispatchers.Main)
        scope = sc
        p.addListener(listener)
        sc.launch { LyricsBus.doc.collect { d -> if (d != null) onUiLyrics(d) } }
        sc.launch { LyricsBus.tiers.collect { t -> if (t != null) { pron = t.first; trans = t.second; postLine() } } }
        onItem(p.currentMediaItem, Player.MEDIA_ITEM_TRANSITION_REASON_PLAYLIST_CHANGED)
    }

    fun detach() {
        val p = player
        handler.removeCallbacks(tick)
        if (p != null) {
            savePosition(p, force = true)
            finishRecord(false, sync = true)
            p.removeListener(listener)
        }
        scope?.cancel()
        scope = null
        lyJob = null
        player = null
        curId = null
        ly = null
        LyricsBus.post("", "")
    }

    /** 서비스 시작 때 config.txt 의 3단 가사 표시 (화면이 LyricsBus.setTiers 로 바꾸기 전) */
    fun configureTiers(showPron: Boolean, showTrans: Boolean) { pron = showPron; trans = showTrans }

    // ================================================================ 리스너
    private val listener = object : Player.Listener {
        override fun onMediaItemTransition(mediaItem: MediaItem?, reason: Int) { onItem(mediaItem, reason) }

        override fun onIsPlayingChanged(isPlaying: Boolean) {
            val p = player ?: return
            if (isPlaying) {
                errorsInRow = 0
                // 1곡 목록에서 끝난 뒤 다시 재생 · '정지' 뒤 재생 → 새 기록
                if (recorder.key == null) startRecord(p)
                schedule()
            } else {
                step(p)
                savePosition(p, force = true)
                handler.removeCallbacks(tick)
            }
        }

        override fun onPlaybackStateChanged(state: Int) {
            val p = player ?: return
            if (state == Player.STATE_READY) tryResume(p)
            if (state == Player.STATE_ENDED) {
                step(p)
                finishRecord(true)
                curId?.let { id -> if (book.put(id, lastDur, lastDur)) persistBook() }
            }
        }

        override fun onPositionDiscontinuity(oldPosition: Player.PositionInfo, newPosition: Player.PositionInfo, reason: Int) {
            // 탐색 (일시정지 중 포함) → 가사 줄 바로
            val p = player ?: return
            if (!p.isPlaying) { lastPos = p.currentPosition.coerceAtLeast(0); postLine() }
        }

        override fun onPlayerError(error: PlaybackException) {
            val p = player ?: return
            val d = ErrorSkip.onError(errorsInRow, p.mediaItemCount, p.hasNextMediaItem())
            val n = errorsInRow + 1
            errorsInRow = d.count
            YLog.w("player", "error ${error.errorCode} item=${p.currentMediaItem?.mediaId} (연속 $n, 서비스)")
            when (d.action) {
                ErrorSkip.Action.SKIP -> {
                    p.seekToNextMediaItem()
                    Util.handlePlayButtonAction(p)        // 오류 뒤 IDLE → prepare + play
                }
                ErrorSkip.Action.STOP -> {
                    // 전체 반복에서 모든 곡이 실패 (저장소 빠짐 · 권한 해제 등) → 끝없이 건너뛰지 않고 멈춤
                    YLog.w("player", "연속 재생 오류 ${n}번 → 건너뛰기 멈춤")
                    notify("재생 오류가 계속됩니다 (${n}곡) — 파일 · 저장소를 확인해 주세요")
                }
                ErrorSkip.Action.NONE -> {}
            }
        }
    }

    /** 곡이 바뀜 (같은 곡 1곡 반복 포함) */
    private fun onItem(item: MediaItem?, reason: Int) {
        val p = player ?: return
        val natural = reason == Player.MEDIA_ITEM_TRANSITION_REASON_AUTO || reason == Player.MEDIA_ITEM_TRANSITION_REASON_REPEAT
        // 지난 곡: 기록 끝 · 이어 듣기 위치
        curId?.let { old ->
            val changed = if (natural) book.put(old, lastDur, lastDur) else book.put(old, lastPos, lastDur)
            if (changed) persistBook()
        }
        finishRecord(natural)
        val id = item?.mediaId?.takeIf { it.isNotEmpty() } ?: item?.localConfiguration?.uri?.toString()
        val same = id != null && id == curId
        curId = id
        lastPos = p.currentPosition.coerceAtLeast(0)
        lastDur = p.duration.coerceAtLeast(0)
        if (id == null) {
            ly = null; lyJob?.cancel(); LyricsBus.post("", "")
            handler.removeCallbacks(tick)
            return
        }
        prefs?.edit()?.putInt(Store.KEY_LAST_INDEX, p.currentMediaItemIndex)?.apply()
        startRecord(p)          // 곡이 바뀌면 새 기록 (들은 시간은 재생 중일 때만 쌓임)
        pendingResume = if (resumeLong && reason != Player.MEDIA_ITEM_TRANSITION_REASON_REPEAT) id else null
        tryResume(p)
        if (!same) loadLyrics(item, id)
        postLine()
        schedule()
    }

    // ================================================================ 위치 확인 (재생 중에만)
    private val tick = object : Runnable {
        override fun run() {
            val p = player ?: return
            step(p)
            savePosition(p, force = false)
            if (p.isPlaying) handler.postDelayed(this, TickPolicy.intervalMs(false, FloatingLyricsService.running, false))
        }
    }

    private fun schedule() {
        handler.removeCallbacks(tick)
        if (player?.isPlaying == true) handler.post(tick)
    }

    private fun step(p: ExoPlayer) {
        lastPos = p.currentPosition.coerceAtLeast(0)
        val d = p.duration
        if (d > 0) lastDur = d
        recorder.setDuration(lastDur)
        recorder.tick(lastPos, p.isPlaying)
        postLine()
    }

    // ================================================================ 재생 기록 (여기 하나만 기록)
    private fun startRecord(p: ExoPlayer) {
        val id = curId ?: return
        if (recorder.key != null) return
        recorder.start(LyricsRepo.keyOf(id), p.duration.coerceAtLeast(0), nowS())
    }

    private fun finishRecord(endedNaturally: Boolean, sync: Boolean = false) {
        val rec = recorder.finish(endedNaturally, nowS()) ?: return
        if (!historyEnabled) return
        val ctx = appCtx ?: return
        YLog.d("history", "${rec.key} ${rec.listenedMs}ms completed=${rec.completed} skipped=${rec.skipped} s=${rec.sessionId}")
        val write = Runnable { runCatching { LibraryDb.get(ctx).recordPlay(rec) }.onFailure { YLog.w("history", "기록 실패", it) } }
        if (sync) Thread(write, "yamp-history").start() else io.execute(write)
    }

    /** 화면의 '정지' (일시정지 + 처음으로): 지금 기록을 끝내고 새 기록 (vr0.1.0.009 까지와 같은 판정) */
    fun restartRecord() {
        val p = player ?: return
        finishRecord(false)
        recorder.start(LyricsRepo.keyOf(curId ?: return), p.duration.coerceAtLeast(0), nowS())
    }

    private fun nowS(): Long = System.currentTimeMillis() / 1000

    // ================================================================ 위치 저장 · V2 이어 듣기
    private fun savePosition(p: ExoPlayer, force: Boolean) {
        val now = android.os.SystemClock.elapsedRealtime()
        if (!force && !TickPolicy.shouldSavePos(now, lastSaveAt)) return
        lastSaveAt = now
        val sp = prefs ?: return
        if (p.mediaItemCount > 0) {
            sp.edit().putInt(Store.KEY_LAST_INDEX, p.currentMediaItemIndex).putLong(Store.KEY_LAST_POS, lastPos).apply()
        }
        curId?.let { id -> if (book.put(id, lastPos, lastDur)) persistBook() }
    }

    private fun persistBook() {
        prefs?.edit()?.putString(Store.KEY_RESUME_BOOK, book.toText())?.apply()
    }

    /** 긴 파일을 처음부터 열었으면 기억한 위치로 (길이를 알아야 하므로 READY 뒤) */
    private fun tryResume(p: ExoPlayer) {
        val id = pendingResume ?: return
        if (id != curId) { pendingResume = null; return }
        val dur = p.duration
        if (dur <= 0) return                // 길이를 아직 모름 → READY 때 다시
        pendingResume = null
        if (!resumeLong || p.currentPosition > RESUME_START_WINDOW_MS) return
        val at = book.resumeAt(id, dur) ?: return
        p.seekTo(at)
        lastPos = at
        YLog.i("player", "이어 듣기 ${fmtTime(at)} / ${fmtTime(dur)} $id")
        notify("이어 듣기 ${fmtTime(at)}")
    }

    /** 이어 듣기 기록 모두 지우기 (설정에서 끔) */
    fun clearResumeBook() {
        book.load("")
        persistBook()
    }

    private fun notify(text: String) { _notice.value = Notice(_notice.value.seq + 1, text) }

    // ================================================================ 가사 줄 (플로팅 · 위젯)
    private fun onUiLyrics(d: LyricsBus.Doc) {
        if (d.uri != curId) return
        lyJob?.cancel()
        ly = d.lyrics
        lyOffset = d.offsetMs
        lyFromUi = true
        postLine()
    }

    /** 곡이 바뀜: 화면이 이미 알려 준 가사가 있으면 그것, 아니면 기기 안(캐시 · .lrc)에서만 */
    private fun loadLyrics(item: MediaItem?, id: String) {
        lyJob?.cancel()
        ly = null
        lyOffset = 0
        lyFromUi = false
        LyricsBus.doc.value?.takeIf { it.uri == id }?.let { onUiLyrics(it); return }
        val ctx = appCtx ?: return
        val md = item?.mediaMetadata
        val t = Track(id, md?.title?.toString().orEmpty(), md?.artist?.toString().orEmpty(),
            path = md?.extras?.getString(PlayerHolder.EXTRA_PATH).orEmpty())
        lyJob = scope?.launch {
            val found = try {
                withContext(Dispatchers.IO) {
                    val st = store ?: Store(ctx).also { store = it }
                    val r = repo ?: LyricsRepo(ctx, st).also { repo = it }
                    r.findOffline(t) to st.offset(r.key(t))
                }
            } catch (e: CancellationException) { throw e } catch (e: Exception) {
                YLog.w("lyrics", "서비스 가사 읽기 실패 ${t.display}", e); null
            }
            if (curId != id || lyFromUi) return@launch
            ly = found?.first
            lyOffset = found?.second ?: 0
            postLine()
        }
    }

    private fun postLine() {
        val l = ly
        val idx = l?.indexAt(lastPos + lyOffset) ?: -1
        val (cur, next) = LyricLines.of(l, idx, pron, trans)
        LyricsBus.post(cur, next)
    }

    /** 처음 몇 초 안에서 시작했을 때만 이어 듣기 (시작 위치를 직접 준 경우 — 앱 시작 이어 듣기 등 — 는 그대로) */
    private const val RESUME_START_WINDOW_MS = 3000L
}
