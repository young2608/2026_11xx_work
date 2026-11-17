package com.ascen.yamp

import android.app.Application
import com.ascen.yamp.core.CrashCatcher

/** 앱 시작 (vr0.1.0.013): 가장 먼저 비정상 종료 잡기 설치 — 화면 · 재생 서비스 · 위젯 어디서 죽어도 보고서를 남김 */
class YampApp : Application() {
    override fun onCreate() {
        super.onCreate()
        CrashCatcher.install(this)
    }
}
