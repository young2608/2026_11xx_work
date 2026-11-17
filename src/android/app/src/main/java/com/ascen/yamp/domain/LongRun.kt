package com.ascen.yamp.domain

/**
 * 장시간 운용 보조 계산 (vr0.1.0.007, 순수 Kotlin — JVM 테스트 대상)
 *   - LruMap      : 크기 제한 캐시 (형식 정보 · 곡 key 등 — 몇 시간/며칠 켜 두어도 메모리가 늘지 않게)
 *   - TickPolicy  : 재생 위치 폴링 주기 (화면 보는 중 / 백그라운드 / 플로팅 가사 / A-B)
 *   - PollPolicy  : 서비스 쪽 페이드 · 슬립 타이머 폴링 주기 (필요한 구간에서만 촘촘히)
 *   - ImageMath   : 앨범아트 축소 비율 (큰 그림을 원본 크기로 디코딩하지 않게)
 *   - CachePrune  : 캐시 폴더 파일 수 제한 (오래된 것부터 지움)
 *   - SkipPolicy  : 곡을 빨리 넘길 때 무거운 작업(파형 디코딩 · 가사 네트워크 · 목록 저장)을 잠깐 미룸 (vr0.1.0.008)
 *   - NetPolicy   : 가사 네트워크 응답 크기 상한 (vr0.1.0.008)
 *   - MaintPolicy : 며칠 켜 둘 때 캐시 · 기록 정리를 하루 한 번 (vr0.1.0.008)
 *   - OverlayMath : 플로팅 가사 창 세로 위치 (화면 회전 뒤에도 화면 안에) (vr0.1.0.008)
 *   - ErrorSkip   : 재생 오류 → 다음 곡 건너뛰기를 연속 몇 번까지만 (vr0.1.0.008, vr0.1.0.010 서비스 쪽으로)
 */

/** 크기 제한 LRU 맵 (접근 순서). 넘치면 가장 오래 안 쓴 항목을 버림. 스레드 안전 (synchronized) */
class LruMap<K, V>(val maxSize: Int) {
    init { require(maxSize > 0) { "maxSize > 0" } }

    private val map = object : LinkedHashMap<K, V>(16, 0.75f, true) {
        override fun removeEldestEntry(eldest: MutableMap.MutableEntry<K, V>?): Boolean = size > maxSize
    }

    @Synchronized operator fun get(k: K): V? = map[k]
    @Synchronized operator fun set(k: K, v: V) { map[k] = v }
    @Synchronized fun remove(k: K): V? = map.remove(k)
    @Synchronized fun clear() = map.clear()
    @Synchronized fun size(): Int = map.size
    /** 오래된 것 → 최근 것 순서 */
    @Synchronized fun keys(): List<K> = map.keys.toList()

    /** 있으면 그 값, 없으면 make() 로 만들어 넣음 */
    @Synchronized fun getOrPut(k: K, make: () -> V): V = map[k] ?: make().also { map[k] = it }
}

/** 재생 위치 폴링 주기 (AppViewModel → PlaybackController) */
object TickPolicy {
    /** 화면을 보는 중: 가사 줄 · 시크바를 부드럽게 */
    const val UI_MS = 50L
    /** 백그라운드 + A-B 반복: B 지점을 많이 넘지 않게 */
    const val AB_MS = 100L
    /** 백그라운드 + 플로팅 가사 표시 중 */
    const val OVERLAY_MS = 200L
    /** 백그라운드(화면 꺼짐 포함): 재생 기록 · 위젯 가사 줄만 — PlayRecorder.MAX_STEP_MS(2초)보다 충분히 짧게 */
    const val BACKGROUND_MS = 500L
    /** 이어 듣기 위치 저장 주기 */
    const val SAVE_POS_MS = 5000L

    fun intervalMs(uiVisible: Boolean, overlay: Boolean, abActive: Boolean): Long = when {
        uiVisible -> UI_MS
        abActive -> AB_MS
        overlay -> OVERLAY_MS
        else -> BACKGROUND_MS
    }

    fun shouldSavePos(nowMs: Long, lastSavedMs: Long): Boolean = nowMs - lastSavedMs >= SAVE_POS_MS
}

/**
 * 서비스 쪽(PlayerHolder) 100ms 폴링을 필요한 구간에서만 (vr0.1.0.007).
 *   페이드 구간(곡 시작 · 끝 fadeMs) 안 = FAST_MS, 밖 = 다음 페이드 구간까지 남은 시간의 절반 (재생 속도 2배까지 안전) — 최대 SLOW_MS
 */
object PollPolicy {
    const val FAST_MS = 100L
    const val SLOW_MS = 500L
    /** 슬립 타이머(시계 기준) 최대 간격 */
    const val SLEEP_MAX_MS = 1000L

    /** 곡 전환 페이드: posMs/durMs = 곡 위치/길이 (재생 시간 기준) */
    fun fadeDelayMs(posMs: Long, durMs: Long, fadeMs: Long): Long {
        if (fadeMs <= 0) return SLOW_MS
        if (posMs < fadeMs) return FAST_MS
        // 길이를 모르거나 짧은 곡은 끝 페이드 없음 (PlayMath.transitionFade 와 같은 조건) → 길이가 알려질 때까지 천천히
        if (durMs <= 0 || durMs <= 2 * fadeMs) return SLOW_MS
        return halfUntil(durMs - fadeMs - posMs, SLOW_MS)
    }

    /** 슬립 타이머 '곡 끝날 때' (재생 시간 기준): remainMs = 곡 끝까지 */
    fun trackEndDelayMs(remainMs: Long, fadeMs: Long): Long = halfUntil(remainMs - maxOf(0L, fadeMs), SLOW_MS)

    /** 슬립 타이머 'N분 뒤' (시계 기준): 정확히 그 시각에 깨어나도록 남은 시간 그대로 (최대 SLEEP_MAX_MS) */
    fun sleepDelayMs(remainMs: Long, fadeMs: Long): Long {
        val d = remainMs - maxOf(0L, fadeMs)
        return if (d <= 0) FAST_MS else d.coerceIn(FAST_MS, SLEEP_MAX_MS)
    }

    private fun halfUntil(distMs: Long, max: Long): Long = if (distMs <= 0) FAST_MS else (distMs / 2).coerceIn(FAST_MS, max)
}

object ImageMath {
    /** 앨범아트 디코딩 목표: 짧은 변 기준 픽셀 (재생 화면 카드 폭 정도) */
    const val COVER_TARGET_PX = 600

    /** BitmapFactory.inSampleSize (2의 거듭제곱): 짧은 변이 target 이상 남는 가장 큰 값 */
    fun sampleSize(w: Int, h: Int, target: Int = COVER_TARGET_PX): Int {
        if (w <= 0 || h <= 0 || target <= 0) return 1
        var s = 1
        while (minOf(w, h) / (s * 2) >= target) s *= 2
        return s
    }
}

object CachePrune {
    data class Entry(val name: String, val mtime: Long)

    /**
     * 파일 수가 maxFiles 를 넘으면 지울 이름 (오래된 mtime 부터, 같으면 이름 순).
     * keep(name) = true 인 항목(예: 직접 편집한 가사)은 지우지 않음 — 필요한 만큼만 차례로 물어봄
     */
    fun victims(entries: List<Entry>, maxFiles: Int, keep: (String) -> Boolean = { false }): List<String> {
        val over = entries.size - maxOf(0, maxFiles)
        if (over <= 0) return emptyList()
        return entries.sortedWith(compareBy<Entry>({ it.mtime }, { it.name })).asSequence()
            .filter { !keep(it.name) }.take(over).map { it.name }.toList()
    }
}

/**
 * 곡 넘김 대기 (vr0.1.0.008): 다음 · 이전을 연달아 누르면 곡마다 디코딩 · 네트워크가 쌓임 →
 * 그 곡에 머문 뒤에만 시작 (캐시에 있으면 바로). 대기 중에 곡이 바뀌면 Job 취소로 시작도 안 함.
 */
object SkipPolicy {
    /** 파형 디코딩 시작 대기 (캐시 없을 때) */
    const val WAVE_START_MS = 1500L
    /** 가사 네트워크 검색 대기 (캐시 · .lrc 에 없을 때) */
    const val LYRICS_NET_MS = 700L
    /** 재생 목록 파일 저장 모음 (편집을 연달아 해도 마지막에 한 번) */
    const val PLAYLIST_SAVE_MS = 500L
}

/** 가사 네트워크 (vr0.1.0.008): 응답 크기 상한 (시간 제한은 config lyrics_timeout_s 1~60초, ConfigTxt 가 범위 제한) */
object NetPolicy {
    /** 가사 응답 최대 바이트 (넘으면 버림 — 잘못된 응답으로 메모리가 튀지 않게) */
    const val MAX_RESPONSE_BYTES = 2 * 1024 * 1024
}

/** 정리 작업 주기 (vr0.1.0.008): 시작 때 + 그 뒤 INTERVAL_MS 마다 (곡이 바뀔 때 확인) */
object MaintPolicy {
    const val INTERVAL_MS = 24 * 3_600_000L

    /** lastMs = 마지막 정리 시각 (elapsedRealtime, 0 = 아직 안 함) */
    fun due(nowMs: Long, lastMs: Long): Boolean = lastMs <= 0L || nowMs - lastMs >= INTERVAL_MS
}

/** 플로팅 가사 창 (vr0.1.0.008) */
object OverlayMath {
    /** 창 위쪽 y (px): 0 ~ (화면 높이 − 창 높이). 크기를 모르면(0) 위쪽만 제한 */
    fun clampY(y: Int, viewH: Int, screenH: Int): Int {
        if (screenH <= 0) return maxOf(0, y)
        return y.coerceIn(0, maxOf(0, screenH - maxOf(0, viewH)))
    }
}

/**
 * 재생 오류 건너뛰기 (vr0.1.0.008): 오류 곡은 다음 곡으로 넘기지만, 연속으로 계속 실패하면 멈춤.
 *   전체 반복(기본값) 에서 SD 카드 제거 · 권한 해제로 모든 곡이 실패하면 오류 → 다음 곡이 끝없이 돌던 것 방지.
 *   errorsInRow = 지금 오류까지 연속 실패 수 (재생이 한 번 시작되면 0 으로)
 */
object ErrorSkip {
    const val MAX_IN_ROW = 10

    fun shouldSkip(errorsInRow: Int, itemCount: Int): Boolean =
        itemCount > 1 && errorsInRow < minOf(itemCount, MAX_IN_ROW)

    /** 오류 하나를 받은 뒤 할 일 (vr0.1.0.010: 재생 서비스 PlaybackTracker 가 사용) — count = 다음 오류 때 넘길 연속 수 */
    enum class Action { NONE, SKIP, STOP }
    data class Decision(val action: Action, val count: Int)

    /** errorsBefore = 이번 오류 전까지 연속 수, hasNext = 다음 곡 있음 (반복 끔 + 마지막 곡이면 false) */
    fun onError(errorsBefore: Int, itemCount: Int, hasNext: Boolean): Decision {
        val n = errorsBefore + 1
        if (!hasNext) return Decision(Action.NONE, n)
        return if (shouldSkip(n, itemCount)) Decision(Action.SKIP, n) else Decision(Action.STOP, 0)
    }
}
