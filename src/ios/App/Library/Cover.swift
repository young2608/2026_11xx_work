// vr0.1.0.030 (f58): ContentView.swift 에서 나눔 — 표지
import SwiftUI
import UIKit

/// 표지 (없으면 테마 색 그라데이션 + 첫 글자, PC · Android 와 같은 모양)
struct Cover: View {
    let data: Data?
    let name: String
    let size: CGFloat
    let s: Skin
    private var initial: String {
        let c = String(name.trimmingCharacters(in: .whitespaces).prefix(1)).uppercased()
        return c.isEmpty ? "♪" : c
    }
    var body: some View {
        Group {
            if let d = data, let img = UIImage(data: d) {
                Image(uiImage: img).resizable().scaledToFill()
            } else {
                ZStack {
                    s.playGradient
                    Text(initial)
                        .font(.system(size: size * 0.42, weight: .bold)).foregroundColor(s.onFill.opacity(0.6))
                }
            }
        }
        .frame(width: size, height: size)
        .clipShape(RoundedRectangle(cornerRadius: size * 0.16))
    }
}
