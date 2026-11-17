"""vr0.1.0.006: 공용 DSP·CUE 벡터 · 형식 라벨 · 폴더 재생 · CUE 재생 목록 · 사운드 설정 · 접기/펼치기 · GUI"""
import importlib.util
import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
if sys.platform.startswith("linux"):
    os.environ.setdefault("QT_AUDIO_BACKEND", "alsa")
PC = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PC))

from yamp.domain import dsp as D                     # noqa: E402
from yamp.data import cue                            # noqa: E402
from yamp.data import playlist as P                  # noqa: E402
from yamp.data.tags import format_label, codec_from_ext  # noqa: E402
from yamp.audio.waveform import reduce_peaks, slice_peaks  # noqa: E402

TD = PC.parent / "testdata"


def _gen():
    spec = importlib.util.spec_from_file_location("gen", PC / "tests" / "gen_testdata.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_all_testdata_fresh():
    """3개 공용 벡터 파일 = 생성 스크립트 결과 (비교만). 알고리즘 변경 시: python tests/gen_testdata.py"""
    m = _gen()
    for name, fn in m.FILES.items():
        assert fn() == (TD / name).read_bytes().decode("utf-8").replace("\r\n", "\n"), name


# ---------------------------------------------------------------- DSP (Android Dsp.kt 와 같은 벡터)
def test_dsp_vectors():
    m = _gen()
    sets = {}
    n_coef = n_resp = n_proc = 0
    for line in (TD / "dsp_cases.txt").read_text(encoding="utf-8").splitlines():
        tag, _, rest = line.partition(" ")
        f = rest.split("|")
        if tag == "SET":
            sets[f[0]] = (D.SoundSettings.from_text(f[1]), int(f[2]), int(f[3]))
        elif tag == "COEF":
            s, fs, ch = sets[f[0]]
            got = D.chain(s, fs)[int(f[1])]
            assert got == pytest.approx([float(x) for x in f[2].split(",")], abs=1e-7)
            n_coef += 1
        elif tag == "RESP":
            s, fs, ch = sets[f[0]]
            pairs = [p.split(":") for p in f[1].split(",")]
            got = D.response_db(s, [float(a) for a, _ in pairs], fs)
            assert got == pytest.approx([float(b) for _, b in pairs], abs=1e-5)
            n_resp += 1
        elif tag == "PROC":
            s, fs, ch = sets[f[0]]
            y = D.Processor(s, fs, ch).process(m.test_signal(fs, ch, 256))
            for p in f[1].split(","):
                i, v = p.split(":")
                assert y[int(i)] == pytest.approx(float(v), abs=1e-6)
            n_proc += 1
        elif tag == "CGAIN":
            assert D.comp_gain_db(float(f[0]), float(f[1]), float(f[2])) == pytest.approx(float(f[3]), abs=1e-6)
        elif tag == "BAL":
            assert D.balance_gains(float(f[0])) == pytest.approx((float(f[1]), float(f[2])), abs=1e-6)
    assert n_coef >= 10 and n_resp >= 6 and n_proc >= 6


def test_sound_text_roundtrip_and_clamp():
    s = D.SoundSettings.from_text("on=1;pre=99;eq=1,2;bass=-40;bal=3;lim=1;comp=1;th=-90;ratio=0.5")
    assert s.enabled and s.preamp_db == 12 and s.bands[:3] == [1, 2, 0] and len(s.bands) == 10
    assert D.SoundSettings.from_text("eq=1,2,x").bands == [0.0] * 10      # 잘못된 목록은 통째로 무시 (Kotlin 과 같음)
    assert s.bass_db == -12 and s.balance == 1 and s.comp_threshold_db == -60 and s.comp_ratio == 1
    assert D.SoundSettings.from_text(s.to_text()).to_text() == s.to_text()
    assert D.SoundSettings.from_text("") == D.SoundSettings()


def test_mpv_af_string():
    s = D.SoundSettings()
    assert D.mpv_af(s) == ""
    s.enabled, s.preamp_db, s.bands[0], s.bass_db = True, -3, 6, 4
    s.balance, s.limiter, s.comp = -0.5, True, True
    af = D.mpv_af(s, pitch_st=2)
    assert "volume=-3dB" in af and "equalizer=f=31" in af and "bass=g=4" in af
    assert "pan=stereo|c0=1.000*c0|c1=0.500*c1" in af
    assert "acompressor=" in af and "alimiter=limit=" in af and af.endswith("pitch-scale=1.122462")


def test_limiter_keeps_peak_below_ceiling():
    s = D.SoundSettings(enabled=True, preamp_db=12, limiter=True)
    y = D.Processor(s, 48000, 1).process([0.9] * 4000)
    assert max(abs(v) for v in y) <= 1.0                                  # 어택 중에도 ±1 을 넘지 않음
    assert max(abs(v) for v in y[1000:]) <= D.db_to_lin(D.LIMIT_DB) + 1e-3  # 어택(1ms) 뒤에는 −1 dBFS 이하


# ---------------------------------------------------------------- CUE
def test_cue_vectors():
    got = cue.parse(cue.decode((TD / "cue_sample.cue").read_bytes()), "")
    exp = [l[4:].split("|") for l in (TD / "cue_cases.txt").read_text(encoding="utf-8").splitlines()]
    assert len(got) == len(exp) == 4                                   # DATA 트랙 제외
    for t, e in zip(got, exp):
        assert [str(t.number), t.file, t.title, t.performer, t.album, str(t.start_ms), str(t.end_ms),
                t.genre, t.date] == e
    assert cue.index_ms("01:02:75") == 63000 and cue.index_ms("bad") == 0


def test_cue_cp949_decode():
    raw = 'TITLE "앨범"\nFILE "a.wav" WAVE\n TRACK 01 AUDIO\n  INDEX 01 00:00:00\n'.encode("cp949")
    t = cue.parse(cue.decode(raw), "/x")
    assert t[0].album == "앨범" and t[0].file.replace("\\", "/") == "/x/a.wav"


def _write_audio(path, sec=1.0, sr=44100, fmt=None, subtype=None):
    from conftest import write_audio      # vr0.1.0.010: soundfile 없으면 표준 wave
    write_audio(path, sec, sr, fmt, subtype)


def test_scan_tracks_with_cue_and_formats(tmp_path):
    a = tmp_path / "앨범"
    (a / "sub").mkdir(parents=True)
    _write_audio(a / "album.flac", 3, subtype="PCM_24")
    (a / "album.cue").write_text('PERFORMER "가수"\nTITLE "앨범"\nFILE "album.flac" WAVE\n'
                                 ' TRACK 01 AUDIO\n  TITLE "하나"\n  INDEX 01 00:00:00\n'
                                 ' TRACK 02 AUDIO\n  TITLE "둘"\n  INDEX 01 00:01:00\n', encoding="utf-8")
    _write_audio(a / "b.wav", 1)
    _write_audio(a / "sub" / "c.aiff", 1, fmt="AIFF")
    (a / "note.txt").write_text("x")
    ts = P.scan_tracks(str(a))
    names = [(Path(t.path).name, t.cue_no) for t in ts]
    assert ("album.flac", 0) not in names                               # CUE 가 덮는 원본은 빠짐
    assert ("album.flac", 1) in names and ("album.flac", 2) in names and ("b.wav", 0) in names
    assert ("c.aiff", 0) in names
    assert len(P.scan_tracks(str(a), recursive=False)) == 3
    t1 = next(t for t in ts if t.cue_no == 1)
    assert t1.title == "하나" and t1.artist == "가수" and t1.end_ms == 1000 and t1.uid.endswith("|cue:1")
    # m3u 저장 → 불러오기: CUE 는 한 줄로 저장되고 다시 펼쳐짐
    m3u = tmp_path / "l.m3u8"
    P.save_m3u(str(m3u), ts)
    assert m3u.read_text(encoding="utf-8").count("album.cue") == 1
    pl = P.Playlist()
    pl.add_paths([str(m3u)])
    assert sorted((Path(t.path).name, t.cue_no) for t in pl.items) == sorted(names)
    # 정렬
    by_title = [t.title or Path(t.path).stem for t in P.sort_tracks(ts, "title")]
    assert by_title == sorted(by_title, key=str.lower)


def test_format_label_and_tags(tmp_path):
    assert format_label("FLAC", 24, 96000, 0) == "FLAC 24bit/96kHz"
    assert format_label("MP3", 0, 44100, 320) == "MP3 320kbps"
    assert format_label("AAC", 0, 48000, 256) == "AAC 256kbps 48kHz"
    assert format_label("DSD", 1, 2822400, 0) == "DSD64"
    assert format_label("", 16, 44100, 0) == ""
    assert codec_from_ext("x.dff") == "DSD" and codec_from_ext("x.FLAC") == "FLAC"
    for e in (".flac", ".wav", ".aiff", ".ape", ".wv", ".dsf", ".opus", ".m4a", ".wma"):
        assert P.is_audio("a" + e)
    pytest.importorskip("soundfile")          # 실제 FLAC 헤더(24bit/96k)가 필요한 부분만
    from yamp.data.tags import read_tags
    _write_audio(tmp_path / "hi.flac", 0.5, 96000, subtype="PCM_24")
    i = read_tags(str(tmp_path / "hi.flac"))
    assert i.format_label == "FLAC 24bit/96kHz" and i.hires


def test_waveform_reduce():
    assert reduce_peaks([]) == []
    b = reduce_peaks([0.1, 0.4, 0.2, 0.8] * 100, 40)
    assert len(b) == 40 and max(b) == 1.0 and min(b) > 0
    assert reduce_peaks([0.0] * 10, 5) == [0.0] * 5
    assert slice_peaks(list(range(100)), 1000, 2000) == list(range(20, 40))
    assert slice_peaks(list(range(100)), 4900, -1) == [98, 99]


# ---------------------------------------------------------------- 컨트롤러 · 설정 · GUI
@pytest.fixture
def app():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_controller_folder_and_sound(app, tmp_path):
    os.environ["YAMP_HOME"] = str(tmp_path)
    from yamp.core.config import Config
    from yamp.app.controller import Controller
    cfg = Config(tmp_path)
    cfg["eq_enabled"], cfg["eq_bands"] = True, "3,0,0,0,0,0,0,0,0,-2"      # 이전 버전 설정 → 이전
    c = Controller(cfg)
    assert c.sound.enabled and c.sound.bands[0] == 3 and c.sound.bands[9] == -2
    music = tmp_path / "music"
    (music / "cd2").mkdir(parents=True)
    _write_audio(music / "b.wav", 0.3)
    _write_audio(music / "a.flac", 0.3)
    _write_audio(music / "cd2" / "c.wav", 0.3)
    assert c.play_folder(str(music), include_sub=False) == 2
    assert [Path(t.path).name for t in c.pl.items] == ["a.flac", "b.wav"]
    assert cfg["last_folder"] == str(music)
    assert c.play_folder(str(music), include_sub=True, shuffle=True) == 3
    assert c.play_folder(str(tmp_path / "없음")) == 0
    c.library.pin_folder(str(music), True)
    assert c.library.pinned_folders() == [str(music)]
    s = c.sound
    s.comp, s.balance = True, 0.3
    c.set_sound(s)
    assert "comp=1" in cfg["sound"] and "bal=0.3" in cfg["sound"]
    c2 = Controller(cfg)
    assert c2.sound.comp and c2.sound.balance == pytest.approx(0.3)
    c.shutdown()
    c2.shutdown()


def test_config_v006_keys(tmp_path):
    from yamp.core import config as C
    vals, warns = C.parse_config_text(C.DEFAULT_CONFIG_TEXT)
    assert not warns and vals["theme"] == "sunny" and vals["folder_sort"] == "name"      # v011: 기본 써니
    cfg = C.Config(tmp_path)
    assert cfg["folds"] == {} and cfg["last_folder"] == "" and cfg["waveform"] is True


def test_section_fold_state_saved(app, tmp_path):
    from PyQt6.QtWidgets import QLabel
    from yamp.core.config import Config
    from yamp.ui.neon import Section
    cfg = Config(tmp_path)
    sec = Section("제목", "t.one", cfg, QLabel("본문"))
    assert sec.is_open()
    sec.toggle()
    assert not sec.is_open() and cfg["folds"] == {"t.one": True} and sec.body.isHidden()
    assert not Section("제목", "t.one", cfg, QLabel("x")).is_open()        # 다시 만들어도 접힌 상태
    sec.set_open(True)
    assert cfg["folds"] == {}


def test_widgets_and_icons_paint(app, tmp_path):
    from PyQt6.QtGui import QImage
    from yamp.ui import icons
    from yamp.ui.neon import EqSliders, Knob, ResponseCurve, WaveformSeek
    for n in icons.NAMES:
        assert not icons.icon(n).isNull()
    k = Knob("베이스", -12, 12, 0, 0)
    got = []
    k.valueChanged.connect(got.append)
    k.setValue(30, emit=True)
    assert k.value() == 12 and got == [12]
    k.mouseDoubleClickEvent(None)
    assert k.value() == 0
    eq = EqSliders()
    eq.set_values(-3, [1] * 10)
    rc = ResponseCurve()
    rc.set_curve(D.response_db(D.SoundSettings(enabled=True, bands=[6] + [0] * 9), D.log_freqs(32)))
    ws = WaveformSeek()
    ws.setRange(0, 10000)
    ws.set_peaks(reduce_peaks([0.2, 0.9] * 50, 60))
    ws.set_pos(4000)
    ws.set_ab((1000, 3000))
    for w in (k, eq, rc, ws):
        w.resize(400, 200)
        img = QImage(w.size(), QImage.Format.Format_ARGB32)
        w.render(img)
    assert ws.maximum() == 10000


def test_mainwindow_v006(app, tmp_path):
    os.environ["YAMP_HOME"] = str(tmp_path)
    from yamp.core.config import Config
    from yamp.app.mainwindow import MainWindow
    from yamp.ui.neon import Section
    cfg = Config(tmp_path)
    music = tmp_path / "m"
    music.mkdir()
    _write_audio(music / "x.flac", 0.5, 48000, subtype="PCM_24")
    cfg["library_folders"] = str(music)
    cfg["layout"] = "classic"                 # v009: 이 테스트는 클래식 배치 기준 (단순 배치는 test_v009)
    w = MainWindow(cfg)
    w.show()
    app.processEvents()
    assert cfg["theme"] == "sunny"                # v011: 기본 써니
    assert [w.tabs.tabText(i) for i in (4, 5)] == ["폴더", "사운드"]
    assert {s.key for s in w.findChildren(Section)} >= {"main.now", "main.lists", "main.lyrics", "sound.eq",
                                                         "sound.tone", "sound.dyn", "folder.tree", "folder.files"}
    w.set_all_sections(False)
    assert all(cfg["folds"].get(k) for k in ("main.now", "sound.eq", "folder.tree"))
    w.set_all_sections(True)
    assert cfg["folds"] == {}
    # 폴더 탭: 라이브러리 폴더가 보이고, 선택 → 재생
    fv = w.folderv
    assert fv.tree.topLevelItemCount() >= 1
    fv.select(str(music))
    assert fv.files.count() == 1 and "FLAC" in fv.summary.text()
    assert fv.play() == 1 and cfg["last_folder"] == str(music)
    app.processEvents()
    try:                                          # 실제 24bit FLAC 을 만들 수 있을 때만 (없으면 WAV 내용)
        import soundfile as _sf
        has_sf = _sf is not None
    except ImportError:
        has_sf = False
    if has_sf:
        assert "FLAC 24bit/48kHz" in w.info.text()
    # 사운드 탭: 프리셋 → 설정 저장
    sv = w.soundv
    w.show_sound()
    sv.set_preset("록")
    sv._apply()
    assert cfg["sound"].startswith("on=1") and "eq=5,3,1" in cfg["sound"]
    assert sv.preset_btns["록"].isChecked()
    sv.reset()
    sv._apply()
    assert "eq=0,0,0" in cfg["sound"]
    for name in ("neon", "classic", "dark", "light"):
        w.apply_skin(name)
    w.apply_skin("neon")
    w.grab().save(str(tmp_path / "v006.png"))
    w.quit_app()
