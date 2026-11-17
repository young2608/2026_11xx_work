"""Qt 공용 도우미 (vr0.1.0.007).

장시간 운용: 부모를 가진 QMenu / QDialog 를 exec() 한 뒤 그대로 두면 부모(메인 창)가 닫힐 때까지
자식으로 계속 쌓임 (우클릭할 때마다 메뉴 1개씩 누수). 아래 함수로 띄우면 닫힌 뒤 바로 삭제.
"""


def exec_menu(menu, pos):
    """메뉴를 띄우고 닫히면 삭제. 반환: 고른 QAction (또는 None)"""
    try:
        return menu.exec(pos)
    finally:
        menu.deleteLater()


def exec_dialog(dialog) -> int:
    """대화상자를 모달로 띄우고 닫히면 삭제. 반환: exec() 결과"""
    try:
        return dialog.exec()
    finally:
        dialog.deleteLater()
