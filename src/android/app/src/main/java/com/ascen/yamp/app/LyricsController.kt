package com.ascen.yamp.app

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import com.ascen.yamp.core.YLog
import com.ascen.yamp.data.Track
import com.ascen.yamp.domain.SkipPolicy
import com.ascen.yamp.lyrics.Lyrics
import com.ascen.yamp.lyrics.LyricsRepo
import com.ascen.yamp.lyrics.LyricsState
import com.ascen.yamp.lyrics.Reason
import com.ascen.yamp.playback.LyricsBus
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

/**
 * 가사: 찾기(캐시 → .lrc → 알송 → LRCLIB, vr0.1.0.008 네트워크는 곡 넘김 대기 후) · 현재 줄 · 싱크 보정 · 3단(A3) · 편집(A1) · 다른 가사(A2) · 줄 반복
 * vr0.1.0.010:
 *   A4 플로팅 · 위젯 줄은 서비스(PlaybackTracker)가 계산 — 여기서는 찾은 가사 · 싱크 보정 · 3단 설정을 LyricsBus 로 넘김
 *   A1 "다시 찾기" 는 편집한 가사를 지우지 않음 — 새 가사를 찾으면 편집 가사일 때 바꿀지 물어봄 (pendingReplace), 바꾸면 .user.bak 보관
 * vr0.1.0.011 (f18):
 *   L7 상태 사유 (state: LyricsState) — 가사 패널 사유 줄 · 출처 칩 · 못 찾음이면 [다른 가사 찾기] [붙여넣기]
 *   L6 실패 기억 중이면 자동 찾기 안 함 (다시 찾기는 무시) · L8 가사 진단 (diagText) · 붙여넣기 (pasteLyrics)
 */
class LyricsController(private val core: AppCore, private val playback: PlaybackController) {
    private val store get() = core.store
    private val repo get() = core.lyricsRepo

    var lyrics by mutableStateOf<Lyrics?>(null); private set
    var lyricsStatus by mutableStateOf(""); private set
    /** L7 상태 사유 */
    var state by mutableStateOf(LyricsState(Reason.NONE)); private set
    /** L8 가사 진단 보고서 (null = 대화상자 닫힘) · 실행 중 · 저장 파일 */
    var diagText by mutableStateOf<String?>(null); private set
    var diagRunning by mutableStateOf(false); private set
    var diagFile by mutableStateOf(""); private set
    var lyricIndex by mutableIntStateOf(-1); private set
    var offsetMs by mutableLongStateOf(0L); private set
    var showPron by mutableStateOf(store.showPron); private set
    var showTrans by mutableStateOf(store.showTrans); private set
    /** 가사 후보 (A2) */
    val candidates = mutableStateListOf<LyricsRepo.Candidate>()
    var candSearching by mutableStateOf(false); private set
    /** A1: 바꿀지 물어볼 새 가사 (null = 없음) */
    var pendingReplace by mutableStateOf<LyricsRepo.Found?>(null); private set
    private var pendingTrack: Track? = null

    private var job: Job? = null

    /** 곡이 바뀜 → 가사 찾기 (t = null 이면 지움) */
    fun load(t: Track?, useCache: Boolean = true) {
        job?.cancel()
        lyricIndex = -1
        pendingReplace = null
        pendingTrack = null
        if (t == null) { lyrics = null; state = LyricsState(Reason.NONE); return }
        offsetMs = store.offset(core.keyOf(t))
        lyrics = null
        state = LyricsState(Reason.SEARCHING)
        lyricsStatus = state.line()
        job = core.scope.launch {
            val r = try {
                // vr0.1.0.008: 기기 안(캐시 · .lrc)은 바로, 네트워크는 그 곡에 SkipPolicy.LYRICS_NET_MS 머문 뒤
                //   (곡을 빨리 넘기면 Job 이 취소되어 요청을 보내지 않음 — 곡마다 알송·LRCLIB 요청이 쌓이지 않게)
                val off = repo.findOffline(t, useCache)
                when {
                    off != null -> LyricsRepo.Result(off, LyricsState(Reason.FOUND, off.source, repo.cachedScore(off)))
                    !repo.usesNetwork -> LyricsRepo.Result(null, LyricsState(Reason.NO_PROVIDER))
                    else -> {
                        // L6: 최근에 검색했지만 없던 곡 → 자동 찾기 안 함 ('다시 찾기'(useCache=false) 는 무시)
                        val nf = if (useCache) core.io("lyrics", "실패 기억 확인 실패", null) { repo.notFoundState(t) } else null
                        if (nf != null) LyricsRepo.Result(null, nf) else {
                            if (useCache) delay(SkipPolicy.LYRICS_NET_MS)      // '다시 찾기'(useCache=false) 는 바로
                            repo.findOnline(t)
                        }
                    }
                }
            } catch (e: CancellationException) { throw e } catch (e: Throwable) {
                YLog.w("lyrics", "가사 찾기 실패 ${t.display}", e); LyricsRepo.Result(null, LyricsState(Reason.NONE))
            }
            if (playback.currentTrack?.uri != t.uri) return@launch
            setLoaded(t, r.lyrics, r.state)
        }
    }

    fun clear() { job?.cancel(); lyrics = null; lyricIndex = -1; pendingReplace = null; pendingTrack = null; state = LyricsState(Reason.NONE) }

    private fun setLoaded(t: Track, ly: Lyrics?, st: LyricsState? = null) {
        lyrics = ly
        LyricsBus.publish(t.uri, ly, offsetMs)     // 서비스 쪽 플로팅 · 위젯 줄 (A4)
        state = when {
            ly != null -> if (st?.reason == Reason.FOUND) st else LyricsState(Reason.FOUND, ly.source, repo.cachedScore(ly))
            st != null && st.reason != Reason.FOUND -> st
            else -> LyricsState(Reason.NONE)
        }
        YLog.i("lyrics", "${t.display} -> ${ly?.source ?: "none"}" + (ly?.let { " blocks=${it.blocks.size} synced=${it.synced}" } ?: "") +
            " · ${state.line()}${state.chip()?.let { " ($it)" } ?: ""}")
        lyricsStatus = state.line() + if (ly != null && !ly.synced) " (싱크 없음)" else ""
        playback.updatePos()
    }

    /** 위치 갱신마다 (PlaybackController.onPosition): 화면의 현재 줄 (플로팅 · 위젯 줄은 서비스가) */
    fun onPosition(posMs: Long) {
        lyricIndex = lyrics?.indexAt(posMs + offsetMs) ?: -1
    }

    /**
     * 가사 다시 찾기 (A1): 캐시를 지우지 않고 .lrc → 알송 → LRCLIB 에서 찾음.
     *   못 찾으면 지금 가사 그대로, 찾으면 — 지금 가사가 직접 편집한 것이면 물어봄 (pendingReplace) / 아니면 바로 바꿈
     */
    fun research() {
        val t = playback.currentTrack ?: return
        job?.cancel()
        pendingReplace = null
        pendingTrack = null
        val before = lyrics
        val status = lyricsStatus
        lyricsStatus = "가사 다시 찾는 중…"
        job = core.scope.launch {
            val (f, st) = try { repo.research(t) } catch (e: CancellationException) { throw e } catch (e: Throwable) {
                YLog.w("lyrics", "가사 다시 찾기 실패 ${t.display}", e); null to LyricsState(Reason.NONE)
            }
            if (playback.currentTrack?.uri != t.uri) return@launch
            if (f == null) {
                YLog.i("lyrics", "다시 찾기: 새 가사 없음 ${t.display} · ${st.line()}")
                if (before != null) {
                    lyricsStatus = status
                    core.toast("새 가사를 찾지 못했습니다 (지금 가사 그대로) — ${st.line()}")
                } else {
                    state = st          // L7: 못 찾은 이유
                    lyricsStatus = st.line()
                    core.toast(st.line())
                }
                return@launch
            }
            val edited = core.io("lyrics", "가사 캐시 확인 실패", false) { repo.isUserEdited(t) }
            if (edited) {
                lyricsStatus = status
                pendingTrack = t
                pendingReplace = f            // 화면(LyricsTab)이 확인 대화상자
                YLog.i("lyrics", "다시 찾기: ${f.source} 찾음 — 편집 가사라 확인 요청 ${t.display}")
            } else applyFound(t, f)
        }
    }

    /** A1 확인 대화상자 답: replace = 새 가사로 바꿈 (편집본은 .user.bak), false = 편집 가사 그대로 */
    fun confirmReplace(replace: Boolean) {
        val f = pendingReplace ?: return
        val t = pendingTrack
        pendingReplace = null
        pendingTrack = null
        if (t == null || playback.currentTrack?.uri != t.uri) return
        if (!replace) { core.toast("직접 편집한 가사를 그대로 둡니다"); return }
        applyFound(t, f)
    }

    private fun applyFound(t: Track, f: LyricsRepo.Found) {
        core.scope.launch {
            val r = core.io("lyrics", "가사 바꾸기 실패", LyricsRepo.APPLY_FAILED) { repo.apply(t, f) }
            if (playback.currentTrack?.uri != t.uri) return@launch
            if (r == LyricsRepo.APPLY_FAILED) { core.toast("편집한 가사를 보관하지 못해 바꾸지 않았습니다"); return@launch }
            if (r == LyricsRepo.APPLY_BACKED_UP) core.toast("새 가사로 바꿈 (편집본 보관: ${repo.backupFile(t).name})")
            YLog.i("lyrics", "다시 찾기 → ${f.source} ${t.display}" + if (r == LyricsRepo.APPLY_BACKED_UP) " (편집본 .user.bak 보관)" else "")
            setLoaded(t, f.lyrics, LyricsState(Reason.FOUND, f.source, f.score))
        }
    }

    fun adjustOffset(delta: Long?) {
        val t = playback.currentTrack ?: return
        offsetMs = if (delta == null) 0 else offsetMs + delta
        store.setOffset(core.keyOf(t), offsetMs)
        LyricsBus.publish(t.uri, lyrics, offsetMs)
        core.toast("가사 싱크 %+.1f초".format(offsetMs / 1000.0))
        playback.updatePos()
    }

    /** 3단 가사 (A3) */
    fun setTiers(pron: Boolean, trans: Boolean) {
        showPron = pron; showTrans = trans
        store.showPron = pron; store.showTrans = trans
        LyricsBus.setTiers(pron, trans)
    }

    /** 가사 줄 반복: 그 줄 시각 ~ 다음 줄 시각 (마지막 줄은 곡 끝) */
    fun repeatLine(blockIndex: Int) {
        val ly = lyrics ?: return
        if (!ly.synced) return
        val b = ly.blocks.getOrNull(blockIndex) ?: return
        val a = (b.tMs - offsetMs).coerceAtLeast(0)
        val nb = ly.blocks.getOrNull(blockIndex + 1)?.let { it.tMs - offsetMs } ?: playback.durationMs
        if (nb <= a) return
        playback.setAB(a, nb)
        playback.seek(a)
        core.toast("가사 줄 반복 (A-B 버튼으로 해제)")
    }

    // ---- 가사 편집 (A1) · 후보 (A2)
    fun saveUserLyrics(lrc: String) {
        val t = playback.currentTrack ?: return
        core.scope.launch {
            val ly = core.io("lyrics", "가사 저장 실패", null) { repo.saveUserLyrics(t, lrc) }
            if (ly == null) { core.toast("저장할 가사가 없습니다"); return@launch }
            // 직접 편집한 시각이 기준 → 싱크 보정 초기화
            offsetMs = 0
            store.setOffset(core.keyOf(t), 0)
            YLog.i("lyrics", "사용자 가사 저장 ${t.display} blocks=${ly.blocks.size}")
            core.toast("가사 저장")
            if (playback.currentTrack?.uri == t.uri) setLoaded(t, ly)
        }
    }

    fun searchCandidates(title: String, artist: String) {
        if (candSearching) return
        candSearching = true
        candidates.clear()
        core.scope.launch {
            val list = try { repo.searchCandidates(playback.currentTrack, title.trim(), artist.trim()) } catch (e: CancellationException) { throw e } catch (e: Throwable) {
                YLog.w("lyrics", "후보 검색 실패", e); emptyList()
            }
            candidates.clear()
            candidates.addAll(list)
            candSearching = false
            YLog.i("lyrics", "가사 후보 '$title' / '$artist' → ${list.size}개")
            if (list.isEmpty()) core.toast("검색 결과 없음")
        }
    }

    /** 붙여넣기: 웹에서 복사한 가사(싱크 없어도 됨) → 직접 편집 가사로 저장 → 편집기에서 싱크 찍기 */
    fun pasteLyrics(text: String?) {
        if (text.isNullOrBlank()) { core.toast("클립보드에 가사가 없습니다"); return }
        if (playback.currentTrack == null) return
        saveUserLyrics(text)
        core.toast("붙여넣은 가사 저장 — 편집(연필) → 싱크 찍기로 시각을 넣을 수 있습니다")
    }

    /** L8 가사 진단: 지금 곡으로 전체 찾기 → 보고서 (대화상자 · 공유 · log/lyrics_diag_*.txt) */
    fun runDiag() {
        val t = playback.currentTrack
        if (t == null) { core.toast("재생 중인 곡이 없습니다"); return }
        if (diagRunning) return
        diagRunning = true
        core.toast("가사 진단 중… (최대 ${store.timeoutMs / 1000}초)")
        core.scope.launch {
            try {
                val (txt, f) = repo.diag(t, store.logDir)
                diagFile = f?.path.orEmpty()
                diagText = txt
            } catch (e: CancellationException) { throw e } catch (e: Throwable) {
                YLog.w("lyrics", "가사 진단 실패", e)
                core.toast("가사 진단 실패: ${e.message ?: e.javaClass.simpleName}")
            } finally { diagRunning = false }
        }
    }

    fun closeDiag() { diagText = null }

    fun chooseCandidate(c: LyricsRepo.Candidate) {
        val t = playback.currentTrack ?: return
        core.scope.launch {
            val ly = core.io("lyrics", "가사 저장 실패", null) { repo.saveCandidate(t, c) }
            if (ly == null) { core.toast("가사를 저장하지 못했습니다"); return@launch }
            YLog.i("lyrics", "가사 후보 선택 ${t.display} ← ${c.source} ${c.artist} - ${c.title}")
            if (playback.currentTrack?.uri == t.uri) setLoaded(t, ly)
        }
    }
}
