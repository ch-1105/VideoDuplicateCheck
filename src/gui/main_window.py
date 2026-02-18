from pathlib import Path
import time

from PySide6.QtCore import QThread
from PySide6.QtWidgets import (
    QLabel,
    QMainWindow,
    QProgressBar,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from ..config import AppConfig
from ..core.comparator import DuplicateGroup
from ..workers.scan_worker import ScanWorker
from .preview_widget import PreviewWidget
from .result_panel import ResultPanel
from .scan_panel import ScanPanel
from .settings_dialog import SettingsDialog


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("重复视频查找工具")
        self.resize(1200, 760)

        self.config = AppConfig()
        self._scan_thread: QThread | None = None
        self._scan_worker: ScanWorker | None = None
        self._last_scan_root: Path | None = None
        self._last_threshold: float = self.config.similarity_threshold
        self._restart_pending = False
        self._last_partial_render_time = 0.0
        self._last_partial_processed = 0

        root = QWidget(self)
        layout = QVBoxLayout(root)

        self.scan_panel = ScanPanel()
        self.result_panel = ResultPanel()
        self.preview = PreviewWidget()

        splitter = QSplitter(self)
        splitter.addWidget(self.result_panel)
        splitter.addWidget(self.preview)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 1)

        self.progress = QProgressBar(self)
        self.progress_label = QLabel("准备就绪", self)
        self.task_label = QLabel("当前任务: -", self)

        layout.addWidget(self.scan_panel)
        layout.addWidget(splitter)
        layout.addWidget(self.progress_label)
        layout.addWidget(self.task_label)
        layout.addWidget(self.progress)

        self.setCentralWidget(root)
        self.setStatusBar(QStatusBar(self))

        self.scan_panel.scan_requested.connect(self._start_scan)
        self.scan_panel.pause_requested.connect(self._pause_scan)
        self.scan_panel.resume_requested.connect(self._resume_scan)
        self.scan_panel.stop_requested.connect(self._stop_scan)
        self.scan_panel.restart_requested.connect(self._restart_scan)
        self.scan_panel.settings_requested.connect(self._open_settings)
        self.result_panel.preview_requested.connect(self.preview.set_video)

    def _open_settings(self) -> None:
        dialog = SettingsDialog(
            self.config.frame_interval_seconds,
            self.config.performance_profile,
            self,
        )
        if dialog.exec():
            self.config.frame_interval_seconds = dialog.frame_interval.value()
            self.config.performance_profile = dialog.performance_profile.currentData()
            self.progress_label.setText(
                "设置已更新："
                f"抽帧间隔 {self.config.frame_interval_seconds} 秒，"
                f"性能档位 {self.config.performance_profile}"
            )

    def _start_scan(self, root_dir: Path, threshold: float) -> None:
        if self._scan_thread is not None and self._scan_thread.isRunning():
            return

        self._last_scan_root = root_dir
        self._last_threshold = threshold
        self.config.similarity_threshold = threshold
        self.progress.setValue(0)
        self.result_panel.set_groups([])
        self.preview.clear_preview("扫描进行中，等待结果...")
        self.progress_label.setText("准备开始扫描...")
        self.task_label.setText("当前任务: 初始化扫描任务")
        self._last_partial_render_time = 0.0
        self._last_partial_processed = 0
        self.scan_panel.set_scan_state(is_scanning=True, is_paused=False)

        worker = ScanWorker(root_dir=root_dir, config=self.config)
        thread = QThread(self)

        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._on_scan_progress)
        worker.status.connect(self._on_status)
        worker.current_task.connect(self._on_task)
        worker.partial_groups.connect(self._on_partial_groups)
        worker.finished.connect(self._on_scan_finished)
        worker.stopped.connect(self._on_scan_stopped)
        worker.failed.connect(self._on_scan_failed)
        worker.finished.connect(thread.quit)
        worker.stopped.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._on_thread_finished)

        self._scan_worker = worker
        self._scan_thread = thread
        thread.start()

    def _on_scan_progress(self, current: int, total: int) -> None:
        if total <= 0:
            self.progress.setValue(0)
            return
        self.progress.setValue(int(current / total * 100))

    def _on_status(self, text: str) -> None:
        self.progress_label.setText(text)

    def _on_task(self, text: str) -> None:
        self.task_label.setText(f"当前任务: {text}")

    def _on_scan_finished(self, groups: list[DuplicateGroup]) -> None:
        self.result_panel.set_groups(groups)
        if groups:
            self.preview.clear_preview("请选择左侧文件查看首帧图")
        else:
            self.preview.clear_preview("未发现重复组")
        self.progress_label.setText(f"完成：发现 {len(groups)} 组")
        self.task_label.setText("当前任务: 扫描完成")
        self.scan_panel.set_scan_state(is_scanning=False, is_paused=False)

    def _on_partial_groups(self, groups: list[DuplicateGroup], processed: int, total: int) -> None:
        now = time.monotonic()
        min_delta = max(120, self.config.partial_result_batch_size * 2)
        enough_progress = processed - self._last_partial_processed >= min_delta
        enough_time = (
            now - self._last_partial_render_time >= self.config.partial_result_min_interval_seconds
        )
        should_render = processed >= total or (enough_progress and enough_time)

        if should_render:
            self.result_panel.set_groups(groups)
            self._last_partial_processed = processed
            self._last_partial_render_time = now

        self.progress_label.setText(
            f"批量输出中：已处理 {processed}/{total}，当前重复组 {len(groups)}"
        )

    def _on_scan_stopped(self) -> None:
        self.progress_label.setText("扫描已终止")
        self.task_label.setText("当前任务: 已终止")
        self.progress.setValue(0)
        self.result_panel.set_groups([])
        self.preview.clear_preview("扫描已终止，当前记录已清空")
        self.scan_panel.set_scan_state(is_scanning=False, is_paused=False)

    def _on_scan_failed(self, error: str) -> None:
        self.progress_label.setText(f"扫描失败：{error}")
        self.task_label.setText("当前任务: 失败")
        self.scan_panel.set_scan_state(is_scanning=False, is_paused=False)

    def _pause_scan(self) -> None:
        if self._scan_worker is None:
            return
        self._scan_worker.request_pause()
        self.scan_panel.set_scan_state(is_scanning=True, is_paused=True)

    def _resume_scan(self) -> None:
        if self._scan_worker is None:
            return
        self._scan_worker.request_resume()
        self.scan_panel.set_scan_state(is_scanning=True, is_paused=False)

    def _stop_scan(self) -> None:
        if self._scan_worker is None:
            return
        self._scan_worker.request_stop()

    def _restart_scan(self, root_dir: Path, threshold: float) -> None:
        self._last_scan_root = root_dir
        self._last_threshold = threshold
        if self._scan_thread is not None and self._scan_thread.isRunning():
            self._restart_pending = True
            self._stop_scan()
            return
        self._start_scan(root_dir, threshold)

    def _on_thread_finished(self) -> None:
        self._scan_thread = None
        self._scan_worker = None
        if self._restart_pending and self._last_scan_root is not None:
            self._restart_pending = False
            self._start_scan(self._last_scan_root, self._last_threshold)
