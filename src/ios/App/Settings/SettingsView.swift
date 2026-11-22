// vr0.1.0.030 (f58): ContentView.swift 에서 나눔 — 설정 화면
import SwiftUI
import YampCore

struct SettingsView: View {
    @EnvironmentObject var settings: AppSettings
    @EnvironmentObject var lib: Library
    @Environment(\.dismiss) private var dismiss
    var body: some View {
        NavigationStack {
            Form {
                Section("테마") {
                    Picker("테마", selection: $settings.theme) {
                        ForEach(ThemeTable.all, id: \.name) { t in Text(t.label).tag(t.name) }
                    }
                    Toggle("어두운 모드 따라가기", isOn: $settings.followDark)
                }
                Section("곡") {
                    Text("곡 \(lib.tracks.count)개 · 앱 폴더: 파일 앱 → 나의 iPhone → yMp3Player").font(.footnote)
                    Button("다시 찾기") { Task { await lib.reload() } }
                }
                Section("정보") {
                    Text("yMp3Player \(BuildInfo.full)").font(.footnote)
                }
            }
            .navigationTitle("설정")
            .toolbar { ToolbarItem(placement: .confirmationAction) { Button("닫기") { dismiss() } } }
        }
    }
}
