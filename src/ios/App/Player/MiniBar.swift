// vr0.1.0.030 (f58): ContentView.swift 에서 나눔 — 아래 미니 플레이어
import SwiftUI

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
