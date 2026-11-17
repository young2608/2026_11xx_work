package com.ascen.yamp.app

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import com.ascen.yamp.core.YLog
import com.ascen.yamp.data.Track
import com.ascen.yamp.domain.HomeCard
import com.ascen.yamp.domain.Recommend
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlin.random.Random

/** 추천 홈 (B2) · 비슷한 곡 라디오 (B3) · 재생 기록 지우기 */
class HomeController(
    private val core: AppCore,
    private val playback: PlaybackController,
    private val playlist: PlaylistController,
    private val library: LibraryController,
) {
    private val db get() = core.db

    val homeCards = mutableStateListOf<HomeCard>()
    var homeLoading by mutableStateOf(false); private set

    private fun today(): Long = System.currentTimeMillis() / DAY_MS

    /** 추천 홈 (하루 1회 또는 새로고침) */
    fun refreshHome(force: Boolean = false) {
        val today = today()
        if (!force && homeCards.isNotEmpty() && core.store.homeDay == today) return
        if (homeLoading) return
        homeLoading = true
        core.scope.launch {
            library.refreshNow()
            val cards = withContext(Dispatchers.Default) {
                runCatching {
                    val now = core.nowS()
                    val stats = db.stats(now)
                    if (stats.none { it.completed > 0 || it.skipped > 0 || it.liked || it.rating > 0 }) emptyList<HomeCard>()
                    else Recommend.buildHome(stats, now, db.coPairs(), db.lastPlayedKey(), db.recentKeys(now),
                        rng = if (force) Random(System.nanoTime()) else Random(today))
                }.onFailure { YLog.w("home", "추천 계산 실패", it) }.getOrDefault(emptyList())
            }
            homeCards.clear()
            homeCards.addAll(cards.map { c -> c.copy(keys = c.keys.filter(library::hasKey)) }.filter { it.keys.isNotEmpty() })
            core.store.homeDay = today
            homeLoading = false
            YLog.i("home", "추천 카드 ${homeCards.size}개" + if (force) " (새로고침)" else "")
        }
    }

    fun playMixKeys(keys: List<String>, label: String) {
        playlist.playMix(keys.mapNotNull(library::trackOfKey), label)
    }

    /** 비슷한 곡 라디오 (B3) */
    fun radio(seed: Track) {
        val seedKey = core.keyOf(seed)
        val isCurrent = playback.currentTrack?.uri == seed.uri
        core.scope.launch {
            core.register(listOf(seed))
            val keys = withContext(Dispatchers.Default) {
                runCatching {
                    Recommend.similar(db.stats(), seedKey, db.coPairs(), db.recentKeys(), rng = Random(System.nanoTime()))
                }.onFailure { YLog.w("mix", "라디오 계산 실패", it) }.getOrDefault(emptyList())
            }
            if (library.isEmpty || keys.any { !library.hasKey(it) }) library.refreshNow()
            val list = keys.mapNotNull(library::trackOfKey)
            if (list.size <= 1) { core.toast("비슷한 곡을 찾지 못했습니다 (라이브러리에 곡을 더 추가해 보세요)"); return@launch }
            YLog.i("mix", "라디오 seed=${seed.display} → ${list.size}곡")
            // 지금 듣는 곡이 기준이면 이어서 (현재 곡은 그대로 두고 뒤에 넣음)
            if (isCurrent) playlist.playMix(list.drop(1), "라디오: ${seed.title}", startNow = false)
            else playlist.playMix(list, "라디오: ${seed.title}")
        }
    }

    fun clearHistory() {
        core.scope.launch {
            core.io("history", "기록 지우기 실패", Unit) { db.clearHistory() }
            YLog.i("history", "재생 기록 지움")
            core.toast("재생 기록을 지웠습니다")
            homeCards.clear()
            library.refreshNow()
            refreshHome(force = true)
        }
    }

    companion object {
        private const val DAY_MS = 86_400_000L
    }
}
