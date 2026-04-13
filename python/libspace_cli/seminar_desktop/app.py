from __future__ import annotations

import io
import os
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
    from PySide6.QtCore import QTimer, Qt, QUrl
    from PySide6.QtGui import QColor, QDesktopServices, QFont, QResizeEvent
    from PySide6.QtWidgets import QApplication
    from qfluentwidgets import (
        FluentIcon as FIF,
        InfoBar,
        InfoBarPosition,
        MSFluentWindow,
        NavigationItemPosition,
        PillPushButton,
        Theme,
        setTheme,
        setThemeColor,
    )

from .controller import SeminarDesktopController
from .views import DashboardPage, LogDrawer, LogsPage, SettingsPage


APP_QSS = """
/* Global premium tokens */
QWidget {
    color: #F3F7FB;
    font-family: "Microsoft YaHei UI";
    font-size: 10pt;
}

/* Scroll areas and page canvas */
QScrollArea#pageScrollArea,
QScrollArea#pageScrollArea > QWidget > QWidget {
    background: transparent;
    border: none;
}

QScrollBar:vertical {
    background: transparent;
    width: 12px;
    margin: 4px;
}

QScrollBar::handle:vertical {
    background: rgba(255, 255, 255, 40);
    border-radius: 6px;
    min-height: 32px;
}

QScrollBar::handle:vertical:hover {
    background: rgba(0, 120, 212, 120);
}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical {
    background: transparent;
    height: 0px;
}

/* Input surfaces */
QLineEdit#shellField,
QTextEdit#shellField,
QPlainTextEdit#shellField,
QWidget#shellField {
    background: transparent;
    border: none;
    color: #F3F7FB;
    selection-background-color: rgba(0, 120, 212, 160);
    font: 500 10.5pt "Microsoft YaHei UI";
}

QLineEdit#shellField {
    min-height: 24px;
}

QLineEdit#shellField::placeholder,
QTextEdit#shellField::placeholder {
    color: rgba(231, 239, 247, 120);
}

QTextEdit#shellField,
QPlainTextEdit#shellField {
    padding-top: 4px;
}

/* Drawer console */
QFrame#logDrawer {
    background: rgba(11, 16, 24, 224);
    border: 1px solid rgba(255, 255, 255, 34);
    border-radius: 24px;
}

QPlainTextEdit {
    background: rgba(6, 9, 14, 160);
    border: 1px solid rgba(255, 255, 255, 26);
    border-radius: 16px;
    padding: 14px;
    color: #DCEAF8;
    font: 10pt "Consolas";
}

QTreeWidget#resultsTree {
    background: rgba(9, 13, 19, 164);
    border: 1px solid rgba(255, 255, 255, 24);
    border-radius: 18px;
    padding: 8px;
    outline: none;
}

QTreeWidget#resultsTree::item {
    min-height: 34px;
    border-radius: 10px;
}

QTreeWidget#resultsTree::item:selected {
    background: rgba(0, 120, 212, 70);
    color: #F3F7FB;
}

QTreeWidget#resultsTree::item:hover {
    background: rgba(255, 255, 255, 16);
}

QHeaderView::section {
    background: rgba(255, 255, 255, 12);
    color: rgba(236, 244, 252, 220);
    border: none;
    border-bottom: 1px solid rgba(255, 255, 255, 22);
    padding: 10px 12px;
    font: 600 10pt "Microsoft YaHei UI";
}

QLabel#emptyStateLabel {
    color: rgba(227, 237, 248, 168);
    padding: 18px 0 8px 0;
}
"""


class SeminarMainWindow(MSFluentWindow):
    def __init__(self) -> None:
        self.log_drawer: LogDrawer | None = None
        self.log_fab: PillPushButton | None = None
        super().__init__()
        self.controller = SeminarDesktopController()

        self.setWindowTitle("独立研讨室预约系统")
        self.resize(1520, 980)
        self.setMinimumSize(1280, 840)
        try:
            self.setWindowIcon(FIF.APPLICATION.icon())
        except Exception:  # pragma: no cover - icon fallback
            pass
        try:
            self.setMicaEffectEnabled(True)
        except Exception:  # pragma: no cover - not all systems support Mica
            pass

        self.dashboard_page = DashboardPage(self)
        self.settings_page = SettingsPage(self)
        self.logs_page = LogsPage(self)

        self.dashboard_page.setObjectName("dashboard-page")
        self.settings_page.setObjectName("settings-page")
        self.logs_page.setObjectName("logs-page")

        self.addSubInterface(self.dashboard_page, FIF.HOME, "仪表盘(预约)")
        self.addSubInterface(self.settings_page, FIF.SETTING, "偏好设置")
        self.addSubInterface(self.logs_page, FIF.HISTORY, "运行日志", position=NavigationItemPosition.BOTTOM)

        self.log_drawer = LogDrawer(self)
        self.log_fab = PillPushButton(self)
        self.log_fab.setText("日志控制台")
        self.log_fab.clicked.connect(self.log_drawer.toggle)
        self.log_drawer.height_changed.connect(self._reposition_overlays)
        self._reposition_overlays()

        self.dashboard_page.save_requested.connect(self._save_form)
        self.dashboard_page.discover_requested.connect(self._discover_today)
        self.dashboard_page.reserve_now_requested.connect(self._reserve_now)
        self.dashboard_page.reserve_wait_requested.connect(self._reserve_wait)
        self.dashboard_page.open_txt_requested.connect(self._open_latest_txt)
        self.dashboard_page.open_doc_requested.connect(self._open_room_doc)
        self.dashboard_page.settings_requested.connect(lambda: self.switchTo(self.settings_page))
        self.settings_page.save_requested.connect(self._save_form)
        self.logs_page.refresh_requested.connect(self.controller.refresh_logs)

        self.controller.form_loaded.connect(self._bind_form)
        self.controller.snapshot_loaded.connect(self.dashboard_page.set_snapshot)
        self.controller.logs_loaded.connect(self._bind_logs)
        self.controller.live_log_arrived.connect(self.log_drawer.append_line)
        self.controller.busy_changed.connect(self._handle_busy_state)
        self.controller.toast_requested.connect(self._show_toast)

        QTimer.singleShot(0, self.controller.initialize)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._reposition_overlays()

    def _reposition_overlays(self) -> None:
        if self.log_drawer is None or self.log_fab is None:
            return
        drawer_width = min(480, max(360, self.width() // 3))
        drawer_height = self.log_drawer.overlay_height
        drawer_x = self.width() - drawer_width - 28
        drawer_y = self.height() - drawer_height - 28
        if drawer_height > 0:
            self.log_drawer.setGeometry(drawer_x, drawer_y, drawer_width, drawer_height)

        fab_size = self.log_fab.sizeHint()
        self.log_fab.resize(fab_size)
        self.log_fab.move(self.width() - fab_size.width() - 28, self.height() - drawer_height - fab_size.height() - 40)

    def _current_form(self):
        return self.settings_page.collect_form()

    def _bind_form(self, form) -> None:
        self.settings_page.bind_form(form)
        self.dashboard_page.set_form_summary(form)

    def _bind_logs(self, lines) -> None:
        self.logs_page.set_logs(lines)
        self.log_drawer.set_lines(lines)

    def _handle_busy_state(self, busy: bool, busy_text: str) -> None:
        self.dashboard_page.set_busy(busy, busy_text)
        self.settings_page.set_busy(busy)
        self.logs_page.set_busy(busy)
        self.log_drawer.set_status(busy_text if busy else "等待操作")

    def _show_toast(self, kind: str, title: str, content: str) -> None:
        method = {
            "success": InfoBar.success,
            "warning": InfoBar.warning,
            "error": InfoBar.error,
        }.get(kind, InfoBar.info)
        method(title=title, content=content, duration=2600, position=InfoBarPosition.TOP_RIGHT, parent=self)

    def _save_form(self) -> None:
        self.controller.save_form(self._current_form())

    def _discover_today(self) -> None:
        self.controller.discover(self._current_form())

    def _reserve_now(self) -> None:
        self.controller.reserve_now(self._current_form())

    def _reserve_wait(self) -> None:
        self.controller.reserve_wait(self._current_form())

    def _open_room_doc(self) -> None:
        self._open_path(self.controller.room_doc_path())

    def _open_latest_txt(self) -> None:
        txt_path = self.controller.latest_txt_path()
        if txt_path is None:
            self._show_toast("warning", "尚未生成 TXT", "请先点击“获取今日空闲”。")
            return
        self._open_path(txt_path)

    def _open_path(self, path: Path) -> None:
        if not path.exists():
            self._show_toast("error", "文件不存在", str(path))
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))


def create_application() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    app.setFont(QFont("Microsoft YaHei UI", 10))
    setTheme(Theme.DARK)
    setThemeColor(QColor("#0078D4"))
    app.setStyleSheet(APP_QSS)
    return app


def main() -> int:
    app = create_application()
    window = SeminarMainWindow()
    window.show()
    if os.environ.get("SEMINAR_GUI_SMOKE") == "1":
        QTimer.singleShot(250, app.quit)
    return app.exec()
