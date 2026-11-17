package com.ascen.yamp.app

import android.os.SystemClock
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import com.ascen.yamp.BuildConfig
import com.ascen.yamp.core.YLog
import com.ascen.yamp.data.Upbit
import com.ascen.yamp.domain.Quote
import com.ascen.yamp.domain.Ticker
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/**
 * 상단 바 시세 · KST 시계 (vr0.1.0.012, f23).
 *   - 앱 화면이 보일 때만 (MainActivity onStart → setUiVisible(true)) 10초 코루틴, 안 보이면 멈춤 (요청 0, D4)
 *   - 다시 보이면 즉시 1회 갱신. 실패가 이어지면 Ticker.nextInterval 로 30 · 60초
 *   - 마지막 시세는 SharedPreferences 에 → 다음 실행 때 첫 갱신 전까지 흐리게 (stale)
 *   - 여러 마켓 (D3) = 한 번에 요청, 화면이 3초마다 번갈아 보여 줌
 */
class TickerController(private val core: AppCore) {
    private val store get() = core.store

    /** 시세 표시 (config topbar_ticker, 0 = 숨김 · 요청 안 함) */
    var tickerOn by mutableStateOf(store.topbarTicker); private set
    var clockOn by mutableStateOf(store.topbarClock); private set
    var clockSeconds by mutableStateOf(store.topbarClockSeconds); private set
    /** 마켓 목록 (쉼표 여러 개) */
    var markets by mutableStateOf(Ticker.parseMarkets(store.tickerMarket)); private set
    /** 마켓 → 마지막 시세 */
    var quotes by mutableStateOf(loadSaved()); private set
    /** 마지막 성공 시각 (epoch ms, 0 = 이번 실행에서 아직) */
    var lastOkMs by mutableLongStateOf(0L); private set
    /** 마지막 실패 사유 ("" = 마지막 요청 성공) */
    var error by mutableStateOf(""); private set
    /** 기기 시계 차이(초, + = 기기가 빠름 — Date 헤더 기준) */
    var skewS by mutableIntStateOf(0); private set
    /** 가격이 바뀐 횟수 (반짝임 트리거) · 바뀐 마켓 · 오름 여부 */
    var flashSeq by mutableIntStateOf(0); private set
    var flashMarket by mutableStateOf(""); private set
    var flashUp by mutableStateOf(true); private set
    /** 화면이 보이는 중 (시계 · 번갈아 표시도 이때만) */
    var visible by mutableStateOf(false); private set

    /** 흐리게: 이번 실행에서 아직 성공 못 함 또는 마지막 요청 실패 */
    val stale: Boolean get() = lastOkMs == 0L || error.isNotEmpty()

    private var job: Job? = null
    private var fails = 0
    private var lastSaved = ""
    private val userAgent = "yMp3Player/${BuildConfig.VERSION_NAME}"

    private fun loadSaved(): Map<String, Quote> {
        val raw = runCatching { store.lastQuotes }.getOrDefault("")
        lastSaved = raw
        return raw.lines().mapNotNull(Ticker::decode).associateBy { it.market }
    }

    fun setUiVisible(v: Boolean) {
        visible = v
        restart()
    }

    private fun restart() {
        job?.cancel()
        job = null
        if (!visible || !tickerOn) return
        job = core.scope.launch {
            while (isActive) {
                refresh()
                delay(Ticker.nextInterval(fails, store.tickerIntervalS) * 1000L)
            }
        }
    }

    private suspend fun refresh() {
        val want = markets
        val t0 = SystemClock.elapsedRealtime()
        val r = withContext(Dispatchers.IO) { Upbit.fetch(want, userAgent) }
        if (want != markets) return               // 그사이 마켓이 바뀜 → 이 결과는 버림 (새 루프가 다시 요청)
        val now = System.currentTimeMillis()
        if (r.serverMs != 0L) skewS = Ticker.clockSkewS(r.serverMs, now)
        if (!r.ok) {
            fails++
            if (error != r.error || fails == 3 || fails == 6) YLog.w("ticker", "갱신 실패 ${fails}번째: ${r.error}")
            error = r.error ?: "?"
            return
        }
        val old = quotes
        val next = LinkedHashMap(old)
        for (q in r.quotes) {
            val prev = old[q.market]
            // 이번 실행 첫 성공(흐린 저장값)에서는 반짝이지 않음
            if (prev != null && lastOkMs != 0L && prev.price != q.price) {
                flashMarket = q.market; flashUp = q.price > prev.price; flashSeq++
            }
            next[q.market] = q
        }
        quotes = next
        if (fails > 0 || error.isNotEmpty()) YLog.i("ticker", "갱신 복구 (${SystemClock.elapsedRealtime() - t0}ms)")
        fails = 0
        error = ""
        lastOkMs = now
        save()
    }

    /** 바뀌었을 때만 저장 (10초마다 같은 값을 쓰지 않음) */
    private fun save() {
        val s = markets.mapNotNull { quotes[it] }.joinToString("\n") { Ticker.encode(it) }
        if (s == lastSaved) return
        lastSaved = s
        store.lastQuotes = s
    }

    // ------------------------------------------------------------ 설정 (설정 → 화면)
    fun changeTicker(on: Boolean) { tickerOn = on; store.topbarTicker = on; restart() }
    fun changeClock(on: Boolean) { clockOn = on; store.topbarClock = on }
    fun changeClockSeconds(on: Boolean) { clockSeconds = on; store.topbarClockSeconds = on }

    /** 마켓 바꾸기 ("krw-btc, KRW-XRP") → 정규화해 저장, 바로 다시 요청 */
    fun changeMarket(text: String) {
        val m = Ticker.parseMarkets(text)
        if (m == markets) return
        markets = m
        store.tickerMarket = m.joinToString(",")
        fails = 0
        error = ""
        lastOkMs = 0L                             // 새 마켓 = 첫 성공 전까지 흐리게
        YLog.i("ticker", "마켓: ${m.joinToString(",")}")
        restart()
    }

    /** 길게 누르기 팝업 글 (시세 + 갱신 상태 + 시계 차이) */
    fun detail(market: String): String {
        val q = quotes[market] ?: return "업비트 $market · 아직 시세 없음" +
            (if (error.isNotEmpty()) "\n갱신 실패 ($error)" else "") + "\n업비트 시세 · 정보 표시용 (지연 가능)"
        return Ticker.detail(q, lastOkMs, error, skewS)
    }

    fun stop() { job?.cancel(); job = null }
}
