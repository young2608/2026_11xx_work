// 재생 엔진 (vr0.1.0.028, f55) — AVAudioEngine + AVAudioPlayerNode
//   vr0.1.0.030 (f58): 스펙트럼 계산 → SpectrumTap.swift · 오디오 세션 · 잠금화면 → PlayerEngine+System.swift
//   · 스펙트럼: 메인 믹서 탭 → 끝 1024 표본 · Hann 창 · DFT(Accelerate) → YampCore.VisMath.bandsFromMags (PC 와 같은 규칙, 마이크 권한 필요 없음)
//   · 레벨: RMS · 피크 (레벨 모드)
//   · 백그라운드 재생 (Info.plist UIBackgroundModes audio) · 잠금화면 / 제어 센터 (MPNowPlayingInfoCenter · MPRemoteCommandCenter)
import AVFoundation
import MediaPlayer
import UIKit
import YampCore

final class PlayerEngine: ObservableObject {
    @Published private(set) var queue: [Track] = []
    @Published private(set) var index = -1
    @Published private(set) var isPlaying = false
    @Published private(set) var durationS: Double = 0
    @Published private(set) var levels = [Float](repeating: 0, count: VisMath.bands)
    @Published private(set) var rms: Float = 0
    @Published private(set) var peak: Float = 0
    @Published var shuffle = false
    @Published var repeatAll = true

    private let engine = AVAudioEngine()
    private let node = AVAudioPlayerNode()
    private var file: AVAudioFile?
    private var startFrame: AVAudioFramePosition = 0
    private var pausedPos: Double = 0
    private var gen = 0
    private let spectrum = SpectrumTap()                 // 스펙트럼 · 레벨 계산 (Player/SpectrumTap.swift)

    var current: Track? { queue.indices.contains(index) ? queue[index] : nil }

    init() {
        engine.attach(node)
        engine.connect(node, to: engine.mainMixerNode, format: nil)
        engine.mainMixerNode.installTap(onBus: 0, bufferSize: 1024, format: nil) { [weak self] buf, _ in
            guard let self = self, let r = self.spectrum.analyze(buf) else { return }
            DispatchQueue.main.async { [weak self] in
                self?.levels = r.levels
                self?.rms = r.rms
                self?.peak = r.peak
            }
        }
        setupSession()
        setupRemote()
    }

    // MARK: - 목록 · 재생
    func setQueue(_ tracks: [Track], start: Int) {
        queue = tracks
        play(at: start)
    }

    func play(at i: Int) {
        guard queue.indices.contains(i) else { return }
        index = i
        load(from: 0, autoplay: true)
    }

    func toggle() { isPlaying ? pause() : resume() }

    func pause() {
        guard isPlaying else { return }
        pausedPos = position()
        node.pause()
        isPlaying = false
        updateNowPlaying()
    }

    func resume() {
        if file == nil { if !queue.isEmpty { play(at: max(0, index)) }; return }
        if !engine.isRunning { try? engine.start() }
        node.play()
        isPlaying = true
        updateNowPlaying()
    }

    func next(auto: Bool = false) {
        guard !queue.isEmpty else { return }
        if shuffle && queue.count > 1 {
            var j = index
            while j == index { j = Int.random(in: 0..<queue.count) }
            play(at: j)
        } else if index + 1 < queue.count {
            play(at: index + 1)
        } else if repeatAll {
            play(at: 0)
        } else if auto {
            node.stop(); isPlaying = false; pausedPos = 0; updateNowPlaying()
        }
    }

    func prev() {
        if position() > 3 { seek(to: 0); return }
        play(at: index > 0 ? index - 1 : (repeatAll ? queue.count - 1 : 0))
    }

    func seek(to s: Double) {
        guard let f = file else { return }
        let was = isPlaying
        let frame = AVAudioFramePosition(max(0, s) * f.processingFormat.sampleRate)
        load(from: frame, autoplay: was)
        if !was { pausedPos = max(0, min(s, durationS)) }
    }

    /// 지금 위치 (초)
    func position() -> Double {
        guard let f = file else { return 0 }
        if !isPlaying { return pausedPos }
        let sr = f.processingFormat.sampleRate
        guard let nt = node.lastRenderTime, let pt = node.playerTime(forNodeTime: nt) else { return Double(startFrame) / sr }
        return min(durationS, Double(startFrame + pt.sampleTime) / sr)
    }

    private func load(from frame: AVAudioFramePosition, autoplay: Bool) {
        gen += 1
        let g = gen
        node.stop()
        guard let t = current else { return }
        do {
            let f = try AVAudioFile(forReading: t.url)
            file = f
            durationS = Double(f.length) / f.processingFormat.sampleRate
            if engine.isRunning { engine.stop() }
            engine.disconnectNodeOutput(node)
            engine.connect(node, to: engine.mainMixerNode, format: f.processingFormat)   // 곡마다 표본율이 달라도 그대로
            let start = max(0, min(frame, f.length - 1))
            startFrame = start
            let count = AVAudioFrameCount(max(0, f.length - start))
            if count > 0 {
                node.scheduleSegment(f, startingFrame: start, frameCount: count, at: nil,
                                     completionCallbackType: .dataPlayedBack) { [weak self] _ in
                    DispatchQueue.main.async { self?.segmentDone(g) }
                }
            }
            try engine.start()
            if autoplay { node.play() }
            isPlaying = autoplay
            pausedPos = Double(start) / f.processingFormat.sampleRate
            updateNowPlaying()
        } catch {
            isPlaying = false
            file = nil
        }
    }

    /// 곡 끝 (node.stop() 이 부르는 이전 콜백은 gen 이 달라 무시)
    private func segmentDone(_ g: Int) {
        guard g == gen, isPlaying else { return }
        next(auto: true)
    }
}
