import os
from pathlib import Path

import cv2
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget


class PreviewWidget(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._current_path: Path | None = None

        layout = QVBoxLayout(self)
        self.title = QLabel("首帧预览", self)
        self.info = QLabel("请选择左侧文件查看首帧图", self)
        self.image_label = QLabel(self)
        self.image_label.setMinimumHeight(260)
        self.image_label.setPixmap(QPixmap())
        self.image_label.setScaledContents(False)
        self.play_btn = QPushButton("用系统播放器打开", self)
        self.play_btn.setEnabled(False)
        self.play_btn.clicked.connect(self._play_current)

        layout.addWidget(self.title)
        layout.addWidget(self.info)
        layout.addWidget(self.image_label)
        layout.addWidget(self.play_btn)

    def set_video(self, path: Path) -> None:
        self._current_path = path
        if not path.exists():
            self.info.setText(f"文件不存在: {path}")
            self.image_label.clear()
            self.play_btn.setEnabled(False)
            return

        self.info.setText(str(path))
        pixmap = self._extract_first_frame(path)
        if pixmap is None:
            self.image_label.clear()
            self.image_label.setText("无法提取首帧预览")
        else:
            scaled = pixmap.scaled(
                480,
                270,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.image_label.setPixmap(scaled)
        self.play_btn.setEnabled(True)

    def clear_preview(self, message: str) -> None:
        self._current_path = None
        self.info.setText(message)
        self.image_label.clear()
        self.play_btn.setEnabled(False)

    def _play_current(self) -> None:
        if self._current_path is None or not self._current_path.exists():
            return
        os.startfile(str(self._current_path))

    def _extract_first_frame(self, path: Path) -> QPixmap | None:
        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            return None
        ok, frame = cap.read()
        cap.release()
        if not ok:
            return None

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        height, width, channels = rgb.shape
        bytes_per_line = channels * width
        image = QImage(rgb.data, width, height, bytes_per_line, QImage.Format.Format_RGB888)
        return QPixmap.fromImage(image.copy())
