"""
cat-trash for Windows
- 떠다니는 위젯 형태의 보조 휴지통
- 평소: 입 다문 고양이 (대기 상태)
- 파일 드래그가 위에 올라옴: 입 벌림 (받을 준비)
- 드래그가 그냥 떠남: 즉시 입 다묾
- 실제 드롭됨: 입 벌린 채 휴지통 이동 → 1초 후 입 다묾 (다 먹음)
- 우클릭: 휴지통 비우기 / 위치 잠금 / 종료

[실행 전 준비]
    py -m pip install PySide6 send2trash

[실행]
    py cat_trash_win.py

같은 폴더에 다음 두 PNG가 있어야 함:
    white_open.png    (입 벌린 상태 - 호버/드롭 시)
    white_closed.png  (입 다문 상태 - 평소)
"""
from __future__ import annotations

import os
import sys
import subprocess
from pathlib import Path

from PySide6.QtCore import Qt, QPoint, QTimer, QSize
from PySide6.QtGui import QAction, QPixmap, QIcon, QCursor, QMouseEvent
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QMenu,
    QSystemTrayIcon,
    QWidget,
)

# Windows 네이티브 휴지통 API 직접 호출
import ctypes
from ctypes import wintypes


def move_to_recycle_bin(paths: list[str]) -> tuple[int, int]:
    """SHFileOperationW로 휴지통 이동. (성공수, 실패수) 반환."""
    if not paths:
        return 0, 0

    FO_DELETE = 0x0003
    FOF_ALLOWUNDO = 0x0040          # 휴지통으로 (이게 빠지면 영구 삭제)
    FOF_NOCONFIRMATION = 0x0010      # 확인 창 없음
    FOF_SILENT = 0x0004              # 진행 표시줄 숨김
    FOF_NOERRORUI = 0x0400           # 에러 다이얼로그 숨김

    class SHFILEOPSTRUCTW(ctypes.Structure):
        _fields_ = [
            ("hwnd", wintypes.HWND),
            ("wFunc", wintypes.UINT),
            ("pFrom", wintypes.LPCWSTR),
            ("pTo", wintypes.LPCWSTR),
            ("fFlags", ctypes.c_ushort),
            ("fAnyOperationsAborted", wintypes.BOOL),
            ("hNameMappings", ctypes.c_void_p),
            ("lpszProgressTitle", wintypes.LPCWSTR),
        ]

    # 경로는 \0 구분 + \0\0 종료
    src = "\0".join(paths) + "\0\0"

    op = SHFILEOPSTRUCTW()
    op.hwnd = None
    op.wFunc = FO_DELETE
    op.pFrom = src
    op.pTo = None
    op.fFlags = FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT | FOF_NOERRORUI

    rc = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op))
    if rc == 0 and not op.fAnyOperationsAborted:
        return len(paths), 0
    print(f"[SHFileOperationW] return code={rc}, aborted={op.fAnyOperationsAborted}")
    return 0, len(paths)

# 위젯 크기
WIDGET_SIZE = 96

# 리소스 경로 - PyInstaller 단일 .exe 모드와 일반 .py 실행 모두 지원
APP_DIR = Path(__file__).resolve().parent


def resource_path(filename: str) -> Path:
    """PyInstaller로 빌드된 .exe에서는 임시 풀린 폴더(_MEIPASS), 평소엔 .py 폴더."""
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / filename
    return APP_DIR / filename


IMG_OPEN = resource_path("white_open.png")
IMG_CLOSED = resource_path("white_closed.png")

# 설정 파일은 항상 사용자 홈에 저장 (.exe 옆엔 쓰기 권한 없을 수 있음)
CONFIG_FILE = Path(os.path.expanduser("~")) / ".cat_trash_config.txt"


class CatTrashWidget(QWidget):
    def __init__(self) -> None:
        super().__init__()

        # 프레임 없는 + 작업표시줄 미표시 (StaysOnTop 제거 - 바탕화면 레이어로 보낼 것)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAcceptDrops(True)
        self.resize(WIDGET_SIZE, WIDGET_SIZE)

        # 이미지 라벨
        self.label = QLabel(self)
        self.label.setGeometry(0, 0, WIDGET_SIZE, WIDGET_SIZE)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 픽스맵 미리 로드
        self._pix_open = self._load_pixmap(IMG_OPEN)
        self._pix_closed = self._load_pixmap(IMG_CLOSED)
        self._set_state_closed()  # 시작 상태: 입 다묾

        # 드래그 이동용
        self._drag_offset: QPoint | None = None
        self._locked: bool = False

        # 복귀 타이머 (드롭 후 입 다물기로 복귀)
        self._revert_timer = QTimer(self)
        self._revert_timer.setSingleShot(True)
        self._revert_timer.timeout.connect(self._set_state_closed)

        # 마지막 위치 복원
        self._restore_position()

        # "잠깐 위로 올라온 상태"에서 자동 복귀시키는 타이머
        self._summon_revert_timer = QTimer(self)
        self._summon_revert_timer.setSingleShot(True)
        self._summon_revert_timer.timeout.connect(self._pin_to_desktop)

    # ---------- 바탕화면 레이어 / 소환 ----------
    def _pin_to_desktop(self) -> None:
        """위젯을 z-order 맨 아래로 보내 다른 창들 뒤에 위치시킴.

        SetParent(Progman) 방식은 Win11에서 위젯이 안 보이는 문제가 있어
        SetWindowPos(HWND_BOTTOM)로 변경.
        """
        try:
            user32 = ctypes.windll.user32
            HWND_BOTTOM = 1
            SWP_NOMOVE = 0x0002
            SWP_NOSIZE = 0x0001
            SWP_NOACTIVATE = 0x0010
            SWP_SHOWWINDOW = 0x0040
            hwnd = int(self.winId())
            user32.SetWindowPos(
                hwnd, HWND_BOTTOM, 0, 0, 0, 0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW,
            )
            print(f"[desktop] sent to bottom of z-order (hwnd={hwnd})")
        except Exception as exc:
            print(f"[desktop] pin failed: {exc}")

    def _summon(self) -> None:
        """위젯을 잠시 모든 창 위로 올림. 5초 후 다시 바닥으로 복귀."""
        try:
            user32 = ctypes.windll.user32
            HWND_TOPMOST = -1
            SWP_NOMOVE = 0x0002
            SWP_NOSIZE = 0x0001
            SWP_SHOWWINDOW = 0x0040
            hwnd = int(self.winId())
            self.show()
            user32.SetWindowPos(
                hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW,
            )
            self.raise_()
            self.activateWindow()
            self._summon_revert_timer.start(5000)
            print("[summon] widget raised to topmost (will sink back in 5s)")
        except Exception as exc:
            print(f"[summon] failed: {exc}")

    # ---------- 이미지 ----------
    def _load_pixmap(self, path: Path) -> QPixmap:
        if not path.exists():
            print(f"이미지 누락: {path}")
            sys.exit(1)
        pix = QPixmap(str(path))
        return pix.scaled(
            QSize(WIDGET_SIZE, WIDGET_SIZE),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

    def _set_state_open(self) -> None:
        self.label.setPixmap(self._pix_open)

    def _set_state_closed(self) -> None:
        self.label.setPixmap(self._pix_closed)

    # ---------- 드래그 앤 드롭 ----------
    def dragEnterEvent(self, event):
        print("[drag] enter")
        if event.mimeData().hasUrls():
            self._revert_timer.stop()
            self._set_state_open()
            # 명시적으로 Move 액션 강제 (커서 + 표시 제거)
            event.setDropAction(Qt.DropAction.MoveAction)
            event.accept()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.setDropAction(Qt.DropAction.MoveAction)
            event.accept()

    def dragLeaveEvent(self, event):
        print("[drag] leave (no drop)")
        self._set_state_closed()
        event.accept()

    def dropEvent(self, event):
        print("[drop] event fired")
        urls = event.mimeData().urls()
        print(f"[drop] received {len(urls)} url(s)")

        paths = []
        for url in urls:
            local = url.toLocalFile()
            print(f"[drop]   raw url={url.toString()!r}, local path={local!r}")
            if local:
                paths.append(local)

        if not paths:
            print("[drop] no local paths - aborting")
            self._set_state_closed()
            return

        self._set_state_open()

        # Windows 네이티브 API로 휴지통 이동
        ok, fail = move_to_recycle_bin(paths)
        print(f"[drop] result: {ok} moved, {fail} failed")

        if ok > 0:
            self._play_sound()

        # 결과를 화면에 잠시 표시 (성공이면 입 다묾, 실패면 그대로 입 벌림 상태 유지)
        self._revert_timer.start(400)

        # 드롭 액션 명시 - Move로 처리됐음을 source에게 알림
        event.setDropAction(Qt.DropAction.MoveAction)
        event.accept()

    # ---------- 마우스: 위치 이동 ----------
    def mousePressEvent(self, event: QMouseEvent):
        if self._locked:
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._locked or self._drag_offset is None:
            return
        if event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        self._drag_offset = None
        self._save_position()

    # ---------- 우클릭 메뉴 ----------
    def contextMenuEvent(self, event):
        menu = QMenu(self)
        a_empty = QAction("휴지통 비우기", self)
        a_empty.triggered.connect(self._empty_recycle_bin)
        menu.addAction(a_empty)

        menu.addSeparator()

        a_lock = QAction("위치 잠금 해제" if self._locked else "위치 잠금", self)
        a_lock.triggered.connect(self._toggle_lock)
        menu.addAction(a_lock)

        menu.addSeparator()

        a_quit = QAction("종료", self)
        a_quit.triggered.connect(QApplication.quit)
        menu.addAction(a_quit)

        menu.exec(event.globalPos())

    def _toggle_lock(self):
        self._locked = not self._locked
        self._save_position()

    def _empty_recycle_bin(self):
        try:
            subprocess.run(
                ["powershell", "-NoProfile", "-Command", "Clear-RecycleBin -Force -ErrorAction SilentlyContinue"],
                check=False,
                creationflags=0x08000000,
            )
            self._set_state_open()
            self._play_sound()
            self._revert_timer.start(400)
        except Exception as exc:
            print(f"휴지통 비우기 실패: {exc}")

    # ---------- 사운드 ----------
    def _play_sound(self):
        try:
            winsound.PlaySound("SystemAsterisk", winsound.SND_ALIAS | winsound.SND_ASYNC)
        except Exception:
            pass

    # ---------- 위치 저장/복원 ----------
    def _save_position(self):
        try:
            CONFIG_FILE.write_text(
                f"{self.x()},{self.y()},{int(self._locked)}",
                encoding="utf-8",
            )
        except Exception:
            pass

    def _restore_position(self):
        try:
            if CONFIG_FILE.exists():
                parts = CONFIG_FILE.read_text(encoding="utf-8").strip().split(",")
                if len(parts) >= 2:
                    self.move(int(parts[0]), int(parts[1]))
                if len(parts) >= 3:
                    self._locked = bool(int(parts[2]))
                return
        except Exception:
            pass
        screen = QApplication.primaryScreen().availableGeometry()
        self.move(screen.right() - WIDGET_SIZE - 40, screen.bottom() - WIDGET_SIZE - 40)


def setup_tray(widget, app):
    """시스템 트레이 아이콘. 좌클릭 = 소환, 우클릭 = 메뉴."""
    tray = QSystemTrayIcon(QIcon(str(IMG_OPEN)), parent=widget)
    tray.setToolTip("CatTrash - 클릭하면 잠깐 위로 올라옴")

    menu = QMenu()

    a_summon = QAction("잠깐 위로 올리기 (5초)", widget)
    a_summon.triggered.connect(widget._summon)
    menu.addAction(a_summon)

    a_pin = QAction("바탕화면에 다시 고정", widget)
    a_pin.triggered.connect(widget._pin_to_desktop)
    menu.addAction(a_pin)

    menu.addSeparator()

    a_empty = QAction("휴지통 비우기", widget)
    a_empty.triggered.connect(widget._empty_recycle_bin)
    menu.addAction(a_empty)

    menu.addSeparator()

    a_quit = QAction("종료", widget)
    a_quit.triggered.connect(app.quit)
    menu.addAction(a_quit)

    tray.setContextMenu(menu)

    def on_activated(reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            widget._summon()
    tray.activated.connect(on_activated)

    tray.show()
    return tray


def main():
    print("[boot] cat-trash starting")
    print(f"[boot] IMG_OPEN={IMG_OPEN} (exists={IMG_OPEN.exists()})")
    print(f"[boot] IMG_CLOSED={IMG_CLOSED} (exists={IMG_CLOSED.exists()})")
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    if IMG_OPEN.exists():
        app.setWindowIcon(QIcon(str(IMG_OPEN)))

    widget = CatTrashWidget()
    widget.show()

    # HWND가 완전히 만들어진 뒤 바닥으로 보냄
    QTimer.singleShot(300, widget._pin_to_desktop)

    tray = setup_tray(widget, app)
    print("[boot] tray ready, widget pushed to bottom of z-order")

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
