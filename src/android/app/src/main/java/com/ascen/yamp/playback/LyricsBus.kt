package com.ascen.yamp.playback

import com.ascen.yamp.lyrics.Lyrics
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/**
 * 가사 공유 (같은 프로세스).
 *   lines : (현재 줄, 다음 줄) — 재생 서비스(PlaybackTracker)가 갱신 → 플로팅 가사 · 홈 위젯이 구독
 *   doc   : 화면(LyricsController)이 찾은 가사 (네트워크 결과 · 직접 편집 · 다른 가사 선택 · 싱크 보정) → 서비스가 받아 씀
 *   tiers : 3단 가사 발음/번역 줄 표시 (설정 화면 → 서비스)
 * vr0.1.0.010 (A4): 줄 계산을 서비스로 옮김 — 앱을 최근 앱에서 밀어 닫아도(화면 · ViewModel 없음) 플로팅 · 위젯 가사가 계속
 */
object LyricsBus {
    /** 화면이 서비스에 넘기는 가사 (uri = 곡 uri = MediaItem.mediaId) */
    data class Doc(val uri: String, val lyrics: Lyrics?, val offsetMs: Long)

    private val _lines = MutableStateFlow("" to "")
    val lines: StateFlow<Pair<String, String>> = _lines.asStateFlow()

    private val _doc = MutableStateFlow<Doc?>(null)
    val doc: StateFlow<Doc?> = _doc.asStateFlow()

    private val _tiers = MutableStateFlow<Pair<Boolean, Boolean>?>(null)
    /** (발음, 번역) — null = 아직 화면이 안 알려 줌 (서비스는 config.txt 값) */
    val tiers: StateFlow<Pair<Boolean, Boolean>?> = _tiers.asStateFlow()

    /** 서비스 → 플로팅 · 위젯 */
    fun post(cur: String, next: String) {
        val v = cur to next
        if (_lines.value != v) _lines.value = v
    }

    /** 화면 → 서비스: 이 곡의 가사 (null = 가사 없음) · 싱크 보정 */
    fun publish(uri: String, lyrics: Lyrics?, offsetMs: Long) {
        _doc.value = Doc(uri, lyrics, offsetMs)
    }

    fun setTiers(pron: Boolean, trans: Boolean) { _tiers.value = pron to trans }
}
