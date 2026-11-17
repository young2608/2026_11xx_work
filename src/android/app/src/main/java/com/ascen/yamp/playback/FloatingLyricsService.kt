package com.ascen.yamp.playback

import android.annotation.SuppressLint
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.res.Configuration
import android.graphics.PixelFormat
import android.graphics.drawable.GradientDrawable
import android.os.IBinder
import android.provider.Settings
import android.util.TypedValue
import android.view.Gravity
import android.view.MotionEvent
import android.view.View
import android.view.WindowManager
import android.widget.LinearLayout
import android.widget.TextView
import com.ascen.yamp.core.YLog
import com.ascen.yamp.domain.OverlayMath
import com.ascen.yamp.ui.ThemePrefs
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.launch

/**
 * 플로팅 가사 (A4): 다른 앱 위에 현재 줄 + 다음 줄 (TYPE_APPLICATION_OVERLAY, SYSTEM_ALERT_WINDOW 권한 필요).
 *   - 드래그로 이동, 길게 누르기 = 잠금 (FLAG_NOT_TOUCHABLE → 터치가 아래 앱으로 통과)
 *   - 잠금 해제: 앱 설정/가사 탭의 "플로팅 가사 잠금" 또는 서비스 다시 시작 (ACTION_UNLOCK)
 *   - 데이터: LyricsBus (vr0.1.0.010: 재생 서비스 PlaybackTracker 가 갱신 — 앱 화면을 닫아도 계속)
 *   - vr0.1.0.008: 화면 회전 · 크기 변경 → 창이 화면 밖으로 나가지 않게 세로 위치 맞춤,
 *                  종료 시 창 · 레이아웃 · WindowManager 참조를 모두 놓음 (서비스를 다시 켜도 옛 창이 남지 않음)
 *   - vr0.1.0.011 (f19): 테마 색 — 바탕 = tooltip_bg (반투명), 현재 줄 = accent_text, 다음 줄 = text (반투명).
 *                  테마 · 기기 어두운 모드가 바뀌면 다시 칠함 (ACTION_RESTYLE · onConfigurationChanged)
 */
class FloatingLyricsService : Service() {
    private var wm: WindowManager? = null
    private var root: LinearLayout? = null
    private var lp: WindowManager.LayoutParams? = null
    private var tvCur: TextView? = null
    private var tvNext: TextView? = null
    private var bgShape: GradientDrawable? = null
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main)
    private var locked = false

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        running = true
        if (!Settings.canDrawOverlays(this)) {
            YLog.w("float", "오버레이 권한 없음 — 플로팅 가사 시작 안 함")
            stopSelf()
            return
        }
        runCatching { show() }.onFailure {
            YLog.e("float", "플로팅 가사 창 생성 실패", it)
            stopSelf()
            return
        }
        scope.launch {
            LyricsBus.lines.collectLatest { (cur, next) ->
                tvCur?.text = cur.ifEmpty { "♪" }
                tvNext?.text = next
            }
        }
        YLog.i("float", "플로팅 가사 시작")
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_RESTYLE -> applyStyle()
            ACTION_LOCK -> applyLock(true)
            ACTION_UNLOCK -> applyLock(false)
        }
        return START_NOT_STICKY
    }

    private fun dp(v: Float): Int = TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, v, resources.displayMetrics).toInt()

    @SuppressLint("ClickableViewAccessibility")
    private fun show() {
        val w = getSystemService(Context.WINDOW_SERVICE) as WindowManager
        wm = w
        val shape = GradientDrawable().apply { cornerRadius = dp(10f).toFloat() }
        val box = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(12f), dp(6f), dp(12f), dp(6f))
            background = shape
        }
        val cur = TextView(this).apply {
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 17f)
            gravity = Gravity.CENTER
            maxLines = 2
            text = "♪"
        }
        val next = TextView(this).apply {
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 13f)
            gravity = Gravity.CENTER
            maxLines = 1
        }
        box.addView(cur, LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT))
        box.addView(next, LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT))
        val params = WindowManager.LayoutParams(
            WindowManager.LayoutParams.MATCH_PARENT,
            WindowManager.LayoutParams.WRAP_CONTENT,
            WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS,
            PixelFormat.TRANSLUCENT,
        ).apply {
            gravity = Gravity.TOP or Gravity.START
            x = 0
            y = dp(120f)
        }
        // 드래그 이동 (세로 위치), 길게 누르기 = 잠금
        var downY = 0f
        var startY = 0
        var moved = false
        box.setOnTouchListener { _, e ->
            when (e.actionMasked) {
                MotionEvent.ACTION_DOWN -> { downY = e.rawY; startY = params.y; moved = false; false }
                MotionEvent.ACTION_MOVE -> {
                    val dy = (e.rawY - downY).toInt()
                    if (Math.abs(dy) > dp(4f)) moved = true
                    if (moved) {
                        box.cancelLongPress()       // 드래그 중에는 길게 누르기(잠금) 취소
                        params.y = OverlayMath.clampY(startY + dy, box.height, resources.displayMetrics.heightPixels)
                        runCatching { w.updateViewLayout(box, params) }
                    }
                    moved
                }
                else -> moved
            }
        }
        box.isLongClickable = true
        box.setOnLongClickListener {
            if (!moved) applyLock(true)
            true
        }
        w.addView(box, params)
        root = box
        lp = params
        tvCur = cur
        tvNext = next
        bgShape = shape
        applyStyle()
    }

    /** 테마 색 칠하기 (지금 테마 = ThemePrefs — 어두운 모드 따라가기 반영) */
    private fun applyStyle() {
        val th = runCatching { ThemePrefs.current(this) }.getOrNull() ?: return
        bgShape?.setColor(th.argb("tooltip_bg", if (th.dark) BG_ALPHA_DARK else BG_ALPHA_LIGHT))
        tvCur?.setTextColor(th.argb("accent_text"))
        tvNext?.setTextColor(th.argb("text", NEXT_ALPHA))
    }

    private fun applyLock(on: Boolean) {
        val v: View = root ?: return
        val params = lp ?: return
        locked = on
        params.flags = if (on) params.flags or WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE
        else params.flags and WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE.inv()
        runCatching { wm?.updateViewLayout(v, params) }
        isLocked = on
        YLog.i("float", if (on) "플로팅 가사 잠금 (터치 통과)" else "플로팅 가사 잠금 해제")
    }

    /** 회전 등: 새 화면 높이 안으로 창 위치 맞춤 (가로 폭은 MATCH_PARENT 라 자동) */
    override fun onConfigurationChanged(newConfig: Configuration) {
        super.onConfigurationChanged(newConfig)
        applyStyle()        // 기기 어두운 모드가 바뀌었을 수 있음 (따라가기 켜짐)
        val v = root ?: return
        val params = lp ?: return
        val y = OverlayMath.clampY(params.y, v.height, resources.displayMetrics.heightPixels)
        if (y != params.y) {
            params.y = y
            runCatching { wm?.updateViewLayout(v, params) }
        }
    }

    override fun onDestroy() {
        scope.cancel()
        root?.let { v ->
            v.setOnTouchListener(null)
            v.setOnLongClickListener(null)
            runCatching { wm?.removeView(v) }
        }
        root = null
        lp = null
        wm = null
        tvCur = null
        tvNext = null
        bgShape = null
        running = false
        isLocked = false
        YLog.i("float", "플로팅 가사 종료")
        super.onDestroy()
    }

    companion object {
        const val ACTION_LOCK = "com.ascen.yamp.FLOAT_LOCK"
        const val ACTION_UNLOCK = "com.ascen.yamp.FLOAT_UNLOCK"
        const val ACTION_RESTYLE = "com.ascen.yamp.FLOAT_RESTYLE"
        /** 바탕 불투명도: 밝은 테마는 진하게 (흰 바탕 위 글자가 뒤 앱과 섞이지 않게), 어두운 테마는 예전처럼 */
        private const val BG_ALPHA_LIGHT = 235
        private const val BG_ALPHA_DARK = 190
        private const val NEXT_ALPHA = 200
        @Volatile var running = false; private set
        @Volatile var isLocked = false; private set

        fun start(ctx: Context) { runCatching { ctx.startService(Intent(ctx, FloatingLyricsService::class.java)) } }
        fun stop(ctx: Context) { runCatching { ctx.stopService(Intent(ctx, FloatingLyricsService::class.java)) } }
        /** 테마가 바뀜 → 창 색 다시 칠함 */
        fun restyle(ctx: Context) { runCatching { ctx.startService(Intent(ctx, FloatingLyricsService::class.java).setAction(ACTION_RESTYLE)) } }
        fun lock(ctx: Context, on: Boolean) {
            runCatching { ctx.startService(Intent(ctx, FloatingLyricsService::class.java).setAction(if (on) ACTION_LOCK else ACTION_UNLOCK)) }
        }
    }
}
