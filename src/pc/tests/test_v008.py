"""vr0.1.0.008: 장시간 운용 2차 — 버퍼 시그널 끊기 · 자동 저장 변경분만 · 깜빡임 정지 · 아이콘 캐시 · 파형 지연 · DB VACUUM"""
import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
if sys.platform.startswith("linux"):
    os.environ.setdefault("QT_AUDIO_BACKEND", "alsa")
PC = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PC))


@pytest.fixture
def app():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_qt_engine_spectrum_signal_detach(app):
    from yamp.audio.engine import AudioEngine
    e = AudioEngine()
    if e.buf_out is None:
        pytest.skip("QAudioBufferOutput 없음 (Qt < 6.8)")
    e.set_spectrum(False)
    assert e._buf_on is False
    e.set_spectrum(False)                     # 두 번 끊어도 오류 없음
    e.set_spectrum(True)
    assert e._buf_on is True and e.player.audioBufferOutput() is e.buf_out


def test_controller_sync_spectrum(app, tmp_path):
    os.environ["YAMP_HOME"] = str(tmp_path)
    from yamp.core.config import Config
    from yamp.app.controller import Controller
    c = Controller(Config(tmp_path))
    c.set_ui_active(False)
    assert c.spectrum.enabled is False
    c.set_ui_active(True)
    assert c.spectrum.enabled is True
    c.cfg["spectrum"] = False
    c.sync_spectrum()
    assert c.spectrum.enabled is False
    c.shutdown()


def test_autosave_writes_only_changes(app, tmp_path):
    os.environ["YAMP_HOME"] = str(tmp_path)
    from yamp.core.config import Config
    from yamp.app.controller import Controller
    cfg = Config(tmp_path)
    c = Controller(cfg)
    (tmp_path / "a.mp3").write_bytes(b"\0" * 10)
    c.add_paths([str(tmp_path / "a.mp3")])
    c.autosave()
    m3u = cfg.data_dir / "playlist.m3u8"
    st = cfg.state_path
    t1, t2 = m3u.stat().st_mtime_ns, st.stat().st_mtime_ns
    old = 1_000_000_000_000_000_000                   # 2001-09-09 — 초 단위 값 (Windows 는 시각 정밀도 100ns: 1ns 는 0 이 됨)
    os.utime(m3u, ns=(old, old))
    os.utime(st, ns=(old, old))
    c.autosave()                                       # 바뀐 것 없음 → 다시 쓰지 않음
    assert m3u.stat().st_mtime_ns == old and st.stat().st_mtime_ns == old
    (tmp_path / "b.mp3").write_bytes(b"\0" * 10)
    c.add_paths([str(tmp_path / "b.mp3")])
    c.autosave()                                       # 목록 바뀜 → m3u 다시 씀
    assert m3u.stat().st_mtime_ns != old and "b.mp3" in m3u.read_text(encoding="utf-8")
    assert t1 and t2
    c.shutdown()


def test_lcd_blink_stops(app):
    from yamp.ui import skin
    from yamp.ui.widgets import LcdTime
    lcd = LcdTime(skin.get("neon"))
    lcd.show()
    lcd.set_paused(True)
    assert lcd._blink_t.isActive()
    for _ in range(LcdTime.BLINK_MAX):
        lcd._on_blink()
    assert not lcd._blink_t.isActive() and lcd.blink is True
    lcd.set_paused(False)
    lcd.set_paused(True)
    assert lcd._blink_t.isActive()


def test_icon_cache(app):
    from yamp.ui import icons
    a = icons.icon("play", "#ffffff")
    assert icons.icon("play", "#ffffff") is a
    assert icons.icon("play", "#000000") is not a


def test_waveform_decode_is_delayed(app, tmp_path):
    from yamp.audio.waveform import WaveformLoader
    f = tmp_path / "x.wav"
    f.write_bytes(b"RIFF")
    wl = WaveformLoader(tmp_path / "wf")
    got = []
    wl.ready.connect(lambda u, b: got.append(u))
    for k in range(5):                                 # 곡을 빨리 넘김
        wl.request(f"u{k}", str(f))
    assert wl.dec is None and wl._delay.isActive()     # 아직 디코더를 만들지 않음
    wl.cancel()
    assert not wl._delay.isActive() and got == []


def test_library_vacuum(tmp_path):
    from yamp.data.library import Library
    lib = Library(tmp_path / "v.db")
    with lib.batch():
        for i in range(3000):
            lib.upsert(f"/m/{i}.mp3", "t" * 50, "a" * 50, "b" * 50, now=1)
    k = lib.all_tracks()[0]["key"]
    for i in range(3000):
        lib.record_play(k, 100 + i, 1000, 1000, 1, 0, 1)
    assert lib.vacuum_if_needed() is False             # 빈 페이지 거의 없음
    lib.prune_plays(now=10**10)                        # 전부 오래됨 → 삭제
    lib.db.execute("DELETE FROM tracks")
    lib.db.commit()
    assert lib.vacuum_if_needed(min_pages=8) is True
    lib.close()
