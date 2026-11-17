package com.ascen.yamp.data

/**
 * 재생 기록 판정 (순수 Kotlin — JVM 테스트 대상). PC yamp/data/recorder.py 와 같은 규칙.
 *
 * - 들은 시간: 재생 중일 때 위치 변화만 누적 (2초 넘게 건너뛰면 탐색으로 보고 제외)
 * - completed : 곡 길이의 50% 이상 또는 4분 이상 들음 (끝까지 재생돼 넘어갔고 30초 이상이면 완청)
 * - skipped   : 30초 미만 듣고 다른 곡으로 넘어감 (끝까지 재생돼 넘어간 경우 제외)
 * - session   : 마지막 기록 후 30분 넘게 쉬면 새 세션 (session_id = 세션 시작 epoch 초)
 */
class PlayRecorder {
    data class Rec(
        val key: String, val startedAt: Long, val listenedMs: Long, val durationMs: Long,
        val completed: Boolean, val skipped: Boolean, val sessionId: Long,
    )

    companion object {
        const val COMPLETE_RATIO = 0.5
        const val COMPLETE_MS = 4 * 60 * 1000L
        const val SKIP_MS = 30 * 1000L
        const val SESSION_GAP_S = 30 * 60L
        const val MAX_STEP_MS = 2000L
    }

    var key: String? = null; private set
    var durationMs = 0L; private set
    var startedAt = 0L; private set
    var listened = 0L; private set
    var sessionId = 0L; private set
    private var lastPos: Long? = null
    private var lastEnd = 0L

    fun start(key: String, durationMs: Long, nowS: Long) {
        if (sessionId == 0L || nowS - lastEnd > SESSION_GAP_S) sessionId = nowS
        this.key = key
        this.durationMs = maxOf(0L, durationMs)
        startedAt = nowS
        listened = 0
        lastPos = null
    }

    fun setDuration(ms: Long) { if (ms > 0) durationMs = ms }

    fun tick(posMs: Long, playing: Boolean) {
        if (key == null) return
        val lp = lastPos
        if (playing && lp != null) {
            val d = posMs - lp
            if (d in 1..MAX_STEP_MS) listened += d
        }
        lastPos = posMs
    }

    /** 기록 반환 (들은 시간 0 이면 null) 후 초기화 */
    fun finish(endedNaturally: Boolean, nowS: Long): Rec? {
        val k = key ?: return null
        val lst = listened
        var rec: Rec? = null
        if (lst > 0) {
            val completed = lst >= COMPLETE_MS || (durationMs > 0 && lst >= durationMs * COMPLETE_RATIO) ||
                (endedNaturally && lst >= SKIP_MS)
            val skipped = !endedNaturally && lst < SKIP_MS
            rec = Rec(k, startedAt, lst, durationMs, completed, skipped, sessionId)
            lastEnd = nowS
        }
        key = null
        return rec
    }
}
