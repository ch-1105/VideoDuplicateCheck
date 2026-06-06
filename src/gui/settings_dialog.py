from PySide6.QtWidgets import QComboBox, QDialog, QFormLayout, QHBoxLayout, QPushButton, QSpinBox

from ..config import PerformanceProfile


class SettingsDialog(QDialog):
    def __init__(
        self,
        frames_per_minute: int,
        performance_profile: PerformanceProfile,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("设置")

        layout = QFormLayout(self)
        self.frames_per_minute = QSpinBox(self)
        self.frames_per_minute.setRange(1, 12)
        self.frames_per_minute.setValue(frames_per_minute)
        layout.addRow("每分钟抽帧数", self.frames_per_minute)

        self.performance_profile = QComboBox(self)
        self.performance_profile.addItem("低资源占用", "low")
        self.performance_profile.addItem("中资源占用（默认）", "medium")
        self.performance_profile.addItem("高资源占用", "high")

        selected = self.performance_profile.findData(performance_profile)
        if selected >= 0:
            self.performance_profile.setCurrentIndex(selected)
        layout.addRow("性能档位", self.performance_profile)

        actions = QHBoxLayout()
        ok_btn = QPushButton("确定", self)
        cancel_btn = QPushButton("取消", self)
        ok_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        actions.addWidget(ok_btn)
        actions.addWidget(cancel_btn)
        layout.addRow(actions)
