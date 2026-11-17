package com.ascen.yamp.lyrics

/**
 * 가사 온라인 찾기 공용 형 (vr0.1.0.011, f18 L5·L6·L7) — 순수 Kotlin (JVM 테스트 대상)
 *  - TrackQuery : 찾을 곡 (태그)
 *  - LyricCand  : 공급자 후보 (점수 포함)
 *  - ProvReport : 공급자 하나의 진행 기록 (요청 단계 · 오류 · 후보) — 상태 사유 · 가사 진단에 씀
 *  - Lookup.decide : 후보 모으기 → 최고점 · 상태 사유 · 실패 기억 여부
 *  - LyricsState : 가사 패널 사유 줄 · 출처 칩 (L7)
 *  - NotFound   : 실패 기억 기간 계산 (L6)
 */
data class TrackQuery(val title: String, val artist: String, val album: String = "", val durS: Double = 0.0)

data class LyricCand(
    val source: String, val title: String, val artist: String, val album: String, val lyric: String,
    val durS: Double = 0.0, val score: Int = 0,
    /** 찾은 방법 (진단용): MD5 · Resemble2 · ByID2 · get · search · q … */
    val via: String = "",
) {
    val synced: Boolean get() = Score.stamps(lyric).isNotEmpty()
}

/** 네트워크 오류 종류: OFFLINE = 연결 안 됨, TIMEOUT = 응답 늦음, SERVER = HTTP 오류 · 응답 이상 */
enum class NetErr { NONE, OFFLINE, TIMEOUT, SERVER }

data class HttpReq(val url: String, val method: String = "GET", val body: String? = null,
                   val headers: Map<String, String> = emptyMap(), val label: String = "")

data class HttpRes(val code: Int, val body: String?, val bytes: Int, val ms: Long, val err: NetErr = NetErr.NONE, val error: String? = null) {
    val ok: Boolean get() = err == NetErr.NONE && code in 200..299 && body != null
}

/** 요청 보내기 (실제: Net.http · 테스트: 고정 응답) */
typealias Transport = (HttpReq) -> HttpRes

/** 공급자 하나의 진행 기록 */
class ProvReport(val source: String) {
    data class Step(val method: String, val query: String, val code: Int, val bytes: Int, val tags: String,
                    val items: Int, val ms: Long, val error: String?)

    // 공급자 스레드가 쓰고 찾기 쪽이 읽음 → 고치기 · 읽기는 동기화, 결정은 snapshot() 사본으로
    val steps = ArrayList<Step>()
    val cands = ArrayList<LyricCand>()
    @Volatile var err: NetErr = NetErr.NONE
    @Volatile var errDetail: String = ""
    /** 끝까지 진행 (중간에 오류 · 시간 초과로 멈추지 않음) */
    @Volatile var completed = false
    @Volatile var ms = 0L
    @Volatile var note = ""

    /** 지금까지의 사본 (끝나지 않았으면 note 에 "중단") */
    @Synchronized fun snapshot(): ProvReport = ProvReport(source).also {
        it.steps.addAll(steps); it.cands.addAll(cands); it.err = err; it.errDetail = errDetail
        it.completed = completed; it.ms = ms; it.note = note
    }

    /** 요청 결과 기록 + 오류 반영 (오류 종류가 처음 생길 때만) */
    @Synchronized fun step(method: String, query: String, r: HttpRes, tags: String = "", items: Int = 0) {
        steps.add(Step(method, query, r.code, r.bytes, tags, items, r.ms, r.error))
        if (r.err != NetErr.NONE && err == NetErr.NONE) { err = r.err; errDetail = "$method: ${r.error ?: r.code}" }
    }

    @Synchronized fun add(c: LyricCand) {
        if (c.lyric.isBlank()) return
        if (cands.any { it.title == c.title && it.artist == c.artist && it.lyric == c.lyric }) return
        cands.add(c)
    }

    @Synchronized fun best(): LyricCand? = cands.maxByOrNull { it.score }
}

/** 가사 상태 사유 (L7) */
enum class Reason { NONE, SEARCHING, FOUND, OFFLINE, TIMEOUT, SERVER_ERROR, NOT_FOUND, LOW_SCORE, REMEMBERED_NOT_FOUND, NO_PROVIDER }

data class LyricsState(val reason: Reason, val source: String = "", val score: Int = -1, val days: Int = 0) {
    /** 가사 없음 계열 — [다른 가사 찾기] [붙여넣기] 버튼을 보임 */
    val notFound: Boolean
        get() = reason in setOf(Reason.NONE, Reason.OFFLINE, Reason.TIMEOUT, Reason.SERVER_ERROR, Reason.NOT_FOUND,
            Reason.LOW_SCORE, Reason.REMEMBERED_NOT_FOUND, Reason.NO_PROVIDER)

    /** 가사 패널 사유 줄 (짧은 한국어) */
    fun line(): String = when (reason) {
        Reason.NONE -> "가사 없음"
        Reason.SEARCHING -> "가사 찾는 중…"
        Reason.FOUND -> "가사: ${sourceLabel(source)}"
        Reason.OFFLINE -> "인터넷 연결이 없어 가사를 못 찾음"
        Reason.TIMEOUT -> "가사 서버 응답이 늦어 못 찾음 — 다시 찾기"
        Reason.SERVER_ERROR -> "${sourceLabel(source)} 서버 응답 오류 — 가사 진단으로 확인"
        Reason.NOT_FOUND -> "맞는 가사를 못 찾음"
        Reason.LOW_SCORE -> "맞는 가사를 못 찾음 (최고 ${score}점 — 다른 가사 찾기에서 고르기)"
        Reason.REMEMBERED_NOT_FOUND -> if (days <= 0) "가사 없음 (오늘 확인) · 다시 찾기" else "가사 없음 (${days}일 전 확인) · 다시 찾기"
        Reason.NO_PROVIDER -> "가사 없음 (인터넷 가사 공급자 꺼짐)"
    }

    /** 출처 칩 "알송 · 92점" (찾음 + 점수 있을 때) */
    fun chip(): String? = if (reason == Reason.FOUND && source.isNotEmpty())
        sourceLabel(source) + if (score >= 0) " · ${score}점" else "" else null

    companion object {
        fun sourceLabel(src: String): String = when (src) {
            "alsong" -> "알송"
            "lrclib" -> "LRCLIB"
            "netease" -> "NetEase"
            "local" -> "로컬 .lrc"
            "user" -> "직접 편집"
            "cache" -> "캐시"
            else -> src
        }
    }
}

object Lookup {
    data class Decision(val best: LyricCand?, val state: LyricsState, val rememberNotFound: Boolean, val all: List<LyricCand>)

    /** 모든 후보 (점수 높은 순, 같으면 싱크 있는 것 → 공급자 순서) — PC service.py 와 같은 순서 */
    fun ranked(reports: List<ProvReport>): List<LyricCand> =
        reports.flatMap { it.cands }.withIndex()
            .sortedWith(compareBy({ -it.value.score }, { if (it.value.synced) 0 else 1 }, { it.index })).map { it.value }

    /**
     * 최종 선택: 최고점 ≥ minScore → 찾음.
     * 아니면: 모든 공급자가 오류 없이 끝남 → 점수 미달 / 0건 (실패 기억 O)
     *        하나라도 오류 · 시간 초과 → 인터넷 / 시간 초과 / 서버 오류 (실패 기억 X — 다음에 다시 시도)
     */
    fun decide(reports: List<ProvReport>, minScore: Int, timedOut: Boolean = false): Decision {
        val all = ranked(reports)
        if (reports.isEmpty()) return Decision(null, LyricsState(Reason.NO_PROVIDER), false, all)
        val best = all.firstOrNull()
        if (best != null && best.score >= minScore) return Decision(best, LyricsState(Reason.FOUND, best.source, best.score), false, all)
        val failing = reports.filter { it.err != NetErr.NONE || !it.completed }
        if (failing.isEmpty() && !timedOut) {
            val st = if (best != null) LyricsState(Reason.LOW_SCORE, best.source, best.score) else LyricsState(Reason.NOT_FOUND)
            return Decision(null, st, true, all)
        }
        val st = when {
            failing.size == reports.size && failing.all { it.err == NetErr.OFFLINE } -> LyricsState(Reason.OFFLINE)
            timedOut || failing.any { it.err == NetErr.TIMEOUT || (it.err == NetErr.NONE && !it.completed) } -> LyricsState(Reason.TIMEOUT)
            else -> LyricsState(Reason.SERVER_ERROR, failing.first { it.err != NetErr.NONE }.source)
        }
        return Decision(null, st, false, all)
    }
}

/** 실패 기억 (L6): 곡별 확인 시각 → days 일 동안 자동 검색 안 함 */
object NotFound {
    const val DAY_MS = 86_400_000L

    fun active(nowMs: Long, atMs: Long, days: Int): Boolean =
        days > 0 && atMs > 0 && nowMs >= atMs - 60_000 && nowMs - atMs < days * DAY_MS

    fun daysAgo(nowMs: Long, atMs: Long): Int = ((nowMs - atMs).coerceAtLeast(0) / DAY_MS).toInt()
}
