import time
from dataclasses import dataclass


@dataclass
class Query:
    path: str
    title: str = ""
    artist: str = ""
    album: str = ""
    duration: float = 0.0       # 초
    embedded: str = ""          # 태그 내장 가사


class Provider:
    name = "base"
    timeout = 5.0

    def call_timeout(self) -> float:
        """요청 1건 제한 시간 — 전체 마감(deadline)까지 남은 시간을 넘지 않게 (vr0.1.0.011b)
        → 곡을 넘기거나 프로그램을 닫을 때 끝나지 않은 요청이 오래 붙잡지 않음"""
        d = getattr(self, "deadline", None)
        if d is None:
            return float(self.timeout)
        return max(0.3, min(float(self.timeout), d - time.monotonic()))

    def fetch(self, q: Query) -> str | None:
        """LRC(또는 일반) 가사 텍스트. 없으면 None. 네트워크 오류는 예외 대신 None."""
        raise NotImplementedError


class NetError(Exception):
    """네트워크 · 서버 오류 (vr0.1.0.011) — '못 찾음'과 구분해 상태 표시 · 실패 기억에서 뺌"""
