"""오프스크린 GUI 스모크 테스트: 창 생성, 메뉴바 버전 라벨(규칙 9), 목록/가사 표시."""
import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
if sys.platform.startswith("linux"):
    os.environ.setdefault("QT_AUDIO_BACKEND", "alsa")   # 오디오 데몬 없는 CI 환경 (pipewire 크래시 회피)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    os.environ["YAMP_HOME"] = str(tmp_path_factory.mktemp("home"))
    from PyQt6.QtWidgets import QApplication
    a = QApplication.instance() or QApplication([])
    yield a


def test_mainwindow_smoke(app, tmp_path):
    from yamp.core.config import Config
    from yamp.core.version import version_label
    from yamp.app.mainwindow import MainWindow
    from yamp.lyrics import lrc
    cfg = Config(tmp_path)
    cfg["layout"] = "classic"                 # v009: 이 테스트는 클래식 배치 기준 (단순 배치는 test_v009)
    w = MainWindow(cfg)
    w.show()
    app.processEvents()
    assert w.ver_label.text() == version_label() and "__" in w.ver_label.text()
    assert version_label() in w.windowTitle()
    for i in range(3):
        (tmp_path / f"0{i}. 가수 - 노래{i}.mp3").write_bytes(b"\x00" * 10)
    assert w.ctrl.add_paths([str(tmp_path)]) == 3
    w.ctrl._pool.waitForDone(3000)
    app.processEvents()
    assert w.model.rowCount() == 3
    w.search.setText("노래1")
    assert w.model.rowCount() == 1
    w.search.setText("")
    ly = lrc.parse("[00:01.00]하나\n[00:02.00]둘\n[00:02.00]two")
    w.ctrl._on_lyrics(ly)
    w.lyv.set_position(2100)
    assert w.lyv.cur == 1
    for name in ("classic", "dark", "light"):
        w.apply_skin(name)
    w.toggle_mini()
    w.mini.set_position(1500)
    assert w.mini.cur == 0
    w.grab().save(str(tmp_path / "shot.png"))
    w.close()
    assert (tmp_path / "config.txt").exists() and (tmp_path / "data" / "state.json").exists()
    txt = (tmp_path / "config.txt").read_text(encoding="utf-8")
    assert "theme            = light" in txt and "#  yMp3Player config.txt" in txt   # 메뉴에서 바꾼 값만 그 줄 갱신


def test_spectrum_buffer_connected(app):
    """vr0.1.0.002 수정: QAudioBufferOutput → bufferReady 연결 실패로 스펙트럼이 동작하지 않던 문제"""
    from yamp.audio import engine as E
    if E.QAudioBufferOutput is None:
        pytest.skip("Qt < 6.8")
    e = E.AudioEngine()
    assert e.buf_out is not None
