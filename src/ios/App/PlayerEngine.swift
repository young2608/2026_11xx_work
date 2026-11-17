// 재생 엔진 (vr0.1.0.028, f55) — AVAudioEngine + AVAudioPlayerNode
//   · 스펙트럼: 메인 믹서 탭 → 끝 1024 표본 · Hann 창 · DFT(Accelerate) → YampCore.VisMath.bandsFromMags (PC 와 같은 규칙, 마이크 권한 필요 없음)
//   · 레벨: RMS · 피크 (레벨 모드)
//   · 백그라운드 재생 (Info.plist UIBackgroundModes audio) · 잠금화면 / 제어 센터 (MPNowPlayingInfoCenter · MPRemoteCommandCenter)
import Accelerate
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
    private let fftN = 1024
    private let dft: vDSP.DFT<Float>?
    private let window: [Float]
    private var lastLevelT: CFTimeInterval = 0

    var current: Track? { queue.indices.contains(index) ? queue[index] : nil }

    init() {
        window = vDSP.window(ofType: Float.self, usingSequence: .hanningDenormalized, count: 1024, isHalfWindow: false)
        dft = vDSP.DFT(count: 1024, direction: .forward, transformType: .complexComplex, ofType: Float.self)
        engine.attach(node)
        engine.connect(node, to: engine.mainMixerNode, format: nil)
        engine.mainMixerNode.installTap(onBus: 0, bufferSize: 1024, format: nil) { [weak self] buf, _ in
            self?.analyze(buf)
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

    // MARK: - 스펙트럼 · 레벨 (오디오 스레드)
    private func analyze(_ buf: AVAudioPCMBuffer) {
        guard let ch = buf.floatChannelData, let dft = dft else { return }
        let n = Int(buf.frameLength)
        guard n >= 64 else { return }
        let now = CACurrentMediaTime()
        if now - lastLevelT < 1.0 / 30 { return }          // 초당 30번까지
        lastLevelT = now
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
        DispatchQueue.main.async { [weak self] in
            self?.levels = lv
            self?.rms = min(1, r)
            self?.peak = min(1, pk)
        }
    }

    // MARK: - 오디오 세션 · 잠금화면
    private func setupSession() {
        let s = AVAudioSession.sharedInstance()
        try? s.setCategory(.playback, mode: .default)
        try? s.setActive(true)
        NotificationCenter.default.addObserver(forName: AVAudioSession.interruptionNotification, object: s, queue: .main) { [weak self] n in
            guard let raw = n.userInfo?[AVAudioSessionInterruptionTypeKey] as? UInt,
                  let type = AVAudioSession.InterruptionType(rawValue: raw) else { return }
            if type == .began { self?.pause() }
        }
    }

    private func setupRemote() {
        let cc = MPRemoteCommandCenter.shared()
        cc.playCommand.addTarget { [weak self] _ in self?.resume(); return .success }
        cc.pauseCommand.addTarget { [weak self] _ in self?.pause(); return .success }
        cc.togglePlayPauseCommand.addTarget { [weak self] _ in self?.toggle(); return .success }
        cc.nextTrackCommand.addTarget { [weak self] _ in self?.next(); return .success }
        cc.previousTrackCommand.addTarget { [weak self] _ in self?.prev(); return .success }
        cc.changePlaybackPositionCommand.addTarget { [weak self] e in
            guard let e = e as? MPChangePlaybackPositionCommandEvent else { return .commandFailed }
            self?.seek(to: e.positionTime)
            return .success
        }
    }

    private func updateNowPlaying() {
        guard let t = current else { MPNowPlayingInfoCenter.default().nowPlayingInfo = nil; return }
        var info: [String: Any] = [
            MPMediaItemPropertyTitle: t.title,
            MPMediaItemPropertyArtist: t.artist,
            MPMediaItemPropertyAlbumTitle: t.album,
            MPMediaItemPropertyPlaybackDuration: durationS,
            MPNowPlayingInfoPropertyElapsedPlaybackTime: position(),
            MPNowPlayingInfoPropertyPlaybackRate: isPlaying ? 1.0 : 0.0,
        ]
        if let d = t.artwork, let img = UIImage(data: d) {
            info[MPMediaItemPropertyArtwork] = MPMediaItemArtwork(boundsSize: img.size) { _ in img }
        }
        MPNowPlayingInfoCenter.default().nowPlayingInfo = info
    }
}
