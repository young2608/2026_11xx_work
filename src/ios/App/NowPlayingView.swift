// 지금 재생 (vr0.1.0.028) — 표지 · 제목 · 비주얼라이저(PC · Android 와 같은 모드) · 위치 막대 · 조작
import SwiftUI
import YampCore

struct NowPlayingView: View {
    @EnvironmentObject var player: PlayerEngine
    @EnvironmentObject var settings: AppSettings
    @Environment(\.colorScheme) private var scheme
    @State private var dragging: Double?

    var body: some View {
        let s = settings.skin(systemDark: scheme == .dark)
        VStack(spacing: 14) {
            Capsule().fill(s.line).frame(width: 40, height: 5).padding(.top, 8)
            Cover(data: player.current?.artwork, name: player.current?.title ?? "♪", size: 220, s: s)
            VStack(spacing: 4) {
                Text(player.current?.title ?? "yMp3Player").font(.title3.bold()).foregroundColor(s.text).lineLimit(1)
                Text([player.current?.artist ?? "", player.current?.album ?? ""].filter { !$0.isEmpty }.joined(separator: " · "))
                    .font(.subheadline).foregroundColor(s.dim).lineLimit(1)
            }
            .padding(.horizontal)
            // 비주얼라이저 — 모드 아이콘 (스펙트럼을 또 누르면 막대 모양 바꾸기)
            VStack(spacing: 6) {
                HStack(spacing: 4) {
                    Text("비주얼라이저").font(.caption.bold()).foregroundColor(s.dim)
                    Spacer()
                    ForEach(Self.modeIcons) { mi in
                        Button { settings.pick(mode: mi.id) } label: {
                            Image(systemName: mi.icon).font(.system(size: 14))
                                .frame(width: 30, height: 30)
                                .background(settings.visMode == mi.id ? s.fill1Soft : Color.clear)
                                .foregroundColor(settings.visMode == mi.id ? s.accentText : s.dim)
                                .clipShape(Circle())
                        }
                    }
                }
                VisualizerView(s: s).frame(height: 150)
                    .background(s.graphBg).clipShape(RoundedRectangle(cornerRadius: 10))
            }
            .padding(.horizontal)
            // 위치
            TimelineView(.periodic(from: .now, by: 0.5)) { _ in
                let pos = dragging ?? player.position()
                VStack(spacing: 2) {
                    Slider(value: Binding(get: { pos }, set: { dragging = $0 }), in: 0...max(1, player.durationS),
                           onEditingChanged: { editing in
                               if !editing, let d = dragging { player.seek(to: d); dragging = nil }
                           })
                    HStack {
                        Text(fmt(pos)); Spacer(); Text(fmt(player.durationS))
                    }
                    .font(.caption.monospacedDigit()).foregroundColor(s.dim)
                }
            }
            .padding(.horizontal)
            // 조작
            HStack(spacing: 28) {
                Button { player.shuffle.toggle() } label: {
                    Image(systemName: "shuffle").foregroundColor(player.shuffle ? s.accentText : s.dim)
                }
                Button { player.prev() } label: { Image(systemName: "backward.end.fill").font(.title2).foregroundColor(s.text) }
                Button { player.toggle() } label: {
                    Image(systemName: player.isPlaying ? "pause.fill" : "play.fill").font(.title)
                        .frame(width: 66, height: 66).background(s.playGradient).foregroundColor(s.onFill).clipShape(Circle())
                }
                Button { player.next() } label: { Image(systemName: "forward.end.fill").font(.title2).foregroundColor(s.text) }
                Button { player.repeatAll.toggle() } label: {
                    Image(systemName: "repeat").foregroundColor(player.repeatAll ? s.accentText : s.dim)
                }
            }
            Text(BuildInfo.full).font(.system(size: 10)).foregroundColor(s.dim)
            Spacer(minLength: 0)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(s.bg)
    }

    struct ModeIcon: Identifiable { let id: String; let icon: String }
    static let modeIcons = [ModeIcon(id: "bars", icon: "chart.bar.fill"), ModeIcon(id: "wave", icon: "waveform"),
                            ModeIcon(id: "radial", icon: "sun.max"), ModeIcon(id: "gram", icon: "square.grid.3x3.fill"),
                            ModeIcon(id: "chart", icon: "chart.xyaxis.line")]

    private func fmt(_ s: Double) -> String {
        let t = max(0, Int(s))
        return String(format: "%d:%02d", t / 60, t % 60)
    }
}
