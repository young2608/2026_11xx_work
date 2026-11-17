package com.ascen.yamp.playback

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.net.Uri
import androidx.annotation.OptIn
import androidx.media3.common.util.BitmapLoader
import androidx.media3.common.util.UnstableApi
import androidx.media3.datasource.BitmapUtil
import androidx.media3.datasource.DataSourceBitmapLoader
import com.ascen.yamp.domain.ImageMath
import com.google.common.util.concurrent.ListenableFuture
import java.util.concurrent.Callable

/**
 * 알림 · 잠금화면 · 블루투스용 앨범아트 디코더 (vr0.1.0.008).
 *
 * media3 기본(DataSourceBitmapLoader)은 곡에 들어 있는 그림(ExoPlayer 가 ID3 APIC 등에서 읽은 artworkData)을
 * 원본 크기로 디코딩 → 3000px 그림이면 곡마다 ~36MB 비트맵이 알림 · 시스템 미디어 세션으로 넘어감.
 * 여기서는 크기만 먼저 읽고 짧은 변 NOTIFY_TARGET_PX 이상이 남게 줄여서 디코딩 (회전 EXIF 처리는 media3 BitmapUtil 그대로).
 * uri 로 불러오기 · 지원 형식 판단은 기본 로더 그대로. 같은 작업 스레드(media3 기본 단일 스레드) 사용.
 * PlaybackService 가 CacheBitmapLoader 로 감싸서 MediaSession 에 넣음 (마지막 그림 1개만 기억).
 */
@OptIn(UnstableApi::class)
class CoverBitmapLoader(ctx: Context) : BitmapLoader {
    private val base = DataSourceBitmapLoader(ctx.applicationContext)
    private val exec = DataSourceBitmapLoader.DEFAULT_EXECUTOR_SERVICE.get()

    override fun supportsMimeType(mimeType: String): Boolean = base.supportsMimeType(mimeType)

    override fun decodeBitmap(data: ByteArray): ListenableFuture<Bitmap> = exec.submit(Callable { decodeScaled(data) })

    override fun loadBitmap(uri: Uri): ListenableFuture<Bitmap> = base.loadBitmap(uri)

    companion object {
        /** 알림 그림 목표: 짧은 변 기준 픽셀 (알림 · 잠금화면 표시에 충분) */
        const val NOTIFY_TARGET_PX = 512

        /** 크기만 먼저 읽고 → 줄여서 디코딩 (실패하면 BitmapUtil 이 IOException) */
        fun decodeScaled(data: ByteArray): Bitmap {
            val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
            BitmapFactory.decodeByteArray(data, 0, data.size, bounds)
            val opts = BitmapFactory.Options().apply {
                inSampleSize = ImageMath.sampleSize(bounds.outWidth, bounds.outHeight, NOTIFY_TARGET_PX)
            }
            return BitmapUtil.decode(data, data.size, opts)
        }
    }
}
