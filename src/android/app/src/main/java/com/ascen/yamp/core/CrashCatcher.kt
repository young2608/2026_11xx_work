package com.ascen.yamp.core

import android.app.Application
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.Process
import android.os.SystemClock
import com.ascen.yamp.BuildConfig
import com.ascen.yamp.data.Store
import java.io.File
import java.util.concurrent.TimeUnit
import kotlin.system.exitProcess

/**
 * 비정상 종료 잡기 (vr0.1.0.013) — Application.onCreate 에서 가장 먼저 설치 (화면 · 서비스 · 위젯 어디서 죽어도).
 *   1) files/crash/crash_*.txt 에 보고서 저장 (CrashReport.build — 예외 · 최근 앱 로그 · logcat)
 *   2) 시작 직후 연속 종료 수 기록 (안전 모드 권함)
 *   3) 별도 프로세스(:crash) 의 CrashActivity 를 띄움 → [로그 보내기] [복사] [다시 시작] [안전 모드로 시작]
 *   4) 이 프로세스 종료 (시스템 '앱이 중지됨' 창 대신 우리 화면)
 *  보고서는 기기 안에만 저장 — 보내기는 사용자가 직접 고른 앱(메일 · 메신저)으로만
 */
object CrashCatcher {
    const val EXTRA_FILE = "crash_file"
    const val EXTRA_SAFE = "suggest_safe"
    private const val P_STREAK = "crash_streak"
    private const val P_SAFE = "safe_mode_once"
    private const val P_PENDING = "crash_pending"
    @Volatile private var startMs = 0L
    @Volatile private var installed = false
    @Volatile private var handling = false

    fun dir(ctx: Context): File = File(ctx.filesDir, CrashReport.DIR).apply { mkdirs() }

    fun install(app: Application) {
        startMs = SystemClock.elapsedRealtime()
        if (installed || isCrashProcess(app)) return
        installed = true
        val prev = Thread.getDefaultUncaughtExceptionHandler()
        Thread.setDefaultUncaughtExceptionHandler { t, e ->
            if (handling) { prev?.uncaughtException(t, e); return@setDefaultUncaughtExceptionHandler }
            handling = true
            val ok = runCatching { handle(app, t, e) }.isSuccess
            if (!ok) { prev?.uncaughtException(t, e); return@setDefaultUncaughtExceptionHandler }
            Process.killProcess(Process.myPid())
            exitProcess(10)
        }
    }

    private fun handle(app: Application, t: Thread, e: Throwable) {
        val now = System.currentTimeMillis()
        val since = SystemClock.elapsedRealtime() - startMs
        val sp = app.getSharedPreferences(Store.PREFS, Context.MODE_PRIVATE)
        val streak = CrashReport.nextStreak(sp.getInt(P_STREAK, 0), since)
        val env = CrashReport.Env(
            BuildConfig.APP_NAME, BuildConfig.VERSION_NAME, BuildConfig.BUILD_TIME,
            "${Build.MANUFACTURER} ${Build.MODEL} (${Build.DEVICE})",
            "${Build.VERSION.RELEASE} (API ${Build.VERSION.SDK_INT})", processName(app),
        )
        val text = CrashReport.build(env, t.name, e, now, since, appLogTail(app), logcat())
        val d = dir(app)
        val f = File(d, CrashReport.fileName(now))
        f.writeText(text, Charsets.UTF_8)
        CrashReport.trim(d)
        // commit: 프로세스가 곧 끝나므로 바로 디스크에
        sp.edit().putInt(P_STREAK, streak).putString(P_PENDING, f.name).commit()
        runCatching { YLog.e("crash", CrashReport.summary(e)) }
        runCatching { YLog.flush() }
        val i = Intent().setClassName(app, "com.ascen.yamp.CrashActivity")
            .putExtra(EXTRA_FILE, f.absolutePath)
            .putExtra(EXTRA_SAFE, CrashReport.suggestSafeMode(streak))
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK)
        app.startActivity(i)
    }

    /** 앱이 정상으로 15초 넘게 살아 있으면 연속 종료 수를 0 으로 (MainActivity 가 부름) */
    fun markHealthy(ctx: Context) {
        val sp = ctx.getSharedPreferences(Store.PREFS, Context.MODE_PRIVATE)
        if (sp.getInt(P_STREAK, 0) != 0) sp.edit().putInt(P_STREAK, 0).apply()
    }

    /** 다음 시작을 안전 모드로 (CrashActivity 버튼) */
    fun requestSafeMode(ctx: Context) {
        ctx.getSharedPreferences(Store.PREFS, Context.MODE_PRIVATE).edit().putBoolean(P_SAFE, true).commit()
    }

    /** 안전 모드 요청이 있었는지 (한 번 읽으면 지움) */
    fun consumeSafeMode(ctx: Context): Boolean {
        val sp = ctx.getSharedPreferences(Store.PREFS, Context.MODE_PRIVATE)
        val on = sp.getBoolean(P_SAFE, false)
        if (on) sp.edit().putBoolean(P_SAFE, false).apply()
        return on
    }

    /** 아직 사용자가 보지 않은 보고서 (서비스 쪽에서 죽어 화면이 못 떴을 때 다음 시작에 알림) */
    fun pending(ctx: Context): File? {
        val n = ctx.getSharedPreferences(Store.PREFS, Context.MODE_PRIVATE).getString(P_PENDING, null) ?: return null
        return File(dir(ctx), n).takeIf { it.isFile }
    }

    fun clearPending(ctx: Context) {
        ctx.getSharedPreferences(Store.PREFS, Context.MODE_PRIVATE).edit().remove(P_PENDING).apply()
    }

    private fun appLogTail(app: Application): String = runCatching {
        val logDir = File(app.getExternalFilesDir(null) ?: app.filesDir, "log")
        val f = YLog.currentFile ?: logDir.listFiles()?.filter { it.isFile }?.maxByOrNull { it.lastModified() }
        CrashReport.tail(f, 120)
    }.getOrDefault("")

    /** 이 앱 프로세스의 logcat 최근 400줄 (자기 로그는 권한 없이 읽힘) — 최대 2초 */
    fun logcat(lines: Int = 400): String = runCatching {
        val p = ProcessBuilder("logcat", "-d", "-v", "time", "-t", lines.toString(), "--pid=${Process.myPid()}")
            .redirectErrorStream(true).start()
        val out = StringBuilder()
        val th = Thread { runCatching { out.append(p.inputStream.bufferedReader().readText()) } }
        th.start()
        th.join(2000)
        if (!p.waitFor(100, TimeUnit.MILLISECONDS)) p.destroy()
        out.toString().takeLast(80_000)
    }.getOrDefault("")

    private fun processName(ctx: Context): String = runCatching {
        if (Build.VERSION.SDK_INT >= 28) Application.getProcessName() else ctx.packageName
    }.getOrDefault(ctx.packageName)

    fun isCrashProcess(ctx: Context): Boolean = processName(ctx).endsWith(":crash")
}
