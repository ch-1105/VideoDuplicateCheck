from dataclasses import dataclass
from pathlib import Path

import cv2

from ..utils.video_info import VideoInfo, read_video_info
from .hasher import FrameHashes, dhash, phash


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


def extract_fingerprint(path: Path, frame_interval_seconds: int) -> VideoFingerprint:
    info = read_video_info(path)
    hashes = _hash_video(info, frame_interval_seconds)
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


def _hash_video(info: VideoInfo, frame_interval_seconds: int) -> FrameHashes:
    cap = cv2.VideoCapture(str(info.path))
    if not cap.isOpened():
        raise ValueError(f"Failed to open video for hashing: {info.path}")

    fps = info.fps if info.fps > 0 else 1.0
    stride = max(1, int(frame_interval_seconds * fps))
    total = max(1, info.frame_count)

    d_values: list[int] = []
    p_values: list[int] = []
    idx = 0

    while idx < total:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ok, frame = cap.read()
        if not ok:
            idx += stride
            continue
        d_values.append(dhash(frame))
        p_values.append(phash(frame))
        idx += stride

    cap.release()

    if not d_values or not p_values:
        return FrameHashes(d_hash=0, p_hash=0)

    return FrameHashes(d_hash=_majority_hash(d_values), p_hash=_majority_hash(p_values))


def _majority_hash(values: list[int], bit_length: int = 64) -> int:
    result = 0
    half = len(values) / 2
    for bit in range(bit_length):
        ones = sum((value >> (bit_length - bit - 1)) & 1 for value in values)
        result = (result << 1) | int(ones >= half)
    return result
