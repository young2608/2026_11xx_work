// 비주얼라이저 계산 (vr0.1.0.028, f55) — PC domain/vis_math.py · Android domain/VisMath.kt 와 같은 규칙
//   testdata/vis_cases.txt 로 세 플랫폼이 같은 값인지 확인 (Tests/YampCoreTests)
import Foundation

public enum VisMath {
    public static let bands = 24
    public static let fLo = 50.0
    public static let fHi = 16000.0
    public static let tiltDbOct = 3.0
    public static let modes = ["bars", "wave", "radial", "gram", "chart"]
    public static let barStyles = ["round", "led", "mirror", "reflex"]
    public static let gramCols = 150
    public static let ledCell = 5.0

    public static func parseMode(_ m: String?) -> String {
        guard let m = m, modes.contains(m) else { return "chart" }
        return m
    }

    public static func nextBarStyle(_ cur: String) -> String {
        let i = barStyles.firstIndex(of: cur) ?? -1
        return barStyles[(i + 1) % barStyles.count]
    }

    /// 미러 배치: 높은 … 낮은 | 낮은 … 높은 (2n칸의 밴드 번호)
    public static func mirrorOrder(_ n: Int) -> [Int] {
        return Array((0..<n).reversed()) + Array(0..<n)
    }

    /// LED 켜진 칸 수 (반올림 .5 = 올림)
    public static func ledCells(_ v: Double, _ h: Double, _ cell: Double = ledCell, _ gap: Double = 2.0) -> Int {
        let total = max(1, Int((h + gap) / (cell + gap)))
        return min(total, max(0, Int(floor(v * Double(total) + 0.5))))
    }

    /// 스펙트로그램 색: 색 4개(0xRRGGBB) 사이 보간 → (r, g, b)
    public static func heatRGB(_ vIn: Double, _ stops: [UInt32]) -> (UInt8, UInt8, UInt8) {
        let v = min(1.0, max(0.0, vIn))
        let seg = stops.count - 1
        let x = v * Double(seg)
        let i = min(seg - 1, Int(x))
        let f = x - Double(i)
        let a = stops[i], b = stops[i + 1]
        func ch(_ sh: UInt32) -> UInt8 {
            let ca = Double((a >> sh) & 0xFF), cb = Double((b >> sh) & 0xFF)
            return UInt8(floor(ca + (cb - ca) * f + 0.5))
        }
        return (ch(16), ch(8), ch(0))
    }

    /// FFT 크기 mags[k] (k × binHz Hz) → n 밴드 0..1 — 낮은 밴드 보간 · 넓은 밴드 RMS · +3 dB/옥타브
    public static func bandsFromMags(_ mags: [Float], binHz: Double, n: Int = bands, rangeDb: Double = 60, ref: Double = 1) -> [Float] {
        let m = mags.count
        var out = [Float](repeating: 0, count: n)
        if m < 2 || binHz <= 0 { return out }
        let ratio = fHi / fLo
        for b in 0..<n {
            let f0 = fLo * pow(ratio, Double(b) / Double(n))
            let f1 = fLo * pow(ratio, Double(b + 1) / Double(n))
            let fc = (f0 * f1).squareRoot()
            let v: Double
            if f1 - f0 < 2 * binHz {
                let x = min(Double(m) - 1, max(1.0, fc / binHz))
                let k = Int(x)
                let fr = x - Double(k)
                let a = Double(mags[k]), c = Double(mags[min(m - 1, k + 1)])
                v = a + (c - a) * fr
            } else {
                let k0 = max(1, Int(f0 / binHz))
                let k1 = min(m, max(k0 + 1, Int(f1 / binHz)))
                var s = 0.0
                if k1 > k0 { for k in k0..<k1 { let q = Double(mags[k]); s += q * q } }
                v = k1 > k0 ? (s / Double(k1 - k0)).squareRoot() : 0
            }
            let db = 20 * log10(max(v, 1e-9) / ref) + tiltDbOct * log2(fc / 1000)
            out[b] = Float(min(1, max(0, (db + rangeDb) / rangeDb)))
        }
        return out
    }
}

/// 막대 · 웨이브 움직임 — 오를 때 τ 50 ms, 내릴 때 τ 350 ms, 꼭대기 0.5초 머문 뒤 중력 낙하, 0.25초 새 값 없으면 목표 0
public final class BandSmoother {
    public let n: Int
    public private(set) var v: [Double]
    public private(set) var peaks: [Double]
    private var hold: [Double]
    private var fall: [Double]
    public private(set) var target: [Double]
    private var age = 0.0

    public static let attack = 0.05, release = 0.35, holdS = 0.5, gravity = 2.5, staleS = 0.25
    public static let spatial = (0.2, 0.6, 0.2)

    public init(_ n: Int = VisMath.bands) {
        self.n = n
        let z = [Double](repeating: 0, count: n)
        v = z; peaks = z; hold = z; fall = z; target = z
    }

    public func setTarget(_ lv: [Float]) {
        for i in 0..<n { target[i] = i < lv.count ? Double(lv[i]) : 0 }
        age = 0
    }

    public func step(_ dtIn: Double) {
        let dt = min(0.25, max(0, dtIn))
        age += dt
        if age > Self.staleS { for i in 0..<n { target[i] = 0 } }
        let (a0, a1, a2) = Self.spatial
        var sm = [Double](repeating: 0, count: n)
        for i in 0..<n { sm[i] = a0 * target[max(0, i - 1)] + a1 * target[i] + a2 * target[min(n - 1, i + 1)] }
        let ka = 1 - exp(-dt / Self.attack)
        let kr = 1 - exp(-dt / Self.release)
        for i in 0..<n {
            var cur = v[i]
            let want = sm[i]
            cur += (want - cur) * (want > cur ? ka : kr)
            v[i] = cur
            if cur >= peaks[i] {
                peaks[i] = cur; hold[i] = Self.holdS; fall[i] = 0
            } else if hold[i] > 0 {
                hold[i] = max(0, hold[i] - dt)
            } else {
                fall[i] += Self.gravity * dt
                peaks[i] = max(cur, peaks[i] - fall[i] * dt)
            }
        }
    }

    public func idle(_ eps: Double = 0.003) -> Bool {
        return (v + peaks + target).allSatisfy { $0 <= eps }
    }
}

/// 스펙트로그램 기록 (최근 cols 프레임 × n 밴드)
public final class GramHistory {
    public let n: Int, cols: Int
    private var buf: [Float]
    private var head = 0
    public private(set) var size = 0

    public init(n: Int = VisMath.bands, cols: Int = VisMath.gramCols) {
        self.n = n; self.cols = cols; buf = Array(repeating: 0, count: n * cols)
    }

    public func push(_ lv: [Double]) {
        let o = head * n
        for i in 0..<n { buf[o + i] = i < lv.count ? Float(lv[i]) : 0 }
        head = (head + 1) % cols
        size = min(cols, size + 1)
    }

    public func at(_ i: Int, _ b: Int) -> Float { buf[((head - size + i + cols) % cols) * n + b] }
    public func clear() { head = 0; size = 0 }
}
