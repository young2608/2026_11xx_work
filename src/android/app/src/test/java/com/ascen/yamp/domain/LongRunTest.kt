package com.ascen.yamp.domain

import com.ascen.yamp.data.PlayRecorder
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** vr0.1.0.007 장시간 운용: 크기 제한 캐시 · 폴링 주기 · 앨범아트 축소 · 캐시 정리 */
class LongRunTest {
    @Test fun lruBoundedAndAccessOrder() {
        val m = LruMap<String, Int>(3)
        m["a"] = 1; m["b"] = 2; m["c"] = 3
        assertEquals(1, m["a"])                 // a 를 최근으로
        m["d"] = 4                              // 가장 오래 안 쓴 b 가 빠짐
        assertEquals(3, m.size())
        assertNull(m["b"])
        assertEquals(listOf("c", "a", "d"), m.keys())
        // 아무리 많이 넣어도 크기 유지 (장시간 운용)
        for (i in 0 until 10_000) m["k$i"] = i
        assertEquals(3, m.size())
        var made = 0
        assertEquals(9_999, m.getOrPut("k9999") { made++; -1 })
        assertEquals(7, m.getOrPut("new") { made++; 7 })
        assertEquals(1, made)
        m.clear()
        assertEquals(0, m.size())
    }

    @Test fun tickIntervals() {
        assertEquals(TickPolicy.UI_MS, TickPolicy.intervalMs(uiVisible = true, overlay = true, abActive = true))
        assertEquals(TickPolicy.AB_MS, TickPolicy.intervalMs(uiVisible = false, overlay = true, abActive = true))
        assertEquals(TickPolicy.OVERLAY_MS, TickPolicy.intervalMs(uiVisible = false, overlay = true, abActive = false))
        assertEquals(TickPolicy.BACKGROUND_MS, TickPolicy.intervalMs(uiVisible = false, overlay = false, abActive = false))
        assertTrue(TickPolicy.shouldSavePos(10_000, 5_000))
        assertFalse(TickPolicy.shouldSavePos(9_999, 5_000))
    }

    @Test fun backgroundTickStillCountsListening() {
        // 백그라운드 주기로 폴링해도 재생 기록(들은 시간)이 빠지지 않아야 함 (MAX_STEP_MS 안쪽)
        assertTrue(TickPolicy.BACKGROUND_MS * 2 < PlayRecorder.MAX_STEP_MS)
        val r = PlayRecorder()
        r.start("k", 200_000, 1000)
        var pos = 0L
        while (pos < 60_000) { r.tick(pos, true); pos += TickPolicy.BACKGROUND_MS }
        r.tick(pos, true)
        val rec = r.finish(false, 1100)!!
        assertEquals(60_000L, rec.listenedMs)
    }

    @Test fun fadePollOnlyNearEdges() {
        val fade = 3000L
        assertEquals(PollPolicy.FAST_MS, PollPolicy.fadeDelayMs(1000, 200_000, fade))       // 시작 페이드 인
        assertEquals(PollPolicy.SLOW_MS, PollPolicy.fadeDelayMs(50_000, 200_000, fade))     // 가운데: 천천히
        assertEquals(PollPolicy.FAST_MS, PollPolicy.fadeDelayMs(198_000, 200_000, fade))    // 끝 페이드 아웃
        // 페이드 아웃 직전: 남은 거리의 절반 (2배속에서도 넘지 않음)
        assertEquals(300L, PollPolicy.fadeDelayMs(200_000 - fade - 600, 200_000, fade))
        assertEquals(PollPolicy.SLOW_MS, PollPolicy.fadeDelayMs(50_000, 0, fade))           // 길이 모름
        // 2배속 시뮬레이션: 깨어날 때마다 위치가 지연×2 만큼 진행 → 페이드 아웃 시작을 FAST_MS×2 이상 넘기지 않음
        var p = fade.toLong()
        val d = 200_000L
        while (p < d - fade) p += PollPolicy.fadeDelayMs(p, d, fade) * 2
        assertTrue(p - (d - fade) <= PollPolicy.FAST_MS * 2)
    }

    @Test fun sleepPoll() {
        assertEquals(PollPolicy.SLEEP_MAX_MS, PollPolicy.sleepDelayMs(10 * 60_000L, 30_000))
        assertEquals(PollPolicy.FAST_MS, PollPolicy.sleepDelayMs(20_000, 30_000))   // 페이드 중
        assertEquals(400L, PollPolicy.sleepDelayMs(400, 0))                          // 끝 시각에 정확히
        assertEquals(PollPolicy.FAST_MS, PollPolicy.trackEndDelayMs(10_000, 30_000))
        assertEquals(PollPolicy.SLOW_MS, PollPolicy.trackEndDelayMs(120_000, 30_000))
    }

    @Test fun coverSampleSize() {
        assertEquals(1, ImageMath.sampleSize(500, 500))
        assertEquals(1, ImageMath.sampleSize(1000, 1000))
        assertEquals(2, ImageMath.sampleSize(1200, 1200))
        assertEquals(4, ImageMath.sampleSize(3000, 3000))       // 3000 → 750
        assertEquals(2, ImageMath.sampleSize(4000, 1500))       // 짧은 변 기준
        assertEquals(1, ImageMath.sampleSize(0, 100))
    }

    @Test fun cachePrune() {
        val e = (1..10).map { CachePrune.Entry("f$it", it.toLong()) }
        assertEquals(emptyList<String>(), CachePrune.victims(e, 10))
        assertEquals(listOf("f1", "f2", "f3"), CachePrune.victims(e.shuffled(), 7))
        // 지우면 안 되는 항목은 건너뛰고 그다음 오래된 것
        assertEquals(listOf("f1", "f3", "f4"), CachePrune.victims(e, 7) { it == "f2" })
        var asked = 0
        CachePrune.victims(e, 9) { asked++; false }
        assertEquals(1, asked)                                   // 필요한 만큼만 확인 (파일 머리 읽기 최소화)
    }

    @Test fun soundSettingsEqualitySkipsRebuild() {
        // SoundEngine.update: 같은 값(clamp 후 equals)이면 처리기를 다시 만들지 않음 → data class 비교가 값 기준이어야 함
        val a = SoundSettings(enabled = true, bands = List(10) { 1.0 }).clamp()
        val b = SoundSettings.fromText(a.toText()).clamp()
        assertEquals(a, b)
        assertFalse(a == a.copy(bands = a.bands.toMutableList().also { it[3] = 2.0 }).clamp())
    }

    // ------------------------------------------------ vr0.1.0.008
    @Test fun maintenanceDailyWhileRunning() {
        assertTrue(MaintPolicy.due(5_000L, 0L))                     // 시작 때 (아직 안 함)
        val t0 = 10_000L
        assertFalse(MaintPolicy.due(t0 + 1, t0))
        assertFalse(MaintPolicy.due(t0 + MaintPolicy.INTERVAL_MS - 1, t0))
        assertTrue(MaintPolicy.due(t0 + MaintPolicy.INTERVAL_MS, t0))
        assertTrue(MaintPolicy.due(t0 + 3 * MaintPolicy.INTERVAL_MS, t0))   // 며칠 지나도 한 번
    }

    @Test fun skipDelaysSane() {
        // 파형 디코딩은 가사 네트워크보다 무거움 → 더 오래 기다림, 둘 다 몇 초 안
        assertTrue(SkipPolicy.WAVE_START_MS in 500L..3000L)
        assertTrue(SkipPolicy.LYRICS_NET_MS in 200L..SkipPolicy.WAVE_START_MS)
        assertTrue(SkipPolicy.PLAYLIST_SAVE_MS in 100L..2000L)
        assertTrue(NetPolicy.MAX_RESPONSE_BYTES >= 512 * 1024)
    }

    @Test fun overlayClampAfterRotation() {
        // 세로(2400) 에서 아래쪽(2000) 에 둔 창 → 가로(1080) 로 돌리면 화면 안으로
        assertEquals(1080 - 150, OverlayMath.clampY(2000, 150, 1080))
        assertEquals(300, OverlayMath.clampY(300, 150, 1080))
        assertEquals(0, OverlayMath.clampY(-40, 150, 1080))
        // 창이 화면보다 큼 / 크기 모름
        assertEquals(0, OverlayMath.clampY(500, 2000, 1080))
        assertEquals(500, OverlayMath.clampY(500, 150, 0))
        assertEquals(0, OverlayMath.clampY(-5, 0, 0))
    }

    @Test fun errorSkipStopsEndlessLoop() {
        // 곡 3개 모두 실패 (전체 반복): 1·2번째 오류는 건너뜀, 3번째(= 모든 곡)는 멈춤
        assertTrue(ErrorSkip.shouldSkip(1, 3))
        assertTrue(ErrorSkip.shouldSkip(2, 3))
        assertFalse(ErrorSkip.shouldSkip(3, 3))
        // 큰 목록: 최대 MAX_IN_ROW 번까지
        assertTrue(ErrorSkip.shouldSkip(ErrorSkip.MAX_IN_ROW - 1, 10_000))
        assertFalse(ErrorSkip.shouldSkip(ErrorSkip.MAX_IN_ROW, 10_000))
        // 한 곡 목록은 건너뛸 곳 없음
        assertFalse(ErrorSkip.shouldSkip(1, 1))
    }
}
