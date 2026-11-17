package com.ascen.yamp.app

import android.content.Context
import com.ascen.yamp.core.YLog
import com.ascen.yamp.data.LibraryDb
import com.ascen.yamp.data.Waveform
import com.ascen.yamp.domain.CachePrune
import com.ascen.yamp.lyrics.LyricsRepo
import java.io.File

/**
 * 장시간 운용 정리 (vr0.1.0.007, 앱 시작 때 IO 스레드에서 한 번):
 *   - 가사 캐시 (filesDir/lyrics)   최대 LYRICS_MAX 개 — 직접 편집한 가사([re:yAmp/user])는 지우지 않음
 *   - 파형 캐시 (filesDir/waveform) 최대 WAVE_MAX 개
 *   - 재생 기록 (plays 테이블)      최근 LibraryDb.MAX_PLAYS 건 (곡별 누적 횟수는 tracks 에 그대로)
 */
object Maintenance {
    const val LYRICS_MAX = 5000
    const val WAVE_MAX = 5000

    fun run(ctx: Context, db: LibraryDb) {
        val ly = prune(LyricsRepo.dirOf(ctx), LYRICS_MAX) { f -> LyricsRepo.isUserFile(f) }
        val wv = prune(Waveform.cacheDir(ctx), WAVE_MAX)
        val pl = db.prunePlays(LibraryDb.MAX_PLAYS)
        if (ly + wv + pl > 0) YLog.i("maint", "정리: 가사 캐시 ${ly}개 · 파형 캐시 ${wv}개 · 재생 기록 ${pl}건")
    }

    /** 반환: 지운 파일 수 */
    fun prune(dir: File, max: Int, keep: (File) -> Boolean = { false }): Int {
        val files = dir.listFiles()?.filter { it.isFile } ?: return 0
        if (files.size <= max) return 0
        val byName = files.associateBy { it.name }
        val victims = CachePrune.victims(files.map { CachePrune.Entry(it.name, it.lastModified()) }, max) { n ->
            byName[n]?.let(keep) ?: false
        }
        return victims.count { n -> byName[n]?.delete() == true }
    }
}
