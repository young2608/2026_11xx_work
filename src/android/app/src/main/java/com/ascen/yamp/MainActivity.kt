package com.ascen.yamp

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import androidx.core.content.ContextCompat
import com.ascen.yamp.app.AppViewModel
import com.ascen.yamp.core.CrashCatcher
import com.ascen.yamp.core.CrashReport
import com.ascen.yamp.ui.MainScreen

class MainActivity : ComponentActivity() {
    private val vm: AppViewModel by viewModels()

    private val audioPerm = if (Build.VERSION.SDK_INT >= 33) Manifest.permission.READ_MEDIA_AUDIO
    else Manifest.permission.READ_EXTERNAL_STORAGE

    private var afterAudioPerm: (() -> Unit)? = null
    private var deniedAudioPerm: (() -> Unit)? = null
    private val reqAudio = registerForActivityResult(ActivityResultContracts.RequestPermission()) { ok ->
        if (ok) afterAudioPerm?.invoke() else deniedAudioPerm?.invoke()
        afterAudioPerm = null
        deniedAudioPerm = null
    }
    private val reqMic = registerForActivityResult(ActivityResultContracts.RequestPermission()) { ok ->
        vm.setSpectrum(ok)
    }
    private val reqNotif = registerForActivityResult(ActivityResultContracts.RequestPermission()) { }
    private val pickFiles = registerForActivityResult(ActivityResultContracts.OpenMultipleDocuments()) { uris ->
        if (uris.isNotEmpty()) vm.addUris(uris)
    }
    /** 폴더 추가 (F4): SAF 폴더 트리 → 읽기 권한 유지 */
    private val pickTree = registerForActivityResult(ActivityResultContracts.OpenDocumentTree()) { uri ->
        if (uri != null) vm.addSafTree(uri)
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        // vr0.1.0.013: 지난번 비정상 종료 보고서를 아직 못 봤으면 (재생 서비스 등 화면 밖에서 종료) 보고서 화면 먼저
        if (savedInstanceState == null) CrashCatcher.pending(this)?.let { f ->
            runCatching {
                startActivity(Intent(this, CrashActivity::class.java).putExtra(CrashCatcher.EXTRA_FILE, f.absolutePath))
            }
            CrashCatcher.clearPending(this)
        }
        // 15초 넘게 정상이면 '시작하자마자 연속 종료' 수를 0 으로
        window.decorView.postDelayed({ CrashCatcher.markHealthy(this) }, CrashReport.START_WINDOW_MS)
        if (Build.VERSION.SDK_INT >= 33 && !granted(Manifest.permission.POST_NOTIFICATIONS)) {
            reqNotif.launch(Manifest.permission.POST_NOTIFICATIONS)
        }
        // A2: 화면 회전 등으로 다시 만들어질 때는 같은 "열기" 요청을 또 처리하지 않음 (처음 생성 때만)
        if (savedInstanceState == null) handleViewIntent(intent)
        setContent {
            MainScreen(
                vm = vm,
                onScanAll = { withAudioPerm { vm.scanAll() } },
                // vr0.1.0.010: 재생 목록 파일(m3u · pls · xspf · wpl)도 고를 수 있게
                onPickFiles = { pickFiles.launch(PICK_MIME) },
                onSpectrum = { on ->
                    if (!on) vm.setSpectrum(false)
                    else if (granted(Manifest.permission.RECORD_AUDIO)) vm.setSpectrum(true)
                    else reqMic.launch(Manifest.permission.RECORD_AUDIO)
                },
                onAddFolder = {
                    runCatching { pickTree.launch(null) }.onFailure { vm.toast("폴더 선택 화면을 열 수 없습니다") }
                },
                // 폴더 새로고침: 음악 권한이 있으면 MediaStore + 추가 폴더, 거부하면 추가 폴더만
                onRefreshFolders = { withAudioPerm({ vm.refreshFolders(false) }) { vm.refreshFolders(true) } },
            )
        }
    }

    // 화면이 보이는 동안만 빠른 위치 폴링 · 스펙트럼 (vr0.1.0.007 — 백그라운드 · 화면 꺼짐에서 배터리 절약)
    override fun onStart() {
        super.onStart()
        vm.setUiVisible(true)
    }

    override fun onStop() {
        vm.setUiVisible(false)
        super.onStop()
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        handleViewIntent(intent)
    }

    /** 파일 앱에서 "yMp3Player 로 열기" */
    private fun handleViewIntent(i: Intent?) {
        if (i?.action == Intent.ACTION_VIEW) i.data?.let { vm.addUris(listOf(it)) }
    }

    companion object {
        /** 파일 추가 고르기 형식: 오디오 + 재생 목록 */
        private val PICK_MIME = arrayOf("audio/*", "application/x-mpegurl", "application/vnd.apple.mpegurl",
            "application/xspf+xml", "application/vnd.ms-wpl", "application/pls+xml")
    }

    private fun granted(p: String) = ContextCompat.checkSelfPermission(this, p) == PackageManager.PERMISSION_GRANTED

    private fun withAudioPerm(denied: (() -> Unit)? = null, block: () -> Unit) {
        if (granted(audioPerm)) block() else {
            afterAudioPerm = block
            deniedAudioPerm = denied
            reqAudio.launch(audioPerm)
        }
    }
}
