// 곡 목록 (vr0.1.0.028) — 앱 Documents 폴더의 음악 파일
//   넣는 법: ① 앱의 + (파일 앱에서 골라 복사) ② 파일 앱 → 나의 iPhone → yMp3Player 폴더에 직접 복사
//            ③ PC iTunes(Windows) / Finder(Mac) 파일 공유 (Info.plist UIFileSharingEnabled)
import AVFoundation
import Foundation

struct Track: Identifiable, Hashable {
    let id: URL
    var url: URL { id }
    var title: String
    var artist: String
    var album: String
    var artwork: Data?

    var display: String { artist.isEmpty ? title : "\(artist) - \(title)" }
}

@MainActor
final class Library: ObservableObject {
    @Published private(set) var tracks: [Track] = []
    @Published private(set) var busy = false
    static let exts: Set<String> = ["mp3", "m4a", "aac", "wav", "aif", "aiff", "caf", "flac", "alac", "mp4", "m4b"]

    nonisolated static var folder: URL {
        FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
    }

    /// 폴더 훑기 (하위 폴더 포함, 이름 순) — 동기 함수로 (async 안에서 NSEnumerator 를 쓰지 않게)
    nonisolated static func scanFiles(_ root: URL) -> [URL] {
        var out: [URL] = []
        if let en = FileManager.default.enumerator(at: root, includingPropertiesForKeys: nil, options: [.skipsHiddenFiles]) {
            while let u = en.nextObject() as? URL {
                if exts.contains(u.pathExtension.lowercased()) { out.append(u) }
            }
        }
        return out.sorted { $0.lastPathComponent.localizedStandardCompare($1.lastPathComponent) == .orderedAscending }
    }

    func reload() async {
        busy = true
        let urls = Self.scanFiles(Self.folder)
        tracks = urls.map { Track(id: $0, title: $0.deletingPathExtension().lastPathComponent, artist: "", album: "", artwork: nil) }
        for i in tracks.indices {
            let m = await Self.meta(tracks[i].url)
            if i < tracks.count {
                if let t = m.title, !t.isEmpty { tracks[i].title = t }
                tracks[i].artist = m.artist ?? ""
                tracks[i].album = m.album ?? ""
                tracks[i].artwork = m.art
            }
        }
        busy = false
    }

    /// 파일 앱에서 고른 파일을 앱 폴더로 복사 (같은 이름이 있으면 건너뜀)
    func importFiles(_ urls: [URL]) async {
        let fm = FileManager.default
        for u in urls {
            let ok = u.startAccessingSecurityScopedResource()
            defer { if ok { u.stopAccessingSecurityScopedResource() } }
            let dst = Self.folder.appendingPathComponent(u.lastPathComponent)
            if !fm.fileExists(atPath: dst.path) { try? fm.copyItem(at: u, to: dst) }
        }
        await reload()
    }

    func delete(_ t: Track) async {
        try? FileManager.default.removeItem(at: t.url)
        await reload()
    }

    nonisolated static func meta(_ url: URL) async -> (title: String?, artist: String?, album: String?, art: Data?) {
        let asset = AVURLAsset(url: url)
        guard let items = try? await asset.load(.commonMetadata) else { return (nil, nil, nil, nil) }
        var title: String?, artist: String?, album: String?, art: Data?
        for it in items {
            guard let key = it.commonKey else { continue }
            switch key {
            case .commonKeyTitle: title = try? await it.load(.stringValue)
            case .commonKeyArtist: artist = try? await it.load(.stringValue)
            case .commonKeyAlbumName: album = try? await it.load(.stringValue)
            case .commonKeyArtwork: art = try? await it.load(.dataValue)
            default: break
            }
        }
        return (title, artist, album, art)
    }
}
