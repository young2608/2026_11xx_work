// vr0.1.0.030 (f58): ContentView.swift 에서 나눔 — 곡 목록 한 줄
import SwiftUI

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
