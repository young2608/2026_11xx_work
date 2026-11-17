package com.ascen.yamp.core

import java.io.File
import java.io.FileOutputStream
import java.io.OutputStreamWriter
import java.io.Writer
import java.time.LocalDate

/**
 * 로그 파일 rotation (PC yamp/core/logger.py 와 같은 규칙) — 순수 Kotlin, JVM 테스트 대상.
 *   파일명 log/NN__YYYY__MMDD.txt  (예: 00__2026__0716.txt), NN = 00 ~ maxFiles-1 순환
 *   크기 초과 / 날짜 변경 → 다음 번호 (그 번호의 옛 파일 삭제) → 최대 maxFiles 개 유지
 *   재시작: 최근 파일이 오늘 날짜이고 여유 있으면 이어서 기록
 */
class RingLog(
    private val dir: File,
    maxBytes: Long = 1024 * 1024,
    maxFiles: Int = 8,
    private val today: () -> LocalDate = { LocalDate.now() },
) {
    val maxBytes = maxOf(4096L, maxBytes)
    val maxFiles = maxFiles.coerceIn(1, 100)
    private var idx = 0
    private var day: LocalDate? = null
    private var size = 0L
    private var out: Writer? = null
    var currentFile: File? = null; private set

    init {
        dir.mkdirs()
        openInitial()
    }

    private data class F(val mtime: Long, val idx: Int, val file: File)

    private fun scan(): List<F> = (dir.listFiles() ?: emptyArray()).mapNotNull { f ->
        NAME.matchEntire(f.name)?.let { F(f.lastModified(), it.groupValues[1].toInt(), f) }
    }.sortedWith(compareBy<F>({ it.mtime }, { it.file.name }))

    private fun openInitial() {
        val t = today()
        val files = scan()
        if (files.isNotEmpty()) {
            val last = files.last()
            if (last.file.name == fileName(last.idx, t) && last.file.length() < maxBytes && last.idx < maxFiles) {
                idx = last.idx; day = t
                size = last.file.length()
                currentFile = last.file
                out = OutputStreamWriter(FileOutputStream(last.file, true), Charsets.UTF_8)
                return
            }
            idx = (last.idx + 1) % maxFiles
        } else idx = 0
        openNew(t)
    }

    private fun openNew(d: LocalDate) {
        runCatching { out?.close() }
        scan().filter { it.idx == idx || it.idx >= maxFiles }.forEach { it.file.delete() }
        day = d
        size = 0
        val f = File(dir, fileName(idx, d))
        currentFile = f
        out = OutputStreamWriter(FileOutputStream(f, true), Charsets.UTF_8)
    }

    @Synchronized
    fun write(line: String, flush: Boolean = false) {
        val msg = line + "\n"
        val n = msg.toByteArray(Charsets.UTF_8).size
        val t = today()
        if (day != t || (size > 0 && size + n > maxBytes)) {
            idx = (idx + 1) % maxFiles
            openNew(t)
        }
        out?.write(msg)
        size += n
        if (flush) out?.flush()
    }

    @Synchronized fun flush() { runCatching { out?.flush() } }
    @Synchronized fun close() { runCatching { out?.close() }; out = null }

    companion object {
        val NAME = Regex("""^(\d{2})__(\d{4})__(\d{4})\.txt$""")
        fun fileName(i: Int, d: LocalDate) = "%02d__%04d__%02d%02d.txt".format(i, d.year, d.monthValue, d.dayOfMonth)
    }
}
