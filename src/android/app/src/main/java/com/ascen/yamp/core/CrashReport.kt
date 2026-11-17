package com.ascen.yamp.core

import java.io.File
import java.io.PrintWriter
import java.io.StringWriter
import java.time.Instant
import java.time.ZoneOffset
import java.time.format.DateTimeFormatter

/**
 * 비정상 종료 보고서 (vr0.1.0.013) — 순수 Kotlin (안드로이드 API 없음, JVM 테스트 대상).
 *   files/crash/crash_YYYYMMDD_HHMMSS.txt : 앱 버전 · 기기 · 시각(KST) · 스레드 · 예외 전체(원인 포함) · 최근 앱 로그 · logcat
 *   시작 직후(START_WINDOW_MS 안) 연속 종료 횟수 → 2번이면 '안전 모드로 시작' 권함
 */
object CrashReport {
    const val DIR = "crash"
    const val PREFIX = "crash_"
    const val KEEP = 10                     // 최근 10개만
    const val START_WINDOW_MS = 15_000L     // 시작 후 15초 안의 종료 = '시작하자마자 종료'
    const val SHARE_MAX_CHARS = 60_000      // 공유(메신저·메일 본문) 최대 글자
    private val KST = ZoneOffset.ofHours(9)
    private val NAME_TS = DateTimeFormatter.ofPattern("yyyyMMdd_HHmmss")
    private val TEXT_TS = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss")

    data class Env(
        val app: String, val version: String, val buildTime: String,
        val device: String, val android: String, val process: String,
    )

    fun fileName(epochMs: Long): String =
        PREFIX + Instant.ofEpochMilli(epochMs).atOffset(KST).format(NAME_TS) + ".txt"

    fun kst(epochMs: Long): String = Instant.ofEpochMilli(epochMs).atOffset(KST).format(TEXT_TS) + " KST"

    fun stackOf(e: Throwable): String {
        val sw = StringWriter()
        e.printStackTrace(PrintWriter(sw))
        return sw.toString()
    }

    /** 예외 한 줄 요약: 가장 깊은 원인의 이름 · 메시지 + 앱 코드(com.ascen.yamp) 첫 위치 */
    fun summary(e: Throwable): String {
        var root = e
        var guard = 0
        while (root.cause != null && root.cause !== root && guard++ < 20) root = root.cause!!
        val at = (root.stackTrace.firstOrNull { it.className.startsWith("com.ascen.yamp") } ?: root.stackTrace.firstOrNull())
            ?.let { " @ ${it.className.substringAfterLast('.')}.${it.methodName}:${it.lineNumber}" } ?: ""
        return "${root.javaClass.simpleName}: ${root.message ?: ""}".trim().removeSuffix(":") + at
    }

    fun build(
        env: Env, threadName: String, e: Throwable, nowMs: Long, sinceStartMs: Long,
        appLogTail: String, logcat: String,
    ): String = buildString {
        appendLine("==== ${env.app} 비정상 종료 보고서 ====")
        appendLine("시각     : ${kst(nowMs)}  (시작 후 ${sinceStartMs / 1000.0}초)")
        appendLine("버전     : ${env.version}__${env.buildTime}")
        appendLine("기기     : ${env.device}")
        appendLine("Android  : ${env.android}")
        appendLine("프로세스 : ${env.process} · 스레드 ${threadName}")
        appendLine("요약     : ${summary(e)}")
        appendLine()
        appendLine("---- 예외 (전체) ----")
        appendLine(stackOf(e).trimEnd())
        appendLine()
        appendLine("---- 최근 앱 로그 ----")
        appendLine(appLogTail.ifBlank { "(없음)" }.trimEnd())
        appendLine()
        appendLine("---- logcat (이 앱) ----")
        appendLine(logcat.ifBlank { "(읽지 못함)" }.trimEnd())
    }

    /** 공유용 글: 너무 길면 예외 부분은 남기고 뒤(로그)를 자름 */
    fun forShare(report: String, max: Int = SHARE_MAX_CHARS): String =
        if (report.length <= max) report else report.take(max - 40) + "\n…(이하 생략, 전체는 파일 참고)"

    fun list(dir: File): List<File> =
        (dir.listFiles { f -> f.isFile && f.name.startsWith(PREFIX) && f.name.endsWith(".txt") } ?: emptyArray())
            .sortedByDescending { it.name }

    /** 오래된 보고서 정리 (최근 KEEP 개) */
    fun trim(dir: File, keep: Int = KEEP) {
        list(dir).drop(keep).forEach { runCatching { it.delete() } }
    }

    /** 파일 끝 n 줄 */
    fun tail(f: File?, lines: Int): String = runCatching {
        if (f == null || !f.isFile) return ""
        val all = f.readLines(Charsets.UTF_8)
        all.takeLast(lines).joinToString("\n")
    }.getOrDefault("")

    /**
     * 시작 직후 연속 종료 수: 이번 종료가 시작 후 START_WINDOW_MS 안이면 +1, 아니면 0 으로.
     * 2 이상이면 다음 시작 때 안전 모드를 권함
     */
    fun nextStreak(prevStreak: Int, sinceStartMs: Long): Int =
        if (sinceStartMs in 0..START_WINDOW_MS) prevStreak + 1 else 0

    fun suggestSafeMode(streak: Int): Boolean = streak >= 2
}
