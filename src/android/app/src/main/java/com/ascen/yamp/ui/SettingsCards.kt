package com.ascen.yamp.ui

import android.content.Intent
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Switch
import androidx.compose.material3.SwitchDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.ascen.yamp.app.AppViewModel

// ============================================================ 설정 카드 (vr0.1.0.030 f58: SettingsTab.kt 149줄 → 카드마다 함수)
// 카드 5개 · 줄 모양 2개(켜기/끄기 · 값 ± 단계). 카드 안 내용은 이전과 같음.

/** 설정 한 줄: 이름 + 스위치 (바꾸면 bump() → 화면 다시 그리기) */
@Composable
internal fun SettingToggle(label: String, value: Boolean, bump: () -> Unit, set: (Boolean) -> Unit) {
    val s = LocalSkin.current
    Row(Modifier.fillMaxWidth().padding(vertical = 2.dp), verticalAlignment = Alignment.CenterVertically) {
        Text(label, color = s.text, fontSize = 14.sp, modifier = Modifier.weight(1f))
        Switch(value, { set(it); bump() }, colors = SwitchDefaults.colors(checkedTrackColor = s.fill1, checkedThumbColor = s.onFill))
    }
}

/** 설정 한 줄: 이름 + [-] 값 [+] */
@Composable
internal fun SettingStepper(label: String, value: String, dec: () -> Unit, inc: () -> Unit) {
    val s = LocalSkin.current
    Row(Modifier.fillMaxWidth().padding(vertical = 4.dp), verticalAlignment = Alignment.CenterVertically) {
        Text(label, color = s.text, fontSize = 14.sp, modifier = Modifier.weight(1f))
        IconAction(YIcons.minus, "step_minus", dec, framed = true, size = 36.dp, iconSize = 16.dp)
        Text(value, color = s.text, fontSize = 14.sp, textAlign = TextAlign.Center, modifier = Modifier.width(64.dp))
        IconAction(YIcons.plus, "step_plus", inc, framed = true, size = 36.dp, iconSize = 16.dp)
    }
}

// ---- 화면 — 테마 · 가사 글자 · 파형 · 스펙트럼 · 상단 바(시세 · 시계)
@Composable
internal fun SettingsViewCard(vm: AppViewModel, tick: Int, bump: () -> Unit, onSpectrum: (Boolean) -> Unit) {
    val s = LocalSkin.current
    val st = vm.store
    @Composable fun toggle(label: String, value: Boolean, set: (Boolean) -> Unit) = SettingToggle(label, value, bump, set)
    CollapsibleCard("set_view", "화면") {
        if (tick < 0) Text("")                     // Store 값 바뀐 뒤 카드 내용 다시 그리기 (카드 안에서 tick 읽기 — v030 재검)
        // vr0.1.0.011 (f19): 색 견본 칩 8개 (누르면 바로 적용) + 기기 어두운 모드 따라가기
        Text("테마", color = s.dim, fontSize = 12.sp)
        ThemePicker(vm.theme) { vm.setThemeName(it) }
        toggle("기기 어두운 모드 따라가기 (써니 → 나이트 써니, 밝은 테마 → 다크 블루)", vm.followSystemDark) { vm.setFollowSystemDark(it) }
        Text("가사 글자 크기", color = s.dim, fontSize = 12.sp)
        Row(Modifier.padding(vertical = 6.dp), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            listOf(14, 17, 20, 24).forEach { sp -> Pill("${sp}sp", on = vm.fontSp == sp, onClick = { vm.setFont(sp) }) }
        }
        toggle("파형 시크바 (곡을 한 번 읽어 모양을 그림)", st.waveform) { vm.setWaveformEnabled(it) }
        // A8: 화면 상태 — 마이크 권한을 허용하고 돌아오면 바로 켜짐으로
        toggle("스펙트럼 (마이크 권한 필요 — 녹음은 하지 않음)", vm.spectrumOn) { onSpectrum(it) }
        // vr0.1.0.012 (f23): 상단 바 — 업비트 시세 · KST 시계
        Text("상단 바", color = s.dim, fontSize = 12.sp, modifier = Modifier.padding(top = 6.dp))
        toggle("시세 표시 (업비트, ${st.tickerIntervalS}초마다 · 앱이 화면에 있을 때만)", vm.tickerOn) { vm.setTickerOn(it) }
        toggle("KST 시계 (한국 시각)", vm.clockOn) { vm.setClockOn(it) }
        toggle("초 표시", vm.clockSeconds) { vm.setClockSeconds(it) }
        var marketEdit by remember { mutableStateOf<String?>(null) }
        Row(Modifier.fillMaxWidth().padding(vertical = 2.dp), verticalAlignment = Alignment.CenterVertically) {
            Text("마켓: ${vm.tickerMarkets.joinToString(", ")}", color = s.text, fontSize = 14.sp, modifier = Modifier.weight(1f))
            TextButton({ marketEdit = vm.tickerMarkets.joinToString(",") }) { Text("바꾸기", color = s.accentText) }
        }
        marketEdit?.let { cur ->
            AlertDialog(onDismissRequest = { marketEdit = null }, title = { Text("업비트 마켓") },
                text = {
                    Column {
                        Text("마켓 코드 (쉼표로 여러 개 → 3초마다 번갈아 표시)\n예: KRW-XRP · KRW-BTC,KRW-ETH", color = s.dim, fontSize = 12.sp,
                            modifier = Modifier.padding(bottom = 8.dp))
                        SkinField(cur, { marketEdit = it }, "KRW-XRP", Modifier.fillMaxWidth())
                    }
                },
                confirmButton = { TextButton({ vm.setTickerMarket(cur); marketEdit = null }) { Text("저장", color = s.accentText) } },
                dismissButton = { TextButton({ marketEdit = null }) { Text("취소", color = s.accentText) } })
        }
    }
}

// ---- 가사 — 공급자 · 3단 가사 · 화면 켜짐 · 플로팅 · 가사 진단
@Composable
internal fun SettingsLyricsCard(vm: AppViewModel, tick: Int, bump: () -> Unit) {
    val s = LocalSkin.current
    val st = vm.store
    @Composable fun toggle(label: String, value: Boolean, set: (Boolean) -> Unit) = SettingToggle(label, value, bump, set)
    CollapsibleCard("set_lyrics", "가사") {
        if (tick < 0) Text("")                     // Store 값 바뀐 뒤 카드 내용 다시 그리기 (카드 안에서 tick 읽기 — v030 재검)
        Text("공급자 (캐시 → .lrc → 알송 ‖ LRCLIB ‖ NetEase 동시 · ${st.lyricsMinScore}점 이상 자동 적용)", color = s.dim, fontSize = 12.sp)
        toggle("같은 폴더 .lrc (Android 11+ 는 제한)", st.useLocal) { st.useLocal = it }
        toggle("알송 (비공식, 개인 사용)", st.useAlsong) { st.useAlsong = it }
        toggle("LRCLIB", st.useLrclib) { st.useLrclib = it }
        toggle("NetEase (비공식, K-pop·J-pop·번역 가사)", st.useNetease) { st.useNetease = it }
        toggle("3단 가사: 발음 줄 (블록 2번째 줄)", vm.showPron) { vm.setTiers(it, vm.showTrans) }
        toggle("3단 가사: 번역 줄 (블록 3번째 줄)", vm.showTrans) { vm.setTiers(vm.showPron, it) }
        toggle("가사 탭에서 화면 꺼짐 방지", st.keepScreenOnLyrics) { st.keepScreenOnLyrics = it }
        val ctx = LocalContext.current
        toggle("플로팅 가사 (다른 앱 위에 표시)", st.floatingLyrics && Floating.canDraw(ctx)) { Floating.set(ctx, vm, it) }
        // vr0.1.0.011 (f18 L8): 가사 진단 — 지금 곡으로 전체 찾기 기록 (공유 · log/lyrics_diag_*.txt)
        Row(Modifier.padding(top = 4.dp), verticalAlignment = Alignment.CenterVertically) {
            TextButton({ vm.runLyricsDiag() }, enabled = !vm.lyricsDiagRunning) {
                Text(if (vm.lyricsDiagRunning) "가사 진단 중…" else "가사 진단", color = s.accentText)
            }
            Text("지금 곡의 가사가 안 나오는 이유 확인", color = s.dim, fontSize = 11.sp)
        }
        vm.lyricsDiagText?.let { txt ->
            AlertDialog(onDismissRequest = { vm.closeLyricsDiag() }, title = { Text("가사 진단") },
                text = {
                    Column(Modifier.heightIn(max = 420.dp).verticalScroll(rememberScrollState())) {
                        if (vm.lyricsDiagFile.isNotEmpty()) Text("저장: ${vm.lyricsDiagFile}", color = s.dim, fontSize = 11.sp)
                        Text(txt, color = s.text, fontSize = 11.sp, fontFamily = FontFamily.Monospace)
                    }
                },
                confirmButton = {
                    TextButton({
                        runCatching {
                            val send = Intent(Intent.ACTION_SEND).setType("text/plain").putExtra(Intent.EXTRA_TEXT, txt)
                                .putExtra(Intent.EXTRA_SUBJECT, "yAmp 가사 진단")
                            ctx.startActivity(Intent.createChooser(send, "가사 진단 보내기").addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
                        }.onFailure { vm.toast("공유할 앱을 열지 못했습니다") }
                    }) { Text("공유", color = s.accentText) }
                },
                dismissButton = { TextButton({ vm.closeLyricsDiag() }) { Text("닫기", color = s.accentText) } })
        }
    }
}

// ---- 재생 — 이어 듣기 · 무음 건너뛰기 · ReplayGain · 프리앰프 · 페이드
@Composable
internal fun SettingsPlayCard(vm: AppViewModel, tick: Int, bump: () -> Unit) {
    val s = LocalSkin.current
    val st = vm.store
    @Composable fun toggle(label: String, value: Boolean, set: (Boolean) -> Unit) = SettingToggle(label, value, bump, set)
    @Composable fun stepper(label: String, value: String, dec: () -> Unit, inc: () -> Unit) = SettingStepper(label, value, dec, inc)
    CollapsibleCard("set_play", "재생") {
        if (tick < 0) Text("")                     // Store 값 바뀐 뒤 카드 내용 다시 그리기 (카드 안에서 tick 읽기 — v030 재검)
        toggle("시작 시 이어 듣기", st.resume) { st.resume = it }
        // vr0.1.0.010 음성 파일: V2 파일별 이어 듣기 · V1 무음 건너뛰기
        toggle("30분 넘는 파일은 파일마다 멈춘 곳부터 (오디오북 · 강의)", vm.resumeLong) { vm.setResumeLong(it) }
        toggle("무음 건너뛰기 (녹음 · 강의의 긴 무음)", vm.skipSilence) { vm.setSkipSilence(it) }
        Text("ReplayGain 볼륨 보정", color = s.dim, fontSize = 12.sp, modifier = Modifier.padding(top = 6.dp))
        Row(Modifier.padding(vertical = 6.dp), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            listOf("off" to "끔", "track" to "곡", "album" to "앨범").forEach { (k, label) ->
                Pill(label, on = st.replayGain == k, onClick = { vm.setReplayGain(k); bump() })
            }
        }
        stepper("프리앰프 (ReplayGain)", "${"%+d".format(st.preampDb)} dB", { vm.setPreamp((st.preampDb - 1).coerceAtLeast(-12)); bump() },
            { vm.setPreamp((st.preampDb + 1).coerceAtMost(12)); bump() })
        Text("※ 휴대폰 플레이어 볼륨은 최대 100% — 소리를 키우는 보정은 적용되지 않고 줄이는 보정만 적용됩니다 (키우려면 사운드 → 프리앰프)",
            color = s.dim, fontSize = 11.sp)
        stepper("곡 전환 페이드 (겹치지 않음)", if (st.crossfadeS == 0) "끔" else "${st.crossfadeS}초",
            { vm.setCrossfade((st.crossfadeS - 1).coerceAtLeast(0)); bump() },
            { vm.setCrossfade((st.crossfadeS + 1).coerceAtMost(12)); bump() })
        stepper("슬립 타이머 페이드", "${st.sleepFadeS}초", { vm.setSleepFade((st.sleepFadeS - 10).coerceAtLeast(0)); bump() },
            { vm.setSleepFade((st.sleepFadeS + 10).coerceAtMost(120)); bump() })
    }
}

// ---- 재생 기록 · 추천 — 기록 남기기 · 지우기
@Composable
internal fun SettingsHistoryCard(vm: AppViewModel, tick: Int, bump: () -> Unit) {
    val s = LocalSkin.current
    val st = vm.store
    @Composable fun toggle(label: String, value: Boolean, set: (Boolean) -> Unit) = SettingToggle(label, value, bump, set)
    CollapsibleCard("set_history", "재생 기록 · 추천 (기기 안에만 저장)") {
        if (tick < 0) Text("")                     // Store 값 바뀐 뒤 카드 내용 다시 그리기 (카드 안에서 tick 읽기 — v030 재검)
        toggle("재생 기록 남기기", st.historyEnabled) { vm.setHistoryEnabled(it) }
        var confirmHist by remember { mutableStateOf(false) }
        Row(Modifier.padding(vertical = 6.dp), verticalAlignment = Alignment.CenterVertically) {
            IconAction(YIcons.trash, "history_clear", { confirmHist = true }, framed = true, size = 38.dp, iconSize = 20.dp)
            Spacer(Modifier.width(8.dp))
            Text("기록 ${vm.historyCount}건", color = s.dim, fontSize = 12.sp)
        }
        if (confirmHist) AlertDialog(onDismissRequest = { confirmHist = false }, title = { Text("재생 기록 지우기") },
            text = { Text("재생 기록과 재생/넘김 횟수를 모두 지울까요?\n(좋아요·별점과 음악 파일은 그대로입니다)") },
            confirmButton = { TextButton({ vm.clearHistory(); confirmHist = false }) { Text("지우기") } },
            dismissButton = { TextButton({ confirmHist = false }) { Text("취소") } })
    }
}

// ---- 정보 — 버전 · config.txt · 로그 보내기 · 지원 형식
@Composable
internal fun SettingsAboutCard(vm: AppViewModel, tick: Int, bump: () -> Unit) {
    val s = LocalSkin.current
    val st = vm.store
    CollapsibleCard("set_about", "정보") {
        if (tick < 0) Text("")                     // Store 값 바뀐 뒤 카드 내용 다시 그리기 (카드 안에서 tick 읽기 — v030 재검)
        Text("${com.ascen.yamp.BuildConfig.APP_NAME} $VERSION_LABEL", color = s.text, fontSize = 14.sp)
        Text("config.txt: ${st.cfg.file.path}\n로그: ${st.logDir.path}  (NN__YYYY__MMDD.txt, ${st.cfg.int("log_max_size_kb")}KB × ${st.cfg.int("log_max_files")}개)\nconfig.txt 를 고친 뒤 앱을 다시 시작하면 적용됩니다.",
            color = s.dim, fontSize = 11.sp, modifier = Modifier.padding(top = 4.dp))
        // vr0.1.0.013: 로그 보내기 — 앱 로그 · 최근 비정상 종료 보고서 · logcat 을 메일 · 메신저로
        val ctxLog = LocalContext.current
        Row(Modifier.padding(top = 4.dp), verticalAlignment = Alignment.CenterVertically) {
            TextButton({
                runCatching { com.ascen.yamp.core.LogShare.share(ctxLog, st.logDir) }
                    .onFailure { vm.toast("보낼 앱이 없습니다") }
            }) { Text("로그 보내기", color = s.accentText) }
            Text("문제가 있을 때 앱 로그 · 오류 보고서를 메일 · 메신저로", color = s.dim, fontSize = 11.sp)
        }
        Text("Winamp 컨셉 음악 플레이어 + 싱크 가사\n재생 형식: MP3 · FLAC · WAV · AAC/M4A/M4B · Ogg · Opus · MKA · WebM · AMR/3GP (+ CUE 시트)\n재생 목록 읽기: M3U · M3U8 · PLS · XSPF · WPL (파일 추가)\n가사는 저작물입니다. 캐시는 개인 사용 목적으로만 저장됩니다.",
            color = s.dim, fontSize = 12.sp, modifier = Modifier.padding(top = 4.dp))
    }
}
