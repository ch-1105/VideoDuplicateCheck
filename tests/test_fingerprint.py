from pathlib import Path

from src.core.fingerprint import _sample_frame_indexes
from src.utils.video_info import VideoInfo


def _info(duration_seconds: float, frame_count: int) -> VideoInfo:
    return VideoInfo(
        path=Path("sample.mp4"),
        size_bytes=100,
        duration_seconds=duration_seconds,
        width=1920,
        height=1080,
        fps=30.0,
        frame_count=frame_count,
        bitrate=1000,
    )


def test_sample_frame_indexes_use_minimum_for_short_video() -> None:
    indexes = _sample_frame_indexes(
        _info(duration_seconds=60, frame_count=1800),
        frames_per_minute=3,
        min_sample_frames=12,
        max_sample_frames=180,
    )

    assert len(indexes) == 12


def test_sample_frame_indexes_scale_with_duration() -> None:
    indexes = _sample_frame_indexes(
        _info(duration_seconds=20 * 60, frame_count=36000),
        frames_per_minute=3,
        min_sample_frames=12,
        max_sample_frames=180,
    )

    assert len(indexes) == 60


def test_sample_frame_indexes_apply_maximum_for_long_video() -> None:
    indexes = _sample_frame_indexes(
        _info(duration_seconds=120 * 60, frame_count=216000),
        frames_per_minute=3,
        min_sample_frames=12,
        max_sample_frames=180,
    )

    assert len(indexes) == 180


def test_sample_frame_indexes_never_exceed_frame_count() -> None:
    indexes = _sample_frame_indexes(
        _info(duration_seconds=60, frame_count=5),
        frames_per_minute=3,
        min_sample_frames=12,
        max_sample_frames=180,
    )

    assert indexes == [0, 1, 2, 3, 4]
