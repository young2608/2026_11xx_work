package com.ascen.yamp.domain

import kotlin.math.pow

/** 재생 보조 계산 (순수 Kotlin — JVM 테스트 대상): 대기열 위치 · 페이드 · 음정 · A-B · 같이 들은 곡 */
object PlayMath {
    /**
     * 대기열(B5): 현재 곡 뒤에 끼워 넣은 곡 수 = queued.
     *   "다음에 재생"     → current+1 (바로 다음)
     *   "대기열 끝에 추가" → current+1+queued (앞서 넣은 곡들 뒤)
     */
    fun insertNextIndex(current: Int, size: Int): Int = if (current < 0) size else minOf(size, current + 1)
    fun insertQueueEndIndex(current: Int, queued: Int, size: Int): Int =
        if (current < 0) size else minOf(size, current + 1 + maxOf(0, queued))

    /**
     * 현재 곡이 바뀐 뒤 남은 대기열 수.
     * 대기열 첫 곡(이전 current+1) 로 이동하면 하나 줄고, 그 밖으로 이동하면 0 (대기열 범위를 벗어남)
     */
    fun queuedAfterMove(oldCurrent: Int, newCurrent: Int, queued: Int): Int {
        if (queued <= 0 || oldCurrent < 0) return 0
        if (newCurrent == oldCurrent) return queued
        val first = oldCurrent + 1
        val last = oldCurrent + queued
        return if (newCurrent in first..last) last - newCurrent else 0
    }

    /**
     * 목록 순서 바꾸기 뒤 대기열 수 (vr0.1.0.010, A14): 곡 하나를 from → to 로 옮김.
     *   current = 옮기기 전 현재 곡, queued = 그 뒤 대기열 곡 수. 반환 (새 current, 새 queued)
     *   - 대기열 곡을 대기열 밖으로 → 하나 줄어듦, 밖의 곡을 대기열 안(새 current 뒤 ~ 대기열 끝)으로 → 하나 늘어남
     *   - 현재 곡을 옮기면 새 위치 바로 뒤부터 이어지는 대기열 곡만 남음
     */
    fun queuedAfterReorder(current: Int, queued: Int, from: Int, to: Int, size: Int): Pair<Int, Int> {
        if (from !in 0 until size || to !in 0 until size || from == to) return current to maxOf(0, queued)
        val newCur = when {
            current < 0 -> current
            from == current -> to
            from < current && to >= current -> current - 1
            from > current && to <= current -> current + 1
            else -> current
        }
        if (current < 0) return newCur to 0
        val q = maxOf(0, queued)
        // 대기열 표시: 옮기기 전 위치 기준 current+1 .. current+q
        val marks = MutableList(size) { it in (current + 1)..(current + q) }
        val moved = marks.removeAt(from)
        marks.add(to, moved)
        // 대기열 밖의 곡(현재 곡 제외)을 대기열 자리(새 current 뒤 1 ~ q 번째)에 넣으면 대기열에 합류
        if (from != current && !moved && to in (newCur + 1)..(newCur + q)) marks[to] = true
        var n = 0
        var i = newCur + 1
        while (i < size && marks[i]) { n++; i++ }
        return newCur to n
    }

    /**
     * 곡 전환 페이드 배율 (0..1): 시작 fadeMs 동안 0→1, 끝 fadeMs 동안 1→0.
     * (겹치는 크로스페이드가 아님 — 플레이어 1개로 앞뒤 볼륨만 조절)
     */
    fun transitionFade(posMs: Long, durMs: Long, fadeMs: Long): Float {
        if (fadeMs <= 0) return 1f
        var f = 1f
        if (posMs < fadeMs) f = minOf(f, posMs.coerceAtLeast(0).toFloat() / fadeMs)
        if (durMs > 0 && durMs > 2 * fadeMs) {
            val left = durMs - posMs
            if (left < fadeMs) f = minOf(f, left.coerceAtLeast(0).toFloat() / fadeMs)
        }
        return f.coerceIn(0f, 1f)
    }

    /** 슬립 타이머: 남은 시간 remainMs, 마지막 fadeMs 동안 1→0 */
    fun sleepFade(remainMs: Long, fadeMs: Long): Float =
        if (fadeMs <= 0 || remainMs >= fadeMs) 1f else (remainMs.coerceAtLeast(0).toFloat() / fadeMs).coerceIn(0f, 1f)

    /** 최종 볼륨: ExoPlayer volume 은 0..1 → 1 넘는 ReplayGain 증폭은 적용 불가 (잘림) */
    fun combineVolume(rgFactor: Double, fade: Float, sleep: Float): Float =
        (rgFactor.toFloat() * fade * sleep).coerceIn(0f, 1f)

    /** 반음 → 음정 배율 2^(st/12) */
    fun pitchFactor(semitones: Float): Float = 2.0.pow(semitones / 12.0).toFloat()

    /** A-B 구간 반복: 위치가 B 이상이면 A 로 */
    fun abSeek(posMs: Long, a: Long, b: Long): Long? = if (a >= 0 && b > a && posMs >= b) a else null

    /** 같은 세션에서 연달아 들은 곡 쌍 → 횟수. rows = (key, session_id), 세션·시작 순 정렬 */
    fun coPairs(rows: List<Pair<String, Long>>): Map<Pair<String, String>, Int> {
        val out = HashMap<Pair<String, String>, Int>()
        var prev: Pair<String, Long>? = null
        for (r in rows) {
            val p = prev
            if (p != null && p.second == r.second && p.first != r.first) {
                val k = p.first to r.first
                out[k] = (out[k] ?: 0) + 1
            }
            prev = r
        }
        return out
    }
}
