from PySide6.QtWidgets import QComboBox, QDialog, QFormLayout, QHBoxLayout, QPushButton, QSpinBox

from ..config import PerformanceProfile


class SettingsDialog(QDialog):
    def __init__(
        self,
        frame_interval: int,
        performance_profile: PerformanceProfile,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("设置")

        layout = QFormLayout(self)
        self.frame_interval = QSpinBox(self)
        self.frame_interval.setRange(1, 60)
        self.frame_interval.setValue(frame_interval)
        layout.addRow("抽帧间隔(秒)", self.frame_interval)

        self.performance_profile = QComboBox(self)
        self.performance_profile.addItem("低（更流畅）", "low")
        self.performance_profile.addItem("中（默认）", "medium")
        self.performance_profile.addItem("高（更快）", "high")

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
