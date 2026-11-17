# -*- coding: utf-8 -*-
"""vr0.1.0.010 — f16 재검토 수정 (P1~P5) · 형식 추가 (R2) · 녹음·강의 듣기 (R3)"""
import os
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TD = ROOT / "testdata"


@pytest.fixture
def app():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


# ---------------------------------------------------------------- R2 형식 표
def test_formats_table_matches_shared_file():
    from yamp.data import formats as F
    assert F.load_table_file(TD / "formats.txt") == F.TABLE           # PC 표 = 공용 표 (Android 도 같은 파일로 검사)
    for e in ("tak", "qcp", "gsm", "voc", "au", "w64", "rf64", "bwf", "eac3", "thd", "ra", "mod", "xm", "m4b", "webm", "3gp"):
        assert "." + e in F.AUDIO_EXT
    assert ".cue" not in F.AUDIO_EXT and ".pls" not in F.AUDIO_EXT and ".pls" in F.PLAYLIST_EXT
    assert F.category("강의.M4B") == "book" and F.category("x.amr") == "voice" and F.category("x.txt") == ""
    from yamp.data import playlist as P
    assert P.AUDIO_EXT is F.AUDIO_EXT and P.is_audio("a.QCP") and not P.is_audio("a.lrc")


def test_dialog_filter_groups():
    from yamp.data.formats import dialog_filter
    parts = dialog_filter().split(";;")
    assert parts[0].startswith("재생 가능한 모든 형식 (") and "*.tak" in parts[0] and "*.xspf" in parts[0]
    assert any(p.startswith("녹음·음성 (") and "*.amr" in p for p in parts)
    assert parts[-1] == "모든 파일 (*)"
    for p in parts:                                   # Qt 필터 문법: 이름 (패턴 …)
        assert re.fullmatch(r"[^()]+ \([^()]+\)", p), p


def test_playlist_parsers(tmp_path):
    from yamp.data import playlist as P
    for n in ("a.mp3", "b c.flac", "d.amr"):
        (tmp_path / n).write_bytes(b"x")
    (tmp_path / "l.pls").write_text("[playlist]\nFile2=b c.flac\nTitle2=B\nFile1=a.mp3\n"
                                    "File3=http://radio/x\nNumberOfEntries=3\nVersion=2\n", encoding="utf-8")
    assert [Path(x).name for x in P.load_pls(str(tmp_path / "l.pls"))] == ["a.mp3", "b c.flac"]
    uri = (tmp_path / "b c.flac").as_uri()
    (tmp_path / "l.xspf").write_text('<?xml version="1.0" encoding="UTF-8"?>\n'
                                     '<playlist version="1" xmlns="http://xspf.org/ns/0/"><trackList>'
                                     f'<track><location>{uri}</location></track>'
                                     '<track><location>d.amr</location></track>'
                                     '<track><location>https://x/y.mp3</location></track>'
                                     '</trackList></playlist>', encoding="utf-8")
    assert [Path(x).name for x in P.load_xspf(str(tmp_path / "l.xspf"))] == ["b c.flac", "d.amr"]
    (tmp_path / "l.wpl").write_text('<?wpl version="1.0"?><smil><head><title>t</title></head><body><seq>'
                                    '<media src="a.mp3"/><media src="d.amr"/></seq></body></smil>', encoding="utf-8")
    assert [Path(x).name for x in P.load_wpl(str(tmp_path / "l.wpl"))] == ["a.mp3", "d.amr"]
    (tmp_path / "bad.xspf").write_text("<playlist", encoding="utf-8")
    assert P.load_xspf(str(tmp_path / "bad.xspf")) == []
    pl = P.Playlist()
    assert pl.add_paths([str(tmp_path / "l.pls"), str(tmp_path / "l.xspf"), str(tmp_path / "l.wpl")]) == 6


# ---------------------------------------------------------------- CUE 리플레이게인 · 가사 경로
def test_cue_replaygain(tmp_path):
    from yamp.data import cue
    txt = ('REM REPLAYGAIN_ALBUM_GAIN -7.20 dB\nREM REPLAYGAIN_ALBUM_PEAK 0.98\nFILE "a.flac" WAVE\n'
           ' TRACK 01 AUDIO\n  REM REPLAYGAIN_TRACK_GAIN -6.50 dB\n  REM REPLAYGAIN_TRACK_PEAK 0.91\n  INDEX 01 00:00:00\n'
           ' TRACK 02 AUDIO\n  INDEX 01 01:00:00\n')
    t = cue.parse(txt, str(tmp_path))
    assert t[0].rg == {"replaygain_album_gain": "-7.20 dB", "replaygain_album_peak": "0.98",
                       "replaygain_track_gain": "-6.50 dB", "replaygain_track_peak": "0.91"}
    assert t[1].rg == {"replaygain_album_gain": "-7.20 dB", "replaygain_album_peak": "0.98"}
    assert cue.load(str(TD / "cue_sample.cue"))[0].rg == {}       # 공용 샘플 (값 없음) 은 그대로
    # 트랙 값이 없으면 앨범 값 사용
    from yamp.app.ctl_effects import EffectsMixin

    class C(EffectsMixin):
        cfg = {"replaygain": "track", "preamp_db": 0}

    class I:
        rg = t[1].rg
    f = C()._rg_factor(I())
    assert abs(f - 10 ** (-7.2 / 20)) < 1e-6


def test_lrc_paths_for_cue():
    from yamp.lyrics.providers.local import lrc_candidates, lrc_save_path
    assert [p.name for p in lrc_candidates("/m/album.flac|cue:2")] == ["album.02.lrc"]
    assert lrc_candidates("/m/a.flac|cue:x") == []
    assert Path(lrc_save_path("/m/song.mp3")).name == "song.lrc"
    assert Path(lrc_save_path("/m/album.flac|cue:12")).name == "album.12.lrc"


# ---------------------------------------------------------------- R3 녹음·강의
def test_voice_preset_and_silence_af():
    from yamp.domain import dsp
    assert "음성" in dsp.PRESETS and len(dsp.PRESETS["음성"]) == 10
    s = dsp.SoundSettings()
    assert dsp.mpv_af(s, 0, True).startswith(dsp.SILENCE_AF) and dsp.SILENCE_AF not in dsp.mpv_af(s)
    assert "silenceremove" in dsp.SILENCE_AF


def test_resume_rules():
    from yamp.domain import resume as R
    long_ms, m = 40 * 60 * 1000, {}
    R.remember(m, "short", 60_000, 5 * 60 * 1000)
    assert m == {}                                    # 짧은 곡은 기억 안 함
    R.remember(m, "a", 5_000, long_ms)
    assert m == {}                                    # 처음 10초 안
    R.remember(m, "a", 600_000, long_ms)
    assert R.start_at(m, "a", long_ms) == 597_000     # 3초 앞에서
    R.remember(m, "a", long_ms - 10_000, long_ms)
    assert "a" not in m                               # 거의 끝 → 지움
    R.remember(m, "b", 100_000, long_ms)
    R.remember(m, "b", 100_000, long_ms, ended=True)
    assert m == {}
    for i in range(205):
        R.remember(m, f"k{i}", 100_000, long_ms)
    assert len(m) == R.RESUME_MAX and "k0" not in m and "k204" in m
    assert R.start_at(m, "k204", 60_000) == 0         # 길이가 짧게 바뀐 파일은 무시


def test_controller_resume_and_skip_silence(app, tmp_path):
    os.environ["YAMP_HOME"] = str(tmp_path)
    from conftest import write_wav
    from yamp.core.config import Config
    from yamp.app.controller import Controller
    cfg = Config(tmp_path)
    assert cfg["resume_long"] is True and cfg["skip_silence"] is False and cfg["resume_pos"] == {}
    c = Controller(cfg)
    try:
        write_wav(tmp_path / "a.wav", 0.2)
        c.add_paths([str(tmp_path / "a.wav")], play_first=False)
        t = c.pl.items[0]
        t.duration = 3600.0                                    # 1시간 파일로 가정
        c.pl.current = 0
        c.rel_pos = lambda: 900_000
        c._resume_remember()
        assert cfg["resume_pos"] == {t.uid: 900_000}
        msgs = []
        c.message.connect(msgs.append)
        c.set_skip_silence(True)
        assert cfg["skip_silence"] is True and any("mpv" in m or "켬" in m for m in msgs)
        c.apply_preset("음성")
        assert c.sound.enabled and c.sound.bands[0] == -8
        # P4: 오류로 넘기다 목록 끝 → 목록 끝 동작 안 함
        called = []
        c.on_list_end = lambda: called.append(1)
        c.cfg["repeat"] = "off"
        c.pl.current = 0
        c.next(manual=False, from_error=True)
        assert called == []
        c.pl.current = 0
        c.next(manual=False)
        assert called == [1]
    finally:
        c.shutdown()


# ---------------------------------------------------------------- P1 · P3 · P5
def test_shipped_config_has_all_keys():
    """P1: 배포 pc/config.txt 에 모든 설정 키가 설명과 함께 있음"""
    from yamp.core.config import FILE_DEFAULTS, DEFAULT_CONFIG_TEXT
    shipped = (ROOT / "pc" / "config.txt").read_text(encoding="utf-8-sig")
    keys = set(re.findall(r"^([a-z_0-9]+)\s*=", shipped, re.M))
    assert set(FILE_DEFAULTS) <= keys, set(FILE_DEFAULTS) - keys
    assert shipped == DEFAULT_CONFIG_TEXT


def test_build_sh_durations():
    build_sh = next(d / "build.sh" for d in (ROOT, *ROOT.parents) if (d / "build.sh").exists())   # v021: src/ 위 00__build
    assert "--durations=10" in build_sh.read_text(encoding="utf-8")


def test_simple_layout_no_hidden_placeholder(app, tmp_path):
    """P5: 단순 배치 목록 화면에 숨겨진 자리표시 버튼이 없음"""
    os.environ["YAMP_HOME"] = str(tmp_path)
    from yamp.core.config import Config
    from yamp.app.mainwindow import MainWindow
    from yamp.ui.iconbutton import IconButton
    w = MainWindow(Config(tmp_path))
    try:
        btns = [b for b in w.page_list.tools if isinstance(b, IconButton)]
        assert btns and all(b.isVisibleTo(w.page_list) or not b.isHidden() for b in btns)
        assert not any(getattr(b, "tip_key", "") == "queue_clear" for b in btns)
        assert hasattr(w, "a_silence") and hasattr(w, "a_resume_long")
        assert {"skip_silence", "resume_long", "voice_preset"} <= set(w.quick_commands())
    finally:
        w.ctrl.shutdown()
        w.deleteLater()


def test_old_config_gets_new_keys_with_comments(tmp_path):
    """P1: 예전 config.txt 를 열면 없는 설정이 설명 주석과 함께 한 번 덧붙여짐 (값은 그대로)"""
    from yamp.core.config import Config, FILE_DEFAULTS, parse_config_text
    (tmp_path / "config.txt").write_text("# 내 설정\nrepeat = one\ntheme = dark\n", encoding="utf-8")
    c = Config(tmp_path)
    assert c["repeat"] == "one" and c["theme"] == "dark"
    txt = (tmp_path / "config.txt").read_text(encoding="utf-8")
    assert txt.startswith("# 내 설정\nrepeat = one\n")
    vals, warns = parse_config_text(txt)
    assert set(vals) == set(FILE_DEFAULTS) and not warns
    assert "# 무음 건너뛰기" in txt and txt.count("repeat") == 1
    Config(tmp_path)                                      # 두 번째 실행: 더 붙지 않음
    assert (tmp_path / "config.txt").read_text(encoding="utf-8") == txt
