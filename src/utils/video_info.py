from dataclasses import dataclass
from pathlib import Path

import cv2


@dataclass(slots=True)
class VideoInfo:
    path: Path
    size_bytes: int
    duration_seconds: float
    width: int
    height: int
    fps: float
    frame_count: int
    bitrate: int


def read_video_info(path: Path) -> VideoInfo:
    stat = path.stat()
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise ValueError(f"Failed to open video: {path}")

    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    cap.release()

    duration = frame_count / fps if fps > 0 else 0.0
    bitrate = int((stat.st_size * 8) / duration) if duration > 0 else 0

    return VideoInfo(
        path=path,
        size_bytes=stat.st_size,
        duration_seconds=duration,
        width=width,
        height=height,
        fps=fps,
        frame_count=frame_count,
        bitrate=bitrate,
    )
