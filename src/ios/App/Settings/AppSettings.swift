// vr0.1.0.030 (f58): YampApp.swift 에서 나눔 — 설정 값 (UserDefaults)
import Combine
import Foundation
import YampCore

/// 설정 (UserDefaults) — PC config · Android SharedPreferences 와 같은 이름
final class AppSettings: ObservableObject {
    private let ud = UserDefaults.standard
    @Published var theme: String { didSet { ud.set(theme, forKey: "theme") } }
    @Published var followDark: Bool { didSet { ud.set(followDark, forKey: "follow_system_dark") } }
    @Published var visMode: String { didSet { ud.set(visMode, forKey: "vis_mode") } }
    @Published var barStyle: String { didSet { ud.set(barStyle, forKey: "vis_bar_style") } }

    init() {
        theme = ud.string(forKey: "theme") ?? ThemeTable.defaultName
        followDark = ud.object(forKey: "follow_system_dark") as? Bool ?? true
        visMode = VisMath.parseMode(ud.string(forKey: "vis_mode") ?? "bars")
        let bs = ud.string(forKey: "vis_bar_style") ?? "round"
        barStyle = VisMath.barStyles.contains(bs) ? bs : "round"
    }

    func skin(systemDark: Bool) -> Skin {
        Skin(ThemeTable.named(ThemeTable.effective(theme, follow: followDark, systemDark: systemDark)))
    }

    /// 스펙트럼을 또 누르면 막대 모양 바꾸기 (PC · Android 와 같음)
    func pick(mode: String) {
        if mode == "bars" && visMode == "bars" { barStyle = VisMath.nextBarStyle(barStyle) }
        visMode = VisMath.parseMode(mode)
    }
}
