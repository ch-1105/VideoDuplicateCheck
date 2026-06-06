from dataclasses import dataclass
import math
from pathlib import Path

import cv2

from ..utils.video_info import VideoInfo, read_video_info
from .hasher import FrameHashes, dhash, phash

# Bump this when sampling or hash aggregation changes so stale cache rows are ignored.
FINGERPRINT_ALGORITHM_VERSION = 2


@dataclass(slots=True)
class VideoFingerprint:
    path: Path
    size_bytes: int
    duration_seconds: float
    width: int
    height: int
    bitrate: int
    d_hash: int
    p_hash: int


def extract_fingerprint(
    path: Path,
    frames_per_minute: int,
    min_sample_frames: int,
    max_sample_frames: int,
) -> VideoFingerprint:
    info = read_video_info(path)
    hashes = _hash_video(info, frames_per_minute, min_sample_frames, max_sample_frames)
    return VideoFingerprint(
        path=path,
        size_bytes=info.size_bytes,
        duration_seconds=info.duration_seconds,
        width=info.width,
        height=info.height,
        bitrate=info.bitrate,
        d_hash=hashes.d_hash,
        p_hash=hashes.p_hash,
    )


def _hash_video(
    info: VideoInfo,
    frames_per_minute: int,
    min_sample_frames: int,
    max_sample_frames: int,
) -> FrameHashes:
    cap = cv2.VideoCapture(str(info.path))
    if not cap.isOpened():
        raise ValueError(f"Failed to open video for hashing: {info.path}")

    try:
        frame_indexes = _sample_frame_indexes(
            info,
            frames_per_minute,
            min_sample_frames,
            max_sample_frames,
        )

        d_values: list[int] = []
        p_values: list[int] = []

        for frame_index in frame_indexes:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
            ok, frame = cap.read()
            if not ok:
                continue

            d_values.append(dhash(frame))
            p_values.append(phash(frame))
    finally:
        cap.release()

    if not d_values or not p_values:
        return FrameHashes(d_hash=0, p_hash=0)

    return FrameHashes(d_hash=_majority_hash(d_values), p_hash=_majority_hash(p_values))


def _sample_frame_indexes(
    info: VideoInfo,
    frames_per_minute: int,
    min_sample_frames: int,
    max_sample_frames: int,
) -> list[int]:
    total_frames = max(1, info.frame_count)
    duration_minutes = max(0.0, info.duration_seconds) / 60
    planned_frames = math.ceil(duration_minutes * max(1, frames_per_minute))
    sample_count = min(max(planned_frames, min_sample_frames), max_sample_frames, total_frames)

    if sample_count <= 1:
        return [total_frames // 2]
    if sample_count >= total_frames:
        return list(range(total_frames))

    # Avoid credits, intro cards, and end slates dominating the video fingerprint.
    start = int((total_frames - 1) * 0.05)
    end = int((total_frames - 1) * 0.95)
    if end <= start:
        return sorted(set(range(total_frames)))

    step = (end - start) / (sample_count - 1)
    return sorted({round(start + step * idx) for idx in range(sample_count)})


def _majority_hash(values: list[int], bit_length: int = 64) -> int:
    result = 0
    half = len(values) / 2
    for bit in range(bit_length):
        ones = sum((value >> (bit_length - bit - 1)) & 1 for value in values)
        result = (result << 1) | int(ones >= half)
    return result
