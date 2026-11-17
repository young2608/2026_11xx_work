"""공용 테스트 벡터 생성: 00__build/src/testdata/recommend_cases.txt (PC·Android 테스트가 같은 파일을 읽음)
    python tests/gen_testdata.py
형식 (줄 단위, '|' 구분):
  NOW <epoch>
  T key|artist|album|genre|folder|liked|rating|completed|skipped|last_played|added_at|completed_recent|tag1,tag2
  CO a|b|count
  RECENT key
  EXPECT <name>|k1,k2,...        name: daily, favorites, rediscover, recent, similar:<seed>, mood:<m>
  SCORE key|value(6자리)
  GAIN text|peak|preamp|factor(6자리)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from yamp.domain import recommend as R  # noqa: E402

NOW = 1_780_000_000
D = R.DAY


def tracks():
    T = R.TrackStat
    return [
        T("a01", "IU", "Palette", "K-Pop", "/m/iu", True, 5, 12, 0, NOW - 1 * D, NOW - 300 * D, 6, ("drive",)),
        T("a02", "IU", "Palette", "K-Pop", "/m/iu", False, 0, 5, 1, NOW - 10 * D, NOW - 300 * D, 2),
        T("a03", "IU", "Lilac", "K-Pop", "/m/iu", False, 4, 3, 0, NOW - 40 * D, NOW - 200 * D, 0),
        T("a04", "IU", "Lilac", "Ballad", "/m/iu", False, 0, 0, 0, 0, NOW - 2 * D, 0),
        T("b01", "BTS", "Butter", "K-Pop", "/m/bts", False, 0, 8, 0, NOW - 60 * D, NOW - 400 * D, 0),
        T("b02", "BTS", "Butter", "Dance", "/m/bts", True, 0, 2, 0, NOW - 5 * D, NOW - 400 * D, 2),
        T("b03", "BTS", "Proof", "Hip Hop", "/m/bts", False, 0, 0, 4, NOW - 2 * D, NOW - 100 * D, 0),
        T("c01", "Chopin", "Nocturnes", "Classical", "/m/cl", False, 3, 4, 0, NOW - 35 * D, NOW - 500 * D, 0),
        T("c02", "Chopin", "Nocturnes", "Classical", "/m/cl", False, 0, 0, 0, 0, NOW - 1 * D, 0),
        T("c03", "Debussy", "Suite", "Classical", "/m/cl", False, 0, 1, 2, NOW - 90 * D, NOW - 500 * D, 0),
        T("d01", "Norah Jones", "Come Away", "Jazz", "/m/jz", False, 0, 6, 0, NOW - 31 * D, NOW - 50 * D, 0, ("sleep",)),
        T("d02", "Norah Jones", "Come Away", "Jazz", "/m/jz", False, 0, 0, 0, 0, NOW - 3 * D, 0),
        T("e01", "Queen", "Opera", "Rock", "/m/rk", False, 2, 9, 1, NOW - 4 * D, NOW - 700 * D, 3),
        T("e02", "Queen", "Opera", "Rock", "/m/rk", False, 0, 0, 0, 0, NOW - 9 * D, 0),
        T("f01", "", "", "", "/m/etc", False, 0, 0, 0, 0, NOW - 20 * D, 0),
        T("f02", "LoFi Girl", "Beats", "Lo-Fi", "/m/etc", False, 0, 2, 0, NOW - 3 * D, NOW - 20 * D, 1),
    ]


def build_text() -> str:
    """벡터 파일 내용 (파일에 쓰지 않음 — 테스트는 이 결과와 저장된 파일을 비교만)"""
    ts = tracks()
    co = {("a01", "b02"): 2, ("e01", "a01"): 5}
    recent = ["a02"]
    out = [f"NOW {NOW}"]
    for t in ts:
        out.append("T " + "|".join([t.key, t.artist, t.album, t.genre, t.folder, str(int(t.liked)), str(t.rating),
                                    str(t.completed), str(t.skipped), str(t.last_played), str(t.added_at),
                                    str(t.completed_recent), ",".join(t.tags)]))
    for (a, b), c in co.items():
        out.append(f"CO {a}|{b}|{c}")
    for k in recent:
        out.append(f"RECENT {k}")
    for t in ts:
        out.append(f"SCORE {t.key}|{R.score(t):.6f}")
    out.append("EXPECT daily|" + ",".join(R.daily(ts, NOW)))
    out.append("EXPECT favorites|" + ",".join(R.favorites(ts)))
    out.append("EXPECT rediscover|" + ",".join(R.rediscover(ts, NOW)))
    out.append("EXPECT recent|" + ",".join(R.recent_added(ts, 5)))
    for seed in ("a01", "c01", "e01"):
        out.append(f"EXPECT similar:{seed}|" + ",".join(R.similar(ts, seed, co, recent)))
    for m in R.MOODS:
        out.append(f"EXPECT mood:{m}|" + ",".join(R.mood(ts, m)))
    for txt, peak, pre in (("-6.52 dB", "", 0.0), ("+3.10 dB", "0.95", 0.0), ("-1.0", "", 6.0), ("bad", "", 0.0),
                           ("−8 dB", "1.2", 2.0)):
        f = R.gain_factor(R.parse_gain(txt), float(peak) if peak else None, pre)
        out.append(f"GAIN {txt}|{peak}|{pre}|{f:.6f}")
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------- 사운드 처리 (dsp_cases.txt)
#  SET  id|settings_text|fs|ch
#  COEF id|k|b0,b1,b2,a1,a2            (8자리)
#  RESP id|f1:db1,f2:db2,...           (6자리)
#  PROC id|i:v,i:v,...                 (입력 신호 = test_signal(fs,ch,frames) 의 출력, 16번째 샘플마다, 8자리)
#  CGAIN level|th|ratio|db             컴프레서 정적 곡선
#  BAL  b|l|r
DSP_SETS = [
    ("flat", "on=1"),
    ("eq", "on=1;pre=-3;eq=6,5,4,2,0,-1,0,1,2,3;bass=0;treble=0"),
    ("tone", "on=1;eq=0,0,0,0,0,0,0,0,0,0;bass=6;treble=-4;bal=-0.4"),
    ("dyn", "on=1;pre=6;eq=3,0,0,0,0,0,0,0,0,0;lim=1;comp=1;th=-20;ratio=4;att=2;rel=50;mk=3"),
    ("off", "on=0;bal=0.5;lim=1"),
]
RESP_FREQS = (20, 31, 100, 440, 1000, 4000, 8000, 16000)


def test_signal(fs, ch, frames):
    """결정적 시험 신호: 100Hz + 3kHz 사인 + 32번째 프레임 임펄스 (인터리브)"""
    import math
    out = []
    for i in range(frames):
        v = 0.6 * math.sin(2 * math.pi * 100 * i / fs) + 0.3 * math.sin(2 * math.pi * 3000 * i / fs)
        if i == 32:
            v += 0.5
        for c in range(ch):
            out.append(v * (1.0 if c == 0 else 0.8))
    return out


def build_dsp_text() -> str:
    from yamp.domain import dsp as D
    out = []
    for sid, txt in DSP_SETS:
        for fs, ch in ((44100, 2), (48000, 1)):
            key = f"{sid}@{fs}x{ch}"
            s = D.SoundSettings.from_text(txt)
            out.append(f"SET {key}|{s.to_text()}|{fs}|{ch}")
            for k, c in enumerate(D.chain(s, fs)):
                out.append(f"COEF {key}|{k}|" + ",".join(f"{v:.8f}" for v in c))
            out.append(f"RESP {key}|" + ",".join(f"{f}:{v:.6f}" for f, v in zip(RESP_FREQS, D.response_db(s, RESP_FREQS, fs))))
            y = D.Processor(s, fs, ch).process(test_signal(fs, ch, 256))
            out.append(f"PROC {key}|" + ",".join(f"{i}:{y[i]:.8f}" for i in range(0, len(y), 16)))
    for lvl, th, r in ((-30, -20, 4), (-10, -20, 4), (0, -18, 3), (-5, -6, 10)):
        out.append(f"CGAIN {lvl}|{th}|{r}|{D.comp_gain_db(lvl, th, r):.6f}")
    for b in (-1, -0.4, 0, 0.5, 1):
        l, r = D.balance_gains(b)
        out.append(f"BAL {b}|{l:.6f}|{r:.6f}")
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------- CUE (cue_cases.txt)
#  CUE number|file(이름만)|title|performer|album|start_ms|end_ms|genre|date
def build_cue_text() -> str:
    from yamp.data import cue
    base = Path(__file__).resolve().parents[2] / "testdata"
    ts = cue.parse(cue.decode((base / "cue_sample.cue").read_bytes()), "")
    return "\n".join(f"CUE {t.number}|{t.file}|{t.title}|{t.performer}|{t.album}|{t.start_ms}|{t.end_ms}|{t.genre}|{t.date}"
                     for t in ts) + "\n"


FILES = {"recommend_cases.txt": build_text, "dsp_cases.txt": build_dsp_text, "cue_cases.txt": build_cue_text}


def main():
    base = Path(__file__).resolve().parents[2] / "testdata"
    for name, fn in FILES.items():
        p = base / name
        with open(p, "w", encoding="utf-8", newline="\n") as f:      # Windows 에서도 LF 고정
            f.write(fn())
        print("wrote", p)


if __name__ == "__main__":
    main()
