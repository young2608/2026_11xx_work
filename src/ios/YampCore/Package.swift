// swift-tools-version:5.9
// YampCore — iOS 앱의 계산 부분 (PC vis_math.py · Android VisMath.kt 와 같은 규칙). UIKit 없음 → `swift test` 로 Mac 에서 바로 검사
import PackageDescription

let package = Package(
    name: "YampCore",
    platforms: [.iOS(.v16), .macOS(.v13)],
    products: [.library(name: "YampCore", targets: ["YampCore"])],
    targets: [
        .target(name: "YampCore"),
        .testTarget(name: "YampCoreTests", dependencies: ["YampCore"]),
    ]
)
