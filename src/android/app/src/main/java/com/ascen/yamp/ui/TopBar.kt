package com.ascen.yamp.ui

import android.content.Intent
import android.net.Uri
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.RichTooltip
import androidx.compose.material3.Text
import androidx.compose.material3.TooltipBox
import androidx.compose.material3.TooltipDefaults
import androidx.compose.material3.rememberTooltipState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.ascen.yamp.BuildConfig
import com.ascen.yamp.app.AppViewModel
import com.ascen.yamp.domain.Ticker
import kotlinx.coroutines.delay

/*
 * 상단 바 (vr0.1.0.012, f23): [앱 이름] [● XRP ₩3,512 ▲1.24%] [18:56 KST] [버전] [?]
 *   - 시세: 상승 = rise(빨강) · 하락 = fall(파랑) · 보합 = dim (한국 표기), 흐림 + 회색 점 = 갱신 전/실패
 *   - 가격이 바뀌면 0.6초 반짝 (flash_rise / flash_fall), 누르면 업비트 화면, 길게 누르면 자세히
 *   - 시계: 기기 시간대와 상관없이 KST, 화면이 보일 때만 갱신 (초 표시 꺼짐 = 1분에 한 번)
 *   - 좁은 화면: 앱 이름 숨김 · 버전 'v012', 길게 누르면 전체 버전 · 빌드 시각
 */

/** 'vr0.1.0.012' → 'v012' */
fun shortVersion(name: String): String = "v" + name.substringAfterLast('.')

@Composable
fun TopBar(vm: AppViewModel, onHelp: () -> Unit, modifier: Modifier = Modifier) {
    val s = LocalSkin.current
    BoxWithConstraints(modifier.fillMaxWidth()) {
        val showTicker = vm.tickerOn
        val wide = maxWidth >= 600.dp
        val narrow = maxWidth < 400.dp
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            // 앱 이름: 넓은 화면이거나 시세 · 시계를 모두 끈 경우만 (휴대폰 세로 = 시세 자리)
            if (wide || (!showTicker && !vm.clockOn)) {
                Text(BuildConfig.APP_NAME, color = s.text, fontSize = 18.sp, fontWeight = FontWeight.Bold, maxLines = 1, softWrap = false,
                    modifier = Modifier.padding(end = 10.dp))
            }
            if (showTicker) TickerChip(vm, compact = narrow)
            Spacer(Modifier.weight(1f))
            if (vm.clockOn) KstClock(vm.uiVisible, vm.clockSeconds, Modifier.padding(horizontal = 6.dp))
            val ver = when { wide -> VERSION_LABEL; narrow -> shortVersion(BuildConfig.VERSION_NAME); else -> BuildConfig.VERSION_NAME }
            TextTip("${BuildConfig.APP_NAME} ${BuildConfig.VERSION_NAME}", { "빌드 ${BuildConfig.BUILD_TIME}\n$VERSION_LABEL" }) {
                Text(ver, color = s.dim, fontSize = 11.sp, maxLines = 1, overflow = TextOverflow.Ellipsis,
                    modifier = Modifier.padding(start = 6.dp, top = 6.dp, bottom = 6.dp))
            }
            // 도움말 (?) — 주요 버튼 이름 · 설명 모음. 처음 실행 때 한 번 저절로 열림
            IconAction(YIcons.help, "help", onHelp, Modifier.padding(start = 4.dp), size = 32.dp, iconSize = 20.dp, tint = s.dim)
        }
    }
}

/** 시세 칸: ● XRP ₩3,512 ▲1.24% — 여러 마켓이면 3초마다 번갈아 (화면이 보일 때만) */
@Composable
private fun TickerChip(vm: AppViewModel, compact: Boolean) {
    val s = LocalSkin.current
    val ctx = LocalContext.current
    val markets = vm.tickerMarkets
    var idx by remember { mutableIntStateOf(0) }
    LaunchedEffect(vm.uiVisible, markets.size) {
        while (vm.uiVisible && markets.size >= 2) {
            delay(Ticker.ROTATE_MS)
            idx = (idx + 1) % markets.size
        }
    }
    val market = markets[idx.coerceIn(0, markets.size - 1)]
    val q = vm.tickerQuotes[market]
    val stale = vm.tickerStale || q == null
    // 반짝임 (D6): 보이는 마켓의 가격이 바뀐 순간 0.6초
    var flash by remember { mutableStateOf(false) }
    LaunchedEffect(vm.tickerFlashSeq) {
        if (vm.tickerFlashSeq > 0 && vm.tickerFlashMarket == market) {
            flash = true
            delay(Ticker.FLASH_MS)
            flash = false
        }
    }
    val dirColor = when (q?.change) { "RISE" -> s.rise; "FALL" -> s.fall; else -> s.dim }
    val fg = if (stale) s.dim.copy(alpha = 0.7f) else dirColor
    val dot = if (stale) s.dim.copy(alpha = 0.45f) else dirColor
    val bg = if (flash) (if (vm.tickerFlashUp) s.flashRise else s.flashFall) else Color.Transparent
    val shape = RoundedCornerShape(8.dp)
    TextTip(if (stale) "시세 (갱신 전 · 실패)" else "시세", { vm.tickerDetail(market) }) {
        Row(Modifier.clip(shape).background(bg, shape)
            .clickable {
                runCatching {
                    ctx.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(Ticker.exchangeUrl(market))).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
                }.onFailure { vm.toast("브라우저를 열지 못했습니다") }
            }
            .padding(horizontal = 6.dp, vertical = 4.dp),
            verticalAlignment = Alignment.CenterVertically) {
            Text("●", color = dot, fontSize = 9.sp, modifier = Modifier.padding(end = 4.dp))
            val sym = q?.symbol ?: market.substringAfter("-")
            val price = q?.let { Ticker.fmtPrice(it.price) } ?: "—"
            val rate = q?.let { Ticker.fmtRate(it.change, it.changeRate) }
            Text(listOfNotNull(sym, price, rate).joinToString(" "),
                color = fg, fontSize = if (compact) 12.sp else 13.sp, fontWeight = FontWeight.Bold, maxLines = 1, softWrap = false)
        }
    }
}

/** KST 시계 — 화면이 보일 때만 갱신 (초 표시 = 1초, 아니면 다음 분에) */
@Composable
private fun KstClock(visible: Boolean, seconds: Boolean, modifier: Modifier = Modifier) {
    val s = LocalSkin.current
    var now by remember { mutableLongStateOf(System.currentTimeMillis()) }
    LaunchedEffect(visible, seconds) {
        while (visible) {
            now = System.currentTimeMillis()
            val step = if (seconds) 1000L else 60_000L
            delay(step - now % step + 5)
        }
    }
    Text(Ticker.kstLabel(now, seconds, date = false), color = s.text, fontSize = 12.sp, maxLines = 1, softWrap = false, modifier = modifier)
}

/**
 * 글 팝업 (TipBox 와 같은 TooltipBox 방식, 글은 Tips 키 대신 직접): 길게 누르기 · 마우스 올리기.
 *   isPersistent = true → 여러 줄 자세히를 읽을 수 있게 바깥을 누를 때까지 유지
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun TextTip(title: String, body: () -> String, content: @Composable () -> Unit) {
    val s = LocalSkin.current
    val shape = RoundedCornerShape(12.dp)
    TooltipBox(
        positionProvider = TooltipDefaults.rememberRichTooltipPositionProvider(6.dp),
        tooltip = {
            RichTooltip(
                modifier = Modifier.border(1.dp, s.line, shape),
                title = { Text(title, color = s.text, fontSize = 14.sp, fontWeight = FontWeight.Bold, maxLines = 1) },
                shape = shape,
                colors = TooltipDefaults.richTooltipColors(containerColor = s.tooltipBg, contentColor = s.text, titleContentColor = s.text),
            ) {
                Column { Text(body(), color = s.text, fontSize = 12.sp) }
            }
        },
        state = rememberTooltipState(isPersistent = true),
        focusable = false,
    ) { Box { content() } }
}
