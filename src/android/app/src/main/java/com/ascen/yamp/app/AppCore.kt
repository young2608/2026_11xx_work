package com.ascen.yamp.app

import android.app.Application
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import com.ascen.yamp.core.CrashCatcher
import com.ascen.yamp.core.YLog
import com.ascen.yamp.data.LibraryDb
import com.ascen.yamp.data.ScanResult
import com.ascen.yamp.data.Store
import com.ascen.yamp.data.Track
import com.ascen.yamp.lyrics.LyricsRepo
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/**
 * 기능 모듈 공용 (vr0.1.0.007 모듈화): 설정 저장소 · 라이브러리 DB · 가사 저장소 · 코루틴 범위 · 화면 알림 메시지.
 * AppViewModel 이 하나 만들어 각 기능 컨트롤러(재생 · 목록 · 라이브러리 · 추천 · 폴더 · 가사 · 사운드 · 설정)에 넘김.
 * Activity 를 참조하지 않음 (Application 만) → 화면을 닫았다 열어도 누수 없음.
 */
class AppCore(val app: Application, val scope: CoroutineScope) {
    val store = Store(app)
    /** vr0.1.0.013: 안전 모드로 시작 (비정상 종료 화면에서 고른 경우 한 번) — 다른 모듈이 설정을 읽기 전에 적용 */
    val safeMode: Boolean = CrashCatcher.consumeSafeMode(app).also { if (it) store.applySafeMode() }
    val lyricsRepo = LyricsRepo(app, store)
    /** 프로세스 하나에 연결 하나 (ViewModel 을 다시 만들어도 SQLite 연결이 늘지 않음) */
    val db: LibraryDb = LibraryDb.get(app)

    /** 화면 알림(토스트) — MainScreen 이 보여 주고 consumeMessage() */
    var message by mutableStateOf(""); private set

    fun toast(m: String) { message = m }
    fun appendToast(m: String) { message += m }
    fun consumeMessage() { message = "" }

    /** MediaStore 전체 스캔 결과 (라이브러리 '음악 스캔' · 폴더 탭 공용) */
    var mediaStoreTracks: List<Track> = emptyList()

    fun keyOf(t: Track): String = lyricsRepo.key(t)
    fun nowS(): Long = System.currentTimeMillis() / 1000

    /** IO 스레드에서 실행, 실패는 경고 로그 후 기본값 (취소는 그대로 전달) */
    suspend fun <T> io(tag: String, what: String, default: T, block: () -> T): T = withContext(Dispatchers.IO) {
        runCatching(block).onFailure { YLog.w(tag, what, it) }.getOrDefault(default)
    }

    /** 곡을 라이브러리 DB 에 등록 (재생 기록 · 좋아요 대상) */
    suspend fun register(list: List<Track>): Int = if (list.isEmpty()) 0 else io("library", "DB 등록 실패", 0) { db.upsert(list) }

    // ---------------------------------------------------------- 건너뛴 파일 안내 (스캔 · 파일 추가 · 폴더 공용)
    fun logSkipped(r: ScanResult, where: String) {
        if (r.skipped.isNotEmpty()) {
            YLog.i("folder", "$where: 재생할 수 없는 형식 ${r.skipped.size}개 건너뜀 — " + r.skipped.take(SKIPPED_LOG_MAX).joinToString(", "))
        }
        if (r.cueFiles > 0) YLog.i("folder", "$where: CUE 시트로 펼친 파일 ${r.cueFiles}개")
    }

    fun skippedText(n: Int): String = "${n}개 파일은 이 기기에서 재생할 수 없는 형식이라 건너뜀"

    fun toastSkipped(n: Int) { if (n > 0) toast(skippedText(n)) }
    fun appendSkipped(n: Int) { if (n > 0) appendToast(" · " + skippedText(n)) }

    companion object {
        /** 건너뛴 파일 이름을 로그에 몇 개까지 */
        const val SKIPPED_LOG_MAX = 20
    }
}
