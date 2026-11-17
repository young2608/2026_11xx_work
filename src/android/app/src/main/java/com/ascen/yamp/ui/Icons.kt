package com.ascen.yamp.ui

import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.graphics.vector.PathBuilder
import androidx.compose.ui.graphics.vector.path
import androidx.compose.ui.unit.dp

/**
 * 직접 그린 벡터 아이콘 (vr0.1.0.006). 글꼴 기호(⏾ 🔀 ⏮ …)는 기기 글꼴에 없으면 네모(□)로 깨지므로 모두 이것으로 바꿈.
 * 24×24 뷰포트, 검정으로 그리고 Icon(tint = …) 로 색 지정. 시안(mock.html) 의 SVG 와 같은 모양.
 */
object YIcons {
    private fun icon(name: String, block: ImageVector.Builder.() -> Unit): ImageVector =
        ImageVector.Builder(name = name, defaultWidth = 24.dp, defaultHeight = 24.dp, viewportWidth = 24f, viewportHeight = 24f)
            .apply(block).build()

    private val black = SolidColor(Color.Black)

    private fun ImageVector.Builder.fill(b: PathBuilder.() -> Unit) {
        path(fill = black, pathBuilder = b)
    }

    private fun ImageVector.Builder.line(w: Float = 2f, b: PathBuilder.() -> Unit) {
        path(fill = null, stroke = black, strokeLineWidth = w, strokeLineCap = StrokeCap.Round,
            strokeLineJoin = StrokeJoin.Round, pathBuilder = b)
    }

    /** 원 (중심 cx,cy 반지름 r) */
    private fun PathBuilder.circle(cx: Float, cy: Float, r: Float) {
        moveTo(cx - r, cy)
        arcTo(r, r, 0f, true, true, cx + r, cy)
        arcTo(r, r, 0f, true, true, cx - r, cy)
        close()
    }

    val play: ImageVector = icon("play") { fill { moveTo(8f, 5f); lineTo(19f, 12f); lineTo(8f, 19f); close() } }

    val pause: ImageVector = icon("pause") {
        fill { moveTo(6f, 5f); lineTo(10f, 5f); lineTo(10f, 19f); lineTo(6f, 19f); close() }
        fill { moveTo(14f, 5f); lineTo(18f, 5f); lineTo(18f, 19f); lineTo(14f, 19f); close() }
    }

    val stop: ImageVector = icon("stop") { fill { moveTo(6f, 6f); lineTo(18f, 6f); lineTo(18f, 18f); lineTo(6f, 18f); close() } }

    val prev: ImageVector = icon("prev") {
        line(2.4f) { moveTo(6f, 5f); lineTo(6f, 19f) }
        fill { moveTo(19f, 5f); lineTo(9f, 12f); lineTo(19f, 19f); close() }
    }

    val next: ImageVector = icon("next") {
        line(2.4f) { moveTo(18f, 5f); lineTo(18f, 19f) }
        fill { moveTo(5f, 5f); lineTo(15f, 12f); lineTo(5f, 19f); close() }
    }

    val shuffle: ImageVector = icon("shuffle") {
        line {
            moveTo(4f, 7f); lineTo(8f, 7f); lineTo(16f, 17f); lineTo(20f, 17f)
            moveTo(4f, 17f); lineTo(8f, 17f); lineTo(10.5f, 14f)
            moveTo(14f, 10f); lineTo(16f, 7f); lineTo(20f, 7f)
            moveTo(18f, 5f); lineTo(20f, 7f); lineTo(18f, 9f)
            moveTo(18f, 15f); lineTo(20f, 17f); lineTo(18f, 19f)
        }
    }

    private fun ImageVector.Builder.repeatBase() {
        line {
            moveTo(4f, 12f); lineTo(4f, 9f); arcTo(2f, 2f, 0f, false, true, 6f, 7f); lineTo(19f, 7f)
            moveTo(16f, 4f); lineTo(19f, 7f); lineTo(16f, 10f)
            moveTo(20f, 12f); lineTo(20f, 15f); arcTo(2f, 2f, 0f, false, true, 18f, 17f); lineTo(5f, 17f)
            moveTo(8f, 20f); lineTo(5f, 17f); lineTo(8f, 14f)
        }
    }

    val repeat: ImageVector = icon("repeat") { repeatBase() }

    val repeatOne: ImageVector = icon("repeatOne") {
        repeatBase()
        line(1.8f) { moveTo(11f, 10.6f); lineTo(12.4f, 9.6f); lineTo(12.4f, 14.4f) }
    }

    /** 반복 끔: 오른쪽 화살표 하나 */
    val repeatOff: ImageVector = icon("repeatOff") {
        line { moveTo(4f, 12f); lineTo(19f, 12f); moveTo(15f, 8f); lineTo(19f, 12f); lineTo(15f, 16f) }
    }

    private fun PathBuilder.heartPath() {
        moveTo(12f, 21.35f)
        lineTo(10.55f, 20.03f)
        curveTo(5.4f, 15.36f, 2f, 12.28f, 2f, 8.5f)
        curveTo(2f, 5.42f, 4.42f, 3f, 7.5f, 3f)
        curveTo(9.24f, 3f, 10.91f, 3.81f, 12f, 5.09f)
        curveTo(13.09f, 3.81f, 14.76f, 3f, 16.5f, 3f)
        curveTo(19.58f, 3f, 22f, 5.42f, 22f, 8.5f)
        curveTo(22f, 12.28f, 18.6f, 15.36f, 13.45f, 20.04f)
        close()
    }

    val heart: ImageVector = icon("heart") { fill { heartPath() } }
    val heartOutline: ImageVector = icon("heartOutline") { line(1.8f) { heartPath() } }

    /** 달 (슬립 타이머) */
    val moon: ImageVector = icon("moon") {
        fill {
            moveTo(20f, 14.5f)
            arcTo(8.5f, 8.5f, 0f, false, true, 9.5f, 4f)
            arcTo(8.5f, 8.5f, 0f, true, false, 20f, 14.5f)
            close()
        }
    }

    private fun PathBuilder.folderPath() {
        moveTo(3f, 7f)
        arcTo(2f, 2f, 0f, false, true, 5f, 5f)
        lineTo(9f, 5f); lineTo(11f, 7f); lineTo(19f, 7f)
        arcTo(2f, 2f, 0f, false, true, 21f, 9f)
        lineTo(21f, 17f)
        arcTo(2f, 2f, 0f, false, true, 19f, 19f)
        lineTo(5f, 19f)
        arcTo(2f, 2f, 0f, false, true, 3f, 17f)
        close()
    }

    val folder: ImageVector = icon("folder") { line { folderPath() } }
    val folderFill: ImageVector = icon("folderFill") { fill { folderPath() } }

    private fun PathBuilder.starPath() {
        moveTo(12f, 3f); lineTo(14.5f, 9f); lineTo(21f, 9.5f); lineTo(16f, 13.8f); lineTo(17.6f, 20f)
        lineTo(12f, 16.7f); lineTo(6.4f, 20f); lineTo(8f, 13.8f); lineTo(3f, 9.5f); lineTo(9.5f, 9f); close()
    }

    val star: ImageVector = icon("star") { fill { starPath() } }
    val starOutline: ImageVector = icon("starOutline") { line { starPath() } }

    val list: ImageVector = icon("list") {
        line(2.2f) { moveTo(4f, 6f); lineTo(20f, 6f); moveTo(4f, 12f); lineTo(20f, 12f); moveTo(4f, 18f); lineTo(14f, 18f) }
    }

    val eq: ImageVector = icon("eq") {
        line(2.4f) {
            moveTo(5f, 20f); lineTo(5f, 10f); moveTo(10f, 20f); lineTo(10f, 4f)
            moveTo(15f, 20f); lineTo(15f, 12f); moveTo(20f, 20f); lineTo(20f, 7f)
        }
    }

    /** 비주얼라이저 모드 (vr0.1.0.014 → v026 이름): 웨이브 · 스펙트럼 · 레벨 */
    val visWave: ImageVector = icon("visWave") {
        line(2f) {
            moveTo(2f, 12f); curveTo(4f, 4f, 6f, 4f, 8f, 12f); curveTo(10f, 20f, 12f, 20f, 14f, 12f)
            curveTo(16f, 6f, 18f, 6f, 20f, 12f); lineTo(22f, 12f)
        }
    }
    val visBars: ImageVector = icon("visBars") {
        fill {
            moveTo(3f, 20f); lineTo(3f, 13f); lineTo(6f, 13f); lineTo(6f, 20f); close()
            moveTo(8f, 20f); lineTo(8f, 6f); lineTo(11f, 6f); lineTo(11f, 20f); close()
            moveTo(13f, 20f); lineTo(13f, 10f); lineTo(16f, 10f); lineTo(16f, 20f); close()
            moveTo(18f, 20f); lineTo(18f, 15f); lineTo(21f, 15f); lineTo(21f, 20f); close()
        }
    }
    /** v027 (f53): 원형 스펙트럼 · 스펙트로그램 (PC icon_paths radial · gram 과 같은 모양) */
    val visRadial: ImageVector = icon("visRadial") {
        line(1.8f) {
            circle(12f, 12f, 4f)
            for (k in 0 until 8) {
                val a = Math.PI * k / 4
                val r1 = if (k % 2 == 1) 9.5 else 8.0
                moveTo((12 + 6 * Math.cos(a)).toFloat(), (12 + 6 * Math.sin(a)).toFloat())
                lineTo((12 + r1 * Math.cos(a)).toFloat(), (12 + r1 * Math.sin(a)).toFloat())
            }
        }
    }
    val visGram: ImageVector = icon("visGram") {
        line(1.8f) {
            moveTo(5f, 4f); lineTo(19f, 4f); arcTo(2f, 2f, 0f, false, true, 21f, 6f); lineTo(21f, 18f)
            arcTo(2f, 2f, 0f, false, true, 19f, 20f); lineTo(5f, 20f); arcTo(2f, 2f, 0f, false, true, 3f, 18f); lineTo(3f, 6f)
            arcTo(2f, 2f, 0f, false, true, 5f, 4f); close()
            moveTo(3f, 12f); lineTo(21f, 12f); moveTo(9f, 4f); lineTo(9f, 20f); moveTo(15f, 4f); lineTo(15f, 20f)
        }
    }
    val visChart: ImageVector = icon("visChart") {
        line(1.6f) { moveTo(3f, 4f); lineTo(3f, 20f); lineTo(21f, 20f) }
        fill { moveTo(4f, 20f); lineTo(4f, 15f); lineTo(8f, 12f); lineTo(12f, 14f); lineTo(16f, 8f); lineTo(20f, 11f); lineTo(20f, 20f); close() }
    }

    val more: ImageVector = icon("more") { fill { circle(12f, 5f, 2f); circle(12f, 12f, 2f); circle(12f, 19f, 2f) } }

    val plus: ImageVector = icon("plus") { line { moveTo(12f, 5f); lineTo(12f, 19f); moveTo(5f, 12f); lineTo(19f, 12f) } }
    val minus: ImageVector = icon("minus") { line { moveTo(5f, 12f); lineTo(19f, 12f) } }
    val chevronDown: ImageVector = icon("chevronDown") { line { moveTo(6f, 9f); lineTo(12f, 15f); lineTo(18f, 9f) } }
    val chevronUp: ImageVector = icon("chevronUp") { line { moveTo(6f, 15f); lineTo(12f, 9f); lineTo(18f, 15f) } }
    val chevronRight: ImageVector = icon("chevronRight") { line { moveTo(9f, 6f); lineTo(15f, 12f); lineTo(9f, 18f) } }
    val close: ImageVector = icon("close") { line { moveTo(6f, 6f); lineTo(18f, 18f); moveTo(18f, 6f); lineTo(6f, 18f) } }
    val check: ImageVector = icon("check") { line { moveTo(5f, 12.5f); lineTo(10f, 17f); lineTo(19f, 7f) } }

    /** A-B 구간 반복: 양쪽 막대 + 안쪽 화살표 */
    val ab: ImageVector = icon("ab") {
        line {
            moveTo(4f, 5f); lineTo(4f, 19f); moveTo(20f, 5f); lineTo(20f, 19f)
            moveTo(8f, 12f); lineTo(16f, 12f)
            moveTo(11f, 9f); lineTo(8f, 12f); lineTo(11f, 15f)
            moveTo(13f, 9f); lineTo(16f, 12f); lineTo(13f, 15f)
        }
    }

    /** 속도 (게이지) */
    val speed: ImageVector = icon("speed") {
        line {
            moveTo(4.5f, 17f)
            arcTo(8.5f, 8.5f, 0f, true, true, 19.5f, 17f)
            moveTo(12f, 14f); lineTo(16f, 9f)
        }
    }

    /** 재생 (하단 내비): 원 + 삼각형 */
    val playCircle: ImageVector = icon("playCircle") {
        line { circle(12f, 12f, 9f) }
        fill { moveTo(10f, 8f); lineTo(16f, 12f); lineTo(10f, 16f); close() }
    }

    val refresh: ImageVector = icon("refresh") {
        line {
            moveTo(20f, 12f)
            arcTo(8f, 8f, 0f, true, true, 17.66f, 6.34f)
            moveTo(20f, 4f); lineTo(20f, 9f); lineTo(15f, 9f)
        }
    }

    /** 위로 (상위 폴더) */
    val up: ImageVector = icon("up") { line { moveTo(12f, 19f); lineTo(12f, 5f); moveTo(6f, 11f); lineTo(12f, 5f); lineTo(18f, 11f) } }

    // ---- vr0.1.0.009: 글자 없는 버튼용 아이콘 (같은 24×24 선 스타일)

    /** 도움말: 원 + 물음표 */
    val help: ImageVector = icon("help") {
        line { circle(12f, 12f, 9f) }
        line(2.2f) { moveTo(9.5f, 9.5f); arcTo(2.5f, 2.5f, 0f, true, true, 13.2f, 11.7f); lineTo(12f, 12.8f); lineTo(12f, 14f) }
        fill { circle(12f, 17.2f, 1.2f) }
    }

    /** 검색 (돋보기) */
    val search: ImageVector = icon("search") {
        line { circle(10.5f, 10.5f, 6f) }
        line(2.6f) { moveTo(15f, 15f); lineTo(20f, 20f) }
    }

    /** 휴지통 (비우기) */
    val trash: ImageVector = icon("trash") {
        line {
            moveTo(4f, 7f); lineTo(20f, 7f)
            moveTo(9f, 7f); lineTo(9f, 4.5f); lineTo(15f, 4.5f); lineTo(15f, 7f)
            moveTo(6.5f, 7f); lineTo(7.5f, 20f); lineTo(16.5f, 20f); lineTo(17.5f, 7f)
            moveTo(10f, 11f); lineTo(10f, 16f); moveTo(14f, 11f); lineTo(14f, 16f)
        }
    }

    /** 파일 추가: 문서 + 더하기 */
    val addFile: ImageVector = icon("addFile") {
        line {
            moveTo(13f, 3f); lineTo(6f, 3f); lineTo(6f, 21f); lineTo(18f, 21f); lineTo(18f, 8f); lineTo(13f, 3f); lineTo(13f, 8f); lineTo(18f, 8f)
            moveTo(12f, 11.5f); lineTo(12f, 17.5f); moveTo(9f, 14.5f); lineTo(15f, 14.5f)
        }
    }

    /** 음악 스캔: 음표 + 둘레 호 (찾는 중) */
    val scan: ImageVector = icon("scan") {
        line {
            moveTo(3f, 8f); lineTo(3f, 3f); lineTo(8f, 3f)
            moveTo(16f, 3f); lineTo(21f, 3f); lineTo(21f, 8f)
            moveTo(21f, 16f); lineTo(21f, 21f); lineTo(16f, 21f)
            moveTo(8f, 21f); lineTo(3f, 21f); lineTo(3f, 16f)
            moveTo(11f, 16f); lineTo(11f, 7f); lineTo(16f, 8.5f)
        }
        fill { circle(9.3f, 16f, 2f) }
    }

    /** 찍기 (깃발) — 가사 편집기 '현재 줄 찍기' */
    val stamp: ImageVector = icon("stamp") {
        line { moveTo(6f, 21f); lineTo(6f, 4f) }
        fill { moveTo(7f, 4f); lineTo(19f, 4f); lineTo(16f, 8f); lineTo(19f, 12f); lineTo(7f, 12f); close() }
    }

    /** 조금 앞으로 (−0.1초): 왼쪽 꺾쇠 + 막대 */
    val nudgeBack: ImageVector = icon("nudgeBack") {
        line { moveTo(14f, 6f); lineTo(8f, 12f); lineTo(14f, 18f); moveTo(18f, 7f); lineTo(18f, 17f) }
    }

    /** 조금 뒤로 (+0.1초): 오른쪽 꺾쇠 + 막대 */
    val nudgeFwd: ImageVector = icon("nudgeFwd") {
        line { moveTo(10f, 6f); lineTo(16f, 12f); lineTo(10f, 18f); moveTo(6f, 7f); lineTo(6f, 17f) }
    }

    private fun ImageVector.Builder.clockBase() {
        line { circle(10f, 12f, 7f); moveTo(10f, 8f); lineTo(10f, 12f); lineTo(12.5f, 13.5f) }
    }

    /** 시각 − (가사 싱크 −0.5초) */
    val timeMinus: ImageVector = icon("timeMinus") { clockBase(); line(2.2f) { moveTo(18f, 5f); lineTo(23f, 5f) } }

    /** 시각 + (가사 싱크 +0.5초) */
    val timePlus: ImageVector = icon("timePlus") {
        clockBase(); line(2.2f) { moveTo(18f, 5f); lineTo(23f, 5f); moveTo(20.5f, 2.5f); lineTo(20.5f, 7.5f) }
    }

    /** 싱크 (시계) */
    val clock: ImageVector = icon("clock") {
        line { circle(12f, 12f, 9f); moveTo(12f, 7f); lineTo(12f, 12f); lineTo(15.5f, 14f) }
    }

    /** 시각 지우기 (시계 + 사선) */
    val clockOff: ImageVector = icon("clockOff") {
        line { circle(12f, 12f, 9f); moveTo(12f, 7f); lineTo(12f, 12f); moveTo(4f, 4f); lineTo(20f, 20f) }
    }

    /** 텍스트 편집 (T) */
    val textMode: ImageVector = icon("textMode") {
        line(2.4f) { moveTo(5f, 6f); lineTo(19f, 6f); moveTo(12f, 6f); lineTo(12f, 19f); moveTo(9f, 19f); lineTo(15f, 19f) }
    }

    /** 편집 (연필) */
    val edit: ImageVector = icon("edit") {
        line { moveTo(4f, 20f); lineTo(4.5f, 16f); lineTo(16f, 4.5f); lineTo(19.5f, 8f); lineTo(8f, 19.5f); close(); moveTo(13.5f, 7f); lineTo(17f, 10.5f) }
    }

    /** 라이브러리 (꽂힌 책 3권) */
    val library: ImageVector = icon("library") {
        line {
            moveTo(4f, 4f); lineTo(4f, 20f); moveTo(8f, 4f); lineTo(8f, 20f)
            moveTo(12f, 5f); lineTo(12f, 20f)
            moveTo(14f, 5.5f); lineTo(18f, 4.5f); lineTo(21f, 19f); lineTo(17f, 20f); close()
        }
    }

    /** 가사 (음표 + 글줄) */
    val lyrics: ImageVector = icon("lyrics") {
        line { moveTo(3f, 6f); lineTo(12f, 6f); moveTo(3f, 11f); lineTo(12f, 11f); moveTo(3f, 16f); lineTo(9f, 16f); moveTo(18f, 17f); lineTo(18f, 5f); lineTo(21.5f, 6.5f) }
        fill { circle(16f, 17.5f, 2.3f) }
    }

    /** 설정 (톱니: 원 + 8 살) */
    val settings: ImageVector = icon("settings") {
        line { circle(12f, 12f, 3.2f); circle(12f, 12f, 6.8f) }
        line(2.6f) {
            moveTo(12f, 2.5f); lineTo(12f, 5f); moveTo(12f, 19f); lineTo(12f, 21.5f)
            moveTo(2.5f, 12f); lineTo(5f, 12f); moveTo(19f, 12f); lineTo(21.5f, 12f)
            moveTo(5.3f, 5.3f); lineTo(7.1f, 7.1f); moveTo(16.9f, 16.9f); lineTo(18.7f, 18.7f)
            moveTo(5.3f, 18.7f); lineTo(7.1f, 16.9f); moveTo(16.9f, 7.1f); lineTo(18.7f, 5.3f)
        }
    }

    /** 플로팅 (창 위의 작은 창) */
    val floating: ImageVector = icon("floating") {
        line { moveTo(3f, 5f); lineTo(21f, 5f); lineTo(21f, 19f); lineTo(3f, 19f); close() }
        fill { moveTo(11f, 11f); lineTo(19f, 11f); lineTo(19f, 17f); lineTo(11f, 17f); close() }
    }

    /** 잠금 (자물쇠) */
    val lock: ImageVector = icon("lock") {
        line { moveTo(5f, 11f); lineTo(19f, 11f); lineTo(19f, 20f); lineTo(5f, 20f); close(); moveTo(8f, 11f); lineTo(8f, 8f); arcTo(4f, 4f, 0f, false, true, 16f, 8f); lineTo(16f, 11f) }
    }

    /** 압축 (위아래 화살표가 가운데로) */
    val compressor: ImageVector = icon("compressor") {
        line {
            moveTo(4f, 12f); lineTo(20f, 12f)
            moveTo(12f, 3f); lineTo(12f, 9f); moveTo(9f, 6.5f); lineTo(12f, 9f); lineTo(15f, 6.5f)
            moveTo(12f, 21f); lineTo(12f, 15f); moveTo(9f, 17.5f); lineTo(12f, 15f); lineTo(15f, 17.5f)
        }
    }

    /** 리미터 (천장 선 + 눌린 파형) */
    val limiter: ImageVector = icon("limiter") {
        line(2.4f) { moveTo(3f, 5f); lineTo(21f, 5f) }
        line { moveTo(3f, 15f); lineTo(6f, 8f); lineTo(9f, 8f); lineTo(12f, 19f); lineTo(15f, 8f); lineTo(18f, 8f); lineTo(21f, 15f) }
    }

    /** 초기화 (되돌리기 화살표) */
    val reset: ImageVector = icon("reset") {
        line {
            moveTo(5f, 12f)
            arcTo(7f, 7f, 0f, true, false, 7.05f, 7.05f)
            moveTo(4f, 4f); lineTo(4f, 9f); lineTo(9f, 9f)
        }
    }

    /** 라디오 (전파) */
    val radio: ImageVector = icon("radio") {
        fill { circle(12f, 12f, 2f) }
        line {
            moveTo(8.5f, 8.5f); arcTo(5f, 5f, 0f, false, false, 8.5f, 15.5f)
            moveTo(15.5f, 8.5f); arcTo(5f, 5f, 0f, false, true, 15.5f, 15.5f)
            moveTo(5.6f, 5.6f); arcTo(9f, 9f, 0f, false, false, 5.6f, 18.4f)
            moveTo(18.4f, 5.6f); arcTo(9f, 9f, 0f, false, true, 18.4f, 18.4f)
        }
    }

    /** 하위 폴더 포함 (트리) */
    val subfolder: ImageVector = icon("subfolder") {
        line {
            moveTo(3f, 4f); lineTo(10f, 4f); lineTo(10f, 9f); lineTo(3f, 9f); close()
            moveTo(6.5f, 9f); lineTo(6.5f, 17.5f); lineTo(13f, 17.5f)
            moveTo(6.5f, 12f); lineTo(13f, 12f)
            moveTo(14f, 10f); lineTo(21f, 10f); lineTo(21f, 14f); lineTo(14f, 14f); close()
            moveTo(14f, 15.5f); lineTo(21f, 15.5f); lineTo(21f, 19.5f); lineTo(14f, 19.5f); close()
        }
    }

    /** 켬/끔 (전원) */
    val power: ImageVector = icon("power") {
        line { moveTo(12f, 3f); lineTo(12f, 11f); moveTo(7f, 6.5f); arcTo(7.5f, 7.5f, 0f, true, false, 17f, 6.5f) }
    }

    /** 저장 (아래 화살표 + 받침) */
    val save: ImageVector = icon("save") {
        line { moveTo(12f, 4f); lineTo(12f, 15f); moveTo(7.5f, 10.5f); lineTo(12f, 15f); lineTo(16.5f, 10.5f); moveTo(5f, 20f); lineTo(19f, 20f) }
    }
}
