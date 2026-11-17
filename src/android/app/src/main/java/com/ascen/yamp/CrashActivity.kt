package com.ascen.yamp

import android.app.Activity
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.os.Bundle
import android.view.Gravity
import android.view.ViewGroup
import android.widget.Button
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Toast
import com.ascen.yamp.core.CrashCatcher
import com.ascen.yamp.core.CrashReport
import com.ascen.yamp.ui.ThemeTable
import java.io.File
import kotlin.system.exitProcess

/**
 * 비정상 종료 화면 (vr0.1.0.013) — 별도 프로세스(:crash)에서 뜸 (앱 본체가 다시 죽어도 이 화면은 남음).
 * Compose · 앱 설정 · DB 를 쓰지 않는 단순한 화면: 보고서 보기 + [로그 보내기] [복사] [다시 시작] [안전 모드로 시작] [닫기]
 * 색 = 기본 테마(써니) 표 (ThemeTable)
 */
class CrashActivity : Activity() {
    private var report = ""
    private var file: File? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        file = intent.getStringExtra(CrashCatcher.EXTRA_FILE)?.let(::File)?.takeIf { it.isFile }
            ?: CrashReport.list(CrashCatcher.dir(this)).firstOrNull()
        report = runCatching { file?.readText(Charsets.UTF_8) }.getOrNull() ?: "(보고서 파일을 읽지 못했습니다)"
        val safe = intent.getBooleanExtra(CrashCatcher.EXTRA_SAFE, false)
        CrashCatcher.clearPending(this)
        setContentView(build(safe))
    }

    private fun col(token: String) = ThemeTable.argb(ThemeTable.of(ThemeTable.DEFAULT).hex(token))
    private fun dp(v: Int) = (v * resources.displayMetrics.density).toInt()

    private fun build(safe: Boolean): LinearLayout {
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setBackgroundColor(col("bg"))
            setPadding(dp(16), dp(28), dp(16), dp(16))
        }
        root.addView(TextView(this).apply {
            text = "yMp3Player 가 예기치 않게 종료되었습니다"
            setTextColor(col("text"))
            textSize = 19f
            setTypeface(typeface, Typeface.BOLD)
        })
        val summary = report.lineSequence().firstOrNull { it.startsWith("요약") }?.substringAfter(":")?.trim() ?: ""
        root.addView(TextView(this).apply {
            text = buildString {
                append("아래 [로그 보내기] 로 보고서를 보내 주시면 원인을 찾아 고치겠습니다.\n")
                append("(보고서에는 앱 버전 · 기기 이름 · 오류 내용 · 앱 로그만 들어 있습니다)")
                if (summary.isNotEmpty()) append("\n\n오류: $summary")
                if (safe) append("\n\n시작하자마자 연속으로 종료되었습니다 — [안전 모드로 시작] 을 권합니다.")
            }
            setTextColor(col("dim"))
            textSize = 13f
            setPadding(0, dp(8), 0, dp(10))
        })
        val log = TextView(this).apply {
            text = report
            setTextColor(col("text"))
            textSize = 11f
            typeface = Typeface.MONOSPACE
            setTextIsSelectable(true)
            setPadding(dp(10), dp(10), dp(10), dp(10))
        }
        root.addView(ScrollView(this).apply {
            background = GradientDrawable().apply { setColor(col("surface2")); cornerRadius = dp(10).toFloat(); setStroke(dp(1), col("line")) }
            addView(log)
        }, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f))
        val row1 = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; setPadding(0, dp(12), 0, 0) }
        row1.addView(button("로그 보내기", primary = true) { share() }, weight())
        row1.addView(button("복사") { copy() }, weight())
        root.addView(row1)
        val row2 = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; setPadding(0, dp(8), 0, 0) }
        row2.addView(button("다시 시작") { restart(false) }, weight())
        row2.addView(button("안전 모드로 시작", primary = safe) { restart(true) }, weight())
        row2.addView(button("닫기") { finishAndRemoveTask(); exitProcess(0) }, weight())
        root.addView(row2)
        return root
    }

    private fun weight() = LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f).apply { marginEnd = dp(6) }

    private fun button(label: String, primary: Boolean = false, onClick: () -> Unit) = Button(this).apply {
        text = label
        setAllCaps(false)
        gravity = Gravity.CENTER
        setTextColor(col(if (primary) "on_fill" else "text"))
        background = GradientDrawable().apply {
            setColor(col(if (primary) "fill1" else "surface2"))
            cornerRadius = dp(22).toFloat()
            setStroke(dp(1), col(if (primary) "fill2" else "line"))
        }
        setOnClickListener { onClick() }
    }

    private fun share() {
        val name = file?.name ?: "crash.txt"
        val send = Intent(Intent.ACTION_SEND).apply {
            setType("text/plain")
            putExtra(Intent.EXTRA_SUBJECT, "yMp3Player 오류 보고서 $name")
            putExtra(Intent.EXTRA_TEXT, CrashReport.forShare(report))
        }
        runCatching { startActivity(Intent.createChooser(send, "로그 보내기 (메일 · 메신저)")) }
            .onFailure { Toast.makeText(this, "보낼 앱이 없습니다 — [복사] 후 붙여 넣으세요", Toast.LENGTH_LONG).show() }
    }

    private fun copy() {
        val cm = getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
        cm.setPrimaryClip(ClipData.newPlainText("yMp3Player crash", CrashReport.forShare(report)))
        Toast.makeText(this, "복사했습니다", Toast.LENGTH_SHORT).show()
    }

    private fun restart(safeMode: Boolean) {
        if (safeMode) CrashCatcher.requestSafeMode(this)
        startActivity(Intent(this, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK))
        finish()
        exitProcess(0)
    }
}
