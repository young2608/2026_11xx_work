package com.ascen.yamp.lyrics

import com.ascen.yamp.domain.NetPolicy
import java.io.IOException
import java.net.ConnectException
import java.net.HttpURLConnection
import java.net.NoRouteToHostException
import java.net.SocketTimeoutException
import java.net.URL
import java.net.URLEncoder
import java.net.UnknownHostException

/**
 * 가사 공급자 HTTP (vr0.1.0.011) — 결과에 HTTP 코드 · 크기 · 걸린 시간 · 오류 종류를 담음 (상태 사유 L7 · 진단 L8)
 *  2xx · 404 = 정상 (404 = 없음), 그 밖의 코드 = SERVER, 연결 안 됨 = OFFLINE, 응답 늦음 = TIMEOUT
 */
object Net {
    fun enc(s: String): String = URLEncoder.encode(s, "UTF-8")

    fun http(req: HttpReq, timeoutMs: Int): HttpRes {
        val t0 = System.currentTimeMillis()
        fun ms() = System.currentTimeMillis() - t0
        var c: HttpURLConnection? = null
        return try {
            c = URL(req.url).openConnection() as HttpURLConnection
            c.requestMethod = req.method
            c.connectTimeout = timeoutMs.coerceAtLeast(500)
            c.readTimeout = timeoutMs.coerceAtLeast(500)
            for ((k, v) in req.headers) c.setRequestProperty(k, v)
            if (req.body != null) {
                c.doOutput = true
                c.outputStream.use { it.write(req.body.toByteArray(Charsets.UTF_8)) }
            }
            val code = c.responseCode
            val ins = if (code >= 400) c.errorStream else c.inputStream
            val bytes = ins?.use { it.readCapped(NetPolicy.MAX_RESPONSE_BYTES) } ?: ByteArray(0)
            val ok = code in 200..299 || code == 404
            HttpRes(code, bytes.toString(Charsets.UTF_8), bytes.size, ms(), if (ok) NetErr.NONE else NetErr.SERVER,
                if (ok) null else "HTTP $code")
        } catch (e: UnknownHostException) {
            HttpRes(-1, null, 0, ms(), NetErr.OFFLINE, "연결 안 됨 (${e.javaClass.simpleName})")
        } catch (e: ConnectException) {
            HttpRes(-1, null, 0, ms(), NetErr.OFFLINE, "연결 안 됨 (${e.javaClass.simpleName})")
        } catch (e: NoRouteToHostException) {
            HttpRes(-1, null, 0, ms(), NetErr.OFFLINE, "연결 안 됨 (${e.javaClass.simpleName})")
        } catch (e: SocketTimeoutException) {
            HttpRes(-1, null, 0, ms(), NetErr.TIMEOUT, "시간 초과")
        } catch (e: IOException) {
            HttpRes(-1, null, 0, ms(), NetErr.SERVER, "${e.javaClass.simpleName}: ${e.message ?: ""}")
        } catch (e: RuntimeException) {
            HttpRes(-1, null, 0, ms(), NetErr.SERVER, "${e.javaClass.simpleName}: ${e.message ?: ""}")
        } finally {
            c?.disconnect()
        }
    }
}
