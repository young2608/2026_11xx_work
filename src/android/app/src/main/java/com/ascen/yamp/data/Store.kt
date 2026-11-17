package com.ascen.yamp.data

import android.content.Context
import com.ascen.yamp.core.ConfigTxt
import org.json.JSONObject
import java.io.File

/**
 * 설정: config.txt (사용자 설정, 단일 소스) + SharedPreferences (실행 상태) + 플레이리스트 파일
 *   config.txt 위치 : Android/data/com.ascen.yamp/files/config.txt  (파일 앱·USB 로 수정 → 앱 다시 시작)
 *   로그 폴더       : Android/data/com.ascen.yamp/files/log/
 */
class Store(private val ctx: Context) {
    companion object {
        /** SharedPreferences 이름 · 서비스도 읽는 키 (PlaybackService) */
        const val PREFS = "yamp"
        const val KEY_SOUND = "sound"
        const val KEY_USER_VOLUME = "user_volume"
        /** vr0.1.0.010 (A4): 재생 서비스(PlaybackTracker)가 직접 쓰는 키 — 화면이 없어도 저장 */
        const val KEY_LAST_INDEX = "last_index"
        const val KEY_LAST_POS = "last_pos"
        const val KEY_OFFSETS = "offsets"
        /** V2 파일별 이어 듣기 (ResumeBook.toText) */
        const val KEY_RESUME_BOOK = "resume_book"

        /** config.txt 쓰기 스레드 (vr0.1.0.010 A13 — 화면 스레드에서 파일을 쓰지 않음). 프로세스에 하나 */
        val CONFIG_WRITER: java.util.concurrent.ExecutorService by lazy {
            java.util.concurrent.Executors.newSingleThreadExecutor { r -> Thread(r, "yamp-config").apply { isDaemon = true } }
        }
        /** vr0.1.0.005 이전 기기 EQ(Equalizer/BassBoost) 저장값 — vr0.1.0.006 부터 SoundEngine 이 대신함 */
        private val LEGACY_KEYS = listOf("eq_on", "eq_bands", "bass")
    }

    private val sp = ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
    private val plFile = File(ctx.filesDir, "playlist.tsv")
    val extDir: File = ctx.getExternalFilesDir(null) ?: ctx.filesDir
    val cfg = ConfigTxt(File(extDir, "config.txt"), CONFIG_WRITER)
    val logDir = File(extDir, "log")

    // ---- config.txt 항목
    var theme: String
        get() = cfg.str("theme")
        set(v) = cfg.set("theme", v)
    var repeat: Int                     // Player.REPEAT_MODE_* (0 off, 1 one, 2 all)
        get() = sp.getInt("repeat", 2)
        set(v) = sp.edit().putInt("repeat", v).apply()
    var shuffle: Boolean
        get() = sp.getBoolean("shuffle", false)
        set(v) = sp.edit().putBoolean("shuffle", v).apply()
    /** 소리 시각화 블럭 모드 wave / bars / chart (vr0.1.0.014, f26 D8 — 화면 상태라 SharedPreferences) */
    var visMode: String
        get() = sp.getString("vis_mode", "chart") ?: "chart"
        set(v) = sp.edit().putString("vis_mode", v).apply()
    /** 스펙트럼 막대 모양 round / led / mirror / reflex (vr0.1.0.027, f53) */
    var visBarStyle: String
        get() = sp.getString("vis_bar_style", "round") ?: "round"
        set(v) = sp.edit().putString("vis_bar_style", v).apply()
    var lastIndex: Int
        get() = sp.getInt(KEY_LAST_INDEX, -1)
        set(v) = sp.edit().putInt(KEY_LAST_INDEX, v).apply()
    var lastPos: Long
        get() = sp.getLong(KEY_LAST_POS, 0)
        set(v) = sp.edit().putLong(KEY_LAST_POS, v).apply()
    var resume: Boolean
        get() = cfg.bool("resume_on_start")
        set(v) = cfg.set("resume_on_start", v)
    var fontSp: Int
        get() = cfg.int("lyrics_font_sp")
        set(v) = cfg.set("lyrics_font_sp", v)
    var spectrum: Boolean
        get() = cfg.bool("spectrum")
        set(v) = cfg.set("spectrum", v)
    var useLocal: Boolean
        get() = cfg.bool("lyrics_local")
        set(v) = cfg.set("lyrics_local", v)
    var useAlsong: Boolean
        get() = cfg.bool("lyrics_alsong")
        set(v) = cfg.set("lyrics_alsong", v)
    var useLrclib: Boolean
        get() = cfg.bool("lyrics_lrclib")
        set(v) = cfg.set("lyrics_lrclib", v)
    val alsongEnc: String get() = cfg.str("alsong_enc_data")
    val timeoutMs: Int get() = cfg.int("lyrics_timeout_s") * 1000
    /** vr0.1.0.011 (f18): NetEase (L10, 기본 끔) · 자동 적용 최저 점수 (L3) · 실패 기억 일수 (L6, 0 = 안 함) */
    var useNetease: Boolean
        get() = cfg.bool("lyrics_netease")
        set(v) = cfg.set("lyrics_netease", v)
    val lyricsMinScore: Int get() = cfg.int("lyrics_min_score")
    val lyricsNotFoundDays: Int get() = cfg.int("lyrics_notfound_days")

    // ---- vr0.1.0.004 추가 항목 (config.txt)
    var replayGain: String              // off / track / album
        get() = cfg.str("replaygain")
        set(v) = cfg.set("replaygain", v)
    var preampDb: Int                   // -12 ~ 12
        get() = cfg.int("preamp_db")
        set(v) = cfg.set("preamp_db", v)
    var crossfadeS: Int                 // 곡 전환 페이드 0 ~ 12초
        get() = cfg.int("crossfade_s")
        set(v) = cfg.set("crossfade_s", v)
    var sleepFadeS: Int                 // 0 ~ 120초
        get() = cfg.int("sleep_fade_s")
        set(v) = cfg.set("sleep_fade_s", v)
    var showPron: Boolean
        get() = cfg.bool("lyric_show_pron")
        set(v) = cfg.set("lyric_show_pron", v)
    var showTrans: Boolean
        get() = cfg.bool("lyric_show_trans")
        set(v) = cfg.set("lyric_show_trans", v)
    var historyEnabled: Boolean
        get() = cfg.bool("history_enabled")
        set(v) = cfg.set("history_enabled", v)
    var floatingLyrics: Boolean
        get() = cfg.bool("floating_lyrics")
        set(v) = cfg.set("floating_lyrics", v)
    /** V1 무음 건너뛰기 (vr0.1.0.010) — 서비스 쪽 ExoPlayer 에 적용 (PlayerHolder.setSkipSilence) */
    var skipSilence: Boolean
        get() = cfg.bool("skip_silence")
        set(v) = cfg.set("skip_silence", v)
    /** V2 30분 넘는 파일 파일별 이어 듣기 (vr0.1.0.010) */
    var resumeLong: Boolean
        get() = cfg.bool("resume_long")
        set(v) = cfg.set("resume_long", v)
    var keepScreenOnLyrics: Boolean
        get() = cfg.bool("keep_screen_on_lyrics")
        set(v) = cfg.set("keep_screen_on_lyrics", v)
    // ---- 상단 바 시세 · KST 시계 (vr0.1.0.012, f23)
    var topbarTicker: Boolean
        get() = cfg.bool("topbar_ticker")
        set(v) = cfg.set("topbar_ticker", v)
    var tickerMarket: String
        get() = cfg.str("ticker_market")
        set(v) = cfg.set("ticker_market", v)
    val tickerIntervalS: Int get() = cfg.int("ticker_interval_s")
    var topbarClock: Boolean
        get() = cfg.bool("topbar_clock")
        set(v) = cfg.set("topbar_clock", v)
    var topbarClockSeconds: Boolean
        get() = cfg.bool("topbar_clock_seconds")
        set(v) = cfg.set("topbar_clock_seconds", v)
    /** 마지막 시세 (Ticker.encode 줄들, 다음 실행 때 첫 갱신 전까지 흐리게) */
    var lastQuotes: String
        get() = sp.getString("last_quote", "") ?: ""
        set(v) = sp.edit().putString("last_quote", v).apply()

    // ---- 재생 속도 · 음정 (A6, SharedPreferences)
    var speed: Float
        get() = sp.getFloat("speed", 1f)
        set(v) = sp.edit().putFloat("speed", v).apply()
    var pitchSt: Float                  // 반음 -6 ~ +6
        get() = sp.getFloat("pitch_st", 0f)
        set(v) = sp.edit().putFloat("pitch_st", v).apply()
    /** 대기열(다음 재생) 곡 수 — 목록과 함께 복원 */
    var queued: Int
        get() = sp.getInt("queued", 0)
        set(v) = sp.edit().putInt("queued", v).apply()
    /** 추천 홈 마지막 계산 날짜 (epoch day) */
    var homeDay: Long
        get() = sp.getLong("home_day", -1)
        set(v) = sp.edit().putLong("home_day", v).apply()

    /** 쓰지 않는 옛 저장값 지우기 (시작 때, 있을 때만) */
    fun cleanupLegacy() {
        val old = LEGACY_KEYS.filter { sp.contains(it) }
        if (old.isEmpty()) return
        val e = sp.edit()
        old.forEach { e.remove(it) }
        e.apply()
    }

    var waveform: Boolean
        get() = cfg.bool("waveform")
        set(v) = cfg.set("waveform", v)

    // ---- 사운드 (vr0.1.0.006): SoundSettings.toText 형식 (PC 와 같음)
    var sound: String
        get() = sp.getString(KEY_SOUND, "").orEmpty()
        set(v) = sp.edit().putString(KEY_SOUND, v).apply()
    /** 앱 볼륨 노브 0..1 (서비스 시작 때도 읽음: PlaybackService) */
    var userVolume: Float
        get() = sp.getFloat(KEY_USER_VOLUME, 1f)
        set(v) = sp.edit().putFloat(KEY_USER_VOLUME, v).apply()
    /** 내 프리셋: 이름 → SoundSettings 텍스트 (줄 = 이름\t텍스트) */
    var userPresets: List<Pair<String, String>>
        get() = pairs("sound_presets")
        set(v) = sp.edit().putString("sound_presets", v.joinToString("\n") { (n, t) ->
            n.replace('\t', ' ').replace('\n', ' ') + "\t" + t }).apply()

    /** 줄 = 앞\t뒤 목록 읽기 */
    private fun pairs(key: String): List<Pair<String, String>> = sp.getString(key, "").orEmpty().lines().mapNotNull { l ->
        val i = l.indexOf('\t')
        if (i <= 0) null else l.substring(0, i) to l.substring(i + 1)
    }

    // ---- 카드 접기/펼치기 (id 별, 기본 펼침)
    fun folded(id: String): Boolean = sp.getBoolean("fold_$id", false)
    fun setFolded(id: String, folded: Boolean) { sp.edit().putBoolean("fold_$id", folded).apply() }

    // ---- 폴더 재생 (F)
    /** 추가한 SAF 폴더: 줄 = 트리 uri\t표시 이름 */
    var safTrees: List<Pair<String, String>>
        get() = pairs("saf_trees")
        set(v) = sp.edit().putString("saf_trees", v.joinToString("\n") { (u, n) -> u + "\t" + n.replace('\t', ' ').replace('\n', ' ') }).apply()
    var pinnedFolders: Set<String>
        get() = sp.getString("folder_pins", "").orEmpty().lines().filter { it.isNotBlank() }.toSet()
        set(v) = sp.edit().putString("folder_pins", v.joinToString("\n")).apply()
    var lastFolder: String
        get() = sp.getString("last_folder", "").orEmpty()
        set(v) = sp.edit().putString("last_folder", v).apply()
    var folderIncludeSub: Boolean
        get() = sp.getBoolean("folder_sub", true)
        set(v) = sp.edit().putBoolean("folder_sub", v).apply()
    var folderShuffle: Boolean
        get() = sp.getBoolean("folder_shuffle", false)
        set(v) = sp.edit().putBoolean("folder_shuffle", v).apply()
    /** name(파일명) / title(제목) / added(추가일) */
    var folderSort: String
        get() = sp.getString("folder_sort", "name").orEmpty()
        set(v) = sp.edit().putString("folder_sort", v).apply()
    /** 하단 내비 마지막 탭 · 목록·가사 하위 탭 */
    var navTab: Int
        get() = sp.getInt("nav_tab", 0)
        set(v) = sp.edit().putInt("nav_tab", v).apply()
    /** vr0.1.0.009: 도움말(버튼 안내)을 한 번 보였는지 — 처음 실행 때만 저절로 열림 */
    var helpShown: Boolean
        get() = sp.getBoolean("help_shown", false)
        set(v) = sp.edit().putBoolean("help_shown", v).apply()
    var listSub: Int
        get() = sp.getInt("list_sub", 0)
        set(v) = sp.edit().putInt("list_sub", v).apply()

    // 곡별 가사 싱크 보정 (key → ms)
    fun offset(key: String): Long = runCatching { JSONObject(sp.getString(KEY_OFFSETS, "{}")!!).optLong(key, 0) }.getOrDefault(0)
    fun setOffset(key: String, ms: Long) {
        val o = runCatching { JSONObject(sp.getString(KEY_OFFSETS, "{}")!!) }.getOrElse { JSONObject() }
        if (ms == 0L) o.remove(key) else o.put(key, ms)
        sp.edit().putString(KEY_OFFSETS, o.toString()).apply()
    }

    /**
     * 안전 모드 (vr0.1.0.013, 비정상 종료 화면에서 고름): 시작에 관여하는 설정을 기본으로 + 재생 목록 파일을 백업으로 옮김.
     *   라이브러리 DB(좋아요 · 기록) · 가사 캐시는 그대로. 되돌리기: playlist.tsv.safe_bak → playlist.tsv
     */
    fun applySafeMode() {
        runCatching {
            cfg.set("theme", "sunny")
            cfg.set("follow_system_dark", false)
            cfg.set("topbar_ticker", false)
            cfg.set("floating_lyrics", false)
            cfg.set("spectrum", false)
        }
        runCatching { if (plFile.exists()) plFile.renameTo(File(plFile.parentFile, plFile.name + ".safe_bak")) }
    }

    fun loadPlaylist(): List<Track> = runCatching {
        if (!plFile.exists()) emptyList() else plFile.readLines(Charsets.UTF_8).mapNotNull { Track.decode(it) }
    }.getOrDefault(emptyList())

    /** 여러 스레드(IO 저장 · 종료 시 저장)에서 불려도 같은 .tmp 파일을 동시에 쓰지 않게 */
    @Synchronized
    fun savePlaylist(items: List<Track>) {
        runCatching {
            val tmp = File(plFile.path + ".tmp")
            tmp.writeText(items.joinToString("\n") { it.encode() }, Charsets.UTF_8)
            if (!tmp.renameTo(plFile)) { plFile.delete(); tmp.renameTo(plFile) }
        }
    }
}
