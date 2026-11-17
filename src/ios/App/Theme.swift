// 테마 색 (vr0.1.0.028) — YampCore.ThemeTable(= src/testdata/themes.txt) 의 토큰을 SwiftUI Color 로
import SwiftUI
import YampCore

struct Skin {
    let def: ThemeDef
    init(_ def: ThemeDef) { self.def = def }

    func c(_ token: String, _ alpha: Double = 1) -> Color {
        let v = def.rgb(token)
        return Color(.sRGB, red: Double((v >> 16) & 0xFF) / 255, green: Double((v >> 8) & 0xFF) / 255,
                     blue: Double(v & 0xFF) / 255, opacity: alpha)
    }

    /// 두 토큰 사이 색 (t = 0..1)
    func mix(_ a: String, _ b: String, _ t: Double) -> Color {
        let x = def.rgb(a), y = def.rgb(b)
        func ch(_ sh: UInt32) -> Double {
            let p = Double((x >> sh) & 0xFF), q = Double((y >> sh) & 0xFF)
            return (p + (q - p) * min(1, max(0, t))) / 255
        }
        return Color(.sRGB, red: ch(16), green: ch(8), blue: ch(0), opacity: 1)
    }

    var dark: Bool { def.dark }
    var bg: Color { c("bg") }
    var surface: Color { c("surface") }
    var surface2: Color { c("surface2") }
    var nav: Color { c("nav") }
    var line: Color { c("line") }
    var text: Color { c("text") }
    var dim: Color { c("dim") }
    var fill1: Color { c("fill1") }
    var fill1Soft: Color { c("fill1_soft") }
    var fill2: Color { c("fill2") }
    var accentText: Color { c("accent_text") }
    var onFill: Color { c("on_fill") }
    var lcdFg: Color { c("lcd_fg") }
    var graphBg: Color { c("graph_bg") }
    var graphGrid: Color { c("graph_grid") }
    var wavePlayed: Color { c("wave_played") }
    var waveRest: Color { c("wave_rest") }
    var spectrumLo: Color { c("spectrum_lo") }
    var spectrumHi: Color { c("spectrum_hi") }
    var peak: Color { c("peak") }
    var playGradient: LinearGradient {
        LinearGradient(colors: [fill1, fill2], startPoint: .topLeading, endPoint: .bottomTrailing)
    }
}
