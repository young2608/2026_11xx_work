# -*- coding: utf-8 -*-
"""앱 아이콘 .ico 만들기 (vr0.1.0.033, f61 H7) — build.sh exe 가 PyInstaller --icon 으로 씀

  python tools/make_icon.py build/yMp3Player.ico        (src/pc 에서, 화면 없이 동작)
모양 = yamp/ui/app_icon.py (Android 런처 아이콘과 같음) · 크기 16 · 20 · 24 · 32 · 40 · 48 · 64 · 96 · 128 · 256
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    out = argv[0] if argv else os.path.join("build", "yMp3Player.ico")
    from PyQt6.QtGui import QGuiApplication
    app = QGuiApplication.instance() or QGuiApplication([sys.argv[0]])  # noqa: F841 (QImage · 글꼴에 필요)
    from yamp.ui.app_icon import ICO_SIZES, write_ico
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    n = write_ico(out)
    print(f"make_icon: {out} ({n} bytes, {len(ICO_SIZES)} 크기)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
