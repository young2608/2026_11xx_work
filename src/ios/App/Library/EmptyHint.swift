// vr0.1.0.030 (f58): ContentView.swift 에서 나눔 — 곡이 없을 때 안내
import SwiftUI

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
