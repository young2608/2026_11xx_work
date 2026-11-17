// PC · Android 와 같은 값인지 — src/testdata/vis_cases.txt (vr0.1.0.028, f55)
import Foundation
import XCTest
@testable import YampCore

final class VisMathTests: XCTestCase {
    private func rows() throws -> [[String]] {
        // Tests/YampCoreTests → YampCore → ios → src → testdata
        let here = URL(fileURLWithPath: #filePath)
        let f = here.deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
            .deletingLastPathComponent().deletingLastPathComponent().appendingPathComponent("testdata/vis_cases.txt")
        let text = try String(contentsOf: f, encoding: .utf8)
        return text.split(separator: "\n").map { String($0) }.filter { !$0.hasPrefix("#") && !$0.isEmpty }
            .map { $0.split(separator: "|", omittingEmptySubsequences: false).map(String.init) }
    }

    private func mags(_ form: String, _ bins: Int) -> [Float] {
        (0..<bins).map { k in
            switch form {
            case "inv": return 1000 / Float(k + 1)
            case "flat": return 50
            default: return k == 1 ? 4000 : k == 2 ? 2000 : k == 40 ? 300 : 0
            }
        }
    }

    private func nums(_ s: String) -> [Double] { s.split(separator: ",").map { Double($0)! } }

    func testSharedCases() throws {
        let sm = BandSmoother(3)
        var nb = 0, ns = 0, nh = 0
        for r in try rows() {
            switch r[0] {
            case "bands":
                let out = VisMath.bandsFromMags(mags(r[5], Int(r[1])!), binHz: Double(r[2])!, n: 24, rangeDb: Double(r[3])!, ref: Double(r[4])!)
                for (i, e) in nums(r[6]).enumerated() { XCTAssertEqual(Double(out[i]), e, accuracy: 2e-5, "\(r[5]) \(i)") }
                nb += 1
            case "step":
                if r[2] != "-" { sm.setTarget(nums(r[2]).map { Float($0) }) }
                sm.step(Double(r[1])!)
                for (i, e) in nums(r[3]).enumerated() { XCTAssertEqual(sm.v[i], e, accuracy: 2e-6) }
                for (i, e) in nums(r[4]).enumerated() { XCTAssertEqual(sm.peaks[i], e, accuracy: 2e-6) }
                ns += 1
            case "heat":
                let stops = r[2].split(separator: ",").map { UInt32($0.dropFirst(), radix: 16)! }
                let c = VisMath.heatRGB(Double(r[1])!, stops)
                let e = r[3].split(separator: ",").map { UInt8($0)! }
                XCTAssertEqual([c.0, c.1, c.2], e, "heat \(r[1])")
                nh += 1
            case "led":
                XCTAssertEqual(VisMath.ledCells(Double(r[1])!, Double(r[2])!, Double(r[3])!), Int(r[4])!)
            case "style":
                XCTAssertEqual(VisMath.nextBarStyle(r[1]), r[2])
            case "mirror":
                XCTAssertEqual(VisMath.mirrorOrder(Int(r[1])!).map(String.init).joined(separator: ","), r[2])
            default: break
            }
        }
        XCTAssertEqual(nb, 4)
        XCTAssertGreaterThanOrEqual(ns, 18)
        XCTAssertGreaterThanOrEqual(nh, 8)
    }

    func testGramAndModes() {
        let g = GramHistory(n: 3, cols: 4)
        for k in 0..<6 { g.push([Double(k), Double(k) + 0.5, Double(k) + 0.25]) }
        XCTAssertEqual(g.size, 4)
        XCTAssertEqual(g.at(0, 0), 2)
        XCTAssertEqual(g.at(3, 1), 5.5)
        XCTAssertEqual(VisMath.parseMode("gram"), "gram")
        XCTAssertEqual(VisMath.parseMode("x"), "chart")
    }

    func testThemeTable() {
        XCTAssertEqual(ThemeTable.all.count, 18)
        XCTAssertEqual(ThemeTable.named("").name, "sunny")
        XCTAssertEqual(ThemeTable.named("light").name, "clean_blue")
        XCTAssertEqual(ThemeTable.effective("light3", follow: true, systemDark: true), "dark3")
        XCTAssertEqual(ThemeTable.named("sunny").rgb("fill1"), 0xFFC72C)
    }
}
