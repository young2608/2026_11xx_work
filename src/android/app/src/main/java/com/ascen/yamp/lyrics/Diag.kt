package com.ascen.yamp.lyrics

/**
 * 가사 진단 보고서 (vr0.1.0.011 f18 L8) — 순수 Kotlin. 지금 곡으로 전체 찾기를 돌린 기록을 글로.
 *  태그 → 검색어 변형 → 공급자별 [요청 · HTTP 코드 · 크기 · 항목 태그 · 후보 수 · 시간] · 최고점 → 최종 선택
 *  (설정 → 가사 → 가사 진단: 대화상자 · 공유 · files/log/lyrics_diag_*.txt 저장)
 */
object Diag {
    fun report(
        header: String, q: TrackQuery, extra: List<Pair<String, String>>, variants: List<Pair<String, String>>,
        reports: List<ProvReport>, decision: Lookup.Decision, minScore: Int, timeoutS: Int, totalMs: Long, timedOut: Boolean,
    ): String = buildString {
        appendLine("== 가사 진단 ==")
        appendLine(header)
        appendLine()
        appendLine("[태그]")
        appendLine("제목: ${q.title}")
        appendLine("가수: ${q.artist}")
        appendLine("앨범: ${q.album}")
        appendLine("길이: ${"%.1f".format(q.durS)}초")
        for ((k, v) in extra) appendLine("$k: $v")
        appendLine()
        appendLine("[검색어 변형] (최대 ${Query.MAX_VARIANTS}개)")
        variants.forEachIndexed { i, (t, a) -> appendLine("${i + 1}. $t / $a") }
        appendLine()
        appendLine("[설정] 자동 적용 ${minScore}점 이상 · 전체 제한 ${timeoutS}초")
        for (r in reports) {
            appendLine()
            appendLine("[${LyricsState.sourceLabel(r.source)}] ${r.ms}ms · 후보 ${r.cands.size}개 · 최고 ${r.best()?.score ?: "-"}점" +
                (if (r.err != NetErr.NONE) " · 오류 ${r.err} (${r.errDetail})" else "") +
                (if (!r.completed) " · 끝까지 못 감" else "") + (if (r.note.isNotEmpty()) " · ${r.note}" else ""))
            for (s in r.steps) {
                appendLine("  - ${s.method} \"${s.query}\" → HTTP ${if (s.code < 0) "-" else s.code} · ${s.bytes}B · 항목 ${s.items}개 · ${s.ms}ms" +
                    (if (s.tags.isNotEmpty()) " · 태그 ${s.tags}" else "") + (if (s.error != null) " · ${s.error}" else ""))
            }
            for (c in r.cands.sortedByDescending { it.score }.take(5)) {
                appendLine("  * ${c.score}점 [${c.via}${if (c.synced) " · 싱크" else ""}] ${c.artist} - ${c.title}" +
                    (if (c.album.isNotEmpty()) " (${c.album})" else "") + (if (c.durS > 0) " ${"%.0f".format(c.durS)}초" else ""))
            }
        }
        appendLine()
        appendLine("[최종] 걸린 시간 ${totalMs}ms${if (timedOut) " (시간 제한 넘음)" else ""}")
        val b = decision.best
        if (b != null) appendLine("선택: ${LyricsState.sourceLabel(b.source)} ${b.score}점 — ${b.artist} - ${b.title} [${b.via}]")
        appendLine("상태: ${decision.state.line()}")
        if (decision.rememberNotFound) appendLine("(자동 찾기라면 실패 기억 대상)")
    }
}
