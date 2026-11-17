# -*- coding: utf-8 -*-
"""
곡 파형 (vr0.1.0.006) — 재생 막대를 곡 모양으로 보여 주기 위한 막대 높이 (0..1, N_BARS 개)
  - QAudioDecoder 로 파일 전체를 한 번 디코드 → 50ms 마다 최대 진폭 → N_BARS 로 줄임 → 정규화
  - data/waveform/<키>.txt 에 저장 (다음부터 즉시)
  - CUE 트랙: 원본 파일 파형에서 트랙 구간만 잘라 씀
  - 한 번에 한 곡만 디코드 (새 곡이 오면 이전 작업 취소)
"""
import hashlib
import logging
import os
from pathlib import Path

import numpy as np
from PyQt6.QtCore import QObject, QTimer, QUrl, pyqtSignal

from .visualizer import buffer_to_mono

log = logging.getLogger(__name__)
N_BARS = 240
CHUNK_MS = 50
DECODE_DELAY_MS = 1500     # 캐시에 없으면 1.5초 뒤 디코드 시작 (곡을 빨리 넘길 때 헛 디코드 방지 — vr0.1.0.008)
CACHE_MAX_FILES = 3000      # 파형 캐시 최대 파일 수 (곡당 수 KB, 넘으면 오래 안 쓴 것부터 삭제)


def reduce_peaks(chunks, n_bars: int = N_BARS) -> list[float]:
    """50ms 최대값 목록 → n_bars 막대 (0..1, 가장 큰 막대 = 1). Qt 비의존 — 테스트 대상"""
    a = np.asarray(chunks, dtype=np.float32)
    if a.size == 0:
        return []
    edges = np.linspace(0, a.size, n_bars + 1).astype(int)
    if a.size >= n_bars:                        # v018: 구간이 모두 1개 이상 → reduceat 한 번 (결과 같음)
        out = np.maximum.reduceat(a, edges[:-1]).astype(np.float32)
    else:
        out = np.array([a[edges[i]:max(edges[i + 1], edges[i] + 1)].max() if edges[i] < a.size else a[-1]
                        for i in range(n_bars)], dtype=np.float32)
    top = float(out.max())
    if top <= 1e-6:
        return [0.0] * n_bars
    out = np.sqrt(out / top)            # 조용한 부분도 보이게 (감마 0.5)
    return [round(float(x), 3) for x in out]


def chunk_peaks(a: np.ndarray, per: int, acc: float = 0.0, acc_n: int = 0):
    """50ms(per 표본) 단위 최대값 — 버퍼 경계를 넘어 이어 붙임. Qt 비의존 — 테스트 대상
    a: |표본| · acc / acc_n: 이전 버퍼에서 이어지는 덜 찬 구간의 최대값 / 표본 수
    반환: (새 acc, 새 acc_n, 다 찬 구간들의 최대값 목록)
    v018 (f33 P6): 파이썬 반복(구간마다) → numpy 한 번 (UI 스레드에서 도는 디코드 처리 시간 ↓)"""
    done = []
    i = 0
    n = int(a.size)
    if acc_n:                                   # 앞 버퍼에서 이어지는 구간 먼저 채움
        take = min(per - acc_n, n)
        if take > 0:
            acc = max(acc, float(a[:take].max()))
            acc_n += take
            i = take
        if acc_n >= per:
            done.append(acc)
            acc, acc_n = 0.0, 0
    full = (n - i) // per
    if full == 1:                               # 작은 버퍼(구간 1~2개)는 reshape 준비 비용이 더 큼
        done.append(float(a[i:i + per].max()))
        i += per
    elif full:
        done.extend(a[i:i + full * per].reshape(full, per).max(axis=1).tolist())
        i += full * per
    if i < n:                                   # 남은 덜 찬 구간 → 다음 버퍼로
        acc = max(acc, float(a[i:].max()))
        acc_n += n - i
    return acc, acc_n, done


def slice_peaks(chunks, start_ms: int, end_ms: int) -> list:
    s = max(0, start_ms // CHUNK_MS)
    e = len(chunks) if end_ms < 0 else min(len(chunks), end_ms // CHUNK_MS)
    return list(chunks[s:e])


class WaveformCache:
    def __init__(self, root):
        self.root = Path(root)

    def _file(self, path: str) -> Path:
        st = Path(path).stat()
        k = hashlib.md5(f"{path.lower()}|{st.st_size}|{int(st.st_mtime)}".encode("utf-8")).hexdigest()[:16]
        return self.root / f"{k}.txt"

    def get(self, path: str):
        try:
            f = self._file(path)
            if f.exists():
                data = [float(x) for x in f.read_text("ascii").split(",") if x]
                try:
                    os.utime(f)                 # 최근 사용 표시 (trim 이 오래 안 쓴 것부터 지우게)
                except OSError:
                    pass
                return data
        except (OSError, ValueError):
            pass
        return None

    def trim(self, max_files: int = CACHE_MAX_FILES) -> int:
        """오래된 캐시 정리 (장시간 운용: 폴더가 끝없이 커지지 않게). 반환: 지운 수"""
        try:
            fs = sorted(self.root.glob("*.txt"), key=lambda f: f.stat().st_mtime)
        except OSError:
            return 0
        n = 0
        for f in fs[:max(0, len(fs) - max_files)]:
            try:
                f.unlink()
                n += 1
            except OSError:
                pass
        return n

    def put(self, path: str, chunks):
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            self._file(path).write_text(",".join(f"{x:.3f}" for x in chunks), "ascii")
        except OSError as e:
            log.warning("waveform cache write: %s", e)


class WaveformLoader(QObject):
    """ready(uid, bars) — bars 가 빈 목록이면 실패(일반 막대 표시)"""
    ready = pyqtSignal(str, list)

    def __init__(self, cache_dir, parent=None):
        super().__init__(parent)
        self.cache = WaveformCache(cache_dir)
        self.dec = None
        self._job = None         # (uid, path, start_ms, end_ms)
        self._chunks: list[float] = []
        self._acc = 0.0
        self._acc_n = 0
        self._sr = 0
        self._delay = None
        self.delay_ms = DECODE_DELAY_MS

    def request(self, uid: str, path: str, start_ms: int = 0, end_ms: int = -1):
        self.cancel()
        if not path or not Path(path).exists():
            self.ready.emit(uid, [])
            return
        ch = self.cache.get(path)
        if ch is not None:
            self.ready.emit(uid, reduce_peaks(slice_peaks(ch, start_ms, end_ms)))
            return
        self._job = (uid, path, start_ms, end_ms)
        if self._delay is None:
            self._delay = QTimer(self, singleShot=True, timeout=self._start_decode)
        self._delay.start(self.delay_ms)

    def _start_decode(self):
        if not self._job:
            return
        uid, path = self._job[0], self._job[1]
        try:
            from PyQt6.QtMultimedia import QAudioDecoder
        except ImportError:
            self._job = None
            self.ready.emit(uid, [])
            return
        self._chunks, self._acc, self._acc_n, self._sr = [], 0.0, 0, 0
        self.dec = QAudioDecoder(self)
        self.dec.bufferReady.connect(self._on_buffer)
        self.dec.finished.connect(self._on_finished)
        self.dec.error.connect(self._on_error)
        self.dec.setSource(QUrl.fromLocalFile(path))
        self.dec.start()

    def cancel(self):
        if self._delay is not None:
            self._delay.stop()
        if self.dec is not None:
            try:
                self.dec.bufferReady.disconnect()
                self.dec.finished.disconnect()
                self.dec.error.disconnect()
            except TypeError:
                pass
            self.dec.stop()
            self.dec.deleteLater()
            self.dec = None
        self._job = None

    def _on_buffer(self):
        if self.dec is None:
            return
        buf = self.dec.read()
        r = buffer_to_mono(buf)
        if r is None:
            return
        mono, sr = r
        if sr <= 0 or mono.size == 0:
            return
        self._sr = sr
        acc, acc_n, done = chunk_peaks(np.abs(mono), max(1, sr * CHUNK_MS // 1000), self._acc, self._acc_n)
        self._chunks.extend(done)
        self._acc, self._acc_n = acc, acc_n

    def _on_finished(self):
        job, chunks = self._job, self._chunks
        if self._acc_n:
            chunks.append(self._acc)
        self.cancel()
        if not job:
            return
        uid, path, s, e = job
        if chunks:
            self.cache.put(path, chunks)
        self.ready.emit(uid, reduce_peaks(slice_peaks(chunks, s, e)))

    def _on_error(self, *_a):
        job = self._job
        log.info("waveform decode failed: %s", job[1] if job else "?")
        self.cancel()
        if job:
            self.ready.emit(job[0], [])
