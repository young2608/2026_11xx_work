package com.ascen.yamp.domain

import com.ascen.yamp.data.PlayRecorder
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class PlayMathTest {
    @Test fun queueIndices() {
        assertEquals(4, PlayMath.insertNextIndex(3, 10))
        assertEquals(10, PlayMath.insertNextIndex(-1, 10))
        assertEquals(6, PlayMath.insertQueueEndIndex(3, 2, 10))
        assertEquals(10, PlayMath.insertQueueEndIndex(3, 20, 10))
        assertEquals(1, PlayMath.queuedAfterMove(3, 4, 2))   // 대기열 첫 곡으로
        assertEquals(0, PlayMath.queuedAfterMove(3, 5, 2))   // 마지막 대기 곡 → 0
        assertEquals(0, PlayMath.queuedAfterMove(3, 0, 2))   // 범위 밖
        assertEquals(2, PlayMath.queuedAfterMove(3, 3, 2))
    }

    @Test fun fades() {
        assertEquals(1f, PlayMath.transitionFade(500, 100_000, 0), 0f)
        assertEquals(0.5f, PlayMath.transitionFade(1000, 100_000, 2000), 1e-6f)
        assertEquals(1f, PlayMath.transitionFade(50_000, 100_000, 2000), 0f)
        assertEquals(0.25f, PlayMath.transitionFade(99_500, 100_000, 2000), 1e-6f)
        assertEquals(0.5f, PlayMath.sleepFade(15_000, 30_000), 1e-6f)
        assertEquals(1f, PlayMath.sleepFade(60_000, 30_000), 0f)
        assertEquals(1f, PlayMath.combineVolume(2.0, 1f, 1f), 0f)          // ExoPlayer 최대 1
        assertEquals(0.25f, PlayMath.combineVolume(0.5, 0.5f, 1f), 1e-6f)
        assertEquals(2f, PlayMath.pitchFactor(12f), 1e-5f)
        assertEquals(0.5f, PlayMath.pitchFactor(-12f), 1e-5f)
    }

    @Test fun abAndCo() {
        assertEquals(1000L, PlayMath.abSeek(5000, 1000, 5000))
        assertNull(PlayMath.abSeek(4999, 1000, 5000))
        assertNull(PlayMath.abSeek(9000, -1, 5000))
        val co = PlayMath.coPairs(listOf("a" to 1L, "b" to 1L, "b" to 1L, "a" to 1L, "c" to 2L, "a" to 2L))
        assertEquals(mapOf(("a" to "b") to 1, ("b" to "a") to 1, ("c" to "a") to 1), co)
    }

    @Test fun recorderRules() {
        val r = PlayRecorder()
        r.start("k1", 200_000, 1000)
        var p = 0L
        while (p <= 110_000) { r.tick(p, true); p += 50 }
        r.tick(180_000, true)            // 탐색(점프) → 무시
        val rec = r.finish(false, 1200)!!
        assertTrue(rec.completed)        // 110초 ≥ 50%
        assertFalse(rec.skipped)
        assertEquals(110_000L, rec.listenedMs)
        val sid = rec.sessionId
        r.start("k2", 300_000, 1300)
        for (i in 0..200) r.tick(i * 50L, true)
        val s = r.finish(false, 1310)!!
        assertTrue(s.skipped && !s.completed)
        assertEquals(sid, s.sessionId)
        r.start("k3", 0, 1310 + 31 * 60)  // 30분 넘게 쉼 → 새 세션
        r.tick(0, true); r.tick(1000, false)
        assertNull(r.finish(false, 4000)) // 일시정지 상태 위치 변화 → 0
        r.start("k4", 0, 5000)
        assertTrue(r.sessionId != sid)
        for (i in 0..800) r.tick(i * 50L, true)   // 40초, 끝까지 재생
        assertTrue(r.finish(true, 5040)!!.completed)
    }
}
