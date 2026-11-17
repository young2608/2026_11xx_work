package com.ascen.yamp.domain

import com.ascen.yamp.lyrics.Json
import java.math.BigDecimal
import java.math.RoundingMode
import java.time.Instant
import java.time.ZoneOffset

/*
 * 상단 바 시세 · KST 시각 (vr0.1.0.012, f23) — 순수 Kotlin (JVM 테스트). PC yamp/domain/ticker.py 와 같은 규칙.
 * 공용 테스트: testdata/upbit_ticker_cases.txt · upbit_ticker_sample.json
 *
 *   업비트 공개 시세 API  GET https://api.upbit.com/v1/ticker?markets=KRW-XRP  (키 없음, 시세 그룹 초당 10회 / IP)
 *   가격 표시  ≥100 → ₩3,512 · 1~100 → ₩12.34 · <1 → ₩0.5123   (0.5 올림 반올림)
 *   변화율     RISE ▲1.23% · FALL ▼0.85% · EVEN 0.00%
 *   KST       기기 시간대와 상관없이 UTC+9
 *   실패 간격  연속 실패 3번부터 30초, 6번부터 60초 (성공하면 기본 주기)
 */

/** 시세 하나 (change_price · change_rate 는 부호 있음, 0.0124 = +1.24%) */
data class Quote(
    val market: String,
    val price: Double,
    val change: String = "EVEN",
    val changePrice: Double = 0.0,
    val changeRate: Double = 0.0,
    val high: Double = 0.0,
    val low: Double = 0.0,
    /** 24시간 거래대금(원) */
    val value24h: Double = 0.0,
    /** 체결 시각 (epoch ms) */
    val tsMs: Long = 0,
) {
    val symbol: String get() = if ("-" in market) market.substringAfter("-") else market
}

object Ticker {
    const val URL = "https://api.upbit.com/v1/ticker"
    const val MIN_INTERVAL_S = 5
    const val DEFAULT_MARKET = "KRW-XRP"
    /** 여러 마켓일 때 번갈아 보이는 간격 (D3) */
    const val ROTATE_MS = 3000L
    /** 가격 바뀔 때 반짝임 (D6) */
    const val FLASH_MS = 600L
    /** 기기 시계 차이 안내 기준 (D7) */
    const val SKEW_WARN_S = 30
    private const val WEEK = "월화수목금토일"
    private val KST = ZoneOffset.ofHours(9)

    /** 가격 클릭 → 업비트 거래 화면 (D5) */
    fun exchangeUrl(market: String): String = "https://upbit.com/exchange?code=CRIX.UPBIT.$market"

    /** 'krw-xrp, KRW-BTC' → [KRW-XRP, KRW-BTC] (빈 값 → 기본) */
    fun parseMarkets(text: String?): List<String> {
        val out = ArrayList<String>()
        for (m0 in (text ?: "").replace(";", ",").split(",")) {
            val m = m0.trim().uppercase()
            if (m.isNotEmpty() && m !in out) out.add(m)
        }
        return out.ifEmpty { listOf(DEFAULT_MARKET) }
    }

    /** 업비트 응답 → 시세 목록. 오류 응답 {"error":{...}} · 형식 오류 → IllegalArgumentException */
    fun parseUpbit(body: String): List<Quote> {
        val data = try { Json.parse(body) } catch (e: Json.Error) { throw IllegalArgumentException(e.message ?: "JSON") }
        Json.obj(data)?.let { throw IllegalArgumentException((it["error"]?.toString() ?: it.toString()).take(120)) }
        val arr = (if (data == null) emptyList() else Json.arr(data)) ?: throw IllegalArgumentException("JSON 배열 아님")
        return arr.map { v ->
            val d = Json.obj(v) ?: throw IllegalArgumentException("JSON 항목 형식")
            val ts = Json.num(d, "trade_timestamp").let { if (it != 0.0) it else Json.num(d, "timestamp") }
            Quote(
                market = Json.str(d, "market"), price = Json.num(d, "trade_price"),
                change = Json.str(d, "change").ifEmpty { "EVEN" }, changePrice = Json.num(d, "signed_change_price"),
                changeRate = Json.num(d, "signed_change_rate"), high = Json.num(d, "high_price"),
                low = Json.num(d, "low_price"), value24h = Json.num(d, "acc_trade_price_24h"), tsMs = ts.toLong(),
            )
        }
    }

    // ------------------------------------------------------------ 숫자 형식 (0.5 올림 = HALF_UP, Python Decimal(repr(x)) 과 같게)
    private fun round(x: Double, places: Int): BigDecimal = BigDecimal(x.toString()).setScale(places, RoundingMode.HALF_UP)

    private fun places(ref: Double): Int {
        val a = Math.abs(ref)
        return if (a >= 100) 0 else if (a >= 1) 2 else 4
    }

    /** 정수 부분에 천 단위 쉼표 ("-1234.50" → "-1,234.50") */
    private fun group(plain: String): String {
        val neg = plain.startsWith("-")
        val s = plain.removePrefix("-")
        val ip = s.substringBefore(".")
        val fp = if ("." in s) "." + s.substringAfter(".") else ""
        val g = StringBuilder()
        ip.forEachIndexed { i, c -> if (i > 0 && (ip.length - i) % 3 == 0) g.append(','); g.append(c) }
        return (if (neg) "-" else "") + g + fp
    }

    /** 가격 숫자 (₩ 없이). ref = 자릿수 기준 가격 (전일 대비 금액은 현재가 기준 자릿수) */
    fun fmtNum(p: Double, ref: Double? = null): String = when (places(ref ?: p)) {
        0 -> group(round(p, 0).toPlainString())
        2 -> group(round(p, 2).toPlainString())
        else -> round(p, 4).toPlainString()
    }

    fun fmtPrice(p: Double): String = "₩" + fmtNum(p)

    fun fmtRate(change: String, rate: Double): String {
        val r = round(Math.abs(rate) * 100, 2).toPlainString()
        return when (change) { "RISE" -> "▲$r%"; "FALL" -> "▼$r%"; else -> "$r%" }
    }

    fun fmtChangePrice(cp: Double, ref: Double): String {
        val s = fmtNum(Math.abs(cp), ref)
        return (if (cp > 0) "+" else if (cp < 0) "-" else "") + s
    }

    /** 거래대금: 1.2조원 / 3,456억원 / 12억원 */
    fun fmtWonBig(v: Double): String = when {
        v >= 1e12 -> round(v / 1e12, 1).toPlainString() + "조원"
        v >= 1e8 -> group(round(v / 1e8, 0).toPlainString()) + "억원"
        else -> group(round(v, 0).toPlainString()) + "원"
    }

    /** KST 글자: seconds = 초까지, date = 'MM-dd(요일) ' 앞에 */
    fun kstLabel(epochMs: Long, seconds: Boolean = true, date: Boolean = true): String {
        val t = Instant.ofEpochMilli(epochMs).atOffset(KST)
        val hm = if (seconds) "%02d:%02d:%02d".format(t.hour, t.minute, t.second) else "%02d:%02d".format(t.hour, t.minute)
        val d = if (date) "%02d-%02d(%c) ".format(t.monthValue, t.dayOfMonth, WEEK[t.dayOfWeek.value - 1]) else ""
        return "$d$hm KST"
    }

    /** 다음 요청까지 초: 연속 실패 3번부터 30초, 6번부터 60초 (기본 주기가 더 길면 기본 주기) */
    fun nextInterval(fails: Int, baseS: Int): Int {
        val base = maxOf(MIN_INTERVAL_S, baseS)
        return when {
            fails >= 6 -> maxOf(base, 60)
            fails >= 3 -> maxOf(base, 30)
            else -> base
        }
    }

    /**
     * 자세히 (길게 누르기 팝업) — PC tooltip() 과 같은 줄 (PC 의 now_ms 인자는 쓰이지 않아 뺌). skewS = 기기 시계 차이(초, + = 기기가 빠름),
     *   |skewS| > 30 이면 마지막 줄 앞에 안내 한 줄 (D7)
     */
    fun detail(q: Quote, lastOkMs: Long, error: String = "", skewS: Int = 0): String {
        val lines = arrayListOf(
            "업비트 ${q.market} · 현재가 ${fmtNum(q.price)}원",
            "전일 대비 ${fmtChangePrice(q.changePrice, q.price)}원 (${fmtRate(q.change, q.changeRate)})",
            "고가 ${fmtNum(q.high)} · 저가 ${fmtNum(q.low)} · 24시간 거래대금 ${fmtWonBig(q.value24h)}",
            if (lastOkMs != 0L) "마지막 갱신 ${kstLabel(lastOkMs, true, false)}" else "아직 갱신 전",
        )
        if (error.isNotEmpty()) lines.add("갱신 실패 ($error)")
        skewText(skewS)?.let { lines.add(it) }
        lines.add("업비트 시세 · 정보 표시용 (지연 가능) · 누르면 업비트 화면")
        return lines.joinToString("\n")
    }

    /** 기기 시계 차이 안내 (30초 넘을 때만, 아니면 null) */
    fun skewText(skewS: Int): String? = when {
        skewS > SKEW_WARN_S -> "기기 시계가 ${skewS}초 빠름 (업비트 서버 시각 기준)"
        skewS < -SKEW_WARN_S -> "기기 시계가 ${-skewS}초 느림 (업비트 서버 시각 기준)"
        else -> null
    }

    /** 서버 응답 시각(Date 헤더)과 기기 시각 차이(초, + = 기기가 빠름). Python round() 와 같게 짝수 반올림 */
    fun clockSkewS(serverMs: Long, localMs: Long): Int =
        if (serverMs == 0L) 0 else Math.rint((localMs - serverMs) / 1000.0).toInt()

    // ------------------------------------------------------------ 마지막 시세 저장 (SharedPreferences 한 줄)
    fun encode(q: Quote): String = listOf(q.market, q.price, q.change, q.changePrice, q.changeRate, q.high, q.low, q.value24h, q.tsMs)
        .joinToString("|")

    fun decode(s: String?): Quote? {
        val p = s?.split("|") ?: return null
        if (p.size != 9 || p[0].isEmpty()) return null
        return runCatching {
            Quote(p[0], p[1].toDouble(), p[2], p[3].toDouble(), p[4].toDouble(), p[5].toDouble(), p[6].toDouble(), p[7].toDouble(), p[8].toLong())
        }.getOrNull()
    }
}
