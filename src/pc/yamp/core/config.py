# -*- coding: utf-8 -*-
"""
설정: config.txt (사용자 설정) + data/state.json (실행 상태)

config.txt
  - 위치: exe 와 같은 폴더 (소스 실행: pc/ 폴더, 테스트: 환경변수 YAMP_HOME)
  - 형식: key = value   ('#' / ';' 주석, [section] 은 보기용)
  - 시작 시 읽어서 적용. 없으면 기본값으로 생성
  - 메뉴에서 바꾼 값은 주석·순서를 그대로 두고 해당 줄만 갱신
  - 모르는 키 / 잘못된 값은 무시하고 기본값 사용 (로그에 경고)

설정 항목 표(기본값 · 범위 · config.txt 기본 내용)는 config_schema.py (v019 R4).

state.json (data_dir 안) : 창 위치, 볼륨, 마지막 곡·위치, 곡별 가사 싱크 등 — 사용자가 고칠 필요 없는 값
"""
import json
import logging
import os
import re
import sys
from pathlib import Path

from .config_schema import CHOICES, DEFAULT_CONFIG_TEXT, FILE_DEFAULTS, LIMITS, STATE_DEFAULTS  # noqa: F401  (v019 R4)

log = logging.getLogger("yamp.config")


_LINE_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$")


def base_dir() -> Path:
    """config.txt 가 있는 폴더"""
    env = os.environ.get("YAMP_HOME")
    if env:
        return Path(env)
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]          # core -> yamp -> pc


def appdata_dir() -> Path:
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA", Path.home())) / "yMp3Player"
    return Path.home() / ".config" / "yMp3Player"


def convert(key: str, raw: str, default):
    """문자열 → 기본값 타입. 잘못된 값은 ValueError"""
    raw = raw.strip()
    if isinstance(default, bool):
        low = raw.lower()
        if low in ("1", "true", "yes", "on", "y"):
            return True
        if low in ("0", "false", "no", "off", "n", ""):
            return False
        raise ValueError(raw)
    if isinstance(default, int):
        v = int(raw)
    elif isinstance(default, float):
        v = float(raw)
    else:
        v = raw
        if key in CHOICES:
            u = v.upper() if key == "log_level" else v.lower()
            if key in ("eq_bands", "sound"):
                return v
            if u not in CHOICES[key]:
                raise ValueError(raw)
            v = u
        return v
    lo, hi = LIMITS.get(key, (None, None))
    if lo is not None:
        v = min(max(v, type(default)(lo)), type(default)(hi))
    return v


def to_text(v) -> str:
    if isinstance(v, bool):
        return "1" if v else "0"
    return str(v)


def parse_config_text(text: str) -> tuple[dict, list[str]]:
    """config.txt 내용 → ({key: 값}, [경고]). 모르는 키·잘못된 값은 경고 후 무시"""
    out, warns = {}, []
    for n, line in enumerate(text.splitlines(), 1):
        s = line.strip()
        if not s or s[0] in "#;[":
            continue
        m = _LINE_RE.match(line)
        if not m:
            warns.append(f"config.txt:{n} 형식 오류: {s}")
            continue
        k, raw = m.group(1).lower(), m.group(2)
        if k not in FILE_DEFAULTS:
            warns.append(f"config.txt:{n} 알 수 없는 키: {k}")
            continue
        try:
            out[k] = convert(k, raw, FILE_DEFAULTS[k])
        except ValueError:
            warns.append(f"config.txt:{n} 잘못된 값: {k} = {raw} (기본값 {to_text(FILE_DEFAULTS[k])} 사용)")
    return out, warns


def update_config_text(text: str, values: dict) -> str:
    """주석·순서 유지, 해당 키 줄만 값 교체. 없는 키는 끝에 추가"""
    lines = text.splitlines()
    done = set()
    for i, line in enumerate(lines):
        s = line.strip()
        if not s or s[0] in "#;[":
            continue
        m = _LINE_RE.match(line)
        if m and m.group(1).lower() in values:
            k = m.group(1).lower()
            head = line[: line.index("=") + 1]
            lines[i] = f"{head} {to_text(values[k])}"
            done.add(k)
    for k, v in values.items():
        if k not in done:
            lines += default_comment(k)          # 설명 주석도 같이 (vr0.1.0.010, P1)
            lines.append(f"{k:<16} = {to_text(v)}")
    return "\n".join(lines) + "\n"


def default_comment(key: str) -> list[str]:
    """DEFAULT_CONFIG_TEXT 에서 key 줄 바로 위의 '#' 설명 줄들"""
    lines = DEFAULT_CONFIG_TEXT.splitlines()
    for i, line in enumerate(lines):
        m = _LINE_RE.match(line)
        if m and m.group(1).lower() == key and not line.lstrip().startswith("#"):
            j = i
            while j > 0 and lines[j - 1].lstrip().startswith("#") and not lines[j - 1].startswith("# ===="):
                j -= 1
            return lines[j:i]
    return []


def missing_keys_text(text: str) -> str:
    """사용자 config.txt 에 없는 설정 키 → 설명과 함께 덧붙일 글 (없으면 빈 문자열)"""
    have, _w = parse_config_text(text)
    present = set(have)
    for line in text.splitlines():                      # 값이 잘못돼 버려진 키도 '있음'으로
        m = _LINE_RE.match(line)
        if m and not line.lstrip().startswith(("#", ";")):
            present.add(m.group(1).lower())
    miss = [k for k in FILE_DEFAULTS if k not in present]
    if not miss:
        return ""
    out = ["", "# ---- 새 버전에서 생긴 설정 (기본값으로 추가됨) ----"]
    for k in miss:
        out += default_comment(k)
        out.append(f"{k:<16} = {to_text(FILE_DEFAULTS[k])}")
    return "\n".join(out) + "\n"


class Config:
    def __init__(self, base: Path | None = None):
        self.base = Path(base) if base else base_dir()
        self.path = self.base / "config.txt"
        self.file = dict(FILE_DEFAULTS)
        self.state = json.loads(json.dumps(STATE_DEFAULTS))
        self.warnings: list[str] = []
        self._dirty_file: set[str] = set()
        self._load_file()
        self.data_dir = self._resolve_data_dir()
        self.state_path = self.data_dir / "state.json"
        self._load_state()

    # ---------------- config.txt
    def _load_file(self):
        try:
            text = self.path.read_text(encoding="utf-8-sig")
        except FileNotFoundError:
            try:
                self.base.mkdir(parents=True, exist_ok=True)
                self.path.write_text(DEFAULT_CONFIG_TEXT, encoding="utf-8")
            except OSError as e:
                self.warnings.append(f"config.txt 생성 실패: {e}")
            return
        except (OSError, UnicodeDecodeError) as e:
            self.warnings.append(f"config.txt 읽기 실패: {e} (기본값 사용)")
            return
        vals, warns = parse_config_text(text)
        self.file.update(vals)
        self.warnings += warns
        add = missing_keys_text(text)                  # P1: 예전 config.txt 에 새 설정을 설명과 함께 한 번 추가
        if add:
            try:
                self.path.write_text(text.rstrip("\n") + "\n" + add, encoding="utf-8")
            except OSError:
                pass

    def path_of(self, key: str) -> Path:
        p = Path(str(self.file.get(key) or ""))
        return p if p.is_absolute() else self.base / p

    def _resolve_data_dir(self) -> Path:
        for d in (self.path_of("data_dir"), appdata_dir()):
            try:
                d.mkdir(parents=True, exist_ok=True)
                probe = d / ".write_test"
                probe.write_text("x", encoding="utf-8")
                probe.unlink()
                return d
            except OSError:
                continue
        return self.base

    # ---------------- state.json
    def _load_state(self):
        try:
            raw = json.loads(self.state_path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                for k, v in raw.items():
                    if k in STATE_DEFAULTS:
                        self.state[k] = v
        except FileNotFoundError:
            pass
        except (OSError, ValueError):
            try:
                self.state_path.replace(self.state_path.with_suffix(".json.corrupt"))
            except OSError:
                pass

    # ---------------- 접근
    def __getitem__(self, k):
        if k in self.file:
            return self.file[k]
        if k in self.state:
            return self.state[k]
        return FILE_DEFAULTS.get(k, STATE_DEFAULTS.get(k))

    def __setitem__(self, k, v):
        if k in FILE_DEFAULTS:
            if self.file.get(k) != v:
                self.file[k] = v
                self._dirty_file.add(k)
        else:
            self.state[k] = v

    def get(self, k, default=None):
        v = self[k]
        return default if v is None else v

    def save(self):
        """state.json 저장 + config.txt 는 바뀐 키만 그 줄 갱신"""
        text = json.dumps(self.state, ensure_ascii=False, indent=2)
        if text != getattr(self, "_saved_state", None) or not self.state_path.exists():   # 같으면 쓰지 않음 (자동 저장)
            tmp = self.state_path.with_suffix(".json.tmp")
            tmp.write_text(text, encoding="utf-8")
            os.replace(tmp, self.state_path)
            self._saved_state = text
        if self._dirty_file:
            try:
                text = self.path.read_text(encoding="utf-8-sig") if self.path.exists() else DEFAULT_CONFIG_TEXT
                text = update_config_text(text, {k: self.file[k] for k in self._dirty_file})
                t2 = self.path.with_suffix(".txt.tmp")
                t2.write_text(text, encoding="utf-8")
                os.replace(t2, self.path)
                self._dirty_file.clear()
            except OSError as e:
                log.warning("config.txt 저장 실패: %s", e)


def app_dir() -> Path:  # 호환: 데이터 폴더
    return Config().data_dir
