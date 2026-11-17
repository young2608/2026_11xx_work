// 비주얼라이저 (vr0.1.0.028, f55) — PC vis_draw.py · Android NeonSpectrum/GramView 와 같은 모양 · 같은 움직임(BandSmoother)
//   스펙트럼(둥근 · LED · 미러 · 반사) · 웨이브 · 원형 · 스펙트로그램 · 레벨
//   TimelineView(.animation) 로 그림 — 재생이 멈추고 막대가 다 내려앉으면 멈춤
import SwiftUI
import YampCore

/// 프레임 사이 상태 (class — 그리기 중 갱신)
final class VisState: ObservableObject {
    let sm = BandSmoother(VisMath.bands)
    let gram = GramHistory()
    var last: Date?
    var gramAcc = 0.0
    var seen: [Float] = []
    var hist: [(Float, Float)] = []          // 레벨: (RMS, 피크) 최근 10초
    var histAcc = 0.0

    func tick(_ now: Date, levels: [Float], rms: Float, peak: Float, playing: Bool, gramOn: Bool) {
        let dt = last.map { now.timeIntervalSince($0) } ?? (1.0 / 30)
        last = now
        if levels != seen { sm.setTarget(levels); seen = levels }
        sm.step(dt)
        guard playing else { return }
        gramAcc += dt
        while gramAcc >= 0.033 {
            gramAcc -= 0.033
            if gramOn { gram.push(sm.v) }
            hist.append((rms, peak))
            if hist.count > 300 { hist.removeFirst(hist.count - 300) }
        }
    }
}

struct VisualizerView: View {
    @EnvironmentObject var player: PlayerEngine
    @EnvironmentObject var settings: AppSettings
    @StateObject private var st = VisState()
    let s: Skin

    var body: some View {
        TimelineView(.animation(minimumInterval: 1.0 / 30, paused: !player.isPlaying && st.sm.idle())) { ctx in
            Canvas { gc, size in
                st.tick(ctx.date, levels: player.levels, rms: player.rms, peak: player.peak,
                        playing: player.isPlaying, gramOn: settings.visMode == "gram")
                let r = CGRect(origin: .zero, size: size).insetBy(dx: 8, dy: 6)
                switch settings.visMode {
                case "wave": drawWave(gc, r)
                case "radial": drawRadial(gc, r)
                case "gram": drawGram(gc, r)
                case "chart": drawChart(gc, r)
                default: drawBars(gc, r, settings.barStyle)
                }
            }
        }
    }

    private func vGrad(_ r: CGRect) -> GraphicsContext.Shading {
        .linearGradient(Gradient(colors: [s.spectrumLo, s.spectrumHi]), startPoint: CGPoint(x: 0, y: r.maxY), endPoint: CGPoint(x: 0, y: r.minY))
    }

    // MARK: 스펙트럼 막대 (round · led · mirror · reflex)
    private func drawBars(_ gc: GraphicsContext, _ r: CGRect, _ style: String) {
        var v = st.sm.v, pk = st.sm.peaks
        if style == "mirror" {
            let o = VisMath.mirrorOrder(v.count)
            v = o.map { v[$0] }; pk = o.map { pk[$0] }
        }
        let n = v.count
        guard n > 0 else { return }
        let slot = r.width / CGFloat(n)
        let gap = max(style == "mirror" ? 1.5 : 2, slot * 0.28)
        let w = slot - gap
        let base = style == "reflex" ? r.minY + r.height * 0.7 : r.maxY
        let hmax = base - r.minY - 4
        let shade = vGrad(CGRect(x: r.minX, y: r.minY, width: r.width, height: base - r.minY))
        for i in 0..<n {
            let x = r.minX + CGFloat(i) * slot + gap / 2
            let top = max(v[i], pk[i])
            if style == "led" {
                let cell = CGFloat(VisMath.ledCell), cg: CGFloat = 2
                let total = max(1, Int((hmax + cg) / (cell + cg)))
                let lit = VisMath.ledCells(v[i], Double(hmax), Double(cell), Double(cg))
                let topOn = VisMath.ledCells(top, Double(hmax), Double(cell), Double(cg))
                for c in 0..<total {
                    let y = r.maxY - CGFloat(c + 1) * (cell + cg) + cg
                    let rect = CGRect(x: x, y: y, width: w, height: cell)
                    if c < lit { gc.fill(Path(rect), with: shade) }
                    else if c == topOn - 1 && topOn > lit { gc.fill(Path(rect), with: .color(s.peak)) }
                    else { gc.fill(Path(rect), with: .color(s.graphGrid)) }
                }
                continue
            }
            let h = max(2, CGFloat(v[i]) * hmax)
            gc.fill(Path(roundedRect: CGRect(x: x, y: base - h, width: w, height: h), cornerRadius: min(3, w / 2)), with: shade)
            if style == "reflex" {
                let rh = min(r.maxY - base - 1, h * 0.45)
                if rh > 0 { gc.fill(Path(CGRect(x: x, y: base + 1, width: w, height: rh)), with: .color(s.c("spectrum_lo", 0.25))) }
            }
            let py = base - CGFloat(top) * hmax - 3
            gc.fill(Path(CGRect(x: x, y: py, width: w, height: 2)), with: .color(s.peak))
        }
        if style == "reflex" {
            var p = Path(); p.move(to: CGPoint(x: r.minX, y: base)); p.addLine(to: CGPoint(x: r.maxX, y: base))
            gc.stroke(p, with: .color(s.graphGrid), lineWidth: 1)
        }
    }

    // MARK: 웨이브 (Catmull-Rom 곡선, 위아래 대칭)
    private func curve(_ vals: [Double], _ r: CGRect, mid: CGFloat, amp: CGFloat, close: Bool) -> Path {
        let pts = [0.0] + vals + [0.0]
        let cnt = pts.count
        func x(_ j: Int) -> CGFloat { r.minX + r.width * CGFloat(min(max(j, 0), cnt - 1)) / CGFloat(cnt - 1) }
        func y(_ j: Int) -> Double { (j <= 0 || j >= cnt - 1) ? 0 : pts[j] }
        var p = Path()
        p.move(to: CGPoint(x: r.minX, y: mid))
        for i in 0..<(cnt - 1) {
            let c1 = CGPoint(x: x(i) + (x(i + 1) - x(i - 1)) / 6, y: mid + CGFloat(max(0, y(i) + (y(i + 1) - y(i - 1)) / 6)) * amp)
            let c2 = CGPoint(x: x(i + 1) - (x(i + 2) - x(i)) / 6, y: mid + CGFloat(max(0, y(i + 1) - (y(i + 2) - y(i)) / 6)) * amp)
            p.addCurve(to: CGPoint(x: x(i + 1), y: mid + CGFloat(y(i + 1)) * amp), control1: c1, control2: c2)
        }
        if close { p.closeSubpath() }
        return p
    }

    private func drawWave(_ gc: GraphicsContext, _ r: CGRect) {
        let mid = r.midY, amp = r.height / 2 - 2
        let fill = GraphicsContext.Shading.linearGradient(Gradient(colors: [s.spectrumHi, s.spectrumLo, s.spectrumHi]),
                                                          startPoint: CGPoint(x: 0, y: r.minY), endPoint: CGPoint(x: 0, y: r.maxY))
        for sign: CGFloat in [-1, 1] {
            gc.fill(curve(st.sm.v, r, mid: mid, amp: amp * sign, close: true), with: fill)
            gc.stroke(curve(st.sm.v, r, mid: mid, amp: amp * sign, close: false), with: .color(s.wavePlayed), lineWidth: 1.6)
            gc.stroke(curve(st.sm.peaks, r, mid: mid, amp: amp * sign, close: false), with: .color(s.c("peak", 0.45)), lineWidth: 1)
        }
        var p = Path(); p.move(to: CGPoint(x: r.minX, y: mid)); p.addLine(to: CGPoint(x: r.maxX, y: mid))
        gc.stroke(p, with: .color(s.graphGrid), lineWidth: 1)
    }

    // MARK: 원형 (12시 = 낮은 소리, 좌우 대칭, 점 = 꼭대기)
    private func drawRadial(_ gc: GraphicsContext, _ r: CGRect) {
        let v = st.sm.v, pk = st.sm.peaks
        let n = v.count
        let c = CGPoint(x: r.midX, y: r.midY)
        let side = min(r.width, r.height)
        let r0 = side * 0.16, span = side * 0.32 - 4
        gc.fill(Path(ellipseIn: CGRect(x: c.x - r0 + 2, y: c.y - r0 + 2, width: 2 * r0 - 4, height: 2 * r0 - 4)), with: .color(s.fill1Soft))
        let m = 2 * n
        let bw = max(2, 2 * .pi * r0 / CGFloat(m) * 0.55)
        for j in 0..<m {
            let i = j < n ? j : m - 1 - j
            let a = -Double.pi / 2 + 2 * Double.pi * (Double(j) + 0.5) / Double(m)
            let ca = CGFloat(cos(a)), sa = CGFloat(sin(a))
            let ln = max(2, CGFloat(v[i]) * span)
            var p = Path()
            p.move(to: CGPoint(x: c.x + ca * r0, y: c.y + sa * r0))
            p.addLine(to: CGPoint(x: c.x + ca * (r0 + ln), y: c.y + sa * (r0 + ln)))
            gc.stroke(p, with: .color(s.mix("spectrum_lo", "spectrum_hi", v[i])), style: StrokeStyle(lineWidth: bw, lineCap: .round))
            let d = r0 + CGFloat(max(v[i], pk[i])) * span + bw
            let dot = bw * 0.45
            gc.fill(Path(ellipseIn: CGRect(x: c.x + ca * d - dot, y: c.y + sa * d - dot, width: 2 * dot, height: 2 * dot)), with: .color(s.peak))
        }
    }

    // MARK: 스펙트로그램 (오른쪽에서 들어와 왼쪽으로, 아래 = 낮은 소리)
    private func drawGram(_ gc: GraphicsContext, _ r: CGRect) {
        let g = st.gram
        let cols = g.cols, n = g.n
        let stops: [UInt32] = s.dark
            ? [s.def.rgb("graph_bg"), s.def.rgb("spectrum_lo"), s.def.rgb("spectrum_hi"), s.def.rgb("peak")]
            : [s.def.rgb("graph_bg"), s.def.rgb("spectrum_hi"), s.def.rgb("spectrum_lo"), s.def.rgb("peak")]
        var px = [UInt8](repeating: 255, count: cols * n * 4)
        let off = cols - g.size
        for x in 0..<cols {
            for b in 0..<n {
                let v: Double = x < off ? 0 : Double(g.at(x - off, b))
                let (rr, gg, bb) = VisMath.heatRGB(v, stops)
                let o = ((n - 1 - b) * cols + x) * 4
                px[o] = rr; px[o + 1] = gg; px[o + 2] = bb; px[o + 3] = 255
            }
        }
        guard let prov = CGDataProvider(data: Data(px) as CFData),
              let img = CGImage(width: cols, height: n, bitsPerComponent: 8, bitsPerPixel: 32, bytesPerRow: cols * 4,
                                space: CGColorSpaceCreateDeviceRGB(), bitmapInfo: CGBitmapInfo(rawValue: CGImageAlphaInfo.noneSkipLast.rawValue),
                                provider: prov, decode: nil, shouldInterpolate: true, intent: .defaultIntent) else { return }
        gc.draw(Image(decorative: img, scale: 1), in: r)
    }

    // MARK: 레벨 (최근 10초: 면 = RMS, 선 = 피크, 눈금 -6 · -12 · -24 · -48 dB)
    private func drawChart(_ gc: GraphicsContext, _ r: CGRect) {
        func yOf(_ v: Float) -> CGFloat {
            let db = v <= 0.001 ? -60 : max(-60, 20 * log10(Double(v)))
            return r.minY + r.height * CGFloat(min(0, db) / -60)
        }
        for db in [-6.0, -12, -24, -48] {
            let y = r.minY + r.height * CGFloat(db / -60)
            var p = Path(); p.move(to: CGPoint(x: r.minX, y: y)); p.addLine(to: CGPoint(x: r.maxX, y: y))
            gc.stroke(p, with: .color(s.graphGrid), style: StrokeStyle(lineWidth: 1, dash: [4, 4]))
        }
        let h = st.hist
        guard h.count > 1 else { return }
        let step = r.width / 299
        let x0 = r.maxX - CGFloat(h.count - 1) * step
        var area = Path(); area.move(to: CGPoint(x: x0, y: r.maxY))
        var line = Path()
        for (i, e) in h.enumerated() {
            let x = x0 + CGFloat(i) * step
            area.addLine(to: CGPoint(x: x, y: yOf(e.0)))
            if i == 0 { line.move(to: CGPoint(x: x, y: yOf(e.1))) } else { line.addLine(to: CGPoint(x: x, y: yOf(e.1))) }
        }
        area.addLine(to: CGPoint(x: r.maxX, y: r.maxY)); area.closeSubpath()
        gc.fill(area, with: .linearGradient(Gradient(colors: [s.c("spectrum_hi", 0.8), s.c("spectrum_lo", 0.35)]),
                                            startPoint: CGPoint(x: 0, y: r.minY), endPoint: CGPoint(x: 0, y: r.maxY)))
        gc.stroke(line, with: .color(s.peak), lineWidth: 1.4)
    }
}
