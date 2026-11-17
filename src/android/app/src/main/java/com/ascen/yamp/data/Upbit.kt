package com.ascen.yamp.data

import com.ascen.yamp.domain.Quote
import com.ascen.yamp.domain.Ticker
import java.io.IOException
import java.net.ConnectException
import java.net.HttpURLConnection
import java.net.SocketTimeoutException
import java.net.URL
import java.net.URLEncoder
import java.net.UnknownHostException

/**
 * 업비트 공개 시세 조회 (vr0.1.0.012, f23) — 키 필요 없음. 순수 계산은 domain/Ticker.kt
 *   GET https://api.upbit.com/v1/ticker?markets=KRW-XRP,KRW-BTC  (제한 시간 3초)
 *   결과 = 시세 목록 + 서버 시각 (Date 헤더, 기기 시계 차이 안내 D7) 또는 오류 한 줄
 */
object Upbit {
    const val TIMEOUT_MS = 3000
    /** 응답 최대 크기 (마켓 몇 개 = 수 KB) */
    private const val MAX_BYTES = 256 * 1024

    class Res(val quotes: List<Quote>, val serverMs: Long, val error: String?) {
        val ok: Boolean get() = error == null
    }

    fun fetch(markets: List<String>, userAgent: String, timeoutMs: Int = TIMEOUT_MS): Res {
        var c: HttpURLConnection? = null
        return try {
            val q = URLEncoder.encode(markets.joinToString(","), "UTF-8")
            c = URL("${Ticker.URL}?markets=$q").openConnection() as HttpURLConnection
            c.connectTimeout = timeoutMs
            c.readTimeout = timeoutMs
            c.setRequestProperty("User-Agent", userAgent)
            c.setRequestProperty("Accept", "application/json")
            val code = c.responseCode
            val serverMs = c.getHeaderFieldDate("Date", 0L)
            val ins = if (code >= 400) c.errorStream else c.inputStream
            val bytes = ins?.use { s ->
                val out = java.io.ByteArrayOutputStream()
                val buf = ByteArray(8192)
                while (out.size() < MAX_BYTES) { val n = s.read(buf); if (n < 0) break; out.write(buf, 0, n) }
                out.toByteArray()
            } ?: ByteArray(0)
            val body = bytes.toString(Charsets.UTF_8)
            when {
                code == 429 -> Res(emptyList(), serverMs, "요청 너무 많음 (429)")
                // 잘못된 마켓 = 404 {"error":{"name":"404","message":"Code not found"}} → 메시지를 함께
                code !in 200..299 -> Res(emptyList(), serverMs, "HTTP $code" +
                    (runCatching { Ticker.parseUpbit(body); "" }.exceptionOrNull()?.message?.let { " $it".take(60) } ?: ""))
                else -> {
                    val list = Ticker.parseUpbit(body)
                    if (list.isEmpty()) Res(emptyList(), serverMs, "시세 없음 (마켓 코드 확인)") else Res(list, serverMs, null)
                }
            }
        } catch (e: UnknownHostException) {
            Res(emptyList(), 0, "인터넷 없음")
        } catch (e: ConnectException) {
            Res(emptyList(), 0, "연결 안 됨")
        } catch (e: SocketTimeoutException) {
            Res(emptyList(), 0, "시간 초과")
        } catch (e: IllegalArgumentException) {
            Res(emptyList(), 0, "응답 형식 오류: ${e.message ?: ""}".take(80))
        } catch (e: IOException) {
            Res(emptyList(), 0, "${e.javaClass.simpleName}: ${e.message ?: ""}".take(80))
        } catch (e: RuntimeException) {
            Res(emptyList(), 0, "${e.javaClass.simpleName}: ${e.message ?: ""}".take(80))
        } finally {
            c?.disconnect()
        }
    }
}
