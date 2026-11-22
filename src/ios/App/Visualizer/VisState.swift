// vr0.1.0.030 (f58): VisualizerView.swift 에서 나눔 — 프레임 사이 상태 (부드럽게 · 스펙트로그램 · 레벨 기록)
import Combine
import Foundation
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
