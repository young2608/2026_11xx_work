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

struct TrackRow: View {
    let t: Track
    let current: Bool
    let s: Skin
    var body: some View {
        HStack(spacing: 12) {
            Cover(data: t.artwork, name: t.album.isEmpty ? t.title : t.album, size: 44, s: s)
            VStack(alignment: .leading, spacing: 2) {
                Text(t.title).font(.body.weight(current ? .bold : .regular))
                    .foregroundColor(current ? s.accentText : s.text).lineLimit(1)
                Text([t.artist, t.album].filter { !$0.isEmpty }.joined(separator: " · "))
                    .font(.caption).foregroundColor(s.dim).lineLimit(1)
            }
            Spacer(minLength: 0)
        }
        .padding(.vertical, 2)
    }
}

/// 표지 (없으면 테마 색 그라데이션 + 첫 글자, PC · Android 와 같은 모양)
struct Cover: View {
    let data: Data?
    let name: String
    let size: CGFloat
    let s: Skin
    var body: some View {
        Group {
            if let d = data, let img = UIImage(data: d) {
                Image(uiImage: img).resizable().scaledToFill()
            } else {
                ZStack {
                    s.playGradient
                    Text(String(name.trimmingCharacters(in: .whitespaces).prefix(1)).uppercased().isEmpty ? "♪" :
                            String(name.trimmingCharacters(in: .whitespaces).prefix(1)).uppercased())
                        .font(.system(size: size * 0.42, weight: .bold)).foregroundColor(s.onFill.opacity(0.6))
                }
            }
        }
        .frame(width: size, height: size)
        .clipShape(RoundedRectangle(cornerRadius: size * 0.16))
    }
}

struct EmptyHint: View {
    let s: Skin
    let busy: Bool
    let onImport: () -> Void
    var body: some View {
        VStack(spacing: 14) {
            Cover(data: nil, name: "♪", size: 120, s: s)
            Text("yMp3Player").font(.title2.bold()).foregroundColor(s.text)
            Text(busy ? "곡 찾는 중…" : "음악 파일을 넣어 주세요").foregroundColor(s.dim)
            Button(action: onImport) {
                Label("파일 가져오기", systemImage: "plus")
                    .padding(.horizontal, 18).padding(.vertical, 10)
                    .background(s.playGradient).foregroundColor(s.onFill).clipShape(Capsule())
            }
            Text("또는 파일 앱 → 나의 iPhone → yMp3Player 폴더에 복사").font(.footnote).foregroundColor(s.dim)
        }
        .padding()
    }
}

/// 아래 미니 플레이어 (누르면 지금 재생)
struct MiniBar: View {
    @EnvironmentObject var player: PlayerEngine
    let s: Skin
    var body: some View {
        HStack(spacing: 12) {
            Cover(data: player.current?.artwork, name: player.current?.title ?? "♪", size: 40, s: s)
            VStack(alignment: .leading, spacing: 1) {
                Text(player.current?.title ?? "").font(.subheadline.bold()).foregroundColor(s.text).lineLimit(1)
                Text(player.current?.artist ?? "").font(.caption).foregroundColor(s.dim).lineLimit(1)
            }
            Spacer(minLength: 0)
            Button { player.toggle() } label: {
                Image(systemName: player.isPlaying ? "pause.fill" : "play.fill")
                    .frame(width: 40, height: 40).background(s.playGradient).foregroundColor(s.onFill).clipShape(Circle())
            }
            Button { player.next() } label: { Image(systemName: "forward.end.fill").foregroundColor(s.text) }
        }
        .padding(.horizontal, 14).padding(.vertical, 8)
        .background(s.nav.overlay(Rectangle().frame(height: 1).foregroundColor(s.line), alignment: .top))
    }
}

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
