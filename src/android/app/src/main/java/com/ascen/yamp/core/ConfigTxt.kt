package com.ascen.yamp.core

import java.io.File

/**
 * config.txt (key = value, '#'/';' 주석, [section] 보기용) — PC yamp/core/config.py 와 같은 형식.
 * 위치: Android/data/com.ascen.yamp/files/config.txt (파일 앱·USB 로 수정 가능)
 * 시작 시 읽어 적용, 설정 화면에서 바꾸면 해당 줄만 갱신. 순수 Kotlin — JVM 테스트 대상.
 */
class ConfigTxt(val file: File, private val writer: java.util.concurrent.Executor? = null) {
    val values = LinkedHashMap<String, String>()
    val warnings = ArrayList<String>()

    init { load() }

    fun load() {
        values.clear()
        warnings.clear()
        values.putAll(DEFAULTS)
        if (!file.exists()) {
            runCatching { file.parentFile?.mkdirs(); file.writeText(DEFAULT_TEXT, Charsets.UTF_8) }
                .onFailure { warnings.add("config.txt 생성 실패: $it") }
            return
        }
        val text = runCatching { file.readText(Charsets.UTF_8).removePrefix("﻿") }.getOrElse {
            warnings.add("config.txt 읽기 실패: $it"); return
        }
        val (v, w) = parse(text)
        values.putAll(v)
        warnings.addAll(w)
    }

    fun str(k: String): String = values[k] ?: DEFAULTS[k].orEmpty()
    fun int(k: String): Int = str(k).toIntOrNull() ?: DEFAULTS[k]?.toIntOrNull() ?: 0
    fun bool(k: String): Boolean = str(k) == "1"

    /**
     * 값 변경 + 파일의 해당 줄만 갱신.
     * vr0.1.0.010 (A13): writer 를 주면 (앱: 단일 IO 스레드) 파일 쓰기는 그 스레드에서 — 화면 스레드에서 설정을 바꿀 때 파일을 읽고 쓰지 않음.
     *   값(values)은 바로 바뀌므로 읽기는 즉시 새 값. 쓰기는 차례대로 (마지막 값이 남음)
     */
    fun set(k: String, v: Any) {
        val s = norm(k, toText(v)) ?: return
        if (values[k] == s) return
        values[k] = s
        val w = writer
        if (w == null) write(k, s) else runCatching { w.execute { write(k, s) } }.onFailure { write(k, s) }
    }

    @Synchronized
    private fun write(k: String, s: String) {
        runCatching {
            val text = if (file.exists()) file.readText(Charsets.UTF_8).removePrefix("\uFEFF") else DEFAULT_TEXT
            val tmp = File(file.path + ".tmp")
            tmp.writeText(update(text, mapOf(k to s)), Charsets.UTF_8)
            if (!tmp.renameTo(file)) { file.delete(); tmp.renameTo(file) }
        }
    }

    companion object {
        private val LINE = Regex("""^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$""")

        val DEFAULTS: Map<String, String> = linkedMapOf(
            "log_level" to "INFO", "log_max_size_kb" to "1024", "log_max_files" to "8",
            "theme" to "sunny", "follow_system_dark" to "0", "resume_on_start" to "1", "spectrum" to "0", "lyrics_font_sp" to "17",
            "lyrics_local" to "1", "lyrics_alsong" to "1", "lyrics_lrclib" to "1",
            "lyrics_timeout_s" to "6", "alsong_enc_data" to "",
            "lyrics_netease" to "0", "lyrics_min_score" to "55", "lyrics_notfound_days" to "7",
            "lyric_show_pron" to "1", "lyric_show_trans" to "1", "floating_lyrics" to "0", "keep_screen_on_lyrics" to "1",
            "replaygain" to "track", "preamp_db" to "0", "crossfade_s" to "0", "sleep_fade_s" to "30",
            "history_enabled" to "1", "waveform" to "1",
            "skip_silence" to "0", "resume_long" to "1",
            // vr0.1.0.012 (f23): 상단 바 시세 · KST 시계
            "topbar_ticker" to "1", "ticker_market" to "KRW-XRP", "ticker_interval_s" to "10",
            "topbar_clock" to "1", "topbar_clock_seconds" to "0",
        )
        private val BOOL = setOf("resume_on_start", "spectrum", "lyrics_local", "lyrics_alsong", "lyrics_lrclib",
            "lyric_show_pron", "lyric_show_trans", "floating_lyrics", "keep_screen_on_lyrics", "history_enabled", "waveform",
            "skip_silence", "resume_long", "follow_system_dark", "lyrics_netease",
            "topbar_ticker", "topbar_clock", "topbar_clock_seconds")
        private val LIMITS = mapOf("log_max_size_kb" to (16 to 1048576), "log_max_files" to (1 to 100),
            "lyrics_font_sp" to (10 to 40), "lyrics_timeout_s" to (1 to 60),
            "lyrics_min_score" to (0 to 100), "lyrics_notfound_days" to (0 to 365),
            "preamp_db" to (-12 to 12), "crossfade_s" to (0 to 12), "sleep_fade_s" to (0 to 120),
            "ticker_interval_s" to (5 to 3600))
        private val CHOICES = mapOf("log_level" to setOf("DEBUG", "INFO", "WARNING", "ERROR"),
            "theme" to setOf("sunny", "clean_blue", "mint", "cherry", "night_sunny", "neon", "dark", "classic", "light",
                "light1", "light2", "light3", "light4", "light5", "dark1", "dark2", "dark3", "dark4", "dark5"), "replaygain" to setOf("off", "track", "album"))

        val DEFAULT_TEXT = """
            |# =====================================================================
            |#  yMp3Player (Android) config.txt   (key = value,  '#' 주석)
            |#  앱 시작 시 읽음. 설정 화면에서 바꾸면 이 파일의 해당 줄이 갱신됨.
            |#  위치: 내장 저장소/Android/data/com.ascen.yamp/files/config.txt
            |#  1 = 켬, 0 = 끔
            |# =====================================================================
            |
            |[log]
            |# DEBUG / INFO / WARNING / ERROR   (로그: files/log/NN__YYYY__MMDD.txt)
            |log_level        = INFO
            |# 파일 1개 최대 크기(KB) — 넘으면 다음 번호 파일로 rotation
            |log_max_size_kb  = 1024
            |# rotation 파일 개수 (8 → 00 ~ 07 순환)
            |log_max_files    = 8
            |
            |[view]
            |# sunny (기본: 흰색·노랑·주황) / clean_blue / mint / cherry / night_sunny / neon (이전 기본) / dark / classic
            |#   단계 (vr0.1.0.024): light1~light5 = 라이트 … 라이트++++ (+ 마다 덜 눈부시게) / dark1~dark5 = 다크 … 다크++++ (dark5 = OLED 검정)
            |theme            = sunny
            |# 기기 어두운 모드 따라가기 (1 = 어두운 모드일 때 sunny → night_sunny, lightN → darkN, 밝은 테마 → dark)
            |follow_system_dark = 0
            |lyrics_font_sp   = 17
            |# 스펙트럼 (마이크 권한 필요)
            |spectrum         = 0
            |# 3단 가사: 블록 2번째 줄 = 발음, 3번째 줄 = 번역 (작은 글자로 표시, 0 = 숨김)
            |lyric_show_pron  = 1
            |lyric_show_trans = 1
            |# 플로팅 가사 (다른 앱 위에 표시 권한 필요) — 마지막 상태 기억
            |floating_lyrics  = 0
            |# 가사 탭을 보는 동안 화면 꺼짐 방지
            |keep_screen_on_lyrics = 1
            |# 파형 시크바 (곡을 한 번 읽어 모양을 그림, 20분 넘는 곡은 일반 막대). 0 = 일반 막대
            |waveform         = 1
            |# 상단 바: 업비트 시세 · KST 시각 · 버전 (vr0.1.0.012)
            |#   시세 = 업비트 공개 시세 (키 필요 없음), 앱이 화면에 없으면 갱신 멈춤 · 정보 표시용 (지연 가능)
            |topbar_ticker    = 1
            |# 업비트 마켓 코드 (쉼표로 여러 개: KRW-XRP,KRW-BTC → 3초마다 번갈아 표시)
            |ticker_market    = KRW-XRP
            |# 시세 갱신 주기(초, 5 ~ 3600) — 3번 연속 실패하면 30초, 6번이면 60초로 늘렸다가 성공하면 복귀
            |ticker_interval_s = 10
            |# KST(한국 시각) 시계 · 초 표시 (휴대폰 기본 = 시:분)
            |topbar_clock     = 1
            |topbar_clock_seconds = 0
            |
            |[play]
            |resume_on_start  = 1
            |# ReplayGain 볼륨 보정: off / track / album (album 태그 없으면 track)
            |#  (Android 플레이어 볼륨 최대 1.0 → 소리를 키우는 보정은 적용되지 않고 줄이는 보정만 적용)
            |replaygain       = track
            |# ReplayGain 프리앰프 dB (-12 ~ 12)
            |preamp_db        = 0
            |# 곡 전환 페이드(초, 0 = 끔, 최대 12): 곡 시작 페이드 인 + 끝 페이드 아웃 (겹치는 크로스페이드 아님)
            |crossfade_s      = 0
            |# 슬립 타이머 마지막 N초 동안 볼륨을 서서히 줄임 (0 ~ 120)
            |sleep_fade_s     = 30
            |# 무음 건너뛰기 (녹음 · 강의의 긴 무음을 건너뜀, vr0.1.0.010)
            |skip_silence     = 0
            |# 30분 넘는 파일(오디오북 · 강의)은 멈춘 위치를 파일마다 기억해 다시 열면 이어서 (최근 200개)
            |resume_long      = 1
            |
            |[history]
            |# 재생 기록 (추천용, 기기 안에만 저장). 0 = 기록 안 함
            |history_enabled  = 1
            |
            |[lyrics]
            |lyrics_local     = 1
            |# 알송: 공식 공개 API 아님 (개인 사용)
            |lyrics_alsong    = 1
            |lyrics_lrclib    = 1
            |# NetEase 클라우드 뮤직 (비공식, K-pop·J-pop·번역 가사) — 기본 꺼짐
            |lyrics_netease   = 0
            |# 네트워크 조회 전체 제한 시간(초, 공급자 동시 조회)
            |lyrics_timeout_s = 6
            |# 자동으로 쓸 최저 점수 (0~100) — 낮은 후보는 '다른 가사 찾기' 에만
            |lyrics_min_score = 55
            |# 못 찾은 곡을 기억하는 기간(일, 0 = 안 함) — 그동안 자동 검색 안 함 (다시 찾기는 함)
            |lyrics_notfound_days = 7
            |# 알송 encData — 비어 있으면 내장 값, off = encData 없이 옛 방식
            |alsong_enc_data  =
            |""".trimMargin()

        fun toText(v: Any): String = when (v) { is Boolean -> if (v) "1" else "0"; else -> v.toString() }

        /** 키별 값 검사·정규화. 잘못되면 null */
        fun norm(k: String, raw: String): String? {
            val r = raw.trim()
            if (k !in DEFAULTS) return null
            if (k in BOOL) return when (r.lowercase()) {
                "1", "true", "yes", "on", "y" -> "1"
                "0", "false", "no", "off", "n", "" -> "0"
                else -> null
            }
            LIMITS[k]?.let { (lo, hi) -> return r.toIntOrNull()?.coerceIn(lo, hi)?.toString() }
            CHOICES[k]?.let { c ->
                val u = if (k == "log_level") r.uppercase() else r.lowercase()
                return if (u in c) u else null
            }
            return r
        }

        fun parse(text: String): Pair<Map<String, String>, List<String>> {
            val out = LinkedHashMap<String, String>()
            val warns = ArrayList<String>()
            text.lines().forEachIndexed { i, line ->
                val s = line.trim()
                if (s.isEmpty() || s[0] in "#;[") return@forEachIndexed
                val m = LINE.find(line)
                if (m == null) { warns.add("config.txt:${i + 1} 형식 오류: $s"); return@forEachIndexed }
                val k = m.groupValues[1].lowercase()
                if (k !in DEFAULTS) { warns.add("config.txt:${i + 1} 알 수 없는 키: $k"); return@forEachIndexed }
                val v = norm(k, m.groupValues[2])
                if (v == null) warns.add("config.txt:${i + 1} 잘못된 값: $k = ${m.groupValues[2]}") else out[k] = v
            }
            return out to warns
        }

        fun update(text: String, kv: Map<String, String>): String {
            val lines = text.lines().toMutableList()
            if (lines.isNotEmpty() && lines.last().isEmpty()) lines.removeAt(lines.size - 1)
            val done = HashSet<String>()
            for (i in lines.indices) {
                val s = lines[i].trim()
                if (s.isEmpty() || s[0] in "#;[") continue
                val m = LINE.find(lines[i]) ?: continue
                val k = m.groupValues[1].lowercase()
                val v = kv[k] ?: continue
                lines[i] = lines[i].substring(0, lines[i].indexOf('=') + 1) + " " + v
                done.add(k)
            }
            for ((k, v) in kv) if (k !in done) lines.add(k.padEnd(16) + " = " + v)
            return lines.joinToString("\n") + "\n"
        }
    }
}
