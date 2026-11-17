package com.ascen.yamp.app

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.setValue
import androidx.media3.common.Player
import com.ascen.yamp.core.YLog
import com.ascen.yamp.data.Track
import com.ascen.yamp.domain.PlayMath
import com.ascen.yamp.domain.SkipPolicy
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/**
 * 재생 목록 편집 · 대기열(B5) · 믹스 재생 · 목록 교체 (폴더 재생)
 * vr0.1.0.010: 재생 기록은 서비스(PlaybackTracker)가 곡 전환으로 판단 (목록 비우기 · 교체 · 지우기 모두 전환으로 들어옴)
 *   A3: "열기"로 연 임시 권한 파일은 목록 파일에 저장하지 않음 (다시 시작하면 열 수 없음)
 *   A14: 순서 바꾸기 때 대기열 수 다시 계산
 */
class PlaylistController(
    private val core: AppCore,
    private val playback: PlaybackController,
) {
    private val store get() = core.store
    private val tracks get() = playback.tracks

    /** 대기열: current 뒤에 끼워 넣은(아직 안 들은) 곡 수 */
    var queued by mutableIntStateOf(store.queued.coerceAtLeast(0)); private set

    /** 목록을 비움 → 가사 · 커버 지우기 (AppViewModel 이 연결) */
    var onEmptied: () -> Unit = {}

    private var saveJob: Job? = null
    /** 영구 권한이 없는 곡 uri (A3) — 이번 실행에서만 목록에 둠 */
    private val transient = HashSet<String>()

    fun markTransient(uris: Collection<String>) { transient.addAll(uris) }

    private fun snapshot(): List<Track> = if (transient.isEmpty()) tracks.toList() else tracks.filter { it.uri !in transient }

    /**
     * 목록 파일 저장 (vr0.1.0.008): 메인 스레드에서는 목록 복사만, 파일 쓰기는 IO 스레드에서
     * SkipPolicy.PLAYLIST_SAVE_MS 뒤 한 번 (1만 곡 목록을 편집할 때마다 메인 스레드에서 수 MB 를 쓰지 않게)
     */
    private fun save() {
        saveJob?.cancel()
        saveJob = core.scope.launch {
            delay(SkipPolicy.PLAYLIST_SAVE_MS)
            val snap = snapshot()
            withContext(Dispatchers.IO) { store.savePlaylist(snap) }
        }
    }

    /** 대기 중인 저장을 바로 (onCleared — viewModelScope 가 곧 취소됨) */
    fun flush() {
        if (saveJob?.isActive != true) return
        saveJob?.cancel()
        saveJob = null
        val snap = snapshot()
        Thread({ store.savePlaylist(snap) }, "yamp-playlist").start()
    }

    fun addTracks(list: List<Track>) {
        if (list.isEmpty()) { core.toast("추가할 곡 없음"); return }
        tracks.addAll(list)
        playback.controller?.let { c ->
            c.addMediaItems(list.map(::mediaItemOf))
            if (c.playbackState == Player.STATE_IDLE) c.prepare()
        }
        save()
        core.toast("${list.size}곡 추가")
    }

    fun remove(i: Int) {
        if (i !in tracks.indices) return
        val cur = playback.current
        if (cur >= 0 && i in (cur + 1)..(cur + queued)) updateQueued(queued - 1)
        // 현재 곡 앞의 곡을 지우면 index 만 당겨짐 (곡 변경 아님 → 재생 기록 유지)
        if (i < cur) playback.current = cur - 1
        else if (i == cur) {
            // 지금 곡을 지움 → 다음 곡(대기열 첫 곡)이 같은 index 로 → 곡 변경으로 처리
            updateQueued(queued - 1)
            playback.current = -1
        }
        tracks.removeAt(i)
        playback.controller?.removeMediaItem(i)
        save()
        playback.sync()
    }

    fun move(i: Int, j: Int) {
        if (i !in tracks.indices || j !in tracks.indices || i == j) return
        // A14: 대기열 범위를 넘나들면 "다음 재생" 곡 수 다시 계산
        val (newCur, q) = PlayMath.queuedAfterReorder(playback.current, queued, i, j, tracks.size)
        val t = tracks.removeAt(i)
        tracks.add(j, t)
        playback.controller?.moveMediaItem(i, j)
        save()
        playback.current = newCur
        updateQueued(q)
    }

    fun clear() {
        tracks.clear()
        playback.controller?.run { stop(); clearMediaItems() }
        save()
        playback.current = -1
        updateQueued(0)
        playback.clearAB()
        onEmptied()
    }

    // ================================================= 대기열 (B5)
    fun updateQueued(n: Int) {
        val v = n.coerceAtLeast(0)
        if (v != queued) { queued = v; store.queued = v }
    }

    /** 곡이 바뀐 뒤 남은 대기열 */
    fun onTrackMoved(old: Int, new: Int) {
        if (old >= 0) updateQueued(PlayMath.queuedAfterMove(old, new, queued))
    }

    private fun insertAt(index: Int, list: List<Track>) {
        val at = index.coerceIn(0, tracks.size)
        tracks.addAll(at, list)
        playback.controller?.let { c ->
            c.addMediaItems(at, list.map(::mediaItemOf))
            if (c.playbackState == Player.STATE_IDLE) c.prepare()
        }
        save()
    }

    private fun shuffleNote() { if (playback.shuffle) core.appendToast(" (셔플 중에는 순서가 바뀔 수 있음)") }

    /** "다음에 재생": 현재 곡 바로 뒤 */
    fun playNext(t: Track) {
        insertAt(PlayMath.insertNextIndex(playback.current, tracks.size), listOf(t))
        if (playback.current >= 0) updateQueued(queued + 1)
        core.toast("다음에 재생: ${t.display}")
        shuffleNote()
    }

    /** "대기열 끝에 추가": 앞서 넣은 대기열 곡들 뒤 */
    fun enqueue(t: Track) {
        insertAt(PlayMath.insertQueueEndIndex(playback.current, queued, tracks.size), listOf(t))
        if (playback.current >= 0) updateQueued(queued + 1)
        core.toast("대기열에 추가: ${t.display}")
        shuffleNote()
    }

    /** 대기열 비우기: 끼워 넣고 아직 안 들은 곡 삭제 */
    fun clearQueue() {
        val n = queued
        val cur = playback.current
        if (n <= 0 || cur < 0) { updateQueued(0); return }
        val from = cur + 1
        val to = minOf(tracks.size, from + n)
        // 한 번에 지움 (removeAt 반복 → 목록 변경 알림이 곡 수만큼 생기지 않게)
        if (to > from) tracks.subList(from, to).clear()
        playback.controller?.removeMediaItems(from, to)
        updateQueued(0)
        save()
        core.toast("대기열 ${to - from}곡 비움")
    }

    /** 믹스/라디오 재생: 현재 곡 뒤에 넣고 첫 곡으로 */
    fun playMix(list: List<Track>, label: String, startNow: Boolean = true) {
        if (list.isEmpty()) { core.toast("재생할 곡이 없습니다"); return }
        val at = PlayMath.insertNextIndex(playback.current, tracks.size)
        insertAt(at, list)
        YLog.i("mix", "$label ${list.size}곡 (startNow=$startNow)")
        // 믹스 곡도 대기열로 셈. 첫 곡으로 이동하면 queuedAfterMove 가 1 줄여 "남은 믹스 + 이전 대기열" 이 됨
        if (playback.current >= 0) updateQueued(queued + list.size)
        if (startNow) playback.playIndex(at)
        core.toast("$label · ${list.size}곡")
    }

    /** 재생 목록 교체 + 재생 (폴더 재생) */
    fun replacePlaylist(list: List<Track>, label: String, startIndex: Int = 0) {
        if (list.isEmpty()) { core.toast("재생할 곡이 없습니다"); return }
        tracks.clear()
        tracks.addAll(list)
        updateQueued(0)
        playback.clearAB()
        playback.current = -1
        save()
        val i = startIndex.coerceIn(0, list.size - 1)
        playback.controller?.let { c ->
            c.setMediaItems(list.map(::mediaItemOf), i, 0L)
            c.prepare()
            c.play()
            playback.sync()
        }
        core.scope.launch { core.register(list) }
        core.toast("$label · ${list.size}곡")
    }
}
