package com.ascen.yamp.core

import android.content.Context
import android.content.Intent
import android.os.Build
import com.ascen.yamp.BuildConfig
import java.io.File

/**
 * 로그 보내기 (vr0.1.0.013) — 설정 → 정보 → [로그 보내기]: 앱이 이상할 때 (종료되지 않아도) 보낼 글 만들기
 *   앱 버전 · 기기 · 최근 비정상 종료 보고서(있으면) · 앱 로그 끝 300줄 · logcat 200줄 → 메일 · 메신저 공유
 */
object LogShare {
    fun build(ctx: Context, logDir: File): String = buildString {
        appendLine("==== ${BuildConfig.APP_NAME} 로그 ====")
        appendLine("시각     : ${CrashReport.kst(System.currentTimeMillis())}")
        appendLine("버전     : ${BuildConfig.VERSION_NAME}__${BuildConfig.BUILD_TIME}")
        appendLine("기기     : ${Build.MANUFACTURER} ${Build.MODEL} · Android ${Build.VERSION.RELEASE} (API ${Build.VERSION.SDK_INT})")
        val crashes = CrashReport.list(CrashCatcher.dir(ctx))
        appendLine("비정상 종료 보고서 : ${crashes.size}개")
        crashes.firstOrNull()?.let { f ->
            appendLine()
            appendLine("---- 가장 최근 비정상 종료 (${f.name}) ----")
            appendLine(runCatching { f.readText(Charsets.UTF_8) }.getOrDefault("(읽지 못함)").take(25_000).trimEnd())
        }
        appendLine()
        appendLine("---- 앱 로그 (최근) ----")
        YLog.flush()
        val cur = YLog.currentFile ?: logDir.listFiles()?.filter { it.isFile }?.maxByOrNull { it.lastModified() }
        appendLine(CrashReport.tail(cur, 300).ifBlank { "(없음)" })
        appendLine()
        appendLine("---- logcat (이 앱, 최근) ----")
        appendLine(CrashCatcher.logcat(200).ifBlank { "(읽지 못함)" })
    }

    /** 글 만들기(logcat 읽기 최대 2초)는 작업 스레드에서, 공유 창은 화면 스레드에서 */
    fun share(ctx: Context, logDir: File) {
        val app = ctx.applicationContext
        Thread {
            val text = runCatching { CrashReport.forShare(build(app, logDir)) }.getOrElse { "로그를 만들지 못했습니다: $it" }
            android.os.Handler(android.os.Looper.getMainLooper()).post { runCatching { open(app, text) } }
        }.apply { name = "yamp-logshare"; isDaemon = true }.start()
    }

    private fun open(ctx: Context, text: String) {
        val send = Intent(Intent.ACTION_SEND).setType("text/plain")
            .putExtra(Intent.EXTRA_SUBJECT, "${BuildConfig.APP_NAME} 로그 ${BuildConfig.VERSION_NAME}")
            .putExtra(Intent.EXTRA_TEXT, text)
        ctx.startActivity(Intent.createChooser(send, "로그 보내기 (메일 · 메신저)").addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
    }
}
