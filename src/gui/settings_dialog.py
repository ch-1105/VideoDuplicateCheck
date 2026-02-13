from PySide6.QtWidgets import QDialog, QFormLayout, QHBoxLayout, QPushButton, QSpinBox


class SettingsDialog(QDialog):
    def __init__(self, frame_interval: int, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("设置")

        layout = QFormLayout(self)
        self.frame_interval = QSpinBox(self)
        self.frame_interval.setRange(1, 60)
        self.frame_interval.setValue(frame_interval)
        layout.addRow("抽帧间隔(秒)", self.frame_interval)

        actions = QHBoxLayout()
        ok_btn = QPushButton("确定", self)
        cancel_btn = QPushButton("取消", self)
        ok_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        actions.addWidget(ok_btn)
        actions.addWidget(cancel_btn)
        layout.addRow(actions)
