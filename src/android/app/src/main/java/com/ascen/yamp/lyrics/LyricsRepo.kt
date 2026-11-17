package com.ascen.yamp.lyrics

import android.content.Context
import android.net.Uri
import com.ascen.yamp.core.YLog
import com.ascen.yamp.BuildConfig
import com.ascen.yamp.data.Store
import com.ascen.yamp.data.Track
import com.ascen.yamp.domain.LruMap
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeoutOrNull
import java.io.File
import java.security.MessageDigest
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.concurrent.atomic.AtomicBoolean

/**
 * 가사 체인: 캐시 → 같은 폴더 .lrc → (알송 ‖ LRCLIB ‖ NetEase 동시)  (내장 가사는 Android API 없음)
 * vr0.1.0.008: 단계마다 취소 확인 (곡을 넘겨 Job 이 취소되면 남은 네트워크 요청을 보내지 않음), 응답 크기 상한
 * vr0.1.0.010:
 *   A1 "다시 찾기" 는 캐시를 지우지 않음 — research() 로 찾기만 하고 (캐시에 쓰지 않음), apply() 로 바꿈.
 *      직접 편집한 가사([re:yAmp/user])를 바꿀 때는 편집본을 <캐시>.user.bak 으로 보관
 *   A11 CUE 트랙이 앨범 전체 .lrc 를 읽으면 그 트랙 구간만 잘라 씀 (Lyrics.slice)
 *   서비스(PlaybackTracker)도 findOffline 을 씀 (플로팅 · 위젯 가사 줄, 네트워크 없음)
 * vr0.1.0.011 (f18):
 *   L5 공급자 동시 조회 + 전체 제한 lyrics_timeout_s → 후보 점수(L3) 최고 ≥ lyrics_min_score 만 자동 적용 (알송 싱크 ≥ 기준이면 바로)
 *   L6 실패 기억: 검색은 됐지만 맞는 가사 없음 → lyrics_notfound_days 동안 자동 검색 안 함 (네트워크 오류 · 시간 초과는 기억 안 함)
 *   L7 결과 사유 (LyricsState) · L8 가사 진단 (diag) · L10 NetEase (lyrics_netease) · 다른 가사 찾기 후보에 점수
 *   L11 (찾은 가사를 음악 옆 .lrc 로 저장) 은 PC 만 — Android 는 저장소 권한(SAF) 때문에 하지 않음
 */
class LyricsRepo(private val ctx: Context, private val store: Store) {
    private val dir = dirOf(ctx).apply { mkdirs() }
    /** 공급자 실행 (요청 중인 블로킹 HTTP 를 기다리지 않고 결과만 받음 — 곡 넘김 · 시간 초과 시 다음 요청부터 멈춤) */
    private val netScope by lazy {
        CoroutineScope(SupervisorJob() + Dispatchers.IO + kotlinx.coroutines.CoroutineExceptionHandler { _, e -> YLog.e("lyrics", "가사 작업 오류", e) })
    }
    private val nf by lazy { ctx.getSharedPreferences(NF_PREFS, Context.MODE_PRIVATE) }

    fun key(t: Track): String = keyOf(t.uri)

    companion object {
        /** 캐시 파일 첫 줄 표시: [re:yAmp/<출처>] (+ 둘째 줄 [yscore:<점수>] — vr0.1.0.011) */
        private const val TAG_PREFIX = "[re:yAmp/"
        /** 편집본 보관 파일 꼬리 (A1) */
        const val USER_BAK = ".user.bak"
        const val APPLY_OK = 0
        const val APPLY_BACKED_UP = 1
        const val APPLY_FAILED = -1
        private val SOURCE_TAG = Regex("""^\[re:yAmp/(\w+)]""", RegexOption.MULTILINE)
        /** key 계산 캐시 (목록 화면에서 곡마다 MD5 를 다시 계산하지 않게, 크기 제한) */
        private val keyCache = LruMap<String, String>(KEY_CACHE_MAX)
        private const val KEY_CACHE_MAX = 4096
        private const val KEY_LEN = 12
        /** 실패 기억 (L6) SharedPreferences — key = 곡 key, 값 = 확인 시각 (epoch ms) */
        const val NF_PREFS = "yamp_lyrics_nf"
        private const val NF_MAX = 2000

        /** 곡 key = uri MD5 앞 12자리 (가사 캐시 · 라이브러리 DB 공용) */
        fun keyOf(uri: String): String = keyCache.getOrPut(uri) {
            MessageDigest.getInstance("MD5").digest(uri.toByteArray()).joinToString("") { "%02x".format(it) }.take(KEY_LEN)
        }

        fun dirOf(ctx: Context): File = File(ctx.filesDir, "lyrics")

        /** 직접 편집한 가사 파일인지 (캐시 정리에서 제외) */
        fun isUserFile(f: File): Boolean = runCatching {
            f.bufferedReader().use { it.readLine() }?.startsWith(TAG_PREFIX + "user]") == true
        }.getOrDefault(true)
    }

    /** 가사 후보 (A2): 출처 alsong / lrclib / netease, synced = 싱크 있음, score = L3 점수 (-1 = 없음) */
    data class Candidate(val source: String, val title: String, val artist: String, val album: String,
                         val synced: Boolean, val text: String, val score: Int = -1) {
        /** 미리보기 3줄 (타임스탬프 제거) */
        val preview: String by lazy { Lrc.parse(text).blocks.flatMap { it.lines }.filter { it.isNotBlank() }.take(3).joinToString("\n") }
        /** 목록 머리 "[알송 · 싱크 · 92점]" */
        val label: String get() = "[" + LyricsState.sourceLabel(source) + (if (synced) " · 싱크" else "") +
            (if (score >= 0) " · ${score}점" else "") + "]"
    }

    private fun cacheFile(t: Track) = File(dir, key(t) + ".lrc")

    /** 편집본 보관 파일: <캐시>.user.bak (A1) */
    fun backupFile(t: Track) = File(dir, key(t) + ".lrc" + USER_BAK)

    fun clearCache(t: Track) { cacheFile(t).delete() }

    /** 지금 캐시가 직접 편집한 가사인지 (A1) */
    fun isUserEdited(t: Track): Boolean {
        val f = cacheFile(t)
        return f.exists() && isUserFile(f)
    }

    /** 다시 찾기 결과 (캐시에 아직 안 씀): text = 캐시에 쓸 글 (local 은 같은 폴더 .lrc 라 쓰지 않음) */
    data class Found(val lyrics: Lyrics, val text: String, val source: String, val score: Int = -1)

    /** 온라인 찾기 결과: lyrics = 찾은 가사 (없으면 null), state = 사유 (L7) */
    data class Result(val lyrics: Lyrics?, val state: LyricsState)

    // ------------------------------------------------------------ 설정값
    private val timeoutMs: Int get() = store.timeoutMs.coerceIn(1000, 60_000)
    private val minScore: Int get() = store.lyricsMinScore
    private val ua: String get() = "${BuildConfig.APP_NAME}/${BuildConfig.VERSION_NAME}"

    /** 네트워크 공급자를 하나라도 쓰는지 */
    val usesNetwork: Boolean get() = store.useAlsong || store.useLrclib || store.useNetease

    fun query(t: Track, title: String = t.title, artist: String = t.artist): TrackQuery =
        TrackQuery(title.trim(), artist.trim(), t.album.trim(), t.durationMs / 1000.0)

    // ------------------------------------------------------------ 실패 기억 (L6)
    /** 실패 기억 중이면 그 상태 (자동 찾기 건너뜀), 아니면 null */
    fun notFoundState(t: Track): LyricsState? = runCatching {
        val days = store.lyricsNotFoundDays
        if (days <= 0) return@runCatching null
        val at = nf.getLong(key(t), 0L)
        val now = System.currentTimeMillis()
        if (NotFound.active(now, at, days)) LyricsState(Reason.REMEMBERED_NOT_FOUND, days = NotFound.daysAgo(now, at)) else null
    }.getOrNull()

    private fun markNotFound(t: Track) {
        if (store.lyricsNotFoundDays <= 0) return
        runCatching {
            val e = nf.edit()
            // 너무 많아지면 기간 지난 것 정리
            val all = nf.all
            if (all.size > NF_MAX) {
                val now = System.currentTimeMillis()
                for ((k, v) in all) if (v !is Long || !NotFound.active(now, v, store.lyricsNotFoundDays)) e.remove(k)
            }
            e.putLong(key(t), System.currentTimeMillis()).apply()
        }.onFailure { YLog.w("lyrics", "실패 기억 저장 실패", it) }
    }

    fun clearNotFound(t: Track) { runCatching { nf.edit().remove(key(t)).apply() } }

    // ------------------------------------------------------------ 동시 조회 (L5)
    /** 동시 조회 결과 (보고서는 멈춘 시점의 사본) */
    data class Online(val decision: Lookup.Decision, val reports: List<ProvReport>, val timedOut: Boolean, val ms: Long,
                      val variants: List<Pair<String, String>>)

    private fun alsongMd5(t: Track): String? = runCatching {
        // CUE 트랙은 파일 전체(앨범)의 MD5 라 곡 단위 검색이 안 됨 → 제목·가수로만
        if (isMp3(t) && t.clip == null) ctx.contentResolver.openInputStream(Uri.parse(t.mediaUri))?.let { Alsong.audioMd5(it) } else null
    }.getOrNull()

    /**
     * 켜진 공급자를 동시에 실행 → 전체 제한 안에 모인 후보로 결정.
     *   all = false (자동 · 다시 찾기 · 진단): 공급자마다 기준 점수 이상이 나오면 멈춤, 알송 싱크 ≥ 기준이면 다른 공급자 안 기다림
     *   all = true (다른 가사 찾기): 변형 모두 · 시간 제한 2배
     *   variants: null = 태그로 만든 변형 (L2), 아니면 그 목록
     */
    suspend fun lookup(t: Track, q: TrackQuery, all: Boolean, useMd5: Boolean = true,
                       variants: List<Pair<String, String>>? = null): Online = withContext(Dispatchers.IO) {
        val t0 = System.currentTimeMillis()
        val budget = timeoutMs.toLong() * (if (all) 2 else 1)
        val deadline = t0 + budget
        val min = minScore
        val vs = variants ?: Query.variants(q.title, q.artist)
        val enc = Alsong.encOf(store.alsongEnc)
        val md5 = if (useMd5 && store.useAlsong) alsongMd5(t) else null
        val alive = AtomicBoolean(true)
        val ctxJob = currentCoroutineContext()
        val isAlive = { alive.get() && System.currentTimeMillis() < deadline && ctxJob.isActive }
        val http: Transport = { r ->
            val left = deadline - System.currentTimeMillis()
            if (left <= 0) HttpRes(-1, null, 0, 0, NetErr.TIMEOUT, "전체 시간 제한") else Net.http(r, minOf(left, timeoutMs.toLong()).toInt())
        }
        val runs = ArrayList<Pair<ProvReport, () -> Unit>>()
        if (store.useAlsong) ProvReport("alsong").let { rep ->
            rep.note = "encData ${if (enc.isEmpty()) "없음(GetLyric5)" else if (enc == Alsong.ENC_BUILTIN) "내장" else "config"}" +
                (if (md5 != null) " · MD5 ${md5.take(8)}…" else " · MD5 없음")
            runs.add(rep to { Alsong.lookup(q, md5, enc, min, http, rep, isAlive, all, vs) })
        }
        if (store.useLrclib) ProvReport("lrclib").let { rep -> runs.add(rep to { Lrclib.lookup(q, min, http, rep, ua, isAlive, all, vs) }) }
        if (store.useNetease) ProvReport("netease").let { rep -> runs.add(rep to { NetEase.lookup(q, min, http, rep, isAlive, all, vs) }) }
        val done = Channel<ProvReport>(Channel.UNLIMITED)
        val jobs = runs.map { (rep, run) ->
            netScope.launch {
                // vr0.1.0.013: Error(클래스 초기화 실패 등)도 잡음 — 가사 하나 때문에 앱이 종료되지 않게
                try { run() } catch (e: kotlinx.coroutines.CancellationException) { throw e } catch (e: Throwable) {
                    YLog.w("lyrics", "${rep.source} 찾기 오류", e)
                    if (rep.err == NetErr.NONE) { rep.err = NetErr.SERVER; rep.errDetail = "${e.javaClass.simpleName}: ${e.message ?: ""}" }
                } finally { done.trySend(rep) }
            }
        }
        var timedOut = false
        try {
            val r = withTimeoutOrNull(budget) {
                var n = 0
                while (n < jobs.size) {
                    val rep = done.receive()
                    n++
                    val b = rep.best()
                    if (!all && rep.source == "alsong" && b != null && b.score >= min && b.synced) break   // 알송 싱크 ≥ 기준 → 바로
                }
                true
            }
            timedOut = r == null
        } finally {
            alive.set(false)          // 아직 도는 공급자는 다음 요청부터 멈춤
        }
        val snaps = runs.map { it.first.snapshot() }
        val d = Lookup.decide(snaps, min, timedOut)
        val ms = System.currentTimeMillis() - t0
        YLog.i("lyrics", "찾기 '${q.title}' / '${q.artist}' ${ms}ms → ${d.state.line()}" +
            snaps.joinToString("") { " | ${it.source} ${it.cands.size}개 최고 ${it.best()?.score ?: "-"} ${it.err}${if (it.completed) "" else " 중단"}" })
        Online(d, snaps, timedOut, ms, vs)
    }

    /** 온라인 찾기 (자동): 찾으면 캐시 · 실패 기억 지움 / 검색은 됐지만 없음 → 실패 기억 */
    suspend fun findOnline(t: Track): Result = withContext(Dispatchers.IO) {
        if (!usesNetwork) return@withContext Result(null, LyricsState(Reason.NO_PROVIDER))
        if (t.title.isBlank()) return@withContext Result(null, LyricsState(Reason.NOT_FOUND))
        val on = lookup(t, query(t), all = false)
        val b = on.decision.best
        if (b != null) {
            val ly = Lrc.parse(b.lyric, b.source)
            if (!ly.isEmpty()) {
                writeCache(t, b.lyric, b.source, b.score)     // 캐시 저장 실패해도 이번 재생에는 사용
                clearNotFound(t)
                return@withContext Result(ly, on.decision.state)
            }
        }
        if (on.decision.rememberNotFound) markNotFound(t)
        Result(null, if (b != null) LyricsState(Reason.NOT_FOUND) else on.decision.state)
    }

    /**
     * 가사 다시 찾기 (A1 · L6): 캐시 · 실패 기억은 건너뛰고 같은 폴더 .lrc → 동시 조회. 찾아도 캐시에 쓰지 않음 (apply 에서)
     */
    suspend fun research(t: Track): Pair<Found?, LyricsState> = withContext(Dispatchers.IO) {
        if (store.useLocal) localLrc(t)?.let { return@withContext Found(it, "", "local") to LyricsState(Reason.FOUND, "local") }
        if (!usesNetwork) return@withContext null to LyricsState(Reason.NO_PROVIDER)
        currentCoroutineContext().ensureActive()
        val on = lookup(t, query(t), all = false)
        val b = on.decision.best
        if (b != null) {
            val ly = Lrc.parse(b.lyric, b.source)
            if (!ly.isEmpty()) return@withContext Found(ly, b.lyric, b.source, b.score) to on.decision.state
        }
        if (on.decision.rememberNotFound) markNotFound(t)
        null to on.decision.state
    }

    /**
     * 다시 찾기 결과로 바꿈 (A1): 직접 편집한 가사였으면 편집본을 .user.bak 으로 먼저 보관 (보관 못 하면 바꾸지 않음).
     *   local(.lrc) = 캐시를 지워 다음부터 .lrc 를 읽게, 네트워크 = 캐시에 씀.
     *   반환: APPLY_OK · APPLY_BACKED_UP (편집본 보관 후 바꿈) · APPLY_FAILED (보관 실패 — 그대로)
     */
    fun apply(t: Track, f: Found): Int {
        val cache = cacheFile(t)
        var backedUp = false
        if (cache.exists() && isUserFile(cache)) {
            backedUp = runCatching { cache.copyTo(backupFile(t), overwrite = true); true }
                .onFailure { YLog.w("lyrics", "편집 가사 보관 실패 ${t.display}", it) }.getOrDefault(false)
            if (!backedUp) return APPLY_FAILED          // 보관 못 하면 편집본을 지우지 않음
        }
        if (f.source == "local") cache.delete() else writeCache(t, f.text, f.source, f.score)
        clearNotFound(t)
        return if (backedUp) APPLY_BACKED_UP else APPLY_OK
    }

    /** 캐시 파일만 (네트워크 없음) — 곡을 넘기자마자 보여 줄 수 있는지 */
    private fun cached(t: Track): Lyrics? {
        val f = cacheFile(t)
        if (!f.exists()) return null
        val txt = runCatching { f.readText() }.getOrNull() ?: return null
        val src = SOURCE_TAG.find(txt)?.groupValues?.get(1) ?: "cache"
        return Lrc.parse(txt, src).takeIf { !it.isEmpty() }
    }

    /** 캐시에 적힌 점수 (없으면 -1) — 출처 칩 (L7) */
    fun cachedScore(ly: Lyrics?): Int = ly?.meta?.get("yscore")?.toIntOrNull() ?: -1

    /** 기기 안에서만 찾기: 캐시 → 같은 폴더 .lrc (네트워크 없음, 빠름) */
    suspend fun findOffline(t: Track, useCache: Boolean = true): Lyrics? = withContext(Dispatchers.IO) {
        (if (useCache) cached(t) else null) ?: if (store.useLocal) localLrc(t) else null
    }

    /** 사용자 편집 가사 저장 (A1) → 캐시 (source "user") */
    fun saveUserLyrics(t: Track, lrc: String): Lyrics? = saveAs(t, lrc, "user", -1)

    /** 후보 선택 (A2) → 캐시 */
    fun saveCandidate(t: Track, c: Candidate): Lyrics? = saveAs(t, c.text, c.source, c.score)

    private fun saveAs(t: Track, txt: String, src: String, score: Int): Lyrics? {
        val ly = Lrc.parse(txt, src)
        if (ly.isEmpty()) return null
        if (!writeCache(t, txt, src, score)) return null
        clearNotFound(t)
        return if (score >= 0) ly.copy(meta = ly.meta + ("yscore" to score.toString())) else ly
    }

    /** 캐시 파일 = 첫 줄 출처 표시 (+ 점수) + 가사 */
    private fun writeCache(t: Track, txt: String, src: String, score: Int = -1): Boolean = runCatching {
        cacheFile(t).writeText("$TAG_PREFIX$src]\n" + (if (score >= 0) "[yscore:$score]\n" else "") + txt.trim() + "\n")
    }.onFailure { YLog.w("lyrics", "가사 저장 실패 ${t.display}", it) }.isSuccess

    /** 다른 가사 찾기 (A2 · L10): 알송 + LRCLIB (+ NetEase) 후보 모두, 점수 높은 순 — 네트워크, IO 스레드에서 */
    suspend fun searchCandidates(t: Track?, title: String, artist: String): List<Candidate> = withContext(Dispatchers.IO) {
        if (title.isBlank() || !usesNetwork) return@withContext emptyList()
        val q = TrackQuery(title.trim(), artist.trim(), t?.album.orEmpty(), (t?.durationMs ?: 0) / 1000.0)
        // 지금 곡 그대로 검색하면 MD5 도 (알송 파일 일치) — 제목·가수를 고쳤으면 검색만
        val same = t != null && q.title == t.title.trim() && q.artist == t.artist.trim()
        val on = if (t != null) lookup(t, q, all = true, useMd5 = same) else return@withContext emptyList()
        on.decision.all.map { c -> Candidate(c.source, c.title, c.artist, c.album, c.synced, c.lyric, c.score) }
    }

    /** 가사 진단 (L8): 지금 곡으로 전체 찾기 (실패 기억 무시, 캐시 · 기록에 쓰지 않음) → 보고서 글 + 저장 파일 */
    suspend fun diag(t: Track, logDir: File): Pair<String, File?> = withContext(Dispatchers.IO) {
        val q = query(t)
        val on = lookup(t, q, all = false)
        val now = Date()
        val enc = store.alsongEnc.trim()
        val extra = listOf(
            "파일" to (t.path.ifEmpty { t.mediaUri }),
            "형식" to (runCatching { ctx.contentResolver.getType(Uri.parse(t.mediaUri)) }.getOrNull() ?: "?") + (if (isMp3(t)) " (mp3 → MD5 조회)" else ""),
            "CUE" to (if (t.clip != null) "예 (MD5 안 씀)" else "아니오"),
            "캐시" to (if (cacheFile(t).exists()) "있음 (${cacheFile(t).name})" else "없음"),
            "실패 기억" to (notFoundState(t)?.line() ?: "없음"),
            "공급자" to listOfNotNull("알송".takeIf { store.useAlsong }, "LRCLIB".takeIf { store.useLrclib },
                "NetEase".takeIf { store.useNetease }).joinToString(", ").ifEmpty { "없음" },
            "alsong_enc_data" to (if (enc.isEmpty()) "(빈 값 → 내장 토큰)" else if (enc.equals("off", true)) "off" else "config 값 ${enc.take(8)}…"),
        )
        val head = "${BuildConfig.APP_NAME} ${BuildConfig.VERSION_NAME} · " +
            SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.US).format(now)
        val text = Diag.report(head, q, extra, on.variants, on.reports, on.decision, minScore, timeoutMs / 1000, on.ms, on.timedOut)
        val f = runCatching {
            logDir.mkdirs()
            File(logDir, "lyrics_diag_" + SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US).format(now) + ".txt").also { it.writeText(text) }
        }.onFailure { YLog.w("lyrics", "가사 진단 저장 실패", it) }.getOrNull()
        YLog.i("lyrics", "가사 진단 ${t.display} → ${on.decision.state.line()} (${f?.name ?: "저장 못 함"})")
        text to f
    }

    private fun isMp3(t: Track): Boolean =
        t.path.endsWith(".mp3", true) || runCatching { ctx.contentResolver.getType(Uri.parse(t.mediaUri))?.contains("mpeg") == true }.getOrDefault(false)

    /**
     * 같은 폴더 .lrc — 저장소 권한 정책상 읽을 수 있을 때만 (Android 11+ 는 대부분 불가)
     * CUE 트랙 (A11): 앨범 파일의 .lrc 는 앨범 전체 시각 → 이 트랙 구간만 잘라 씀
     */
    private fun localLrc(t: Track): Lyrics? {
        if (t.path.isEmpty()) return null
        val f = File(t.path.substringBeforeLast('.') + ".lrc")
        if (!f.canRead()) return null
        val raw = runCatching { f.readBytes() }.getOrNull() ?: return null
        val txt = runCatching { Charsets.UTF_8.newDecoder().decode(java.nio.ByteBuffer.wrap(raw)).toString() }
            .getOrElse { runCatching { String(raw, charset("MS949")) }.getOrElse { String(raw, Charsets.ISO_8859_1) } }
        val ly = Lrc.parse(txt, "local")
        val c = t.clip
        val part = if (c != null) ly.slice(c.startMs, c.endMs) else ly
        return part.takeIf { !it.isEmpty() }
    }
}
