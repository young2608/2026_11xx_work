// yMp3Player iOS (vr0.1.0.028, f55) — 앱 시작점
//   Library(곡 목록: 앱 Documents 폴더) · PlayerEngine(재생 · 스펙트럼 · 잠금화면) · AppSettings(테마 · 비주얼라이저)
import SwiftUI
import YampCore

@main
struct YampApp: App {
    @StateObject private var library = Library()
    @StateObject private var player = PlayerEngine()
    @StateObject private var settings = AppSettings()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(library)
                .environmentObject(player)
                .environmentObject(settings)
        }
    }
}
