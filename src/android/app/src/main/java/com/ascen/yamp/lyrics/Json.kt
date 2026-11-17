package com.ascen.yamp.lyrics

/**
 * 작은 JSON 읽기 (vr0.1.0.011) — LRCLIB · NetEase 응답용. 순수 Kotlin (JVM 테스트에서 org.json 없이 동작)
 * 결과: Map<String, Any?> · List<Any?> · String · Double · Boolean · null
 */
object Json {
    class Error(msg: String) : Exception(msg)

    fun parse(s: String): Any? {
        val p = P(s)
        p.ws()
        val v = p.value()
        p.ws()
        if (p.i != s.length) throw Error("JSON 끝에 남은 글자 (${p.i})")
        return v
    }

    @Suppress("UNCHECKED_CAST")
    fun obj(v: Any?): Map<String, Any?>? = v as? Map<String, Any?>

    @Suppress("UNCHECKED_CAST")
    fun arr(v: Any?): List<Any?>? = v as? List<Any?>

    /** 글자 값 (없음 · null → "") */
    fun str(m: Map<String, Any?>?, k: String): String = when (val v = m?.get(k)) {
        null -> ""
        is String -> v
        is Double -> if (v == Math.floor(v) && Math.abs(v) < 1e15) v.toLong().toString() else v.toString()
        else -> v.toString()
    }

    fun num(m: Map<String, Any?>?, k: String): Double = when (val v = m?.get(k)) {
        is Double -> v
        is String -> v.toDoubleOrNull() ?: 0.0
        else -> 0.0
    }

    private class P(val s: String) {
        var i = 0

        fun ws() { while (i < s.length && s[i].isWhitespace()) i++ }

        fun value(): Any? {
            if (i >= s.length) throw Error("JSON 이 끝남")
            return when (val c = s[i]) {
                '{' -> objectV()
                '[' -> arrayV()
                '"' -> string()
                't' -> lit("true", true)
                'f' -> lit("false", false)
                'n' -> lit("null", null)
                else -> if (c == '-' || c.isDigit()) number() else throw Error("JSON 글자 '$c' ($i)")
            }
        }

        fun lit(w: String, v: Any?): Any? {
            if (!s.startsWith(w, i)) throw Error("JSON '$w' ($i)")
            i += w.length
            return v
        }

        fun number(): Double {
            val st = i
            while (i < s.length && (s[i].isDigit() || s[i] in "+-.eE")) i++
            return s.substring(st, i).toDoubleOrNull() ?: throw Error("JSON 숫자 ($st)")
        }

        fun string(): String {
            i++
            val b = StringBuilder()
            while (true) {
                if (i >= s.length) throw Error("JSON 글자열이 끝나지 않음")
                val c = s[i++]
                when (c) {
                    '"' -> return b.toString()
                    '\\' -> {
                        if (i >= s.length) throw Error("JSON 이스케이프")
                        when (val e = s[i++]) {
                            'n' -> b.append('\n'); 't' -> b.append('\t'); 'r' -> b.append('\r')
                            'b' -> b.append('\b'); 'f' -> b.append('\u000C')
                            'u' -> {
                                if (i + 4 > s.length) throw Error("JSON \\u")
                                b.append(s.substring(i, i + 4).toInt(16).toChar()); i += 4
                            }
                            else -> b.append(e)
                        }
                    }
                    else -> b.append(c)
                }
            }
        }

        fun arrayV(): List<Any?> {
            i++
            val out = ArrayList<Any?>()
            ws()
            if (i < s.length && s[i] == ']') { i++; return out }
            while (true) {
                ws(); out.add(value()); ws()
                if (i >= s.length) throw Error("JSON 배열이 끝나지 않음")
                when (s[i++]) { ',' -> continue; ']' -> return out; else -> throw Error("JSON 배열 (${i - 1})") }
            }
        }

        fun objectV(): Map<String, Any?> {
            i++
            val out = LinkedHashMap<String, Any?>()
            ws()
            if (i < s.length && s[i] == '}') { i++; return out }
            while (true) {
                ws()
                if (i >= s.length || s[i] != '"') throw Error("JSON 키 ($i)")
                val k = string()
                ws()
                if (i >= s.length || s[i++] != ':') throw Error("JSON ':' ($i)")
                ws(); out[k] = value(); ws()
                if (i >= s.length) throw Error("JSON 객체가 끝나지 않음")
                when (s[i++]) { ',' -> continue; '}' -> return out; else -> throw Error("JSON 객체 (${i - 1})") }
            }
        }
    }
}
