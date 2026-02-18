from pathlib import Path

from src.core.fingerprint import VideoFingerprint
from src.workers.compare_worker import build_duplicate_groups


def _fp(name: str, d_hash: int, p_hash: int) -> VideoFingerprint:
    return VideoFingerprint(
        path=Path(name),
        size_bytes=100,
        duration_seconds=10.0,
        width=1920,
        height=1080,
        bitrate=1000,
        d_hash=d_hash,
        p_hash=p_hash,
    )


def test_build_duplicate_groups() -> None:
    groups = build_duplicate_groups(
        [_fp("a.mp4", 0, 0), _fp("b.mp4", 1, 1), _fp("c.mp4", (1 << 64) - 1, (1 << 64) - 1)],
        similarity_threshold=0.95,
        duration_tolerance_seconds=2.0,
    )

    assert len(groups) == 1
    assert len(groups[0].items) == 2


def test_build_duplicate_groups_for_small_input() -> None:
    groups = build_duplicate_groups(
        [_fp("a.mp4", 0, 0)],
        similarity_threshold=0.95,
        duration_tolerance_seconds=2.0,
    )
    assert groups == []
