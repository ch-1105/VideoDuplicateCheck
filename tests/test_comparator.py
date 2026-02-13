from pathlib import Path

from src.core.comparator import find_duplicate_groups
from src.core.fingerprint import VideoFingerprint


def _fp(name: str, d_hash: int, p_hash: int, dur: float = 10.0) -> VideoFingerprint:
    return VideoFingerprint(
        path=Path(name),
        size_bytes=100,
        duration_seconds=dur,
        width=1920,
        height=1080,
        bitrate=1000,
        d_hash=d_hash,
        p_hash=p_hash,
    )


def test_find_duplicate_groups() -> None:
    a = _fp("a.mp4", d_hash=0, p_hash=0)
    b = _fp("b.mp4", d_hash=1, p_hash=1)
    c = _fp("c.mp4", d_hash=(1 << 64) - 1, p_hash=(1 << 64) - 1)

    groups = find_duplicate_groups(
        [a, b, c],
        similarity_threshold=0.95,
        duration_tolerance_seconds=2.0,
    )
    assert len(groups) == 1
    assert len(groups[0].items) == 2
