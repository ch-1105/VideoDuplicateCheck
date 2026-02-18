from ..core.comparator import DuplicateGroup, find_duplicate_groups
from ..core.fingerprint import VideoFingerprint


def build_duplicate_groups(
    fingerprints: list[VideoFingerprint],
    similarity_threshold: float,
    duration_tolerance_seconds: float,
) -> list[DuplicateGroup]:
    if len(fingerprints) < 2:
        return []
    return find_duplicate_groups(
        fingerprints,
        similarity_threshold=similarity_threshold,
        duration_tolerance_seconds=duration_tolerance_seconds,
    )
