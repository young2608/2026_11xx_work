# -*- coding: utf-8 -*-
"""곡 우클릭 메뉴 · 스마트 재생목록 메뉴 (vr0.1.0.019 R6 — ui/library_views.py 에서 나눔, 홈 · 라이브러리 공용)"""
import os

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QMenu

from . import icons
from .qtutil import exec_menu


KEY_ROLE = Qt.ItemDataRole.UserRole


def _label(d: dict) -> str:
    t = d.get("title") or os.path.splitext(os.path.basename(d.get("path", "")))[0]
    return f"{d['artist']} - {t}" if d.get("artist") else t


def track_menu(parent, ctrl, keys_fn, single_key=None):
    """곡 우클릭 메뉴 (홈·라이브러리 공용)"""
    m = QMenu(parent)
    m.addAction("재생", lambda: ctrl.play_mix(keys_fn(), "선택"))
    m.addAction("다음에 재생", lambda: ctrl.play_next(keys_fn()))
    m.addAction("대기열 끝에 추가", lambda: ctrl.enqueue(keys_fn()))
    if single_key:
        m.addSeparator()
        m.addAction("이 곡으로 라디오", lambda: ctrl.radio(single_key))
        m.addAction("좋아요 ♥ 켜기/끄기", lambda: ctrl.toggle_like(single_key))
        rm = m.addMenu("별점")
        for r in range(6):
            rm.addAction("☆ 없음" if r == 0 else "★" * r, lambda r=r: ctrl.set_rating(single_key, r))
        tm = m.addMenu("상황 태그")
        from ..domain.recommend import MOODS
        cur = set(ctrl.library.tags_of(single_key))
        for mk, (label, _) in MOODS.items():
            a = tm.addAction(label)
            a.setCheckable(True)
            a.setChecked(mk in cur)
            a.toggled.connect(lambda on, mk=mk: (ctrl.library.add_tag if on else ctrl.library.remove_tag)(single_key, mk))
    return m


def show_smart_menu(parent, ctrl, btn):
    """스마트 재생목록 (W7) — 규칙으로 자동 생성, 고르면 바로 재생"""
    from ..domain.smart import RULES
    m = QMenu(parent)
    lists = ctrl.smart_lists(RULES)                 # v019: 통계 1번 (전에는 규칙마다 + 고를 때 또 = 8번)
    for rid, (label, _desc) in RULES.items():
        keys = lists.get(rid, [])
        n = len(keys)
        a = m.addAction(icons.icon("smart", "dim"), f"{label}  ({n})", lambda keys=keys, label=label: ctrl.play_mix(keys, label))
        a.setEnabled(n > 0)
        a.setToolTip(_desc)
    m.setToolTipsVisible(True)
    exec_menu(m, btn.mapToGlobal(btn.rect().bottomLeft()))
