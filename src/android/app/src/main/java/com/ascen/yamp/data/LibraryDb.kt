package com.ascen.yamp.data

import android.content.ContentValues
import android.content.Context
import android.database.sqlite.SQLiteDatabase
import android.database.sqlite.SQLiteOpenHelper
import com.ascen.yamp.domain.PlayMath
import com.ascen.yamp.domain.TrackStat
import com.ascen.yamp.lyrics.LyricsRepo

/**
 * 라이브러리 DB (앱 내부 SQLite "library.db") — 곡 정보 · 재생 기록 · 좋아요/별점 · 사용자 태그.
 * PC yamp/data/library.py 와 같은 스키마 (path 대신 uri). 추천(domain/Recommend.kt) 의 입력을 만든다.
 *
 * key = LyricsRepo.key(track) (uri MD5 앞 12자리, 가사 캐시 키와 같음)
 * 스레드: SQLiteOpenHelper 의 한 연결 (SQLiteDatabase 자체가 스레드 안전) — 호출은 Dispatchers.IO 에서
 */
class LibraryDb private constructor(ctx: Context) : SQLiteOpenHelper(ctx, "library.db", null, 1) {

    companion object {
        /** 재생 기록(plays) 최대 건수 — 넘으면 오래된 것부터 지움 (곡별 누적 횟수 · 좋아요는 tracks 에 유지) */
        const val MAX_PLAYS = 50_000
        /** 추천: 최근 완청 집계 기간 (초) · 라디오에서 뺄 최근 재생 (초) */
        private const val RECENT_COMPLETE_S = 30 * 86_400L
        private const val RECENT_PLAYED_S = 3_600L

        @Volatile private var inst: LibraryDb? = null

        /** 프로세스에 하나 (ViewModel 을 다시 만들어도 연결이 늘지 않음) */
        fun get(ctx: Context): LibraryDb = inst ?: synchronized(this) {
            inst ?: LibraryDb(ctx.applicationContext).also { inst = it }
        }
    }

    /** v018 (f33 P3): WAL — 기록 · 좋아요 저장 중에도 라이브러리 읽기가 막히지 않고, 커밋마다 DB 파일 전체를 동기화하지 않음 */
    override fun onConfigure(db: SQLiteDatabase) {
        super.onConfigure(db)
        db.enableWriteAheadLogging()
    }

    override fun onCreate(db: SQLiteDatabase) {
        db.execSQL("""CREATE TABLE IF NOT EXISTS tracks(
            key TEXT PRIMARY KEY, uri TEXT, title TEXT, artist TEXT, album TEXT, genre TEXT, folder TEXT, path TEXT,
            duration_ms INTEGER DEFAULT 0, added_at INTEGER DEFAULT 0,
            liked INTEGER DEFAULT 0, rating INTEGER DEFAULT 0, play_count INTEGER DEFAULT 0,
            skip_count INTEGER DEFAULT 0, last_played INTEGER DEFAULT 0)""")
        db.execSQL("""CREATE TABLE IF NOT EXISTS plays(
            id INTEGER PRIMARY KEY AUTOINCREMENT, key TEXT, started_at INTEGER, listened_ms INTEGER,
            duration_ms INTEGER, completed INTEGER, skipped INTEGER, session_id INTEGER)""")
        db.execSQL("CREATE INDEX IF NOT EXISTS plays_key ON plays(key)")
        db.execSQL("CREATE INDEX IF NOT EXISTS plays_time ON plays(started_at)")
        db.execSQL("CREATE TABLE IF NOT EXISTS tags(key TEXT, tag TEXT, PRIMARY KEY(key, tag))")
    }

    override fun onUpgrade(db: SQLiteDatabase, oldVersion: Int, newVersion: Int) {
        onCreate(db)
    }

    /** 라이브러리 화면용 곡 행 */
    data class Row(val key: String, val track: Track, val liked: Boolean, val rating: Int, val playCount: Int)

    private fun now(): Long = System.currentTimeMillis() / 1000

    // ---------------------------------------------------------- 곡
    /** 곡 추가/갱신 (좋아요·기록은 유지). 반환: 새로 추가된 수 */
    fun upsert(list: List<Track>): Int {
        if (list.isEmpty()) return 0
        val db = writableDatabase
        var added = 0
        val t0 = now()
        db.beginTransaction()
        try {
            for (t in list) {
                val k = LyricsRepo.keyOf(t.uri)
                val cv = ContentValues().apply {
                    put("uri", t.uri); put("title", t.title); put("artist", t.artist); put("album", t.album)
                    put("folder", t.folder); put("path", t.path)
                    if (t.genre.isNotBlank()) put("genre", t.genre)
                    if (t.durationMs > 0) put("duration_ms", t.durationMs)
                }
                val n = db.update("tracks", cv, "key=?", arrayOf(k))
                if (n == 0) {
                    cv.put("key", k)
                    cv.put("added_at", t0)
                    if (!cv.containsKey("genre")) cv.put("genre", "")
                    db.insertWithOnConflict("tracks", null, cv, SQLiteDatabase.CONFLICT_IGNORE)
                    added++
                }
            }
            db.setTransactionSuccessful()
        } finally {
            db.endTransaction()
        }
        return added
    }

    fun rows(): List<Row> {
        val out = ArrayList<Row>()
        readableDatabase.rawQuery(
            "SELECT key, uri, title, artist, album, genre, folder, path, duration_ms, liked, rating, play_count FROM tracks " +
                "ORDER BY artist COLLATE NOCASE, album COLLATE NOCASE, title COLLATE NOCASE", null).use { c ->
            while (c.moveToNext()) {
                val t = Track(c.getString(1).orEmpty(), c.getString(2).orEmpty(), c.getString(3).orEmpty(),
                    c.getString(4).orEmpty(), c.getLong(8), c.getString(7).orEmpty(), c.getString(6).orEmpty(),
                    c.getString(5).orEmpty())
                out.add(Row(c.getString(0), t, c.getInt(9) != 0, c.getInt(10), c.getInt(11)))
            }
        }
        return out
    }

    // ---------------------------------------------------------- 좋아요 · 별점
    fun setLiked(key: String, liked: Boolean) {
        writableDatabase.execSQL("UPDATE tracks SET liked=? WHERE key=?", arrayOf<Any>(if (liked) 1 else 0, key))
    }

    fun setRating(key: String, rating: Int) {
        writableDatabase.execSQL("UPDATE tracks SET rating=? WHERE key=?", arrayOf<Any>(rating.coerceIn(0, 5), key))
    }

    /** (liked, rating) — 없으면 (false, 0) */
    fun likeRating(key: String): Pair<Boolean, Int> =
        readableDatabase.rawQuery("SELECT liked, rating FROM tracks WHERE key=?", arrayOf(key)).use { c ->
            if (c.moveToFirst()) (c.getInt(0) != 0) to c.getInt(1) else false to 0
        }

    // ---------------------------------------------------------- 재생 기록
    fun recordPlay(r: PlayRecorder.Rec) {
        val db = writableDatabase
        db.beginTransaction()
        try {
            db.execSQL("INSERT INTO plays(key, started_at, listened_ms, duration_ms, completed, skipped, session_id) VALUES(?,?,?,?,?,?,?)",
                arrayOf<Any>(r.key, r.startedAt, r.listenedMs, r.durationMs, if (r.completed) 1 else 0, if (r.skipped) 1 else 0, r.sessionId))
            db.execSQL("UPDATE tracks SET play_count=play_count+?, skip_count=skip_count+?, " +
                "last_played=CASE WHEN ? THEN ? ELSE last_played END WHERE key=?",
                arrayOf<Any>(if (r.completed) 1 else 0, if (r.skipped) 1 else 0, if (r.listenedMs > 0) 1 else 0, r.startedAt, r.key))
            db.setTransactionSuccessful()
        } finally {
            db.endTransaction()
        }
    }

    fun clearHistory() {
        val db = writableDatabase
        db.execSQL("DELETE FROM plays")
        db.execSQL("UPDATE tracks SET play_count=0, skip_count=0, last_played=0")
    }

    /** 오래된 재생 기록 정리 (최근 maxRows 건만). 반환: 지운 건수 */
    fun prunePlays(maxRows: Int): Int {
        val n = playCount()
        if (n <= maxRows) return 0
        writableDatabase.execSQL("DELETE FROM plays WHERE id NOT IN (SELECT id FROM plays ORDER BY id DESC LIMIT ?)", arrayOf<Any>(maxRows))
        return n - maxRows
    }

    fun playCount(): Int = readableDatabase.rawQuery("SELECT COUNT(*) FROM plays", null).use { c ->
        if (c.moveToFirst()) c.getInt(0) else 0
    }

    fun lastPlayedKey(): String? =
        readableDatabase.rawQuery("SELECT key FROM plays WHERE listened_ms>0 ORDER BY started_at DESC, id DESC LIMIT 1", null).use { c ->
            if (c.moveToFirst()) c.getString(0) else null
        }

    /** 최근 withinS 초 안에 재생한 곡 (라디오에서 제외) */
    fun recentKeys(nowS: Long = now(), withinS: Long = RECENT_PLAYED_S): List<String> {
        val out = ArrayList<String>()
        readableDatabase.rawQuery("SELECT DISTINCT key FROM plays WHERE started_at>=?", arrayOf((nowS - withinS).toString())).use { c ->
            while (c.moveToNext()) out.add(c.getString(0))
        }
        return out
    }

    /** 같은 세션에서 연달아 들은 곡 쌍 → 횟수 */
    fun coPairs(): Map<Pair<String, String>, Int> {
        val rows = ArrayList<Pair<String, Long>>()
        readableDatabase.rawQuery("SELECT key, session_id FROM plays WHERE listened_ms>0 ORDER BY session_id, started_at, id", null).use { c ->
            while (c.moveToNext()) rows.add(c.getString(0) to c.getLong(1))
        }
        return PlayMath.coPairs(rows)
    }

    /** 추천 입력 (completed_recent = 최근 30일 완청 수) */
    fun stats(nowS: Long = now()): List<TrackStat> {
        val db = readableDatabase
        val rec = HashMap<String, Int>()
        db.rawQuery("SELECT key, SUM(completed) FROM plays WHERE started_at>=? GROUP BY key", arrayOf((nowS - RECENT_COMPLETE_S).toString())).use { c ->
            while (c.moveToNext()) rec[c.getString(0)] = c.getInt(1)
        }
        val tg = HashMap<String, MutableList<String>>()
        db.rawQuery("SELECT key, tag FROM tags", null).use { c ->
            while (c.moveToNext()) tg.getOrPut(c.getString(0)) { ArrayList() }.add(c.getString(1))
        }
        val out = ArrayList<TrackStat>()
        db.rawQuery("SELECT key, artist, album, genre, folder, liked, rating, play_count, skip_count, last_played, added_at FROM tracks", null).use { c ->
            while (c.moveToNext()) {
                val k = c.getString(0)
                out.add(TrackStat(k, c.getString(1).orEmpty(), c.getString(2).orEmpty(), c.getString(3).orEmpty(),
                    c.getString(4).orEmpty(), c.getInt(5) != 0, c.getInt(6), c.getInt(7), c.getInt(8), c.getLong(9),
                    c.getLong(10), rec[k] ?: 0, tg[k] ?: emptyList()))
            }
        }
        return out
    }
}
