# -*- coding: utf-8 -*-
"""공용 테스트 도우미 (vr0.1.0.010, P2)
Windows MSYS2 에는 soundfile(libsndfile) 패키지가 없어 v006~v009 GUI·컨트롤러 테스트 일부가 건너뛰어졌음.
→ 소리 파일 만들기를 표준 라이브러리 wave 로 바꿈. soundfile 이 있으면 그대로 사용(FLAC·AIFF 등 실제 형식).
  soundfile 이 없고 확장자가 wav 가 아니면 내용은 WAV 로 씀 — FFmpeg 는 내용으로 형식을 알아내므로
  목록·재생 테스트에는 충분 (실제 FLAC 헤더가 필요한 태그 테스트만 따로 importorskip)."""
import math
import os
import struct
import sys
import wave
from pathlib import Path

# 모든 테스트 공통: 화면 없이 · 오디오 데몬 없는 리눅스 CI 에서 pipewire 크래시 회피 (test_gui 와 같음)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
if sys.platform.startswith("linux"):
    os.environ.setdefault("QT_AUDIO_BACKEND", "alsa")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# vr0.1.0.011b: 테스트 중 인터넷 차단 — 화면·컨트롤러 테스트가 곡을 틀면 가사 서비스가 알송·LRCLIB 에 실제로 접속해
#   Windows(인터넷 연결됨)에서는 요청마다 제한 시간(6초)을 기다려 테스트가 수 분 ~ 수십 분 걸렸음.
#   (Linux 빌드 환경은 인터넷이 막혀 바로 실패 → 빠름, 그래서 차이를 못 봤음)
#   네트워크가 필요한 테스트는 각자 _post / _get 을 가짜로 바꿔 씀.
import urllib.error  # noqa: E402
import urllib.request  # noqa: E402


def _no_network(*a, **k):
    raise urllib.error.URLError("테스트 중 인터넷 사용 안 함 (tests/conftest.py)")


urllib.request.urlopen = _no_network


def write_wav(path, sec=0.3, sr=22050, freq=440.0, amp=0.3):
    n = int(sec * sr)
    frames = b"".join(struct.pack("<h", int(amp * 32767 * math.sin(2 * math.pi * freq * i / sr))) for i in range(n))
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(frames)


def write_audio(path, sec=1.0, sr=44100, fmt=None, subtype=None):
    try:
        import soundfile as sf
        import numpy as np
    except ImportError:
        write_wav(path, sec, sr)
        return
    x = (0.3 * np.sin(2 * np.pi * 440 * np.arange(int(sec * sr)) / sr)).astype("float32")
    sf.write(str(path), x, sr, format=fmt, subtype=subtype)
