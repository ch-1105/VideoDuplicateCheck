from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)


class ScanPanel(QWidget):
    scan_requested = Signal(Path, float)
    pause_requested = Signal()
    resume_requested = Signal()
    stop_requested = Signal()
    restart_requested = Signal(Path, float)
    settings_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)

        row = QHBoxLayout()
        self.dir_input = QLineEdit(self)
        self.dir_input.setPlaceholderText("选择要扫描的目录")
        browse_btn = QPushButton("浏览", self)
        browse_btn.clicked.connect(self._pick_directory)
        row.addWidget(QLabel("目录:", self))
        row.addWidget(self.dir_input)
        row.addWidget(browse_btn)
        layout.addLayout(row)

        threshold_row = QHBoxLayout()
        self.threshold_slider = QSlider(self)
        self.threshold_slider.setOrientation(Qt.Orientation.Horizontal)
        self.threshold_slider.setRange(70, 100)
        self.threshold_slider.setValue(90)
        self.threshold_label = QLabel("0.90", self)
        self.threshold_slider.valueChanged.connect(self._on_threshold_change)

        threshold_row.addWidget(QLabel("相似度阈值:", self))
        threshold_row.addWidget(self.threshold_slider)
        threshold_row.addWidget(self.threshold_label)
        layout.addLayout(threshold_row)

        actions = QHBoxLayout()
        self.start_btn = QPushButton("开始扫描", self)
        self.pause_btn = QPushButton("暂停", self)
        self.resume_btn = QPushButton("继续", self)
        self.stop_btn = QPushButton("终止", self)
        self.restart_btn = QPushButton("重新扫描", self)
        self.settings_btn = QPushButton("设置", self)

        self.start_btn.clicked.connect(self._emit_scan)
        self.pause_btn.clicked.connect(self.pause_requested.emit)
        self.resume_btn.clicked.connect(self.resume_requested.emit)
        self.stop_btn.clicked.connect(self.stop_requested.emit)
        self.restart_btn.clicked.connect(self._emit_restart)
        self.settings_btn.clicked.connect(self.settings_requested.emit)

        actions.addWidget(self.start_btn)
        actions.addWidget(self.pause_btn)
        actions.addWidget(self.resume_btn)
        actions.addWidget(self.stop_btn)
        actions.addWidget(self.restart_btn)
        actions.addWidget(self.settings_btn)
        layout.addLayout(actions)

        self.set_scan_state(is_scanning=False, is_paused=False)

    def _pick_directory(self) -> None:
        selected = QFileDialog.getExistingDirectory(self, "选择目录")
        if selected:
            self.dir_input.setText(selected)

    def _on_threshold_change(self, value: int) -> None:
        self.threshold_label.setText(f"{value / 100:.2f}")

    def _emit_scan(self) -> None:
        path = self.dir_input.text().strip()
        if not path:
            return
        threshold = self.threshold_slider.value() / 100
        self.scan_requested.emit(Path(path), threshold)

    def _emit_restart(self) -> None:
        path = self.dir_input.text().strip()
        if not path:
            return
        threshold = self.threshold_slider.value() / 100
        self.restart_requested.emit(Path(path), threshold)

    def set_scan_state(self, *, is_scanning: bool, is_paused: bool) -> None:
        self.start_btn.setEnabled(not is_scanning)
        self.pause_btn.setEnabled(is_scanning and not is_paused)
        self.resume_btn.setEnabled(is_scanning and is_paused)
        self.stop_btn.setEnabled(is_scanning)
        self.restart_btn.setEnabled(True)
