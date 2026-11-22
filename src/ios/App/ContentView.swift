// 첫 화면 (vr0.1.0.028) — 곡 목록 + 아래 미니 플레이어 + 위 버전 표시 (규칙 9: 버전__빌드날짜 시간)
import SwiftUI
import UniformTypeIdentifiers
import YampCore

struct ContentView: View {
    @EnvironmentObject var lib: Library
    @EnvironmentObject var player: PlayerEngine
    @EnvironmentObject var settings: AppSettings
    @Environment(\.colorScheme) private var scheme
    @State private var importing = false
    @State private var showNow = false
    @State private var showSettings = false

    var body: some View {
        let s = settings.skin(systemDark: scheme == .dark)
        NavigationStack {
            Group {
                if lib.tracks.isEmpty {
                    EmptyHint(s: s, busy: lib.busy) { importing = true }
                } else {
                    List {
                        ForEach(Array(lib.tracks.enumerated()), id: \.element.id) { i, t in
                            Button { player.setQueue(lib.tracks, start: i) } label: {
                                TrackRow(t: t, current: player.current?.id == t.id, s: s)
                            }
                            .listRowBackground(s.surface)
                            .swipeActions {
                                Button(role: .destructive) { Task { await lib.delete(t) } } label: { Label("삭제", systemImage: "trash") }
                            }
                        }
                    }
                    .listStyle(.plain)
                    .scrollContentBackground(.hidden)
                    .refreshable { await lib.reload() }
                }
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .background(s.bg)
            .navigationTitle("yMp3Player")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Text(BuildInfo.full).font(.system(size: 10)).foregroundColor(s.dim)
                }
                ToolbarItemGroup(placement: .navigationBarTrailing) {
                    Button { importing = true } label: { Image(systemName: "plus") }
                    Button { showSettings = true } label: { Image(systemName: "gearshape") }
                }
            }
            .safeAreaInset(edge: .bottom) {
                if player.current != nil {
                    MiniBar(s: s).onTapGesture { showNow = true }
                }
            }
        }
        .tint(s.accentText)
        .fileImporter(isPresented: $importing, allowedContentTypes: [.audio], allowsMultipleSelection: true) { r in
            if case .success(let urls) = r { Task { await lib.importFiles(urls) } }
        }
        .sheet(isPresented: $showNow) {
            NowPlayingView().environmentObject(player).environmentObject(settings)
        }
        .sheet(isPresented: $showSettings) {
            SettingsView().environmentObject(settings).environmentObject(lib)
        }
        .task { await lib.reload() }
    }
}
