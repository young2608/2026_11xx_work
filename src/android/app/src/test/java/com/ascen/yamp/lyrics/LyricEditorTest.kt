package com.ascen.yamp.lyrics

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/** PC lyrics/editor.py 와 같은 동작 */
class LyricEditorTest {
    @Test fun stampAdvancesSkippingBlank() {
        val e = LyricEditor.fromText("첫 줄\n\n둘째\n셋째")
        assertEquals(4, e.lines.size)
        assertEquals(2, e.stamp(1000))      // 빈 줄 건너뜀
        assertEquals(3, e.stamp(2500))
        assertEquals(3, e.stamp(4000))      // 마지막 줄에 머묾
        assertEquals(listOf(1000L, -1L, 2500L, 4000L), e.lines.map { it.tMs })
        assertEquals(3, e.stamped())
    }

    @Test fun nudgeAndSelect() {
        val e = LyricEditor.fromText("a\nb")
        e.nudge(100)                        // 시각 없음 → 변화 없음
        assertEquals(-1L, e.lines[0].tMs)
        e.stamp(50)
        e.nudge(-100, 0)
        assertEquals(0L, e.lines[0].tMs)    // 0 아래로 안 감
        e.nudge(+100, 0)
        assertEquals(100L, e.lines[0].tMs)
        e.select(99)
        assertEquals(1, e.cur)
        e.clearTimes()
        assertEquals(0, e.stamped())
        assertEquals(0, e.cur)
    }

    @Test fun toLrcRoundTrip() {
        val e = LyricEditor.fromText("하나\n둘\n셋 (plain)")
        e.stamp(1230); e.stamp(65_400)
        val lrc = e.toLrc()
        assertEquals("[00:01.23]하나\n[01:05.40]둘\n셋 (plain)\n", lrc)
        val ly = Lrc.parse(lrc)
        assertTrue(ly.synced)
        assertEquals(listOf(1230L, 65_400L), ly.blocks.map { it.tMs })
        // 다시 불러와 편집 → 같은 LRC
        val e2 = LyricEditor.fromLyrics(ly)
        assertEquals("[00:01.23]하나\n[01:05.40]둘\n", e2.toLrc())
    }

    @Test fun setTextKeepsTimes() {
        val e = LyricEditor.fromLyrics(Lrc.parse("[00:01.00]a\n[00:02.00]b\n[00:02.00]b-trans"))
        assertEquals(3, e.lines.size)
        assertEquals(2000L, e.lines[2].tMs)
        e.setText("A\nB\nB2\nC")
        assertEquals(listOf(1000L, 2000L, 2000L, -1L), e.lines.map { it.tMs })
        assertEquals("A\nB\nB2\nC", e.text())
    }

    @Test fun tiers() {
        val l = listOf("원문", "발음", "번역", "기타")
        assertEquals(listOf("원문" to 0, "발음" to 1, "번역" to 2, "기타" to 2), LyricTiers.visible(l, true, true))
        assertEquals(listOf("원문" to 0, "번역" to 2, "기타" to 2), LyricTiers.visible(l, false, true))
        assertEquals("원문 / 발음", LyricTiers.joined(l, true, false))
        assertEquals(listOf("only" to 0), LyricTiers.visible(listOf("only"), false, false))
    }
}
