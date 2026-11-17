package com.ascen.yamp.data

/**
 * 폴더 트리 (순수 Kotlin — JVM 테스트 대상). 폴더 탭(F1)의 계층 · 곡 수 · 총 시간 · 형식별 곡 수.
 *
 * 폴더 문자열
 *   MediaStore : 실제 경로  "/storage/emulated/0/Music/K-Pop"  → 최상위 "내장 저장소"
 *                SD/USB    "/storage/1234-ABCD/Music"         → 최상위 "SD·USB (1234-ABCD)"
 *   SAF 추가 폴더 : "saf:<번호>/하위/폴더"                       → 최상위 = 추가한 폴더 이름 (labels)
 * 노드 path 는 위 문자열 규칙 그대로 (트리 안에서 유일).
 */
object FolderTree {
    /** idx = 호출한 쪽 목록의 위치 (Track 목록 index) */
    data class Item(val idx: Int, val folder: String, val ext: String, val durationMs: Long)

    class Node(val path: String, val label: String, val parent: Node?) {
        val children = ArrayList<Node>()
        val direct = ArrayList<Int>()               // 이 폴더 바로 아래 곡 (idx)
        var count = 0                               // 하위 포함 곡 수
        var totalMs = 0L                            // 하위 포함 총 시간
        val formats = LinkedHashMap<String, Int>()  // 하위 포함 형식별 곡 수 (확장자 대문자)
        val depth: Int get() = (parent?.depth ?: -1) + 1

        /** 곡 idx 목록: 하위 포함이면 이 폴더 곡 → 하위 폴더(이름 순) 곡 */
        fun items(includeSub: Boolean): List<Int> {
            if (!includeSub) return direct.toList()
            val out = ArrayList<Int>(count)
            fun walk(n: Node) { out.addAll(n.direct); n.children.forEach { walk(it) } }
            walk(this)
            return out
        }

        /** 루트(가상) 바로 아래부터 이 노드까지 */
        fun crumbs(): List<Node> {
            val out = ArrayList<Node>()
            var n: Node? = this
            while (n != null && n.parent != null) { out.add(n); n = n.parent }
            return out.reversed()
        }

        fun find(p: String): Node? {
            if (path == p) return this
            for (c in children) {
                if (p == c.path || p.startsWith(c.path.trimEnd('/') + "/")) c.find(p)?.let { return it }
            }
            return null
        }
    }

    private data class RootSplit(val rootPath: String, val label: String, val rest: List<String>)

    private fun splitRoot(folder: String, labels: Map<String, String>): RootSplit {
        val f = folder.trim()
        if (f.isEmpty()) return RootSplit("?", "(폴더 없음)", emptyList())
        if (f.startsWith("saf:")) {
            val segs = f.split('/').filter { it.isNotEmpty() }
            val root = segs[0]
            return RootSplit(root, labels[root] ?: root.removePrefix("saf:"), segs.drop(1))
        }
        val segs = f.split('/').filter { it.isNotEmpty() }
        if (segs.size >= 3 && segs[0] == "storage" && segs[1] == "emulated") {
            val u = segs[2]
            return RootSplit("/storage/emulated/$u", if (u == "0") "내장 저장소" else "내장 저장소 ($u)", segs.drop(3))
        }
        if (segs.size >= 2 && segs[0] == "storage" && segs[1] != "self") {
            return RootSplit("/storage/${segs[1]}", "SD·USB (${segs[1]})", segs.drop(2))
        }
        return RootSplit("/", "기기", segs)
    }

    /** labels: SAF 루트("saf:<번호>") → 표시 이름 */
    fun build(items: List<Item>, labels: Map<String, String> = emptyMap()): Node {
        val root = Node("", "", null)
        val index = HashMap<String, Node>()
        for (item in items) {
            val sp = splitRoot(item.folder, labels)
            var node = index.getOrPut(sp.rootPath) { Node(sp.rootPath, sp.label, root).also { n -> root.children.add(n) } }
            for (seg in sp.rest) {
                val p = if (node.path.endsWith("/")) node.path + seg else node.path + "/" + seg
                val parent = node
                node = index.getOrPut(p) { Node(p, seg, parent).also { n -> parent.children.add(n) } }
            }
            node.direct.add(item.idx)
            val fmt = item.ext.uppercase().ifEmpty { "?" }
            var n: Node? = node
            while (n != null) {
                n.count++
                n.totalMs += item.durationMs.coerceAtLeast(0)
                n.formats[fmt] = (n.formats[fmt] ?: 0) + 1
                n = n.parent
            }
        }
        fun sortRec(n: Node) {
            n.children.sortWith(compareBy({ it.label.lowercase() }, { it.label }))
            n.children.forEach { sortRec(it) }
        }
        sortRec(root)
        return root
    }

    /** "FLAC 120 · MP3 98 · WAV 18 · 기타 12" (많은 순 3개 + 나머지) */
    fun formatSummary(formats: Map<String, Int>, top: Int = 3): String {
        val sorted = formats.entries.sortedWith(compareBy({ -it.value }, { it.key }))
        val head = sorted.take(top).map { "${it.key} ${it.value}" }
        val restN = sorted.drop(top).sumOf { it.value }
        return (if (restN > 0) head + "기타 $restN" else head).joinToString(" · ")
    }

    /** "15시간 42분" / "42분" / "0분" */
    fun durationText(ms: Long): String {
        val m = (ms.coerceAtLeast(0) + 30_000) / 60_000
        return if (m >= 60) "${m / 60}시간 ${m % 60}분" else "${m}분"
    }

    /** 폴더 카드 두 번째 줄: "하위 폴더 3 · 248곡 · 15시간 42분" */
    fun summaryLine(n: Node): String {
        val parts = ArrayList<String>()
        if (n.children.isNotEmpty()) parts.add("하위 폴더 ${n.children.size}")
        parts.add("${n.count}곡")
        if (n.totalMs > 0) parts.add(durationText(n.totalMs))
        return parts.joinToString(" · ")
    }
}

/** 파형 시크바용 피크 버킷 (순수 — data/Waveform.kt 의 디코더가 PCM 을 넣음) */
class WavePeaks(val n: Int, private val durationUs: Long) {
    val peaks = FloatArray(n)

    private fun bucket(timeUs: Long): Int =
        if (durationUs <= 0) 0 else ((timeUs.toDouble() / durationUs) * n).toInt().coerceIn(0, n - 1)

    /** 16비트 PCM (인터리브) 한 덩어리. timeUs = 덩어리 시작 시각, frameUs = 프레임 1개 길이 */
    fun add16(samples: ShortArray, len: Int, channels: Int, timeUs: Long, frameUs: Double) {
        val ch = channels.coerceAtLeast(1)
        var i = 0
        var f = 0
        while (i + ch <= len) {
            var m = 0
            for (c in 0 until ch) { val v = kotlin.math.abs(samples[i + c].toInt()); if (v > m) m = v }
            val b = bucket(timeUs + (f * frameUs).toLong())
            val fv = m / 32768f
            if (fv > peaks[b]) peaks[b] = fv
            i += ch; f++
        }
    }

    /** float PCM (인터리브) */
    fun addFloat(samples: FloatArray, len: Int, channels: Int, timeUs: Long, frameUs: Double) {
        val ch = channels.coerceAtLeast(1)
        var i = 0
        var f = 0
        while (i + ch <= len) {
            var m = 0f
            for (c in 0 until ch) { val v = kotlin.math.abs(samples[i + c]); if (v > m) m = v }
            val b = bucket(timeUs + (f * frameUs).toLong())
            val fv = m.coerceAtMost(1f)
            if (fv > peaks[b]) peaks[b] = fv
            i += ch; f++
        }
    }

    /** 0..1 로 맞춤 (가장 큰 값 = 1, 조용한 곡도 보이게). 전부 0 이면 그대로 */
    fun normalized(): FloatArray {
        val mx = peaks.maxOrNull() ?: 0f
        if (mx <= 1e-6f) return peaks.copyOf()
        return FloatArray(n) { (peaks[it] / mx).coerceIn(0f, 1f) }
    }

    companion object {
        /** 캐시 파일 형식: 1바이트 × n (0..255) */
        fun encode(v: FloatArray): ByteArray = ByteArray(v.size) { (v[it].coerceIn(0f, 1f) * 255f + 0.5f).toInt().toByte() }
        fun decode(b: ByteArray): FloatArray = FloatArray(b.size) { (b[it].toInt() and 0xff) / 255f }
    }
}
