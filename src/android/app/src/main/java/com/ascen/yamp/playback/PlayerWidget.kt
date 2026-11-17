package com.ascen.yamp.playback

import android.app.PendingIntent
import android.appwidget.AppWidgetManager
import android.appwidget.AppWidgetProvider
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.os.SystemClock
import android.widget.RemoteViews
import androidx.media3.common.Player
import androidx.media3.common.util.Util
import com.ascen.yamp.BuildConfig
import com.ascen.yamp.MainActivity
import com.ascen.yamp.R
import com.ascen.yamp.core.YLog
import com.ascen.yamp.ui.ThemeDef
import com.ascen.yamp.ui.ThemePrefs

/**
 * 홈 화면 위젯 4x1 (C4): 제목 · 현재 가사 줄 · 이전 · 재생/일시정지 · 다음 (벡터 이미지 버튼)
 * 버튼 → 이 Provider 로 명시적 브로드캐스트 → PlayerHolder.player 제어 (서비스가 없으면 앱 실행)
 * 갱신: PlaybackService 가 재생 상태 / 가사 줄이 바뀔 때 PlayerWidget.update(...)
 * vr0.1.0.007: 위젯 id 목록은 IDS_TTL_MS 동안 기억 (가사 줄마다 시스템 호출 안 함), 내용이 같으면 다시 그리지 않음
 * vr0.1.0.011 (f19): 테마 색 따라감 — 바탕 = surface (밝은 테마 = 흰색), 테두리 = line, 제목 = accent_text, 가사 줄 = text,
 *   버튼 = text / 재생 버튼 = accent_text (벡터는 흰색, setColorFilter 로 칠함). 테마를 바꾸면 refresh()
 */
class PlayerWidget : AppWidgetProvider() {

    override fun onUpdate(context: Context, manager: AppWidgetManager, appWidgetIds: IntArray) {
        forget()        // 위젯이 추가·복원됨 → id 목록 · 마지막 내용 다시
        val p = PlayerHolder.player
        val title = p?.mediaMetadata?.title?.toString().orEmpty()
        render(context, manager, appWidgetIds, title, p?.isPlaying == true, LyricsBus.lines.value.first, ThemePrefs.current(context))
    }

    override fun onReceive(context: Context, intent: Intent) {
        when (intent.action) {
            ACTION_PREV, ACTION_TOGGLE, ACTION_NEXT -> handle(context, intent.action.orEmpty())
            else -> super.onReceive(context, intent)
        }
    }

    private fun handle(context: Context, action: String) {
        val p = PlayerHolder.player
        if (p == null || p.mediaItemCount == 0) {
            // 재생 서비스가 없음 → 앱 열기
            val i = Intent(context, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            runCatching { context.startActivity(i) }.onFailure { YLog.w("widget", "앱 실행 실패", it) }
            return
        }
        when (action) {
            ACTION_PREV -> if (p.currentPosition > PREV_RESTART_MS || !p.hasPreviousMediaItem()) p.seekTo(0) else p.seekToPreviousMediaItem()
            // 목록 끝 → 처음 (셔플이면 셔플 순서의 첫 곡, A15)
            ACTION_NEXT -> if (p.hasNextMediaItem()) p.seekToNextMediaItem() else p.seekTo(firstIndex(p), 0)
            else -> if (p.isPlaying) p.pause() else {
                // vr0.1.0.010 (A5): 목록 끝(반복 끔) · 재생 오류 뒤(IDLE)에도 동작 — 끝났으면 처음 곡부터, IDLE 이면 prepare 후 재생
                if (p.playbackState == Player.STATE_ENDED) p.seekTo(firstIndex(p), 0)
                Util.handlePlayButtonAction(p)
            }
        }
    }

    companion object {
        /** 재생 순서의 첫 곡 (셔플이면 셔플 순서) */
        fun firstIndex(p: Player): Int = p.currentTimeline.getFirstWindowIndex(p.shuffleModeEnabled).takeIf { it >= 0 } ?: 0

        const val ACTION_PREV = "com.ascen.yamp.WIDGET_PREV"
        const val ACTION_TOGGLE = "com.ascen.yamp.WIDGET_TOGGLE"
        const val ACTION_NEXT = "com.ascen.yamp.WIDGET_NEXT"
        /** 이전 버튼: 이만큼 지났으면 곡 처음으로 */
        private const val PREV_RESTART_MS = 3000L
        /** 위젯 id 목록 기억 시간 */
        private const val IDS_TTL_MS = 30_000L
        private const val REQ_PREV = 1
        private const val REQ_TOGGLE = 2
        private const val REQ_NEXT = 3
        private const val REQ_OPEN = 4

        @Volatile private var ids: IntArray? = null
        @Volatile private var idsAt = 0L
        @Volatile private var lastShown: String? = null

        private fun forget() { ids = null; lastShown = null }

        private fun pi(ctx: Context, action: String, req: Int): PendingIntent =
            PendingIntent.getBroadcast(ctx, req, Intent(ctx, PlayerWidget::class.java).setAction(action),
                PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)

        private fun render(ctx: Context, mgr: AppWidgetManager, ids: IntArray, title: String, playing: Boolean, line: String, th: ThemeDef) {
            if (ids.isEmpty()) return
            val v = RemoteViews(ctx.packageName, R.layout.widget_player)
            v.setTextViewText(R.id.widget_title, title.ifBlank { BuildConfig.APP_NAME })
            v.setTextViewText(R.id.widget_line, line)
            v.setImageViewResource(R.id.widget_toggle, if (playing) R.drawable.ic_w_pause else R.drawable.ic_w_play)
            // 테마 색: 흰색 모양(바탕 95% 불투명 — 배경화면이 살짝 비침) · 흰 벡터에 색 필터 (SRC_ATOP, 투명도 유지)
            v.setInt(R.id.widget_bg, "setColorFilter", th.argb("surface"))
            v.setInt(R.id.widget_border, "setColorFilter", th.argb("line"))
            v.setTextColor(R.id.widget_title, th.argb("accent_text"))
            v.setTextColor(R.id.widget_line, th.argb("text"))
            v.setInt(R.id.widget_prev, "setColorFilter", th.argb("text"))
            v.setInt(R.id.widget_next, "setColorFilter", th.argb("text"))
            v.setInt(R.id.widget_toggle, "setColorFilter", th.argb("accent_text"))
            val open = PendingIntent.getActivity(ctx, REQ_OPEN, Intent(ctx, MainActivity::class.java),
                PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
            // 재생 서비스가 없으면 버튼도 앱 열기 (백그라운드 브로드캐스트에서는 Activity 시작이 막힐 수 있음)
            val alive = PlayerHolder.player != null
            v.setOnClickPendingIntent(R.id.widget_prev, if (alive) pi(ctx, ACTION_PREV, REQ_PREV) else open)
            v.setOnClickPendingIntent(R.id.widget_toggle, if (alive) pi(ctx, ACTION_TOGGLE, REQ_TOGGLE) else open)
            v.setOnClickPendingIntent(R.id.widget_next, if (alive) pi(ctx, ACTION_NEXT, REQ_NEXT) else open)
            v.setOnClickPendingIntent(R.id.widget_title, open)
            v.setOnClickPendingIntent(R.id.widget_line, open)
            runCatching { mgr.updateAppWidget(ids, v) }
        }

        /** 서비스·화면에서 호출 (위젯이 없으면 아무것도 안 함) */
        fun update(ctx: Context, title: String, playing: Boolean, line: String) {
            val mgr = AppWidgetManager.getInstance(ctx) ?: return
            val now = SystemClock.elapsedRealtime()
            var list = ids
            if (list == null || now - idsAt > IDS_TTL_MS) {
                list = runCatching { mgr.getAppWidgetIds(ComponentName(ctx, PlayerWidget::class.java)) }.getOrNull() ?: return
                if (ids?.contentEquals(list) != true) lastShown = null
                ids = list
                idsAt = now
            }
            if (list.isEmpty()) return
            val th = ThemePrefs.current(ctx)
            val shown = "$title\u0001$playing\u0001$line\u0001${PlayerHolder.player != null}\u0001${th.name}"
            if (shown == lastShown) return
            lastShown = shown
            render(ctx, mgr, list, title, playing, line, th)
        }

        /** 테마가 바뀜 → 지금 내용으로 다시 그림 (위젯이 없으면 아무것도 안 함) */
        fun refresh(ctx: Context) {
            lastShown = null
            val p = PlayerHolder.player
            runCatching { update(ctx, p?.mediaMetadata?.title?.toString().orEmpty(), p?.isPlaying == true, LyricsBus.lines.value.first) }
                .onFailure { YLog.w("widget", "테마 다시 칠하기 실패", it) }
        }
    }
}
