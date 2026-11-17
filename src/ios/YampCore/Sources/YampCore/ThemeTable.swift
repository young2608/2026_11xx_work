// 자동 생성 — 손으로 고치지 마세요 (src/ios/tools/gen_ios.py ← src/testdata/themes.txt)
// 테마 색 표: PC ui/themes.py · Android ThemeTable.kt 와 같은 값 (PC 테스트 test_v028_ios.py 가 확인)

public struct ThemeDef {
    public let name: String
    public let label: String
    public let dark: Bool
    public let tokens: [String: String]
    public let bands: [String]
    /// 토큰 → 0xRRGGBB (없으면 0)
    public func rgb(_ token: String) -> UInt32 {
        guard let h = tokens[token], h.count == 7 else { return 0 }
        return UInt32(h.dropFirst(), radix: 16) ?? 0
    }
}

public enum ThemeTable {
    public static let defaultName = "sunny"
    /// 어두운 모드 짝 (써니 → 나이트 써니, 라이트 n → 다크 n, 나머지 밝은 테마 → 다크 블루)
    public static let night: [String: String] = ["sunny": "night_sunny", "light1": "dark1", "light2": "dark2", "light3": "dark3", "light4": "dark4", "light5": "dark5"]
    public static let all: [ThemeDef] = [
        ThemeDef(name: "sunny", label: "써니", dark: false,
                 tokens: ["bg": "#FFFFFF", "surface": "#FFFFFF", "surface2": "#FFF8E7", "nav": "#FFFBF2", "line": "#F0E3C6", "text": "#2B2B2B", "dim": "#6F685D", "fill1": "#FFC72C", "fill1_soft": "#FFF1C2", "fill2": "#FF8A00", "accent_text": "#C2410C", "on_fill": "#2B2B2B", "lcd_bg": "#FFF8E7", "lcd_fg": "#C2410C", "wave_played": "#D9680A", "wave_rest": "#EFE6D3", "knob": "#FFF8E7", "knob_rim": "#E8D6B0", "graph_bg": "#FFFDF7", "graph_grid": "#F0E3C6", "tooltip_bg": "#FFFFFF", "spectrum_lo": "#FF8A00", "spectrum_hi": "#FFC72C", "peak": "#C2410C", "rise": "#C62828", "fall": "#1565C0", "flash_rise": "#FFE5E2", "flash_fall": "#E3EEFF"],
                 bands: ["#FFE082", "#FFD54F", "#FFCA28", "#FFC107", "#FFB300", "#FFA000", "#FF8F00", "#FF6F00", "#F57C00", "#EF6C00", "#E65100"]),
        ThemeDef(name: "clean_blue", label: "클린 블루", dark: false,
                 tokens: ["bg": "#FFFFFF", "surface": "#FFFFFF", "surface2": "#F3F5F8", "nav": "#F6F7F9", "line": "#E1E5EB", "text": "#1F2937", "dim": "#5F6672", "fill1": "#2F6FEB", "fill1_soft": "#EAF1FF", "fill2": "#1D4ED8", "accent_text": "#1D4ED8", "on_fill": "#FFFFFF", "lcd_bg": "#F3F5F8", "lcd_fg": "#1D4ED8", "wave_played": "#2F6FEB", "wave_rest": "#E1E5EB", "knob": "#F3F5F8", "knob_rim": "#CBD3DE", "graph_bg": "#FAFBFC", "graph_grid": "#E1E5EB", "tooltip_bg": "#FFFFFF", "spectrum_lo": "#2F6FEB", "spectrum_hi": "#7FB0FF", "peak": "#1D4ED8", "rise": "#C62828", "fall": "#1565C0", "flash_rise": "#FDE7E7", "flash_fall": "#E3EEFF"],
                 bands: ["#BFD7FF", "#A5C6FF", "#8AB4FF", "#6FA1FF", "#558FFA", "#3F7EF2", "#2F6FEB", "#2563EB", "#1D4ED8", "#1E40AF", "#1E3A8A"]),
        ThemeDef(name: "mint", label: "민트", dark: false,
                 tokens: ["bg": "#FFFFFF", "surface": "#FFFFFF", "surface2": "#F1FAF4", "nav": "#F5FBF7", "line": "#D8EEDF", "text": "#1F2A24", "dim": "#5A6A61", "fill1": "#13804D", "fill1_soft": "#E3F6EA", "fill2": "#0E6B40", "accent_text": "#0E6B40", "on_fill": "#FFFFFF", "lcd_bg": "#F1FAF4", "lcd_fg": "#0E6B40", "wave_played": "#15965A", "wave_rest": "#D8EEDF", "knob": "#F1FAF4", "knob_rim": "#C3E4CE", "graph_bg": "#FAFDFB", "graph_grid": "#D8EEDF", "tooltip_bg": "#FFFFFF", "spectrum_lo": "#15965A", "spectrum_hi": "#7FD3A6", "peak": "#0E6B40", "rise": "#C62828", "fall": "#1565C0", "flash_rise": "#FDE7E7", "flash_fall": "#E3EEFF"],
                 bands: ["#C8F0D8", "#A8E6C2", "#88DCAC", "#68D096", "#4BC282", "#33B26F", "#20A060", "#15965A", "#0F8550", "#0E6B40", "#0B5534"]),
        ThemeDef(name: "cherry", label: "체리", dark: false,
                 tokens: ["bg": "#FFFFFF", "surface": "#FFFFFF", "surface2": "#FFF3F6", "nav": "#FFF8FA", "line": "#F6D9E2", "text": "#2A1F24", "dim": "#6F5B63", "fill1": "#C92A62", "fill1_soft": "#FFE8EF", "fill2": "#A61E4D", "accent_text": "#A61E4D", "on_fill": "#FFFFFF", "lcd_bg": "#FFF3F6", "lcd_fg": "#A61E4D", "wave_played": "#D6336C", "wave_rest": "#F6D9E2", "knob": "#FFF3F6", "knob_rim": "#EFC3D1", "graph_bg": "#FFFBFC", "graph_grid": "#F6D9E2", "tooltip_bg": "#FFFFFF", "spectrum_lo": "#D6336C", "spectrum_hi": "#FF8FB1", "peak": "#A61E4D", "rise": "#B71C1C", "fall": "#1565C0", "flash_rise": "#FFE0E6", "flash_fall": "#E3EEFF"],
                 bands: ["#FFD0DE", "#FFB8CC", "#FFA0BA", "#FF87A8", "#F76D96", "#EE5584", "#E64074", "#D6336C", "#C2255C", "#A61E4D", "#87163C"]),
        ThemeDef(name: "night_sunny", label: "나이트 써니", dark: true,
                 tokens: ["bg": "#1E1B16", "surface": "#2A251D", "surface2": "#332C22", "nav": "#18150F", "line": "#3D3528", "text": "#F3EDE2", "dim": "#ADA393", "fill1": "#FFC72C", "fill1_soft": "#3A3020", "fill2": "#FF8A00", "accent_text": "#FFB547", "on_fill": "#1E1B16", "lcd_bg": "#15120D", "lcd_fg": "#FFB547", "wave_played": "#FF9F1C", "wave_rest": "#4A4234", "knob": "#2A251D", "knob_rim": "#4A4234", "graph_bg": "#15120D", "graph_grid": "#3D3528", "tooltip_bg": "#2A251D", "spectrum_lo": "#FF8A00", "spectrum_hi": "#FFC72C", "peak": "#FFE08A", "rise": "#FF7A6E", "fall": "#74B6FF", "flash_rise": "#4A221D", "flash_fall": "#1C2E47"],
                 bands: ["#FFE082", "#FFD54F", "#FFCA28", "#FFC107", "#FFB300", "#FFA000", "#FF8F00", "#FF6F00", "#F57C00", "#EF6C00", "#E65100"]),
        ThemeDef(name: "neon", label: "네온", dark: true,
                 tokens: ["bg": "#07080B", "surface": "#121319", "surface2": "#181A22", "nav": "#0D0E13", "line": "#262935", "text": "#E9ECF3", "dim": "#8D93A6", "fill1": "#F2DC19", "fill1_soft": "#2A2410", "fill2": "#F2A90C", "accent_text": "#F2DC19", "on_fill": "#07080B", "lcd_bg": "#0B0C10", "lcd_fg": "#3DDC84", "wave_played": "#F2DC19", "wave_rest": "#3A3D4C", "knob": "#1D1F28", "knob_rim": "#2E3140", "graph_bg": "#0B0C10", "graph_grid": "#262935", "tooltip_bg": "#1B1D26", "spectrum_lo": "#3DDC84", "spectrum_hi": "#F2DC19", "peak": "#FF5FA2", "rise": "#FF6B6B", "fall": "#5CB8FF", "flash_rise": "#3A1518", "flash_fall": "#11243A"],
                 bands: ["#E9ECF3", "#FF7A1A", "#FF3D3D", "#FFB020", "#F2DC19", "#3DDC84", "#16E0C0", "#22C3FF", "#4F86FF", "#A06BFF", "#FF5FA2"]),
        ThemeDef(name: "dark", label: "다크 블루", dark: true,
                 tokens: ["bg": "#15171C", "surface": "#1F232B", "surface2": "#262B34", "nav": "#101318", "line": "#323845", "text": "#E6E9EF", "dim": "#8C95A4", "fill1": "#4FB3FF", "fill1_soft": "#12304A", "fill2": "#2F8FE0", "accent_text": "#6FC1FF", "on_fill": "#0A0C10", "lcd_bg": "#0A0C10", "lcd_fg": "#4FB3FF", "wave_played": "#4FB3FF", "wave_rest": "#323845", "knob": "#262B34", "knob_rim": "#3A4250", "graph_bg": "#0A0C10", "graph_grid": "#323845", "tooltip_bg": "#1F232B", "spectrum_lo": "#2F8FE0", "spectrum_hi": "#9FD6FF", "peak": "#FFFFFF", "rise": "#FF7A7A", "fall": "#6FC1FF", "flash_rise": "#3A1A1E", "flash_fall": "#12304A"],
                 bands: ["#9FD6FF", "#8ACCFF", "#75C2FF", "#60B8FF", "#4FB3FF", "#3FA6F5", "#3399EA", "#2F8FE0", "#2A80CC", "#2471B8", "#1E62A3"]),
        ThemeDef(name: "classic", label: "클래식", dark: true,
                 tokens: ["bg": "#23232F", "surface": "#2E2E3D", "surface2": "#23232F", "nav": "#1B1B25", "line": "#4A4A5A", "text": "#D8D8E0", "dim": "#9A9AAA", "fill1": "#C9A227", "fill1_soft": "#3A3420", "fill2": "#00E64D", "accent_text": "#7DFF9E", "on_fill": "#000000", "lcd_bg": "#000000", "lcd_fg": "#00E64D", "wave_played": "#00D040", "wave_rest": "#0B3D1D", "knob": "#23232F", "knob_rim": "#4A4A5A", "graph_bg": "#000000", "graph_grid": "#0B3D1D", "tooltip_bg": "#2E2E3D", "spectrum_lo": "#00D040", "spectrum_hi": "#7DFF9E", "peak": "#FFFFFF", "rise": "#FF7070", "fall": "#7CB8FF", "flash_rise": "#3D1E22", "flash_fall": "#1B2E45"],
                 bands: ["#00E64D", "#00E64D", "#00E64D", "#00E64D", "#00E64D", "#00E64D", "#00E64D", "#00E64D", "#00E64D", "#00E64D", "#00E64D"]),
        ThemeDef(name: "light1", label: "라이트", dark: false,
                 tokens: ["bg": "#FFFFFF", "surface": "#FFFFFF", "surface2": "#F3F4F7", "nav": "#F7F8FA", "line": "#E2E5EA", "text": "#1F2329", "dim": "#5F6672", "fill1": "#5561DC", "fill1_soft": "#E7E9FA", "fill2": "#4049BF", "accent_text": "#3D46B8", "on_fill": "#FFFFFF", "lcd_bg": "#F3F4F7", "lcd_fg": "#3D46B8", "wave_played": "#5561DC", "wave_rest": "#E2E5EA", "knob": "#F3F4F7", "knob_rim": "#D0D3D7", "graph_bg": "#FFFFFF", "graph_grid": "#E2E5EA", "tooltip_bg": "#FFFFFF", "spectrum_lo": "#5561DC", "spectrum_hi": "#9FA7F2", "peak": "#3D46B8", "rise": "#C62828", "fall": "#1565C0", "flash_rise": "#FFEAEA", "flash_fall": "#E8EFFF"],
                 bands: ["#C7CCF8", "#B3B9F5", "#9FA7F2", "#8B94EE", "#7882EA", "#6670E4", "#5561DC", "#4A55CF", "#4049BF", "#383FAC", "#303596"]),
        ThemeDef(name: "light2", label: "라이트+", dark: false,
                 tokens: ["bg": "#F4F5F8", "surface": "#FBFBFC", "surface2": "#EAECF0", "nav": "#EEF0F3", "line": "#D9DDE3", "text": "#1C2026", "dim": "#5F6672", "fill1": "#5561DC", "fill1_soft": "#E4E5F8", "fill2": "#4049BF", "accent_text": "#3D46B8", "on_fill": "#FFFFFF", "lcd_bg": "#EAECF0", "lcd_fg": "#3D46B8", "wave_played": "#5561DC", "wave_rest": "#D9DDE3", "knob": "#EAECF0", "knob_rim": "#C8CBD1", "graph_bg": "#FBFBFC", "graph_grid": "#D9DDE3", "tooltip_bg": "#FBFBFC", "spectrum_lo": "#5561DC", "spectrum_hi": "#9FA7F2", "peak": "#3D46B8", "rise": "#C62828", "fall": "#1565C0", "flash_rise": "#FBE6E7", "flash_fall": "#E4ECFC"],
                 bands: ["#C7CCF8", "#B3B9F5", "#9FA7F2", "#8B94EE", "#7882EA", "#6670E4", "#5561DC", "#4A55CF", "#4049BF", "#383FAC", "#303596"]),
        ThemeDef(name: "light3", label: "라이트++", dark: false,
                 tokens: ["bg": "#E8EAEE", "surface": "#F1F2F5", "surface2": "#DEE1E6", "nav": "#E2E5EA", "line": "#CDD2D9", "text": "#191C21", "dim": "#5D6470", "fill1": "#5561DC", "fill1_soft": "#DBDEF2", "fill2": "#4049BF", "accent_text": "#3D46B8", "on_fill": "#FFFFFF", "lcd_bg": "#DEE1E6", "lcd_fg": "#3D46B8", "wave_played": "#5561DC", "wave_rest": "#CDD2D9", "knob": "#DEE1E6", "knob_rim": "#BDC1C8", "graph_bg": "#F1F2F5", "graph_grid": "#CDD2D9", "tooltip_bg": "#F1F2F5", "spectrum_lo": "#5561DC", "spectrum_hi": "#9FA7F2", "peak": "#3D46B8", "rise": "#C22727", "fall": "#1563BC", "flash_rise": "#F3DEE1", "flash_fall": "#DBE4F6"],
                 bands: ["#C7CCF8", "#B3B9F5", "#9FA7F2", "#8B94EE", "#7882EA", "#6670E4", "#5561DC", "#4A55CF", "#4049BF", "#383FAC", "#303596"]),
        ThemeDef(name: "light4", label: "라이트+++", dark: false,
                 tokens: ["bg": "#DCDFE4", "surface": "#E7E9ED", "surface2": "#D2D6DC", "nav": "#D6DAE0", "line": "#C0C6CE", "text": "#16191D", "dim": "#565C67", "fill1": "#5561DC", "fill1_soft": "#D3D6EB", "fill2": "#4049BF", "accent_text": "#3D46B8", "on_fill": "#FFFFFF", "lcd_bg": "#D2D6DC", "lcd_fg": "#3D46B8", "wave_played": "#5561DC", "wave_rest": "#C0C6CE", "knob": "#D2D6DC", "knob_rim": "#B1B6BE", "graph_bg": "#E7E9ED", "graph_grid": "#C0C6CE", "tooltip_bg": "#E7E9ED", "spectrum_lo": "#5561DC", "spectrum_hi": "#9FA7F2", "peak": "#3D46B8", "rise": "#B62525", "fall": "#135DB1", "flash_rise": "#EAD6DA", "flash_fall": "#D3DCEF"],
                 bands: ["#C7CCF8", "#B3B9F5", "#9FA7F2", "#8B94EE", "#7882EA", "#6670E4", "#5561DC", "#4A55CF", "#4049BF", "#383FAC", "#303596"]),
        ThemeDef(name: "light5", label: "라이트++++", dark: false,
                 tokens: ["bg": "#D0D4DA", "surface": "#DCDFE4", "surface2": "#C6CBD2", "nav": "#CACFD6", "line": "#B3BAC4", "text": "#121417", "dim": "#505660", "fill1": "#5561DC", "fill1_soft": "#C9CDE3", "fill2": "#4049BF", "accent_text": "#3D46B8", "on_fill": "#FFFFFF", "lcd_bg": "#C6CBD2", "lcd_fg": "#3D46B8", "wave_played": "#5561DC", "wave_rest": "#B3BAC4", "knob": "#C6CBD2", "knob_rim": "#A5ABB4", "graph_bg": "#DCDFE4", "graph_grid": "#B3BAC4", "tooltip_bg": "#DCDFE4", "spectrum_lo": "#5561DC", "spectrum_hi": "#9FA7F2", "peak": "#3D46B8", "rise": "#AA2222", "fall": "#1257A5", "flash_rise": "#E0CDD2", "flash_fall": "#C9D3E7"],
                 bands: ["#C7CCF8", "#B3B9F5", "#9FA7F2", "#8B94EE", "#7882EA", "#6670E4", "#5561DC", "#4A55CF", "#4049BF", "#383FAC", "#303596"]),
        ThemeDef(name: "dark1", label: "다크", dark: true,
                 tokens: ["bg": "#2C2E33", "surface": "#36383E", "surface2": "#3E4148", "nav": "#26282C", "line": "#4B4E56", "text": "#E8EAEE", "dim": "#A9ADB6", "fill1": "#8C96FF", "fill1_soft": "#454961", "fill2": "#7480F7", "accent_text": "#ACB4FF", "on_fill": "#0B0C10", "lcd_bg": "#1D1E21", "lcd_fg": "#ACB4FF", "wave_played": "#8C96FF", "wave_rest": "#4B4E56", "knob": "#3E4148", "knob_rim": "#595C64", "graph_bg": "#1D1E21", "graph_grid": "#4B4E56", "tooltip_bg": "#36383E", "spectrum_lo": "#7480F7", "spectrum_hi": "#C9CEFF", "peak": "#FFFFFF", "rise": "#FF9292", "fall": "#7AB7FF", "flash_rise": "#5A3C41", "flash_fall": "#374665"],
                 bands: ["#E0E3FF", "#CDD2FF", "#BAC1FF", "#A8B0FF", "#97A0FF", "#8791FA", "#7A84F2", "#6E78E8", "#636DDC", "#5862CE", "#4E57BF"]),
        ThemeDef(name: "dark2", label: "다크+", dark: true,
                 tokens: ["bg": "#222429", "surface": "#2C2E34", "surface2": "#34373D", "nav": "#1D1F23", "line": "#41444B", "text": "#EBEDF0", "dim": "#A3A8B1", "fill1": "#8C96FF", "fill1_soft": "#3D4159", "fill2": "#7480F7", "accent_text": "#A7AFFF", "on_fill": "#0B0C10", "lcd_bg": "#16171B", "lcd_fg": "#A7AFFF", "wave_played": "#8C96FF", "wave_rest": "#41444B", "knob": "#34373D", "knob_rim": "#505359", "graph_bg": "#16171B", "graph_grid": "#41444B", "tooltip_bg": "#2C2E34", "spectrum_lo": "#7480F7", "spectrum_hi": "#C9CEFF", "peak": "#FFFFFF", "rise": "#FF7F7F", "fall": "#74B4FF", "flash_rise": "#523438", "flash_fall": "#2F3E5D"],
                 bands: ["#E0E3FF", "#CDD2FF", "#BAC1FF", "#A8B0FF", "#97A0FF", "#8791FA", "#7A84F2", "#6E78E8", "#636DDC", "#5862CE", "#4E57BF"]),
        ThemeDef(name: "dark3", label: "다크++", dark: true,
                 tokens: ["bg": "#18191D", "surface": "#222327", "surface2": "#2A2C31", "nav": "#131417", "line": "#37393F", "text": "#EEF0F2", "dim": "#A3A8B1", "fill1": "#8C96FF", "fill1_soft": "#35384E", "fill2": "#7480F7", "accent_text": "#A7AFFF", "on_fill": "#0B0C10", "lcd_bg": "#101013", "lcd_fg": "#A7AFFF", "wave_played": "#8C96FF", "wave_rest": "#37393F", "knob": "#2A2C31", "knob_rim": "#47494E", "graph_bg": "#101013", "graph_grid": "#37393F", "tooltip_bg": "#222327", "spectrum_lo": "#7480F7", "spectrum_hi": "#C9CEFF", "peak": "#FFFFFF", "rise": "#FF7A7A", "fall": "#74B4FF", "flash_rise": "#4A2B2E", "flash_fall": "#273552"],
                 bands: ["#E0E3FF", "#CDD2FF", "#BAC1FF", "#A8B0FF", "#97A0FF", "#8791FA", "#7A84F2", "#6E78E8", "#636DDC", "#5862CE", "#4E57BF"]),
        ThemeDef(name: "dark4", label: "다크+++", dark: true,
                 tokens: ["bg": "#0E0F11", "surface": "#18191C", "surface2": "#202125", "nav": "#0A0A0C", "line": "#2D2F34", "text": "#F1F2F4", "dim": "#A3A8B1", "fill1": "#8C96FF", "fill1_soft": "#2D3045", "fill2": "#7480F7", "accent_text": "#A7AFFF", "on_fill": "#0B0C10", "lcd_bg": "#090A0B", "lcd_fg": "#A7AFFF", "wave_played": "#8C96FF", "wave_rest": "#2D2F34", "knob": "#202125", "knob_rim": "#3E4044", "graph_bg": "#090A0B", "graph_grid": "#2D2F34", "tooltip_bg": "#18191C", "spectrum_lo": "#7480F7", "spectrum_hi": "#C9CEFF", "peak": "#FFFFFF", "rise": "#FF7A7A", "fall": "#74B4FF", "flash_rise": "#422225", "flash_fall": "#1F2D49"],
                 bands: ["#E0E3FF", "#CDD2FF", "#BAC1FF", "#A8B0FF", "#97A0FF", "#8791FA", "#7A84F2", "#6E78E8", "#636DDC", "#5862CE", "#4E57BF"]),
        ThemeDef(name: "dark5", label: "다크++++", dark: true,
                 tokens: ["bg": "#000000", "surface": "#0D0E10", "surface2": "#16171A", "nav": "#000000", "line": "#26272C", "text": "#F4F5F7", "dim": "#A3A8B1", "fill1": "#8C96FF", "fill1_soft": "#24263B", "fill2": "#7480F7", "accent_text": "#A7AFFF", "on_fill": "#0B0C10", "lcd_bg": "#000000", "lcd_fg": "#A7AFFF", "wave_played": "#8C96FF", "wave_rest": "#26272C", "knob": "#16171A", "knob_rim": "#37383D", "graph_bg": "#000000", "graph_grid": "#26272C", "tooltip_bg": "#0D0E10", "spectrum_lo": "#7480F7", "spectrum_hi": "#C9CEFF", "peak": "#FFFFFF", "rise": "#FF7A7A", "fall": "#74B4FF", "flash_rise": "#39191B", "flash_fall": "#172440"],
                 bands: ["#E0E3FF", "#CDD2FF", "#BAC1FF", "#A8B0FF", "#97A0FF", "#8791FA", "#7A84F2", "#6E78E8", "#636DDC", "#5862CE", "#4E57BF"]),
    ]

    public static func named(_ n: String) -> ThemeDef {
        let key = n == "light" ? "clean_blue" : n
        return all.first { $0.name == key } ?? all.first { $0.name == defaultName }!
    }

    /// 실제로 쓸 테마: 어두운 모드 따라가기 + 시스템 어두움이면 짝 테마
    public static func effective(_ n: String, follow: Bool, systemDark: Bool) -> String {
        let t = named(n)
        if !follow || !systemDark || t.dark { return t.name }
        return night[t.name] ?? "dark"
    }
}
