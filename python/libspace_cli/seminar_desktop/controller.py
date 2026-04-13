from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QObject, QThread, Signal

from .models import ActionResult, DiscoverSnapshot, SeminarGuiFormData
from .service import SeminarDesktopService


class _CommandWorker(QThread):
    log_arrived = Signal(str)
    finished_with_result = Signal(object)

    def __init__(self, runner: Callable[..., ActionResult]) -> None:
        super().__init__()
        self.runner = runner

    def run(self) -> None:
        try:
            result = self.runner(log_callback=self.log_arrived.emit)
        except Exception as exc:  # pragma: no cover - UI safety net
            result = ActionResult(success=False, exit_code=1, message=str(exc))
        self.finished_with_result.emit(result)


class SeminarDesktopController(QObject):
    form_loaded = Signal(object)
    snapshot_loaded = Signal(object)
    logs_loaded = Signal(object)
    live_log_arrived = Signal(str)
    busy_changed = Signal(bool, str)
    toast_requested = Signal(str, str, str)

    def __init__(self, service: SeminarDesktopService | None = None) -> None:
        super().__init__()
        self.service = service or SeminarDesktopService()
        self._worker: _CommandWorker | None = None
        self._latest_snapshot: DiscoverSnapshot | None = None

    def initialize(self) -> None:
        form = self.service.load_form()
        self.form_loaded.emit(form)

        snapshot = self.service.load_latest_snapshot()
        self._latest_snapshot = snapshot
        self.snapshot_loaded.emit(snapshot)
        self.logs_loaded.emit(self.service.read_recent_logs())

    def save_form(self, form: SeminarGuiFormData) -> None:
        errors = self.service.validate_form(form, action="save")
        if errors:
            self.toast_requested.emit("error", "保存失败", "\n".join(errors))
            return

        self.service.save_form(form)
        self.form_loaded.emit(form)
        self.toast_requested.emit("success", "配置已保存", "仪表盘摘要已经同步更新。")

    def discover(self, form: SeminarGuiFormData) -> None:
        self._save_and_run(
            form=form,
            action="discover",
            busy_text="正在获取今日空闲研讨室...",
            runner=self.service.discover,
        )

    def reserve_now(self, form: SeminarGuiFormData) -> None:
        self._save_and_run(
            form=form,
            action="reserve",
            busy_text="正在立即提交预约...",
            runner=lambda **kwargs: self.service.reserve(wait=False, **kwargs),
        )

    def reserve_wait(self, form: SeminarGuiFormData) -> None:
        self._save_and_run(
            form=form,
            action="reserve_wait",
            busy_text="正在等待触发时间并准备提交预约...",
            runner=lambda **kwargs: self.service.reserve(wait=True, **kwargs),
        )

    def room_doc_path(self):
        return self.service.room_doc_path()

    def latest_txt_path(self):
        if self._latest_snapshot is not None:
            return self._latest_snapshot.txt_path
        snapshot = self.service.load_latest_snapshot()
        self._latest_snapshot = snapshot
        return snapshot.txt_path if snapshot is not None else None

    def refresh_logs(self) -> None:
        self.logs_loaded.emit(self.service.read_recent_logs())

    def _save_and_run(
        self,
        *,
        form: SeminarGuiFormData,
        action: str,
        busy_text: str,
        runner: Callable[..., ActionResult],
    ) -> None:
        if self._worker is not None and self._worker.isRunning():
            self.toast_requested.emit("warning", "任务仍在运行", "请等待当前任务结束后再发起新的操作。")
            return

        errors = self.service.validate_form(form, action=action)
        if errors:
            self.toast_requested.emit("error", "表单校验失败", "\n".join(errors))
            return

        self.service.save_form(form)
        self.form_loaded.emit(form)
        self.logs_loaded.emit(self.service.read_recent_logs())

        self._worker = _CommandWorker(runner)
        self._worker.log_arrived.connect(self.live_log_arrived)
        self._worker.finished_with_result.connect(self._handle_worker_result)
        self.busy_changed.emit(True, busy_text)
        self._worker.start()

    def _handle_worker_result(self, result: ActionResult) -> None:
        self.busy_changed.emit(False, "")
        self.logs_loaded.emit(self.service.read_recent_logs())

        if result.snapshot is not None:
            self._latest_snapshot = result.snapshot
            self.snapshot_loaded.emit(result.snapshot)

        if result.success:
            self.toast_requested.emit("success", "操作完成", result.message)
        else:
            self.toast_requested.emit("error", "操作失败", result.message)

        if self._worker is not None:
            self._worker.deleteLater()
            self._worker = None
