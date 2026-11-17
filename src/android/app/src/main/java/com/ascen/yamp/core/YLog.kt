package com.ascen.yamp.core

import java.io.File
import java.time.LocalDateTime
import java.time.format.DateTimeFormatter
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit

/**
 * 앱 전역 로그: 백그라운드 단일 스레드에서 파일 기록 (UI 스레드 IO 없음) + logcat
 * vr0.1.0.007: init 을 여러 번 불러도 (화면을 닫았다 다시 열어 ViewModel 이 새로 생김) 1초 flush 작업 · 크래시 핸들러가 쌓이지 않음
 * vr0.1.0.008: 1초마다 도는 flush 작업 대신, 기록한 줄이 있을 때만 FLUSH_S 뒤 한 번 flush 예약
 *              (로그가 없는 동안 — 며칠 켜 둔 백그라운드 — 스레드가 1초마다 깨어나지 않음)
 */
object YLog {
    private const val TAG = "yMp3Player"
    private val exec = Executors.newSingleThreadScheduledExecutor { r -> Thread(r, "ylog").apply { isDaemon = true } }
    private val TS = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss.SSS")
    @Volatile private var ring: RingLog? = null
    @Volatile private var level = 1      // 0 DEBUG 1 INFO 2 WARNING 3 ERROR
    val currentFile: File? get() = ring?.currentFile
    /** flush 예약됨 (exec 스레드에서만 읽고 씀) */
    private var flushPending = false
    private var crashHooked = false
    private const val FLUSH_S = 1L

    @Synchronized
    fun init(dir: File, cfg: ConfigTxt) {
        level = listOf("DEBUG", "INFO", "WARNING", "ERROR").indexOf(cfg.str("log_level")).coerceAtLeast(0)
        exec.execute {
            runCatching { ring?.close() }
            ring = runCatching { RingLog(dir, cfg.int("log_max_size_kb") * 1024L, cfg.int("log_max_files")) }.getOrNull()
        }
        if (crashHooked) return
        crashHooked = true
        val prev = Thread.getDefaultUncaughtExceptionHandler()
        Thread.setDefaultUncaughtExceptionHandler { t, e ->
            ring?.write("${LocalDateTime.now().format(TS)} [CRIT ] crash: ${android.util.Log.getStackTraceString(e)}", true)
            prev?.uncaughtException(t, e)
        }
    }

    private fun log(lv: Int, tag: String, msg: String, tr: Throwable? = null) {
        when (lv) {
            0 -> android.util.Log.d(TAG, "$tag: $msg")
            1 -> android.util.Log.i(TAG, "$tag: $msg")
            2 -> android.util.Log.w(TAG, "$tag: $msg", tr)
            else -> android.util.Log.e(TAG, "$tag: $msg", tr)
        }
        if (lv < level) return
        val name = arrayOf("DEBUG", "INFO ", "WARN ", "ERROR")[lv]
        val line = "${LocalDateTime.now().format(TS)} [$name] $tag: $msg" +
            (tr?.let { "\n" + android.util.Log.getStackTraceString(it) } ?: "")
        exec.execute {
            runCatching { ring?.write(line, lv >= 2) }
            scheduleFlush()
        }
    }

    /** exec 스레드에서: 아직 예약이 없으면 FLUSH_S 뒤 flush 한 번 */
    private fun scheduleFlush() {
        if (flushPending) return
        flushPending = true
        exec.schedule({ flushPending = false; runCatching { ring?.flush() } }, FLUSH_S, TimeUnit.SECONDS)
    }

    fun d(tag: String, msg: String) = log(0, tag, msg)
    fun i(tag: String, msg: String) = log(1, tag, msg)
    fun w(tag: String, msg: String, tr: Throwable? = null) = log(2, tag, msg, tr)
    fun e(tag: String, msg: String, tr: Throwable? = null) = log(3, tag, msg, tr)
    fun flush() = exec.execute { ring?.flush() }
}
