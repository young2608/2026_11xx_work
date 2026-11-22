// 스펙트럼 · 레벨 계산 (vr0.1.0.030 f58: PlayerEngine.swift 에서 나눔) — 오디오 스레드에서 부름
//   메인 믹서 탭 버퍼 → 끝 1024 표본 (모노) · Hann 창 · DFT(Accelerate) → YampCore.VisMath.bandsFromMags
//   (PC compute_bands · Android 와 같은 규칙, 마이크 권한 필요 없음) · 초당 30번까지
import Accelerate
import AVFoundation
import QuartzCore
import YampCore

final class SpectrumTap {
    struct Result {
        let levels: [Float]
        let rms: Float
        let peak: Float
    }

    private let fftN = 1024
    private let dft: vDSP.DFT<Float>?
    private let window: [Float]
    private var lastT: CFTimeInterval = 0

    init() {
        window = vDSP.window(ofType: Float.self, usingSequence: .hanningDenormalized, count: 1024, isHalfWindow: false)
        dft = vDSP.DFT(count: 1024, direction: .forward, transformType: .complexComplex, ofType: Float.self)
    }

    /// 너무 자주 불리면 nil (초당 30번까지)
    func analyze(_ buf: AVAudioPCMBuffer) -> Result? {
        guard let ch = buf.floatChannelData, let dft = dft else { return nil }
        let n = Int(buf.frameLength)
        guard n >= 64 else { return nil }
        let now = CACurrentMediaTime()
        if now - lastT < 1.0 / 30 { return nil }
        lastT = now
        let chans = max(1, Int(buf.format.channelCount))
        let take = min(n, fftN)
        let off = n - take
        var x = [Float](repeating: 0, count: fftN)
        var sq: Float = 0, pk: Float = 0
        for i in 0..<take {
            var s: Float = 0
            for c in 0..<chans { s += ch[c][off + i] }
            s /= Float(chans)
            x[fftN - take + i] = s
            sq += s * s
            pk = max(pk, abs(s))
        }
        let r = (sq / Float(take)).squareRoot()
        x = vDSP.multiply(x, window)
        let zeros = [Float](repeating: 0, count: fftN)
        var re = [Float](repeating: 0, count: fftN)
        var im = [Float](repeating: 0, count: fftN)
        dft.transform(inputReal: x, inputImaginary: zeros, outputReal: &re, outputImaginary: &im)
        let half = fftN / 2
        let scale = Float(fftN) / 4                          // 꽉 찬 사인 ≈ 1.0 (PC compute_bands 와 같은 기준)
        var mags = [Float](repeating: 0, count: half)
        for k in 0..<half { mags[k] = (re[k] * re[k] + im[k] * im[k]).squareRoot() / scale }
        let lv = VisMath.bandsFromMags(mags, binHz: buf.format.sampleRate / Double(fftN))
        return Result(levels: lv, rms: min(1, r), peak: min(1, pk))
    }
}
