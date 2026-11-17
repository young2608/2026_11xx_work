package com.ascen.yamp.domain

/**
 * 음성 파일 기능 (vr0.1.0.010, R3 · D6 — 순수 Kotlin, JVM 테스트 대상)
 *   - ResumeBook : V2 파일별 이어 듣기 — 30분 넘는 파일(오디오북 · 강의 · 녹음)은 멈춘 위치를 파일마다 기억 (최근 200개)
 *   - V1 무음 건너뛰기는 ExoPlayer.setSkipSilenceEnabled (PlayerHolder), V4 "음성" EQ 프리셋은 Dsp.PRESETS
 */

/**
 * 파일별 이어 듣기 위치 (LRU, 가장 오래 안 들은 것부터 버림). 키 = 곡 uri (CUE 트랙은 구간 표시 포함 → 트랙마다 따로)
 *   저장 형식 (SharedPreferences 한 칸): 줄 = uri \t 위치ms  (오래된 것 → 최근 것)
 */
class ResumeBook(val maxEntries: Int = MAX_ENTRIES) {
    companion object {
        /** 이보다 긴 파일만 기억 (30분) */
        const val LONG_MS = 30 * 60_000L
        /** 끝에서 이만큼 안이면 다 들은 것 → 처음부터 (기록 지움) */
        const val END_GUARD_MS = 10_000L
        /** 이보다 앞이면 기억할 것이 없음 (처음부터와 같음) */
        const val MIN_POS_MS = 5_000L
        const val MAX_ENTRIES = 200

        fun isLong(durMs: Long): Boolean = durMs > LONG_MS
    }

    private val map = object : LinkedHashMap<String, Long>(16, 0.75f, true) {
        override fun removeEldestEntry(eldest: MutableMap.MutableEntry<String, Long>?): Boolean = size > maxEntries
    }

    @Synchronized fun size(): Int = map.size
    @Synchronized fun get(uri: String): Long? = map[uri]
    @Synchronized fun remove(uri: String): Boolean = map.remove(uri) != null

    /**
     * 위치 기록. 반환: 저장 내용이 바뀜.
     *   긴 파일이 아니면 무시, 끝 END_GUARD_MS 안 · 앞 MIN_POS_MS 안이면 지움
     */
    @Synchronized fun put(uri: String, posMs: Long, durMs: Long): Boolean {
        if (uri.isEmpty() || !isLong(durMs)) return false
        if (posMs < MIN_POS_MS || posMs >= durMs - END_GUARD_MS) return map.remove(uri) != null
        val old = map[uri]
        map[uri] = posMs
        return old != posMs
    }

    /** 다시 재생할 때 이동할 위치 (없음 · 짧은 파일 · 끝 근처면 null) */
    @Synchronized fun resumeAt(uri: String, durMs: Long): Long? {
        val p = map[uri] ?: return null
        if (!isLong(durMs)) return null
        if (p < MIN_POS_MS || p >= durMs - END_GUARD_MS) { map.remove(uri); return null }
        return p
    }

    @Synchronized fun toText(): String = map.entries.joinToString("\n") { (u, p) -> u.replace('\t', ' ').replace('\n', ' ') + "\t" + p }

    @Synchronized fun load(text: String) {
        map.clear()
        for (l in text.lines()) {
            val i = l.lastIndexOf('\t')
            if (i <= 0) continue
            val p = l.substring(i + 1).trim().toLongOrNull() ?: continue
            map[l.substring(0, i)] = p
        }
    }
}
