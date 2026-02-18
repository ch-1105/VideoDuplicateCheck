from dataclasses import dataclass

from .fingerprint import VideoFingerprint
from .hasher import normalized_similarity


@dataclass(slots=True)
class DuplicateGroup:
    items: list[VideoFingerprint]
    similarity: float
    recommended_keep: VideoFingerprint


def find_duplicate_groups(
    fingerprints: list[VideoFingerprint],
    similarity_threshold: float,
    duration_tolerance_seconds: float,
) -> list[DuplicateGroup]:
    if len(fingerprints) < 2:
        return []

    buckets: dict[int, list[VideoFingerprint]] = {}
    for fp in fingerprints:
        bucket_key = int(fp.duration_seconds / max(duration_tolerance_seconds, 1e-6))
        buckets.setdefault(bucket_key, []).append(fp)

    groups: list[DuplicateGroup] = []
    visited: set[str] = set()

    for candidates in buckets.values():
        for idx, source in enumerate(candidates):
            if str(source.path) in visited:
                continue

            group = [source]
            min_similarity = 1.0
            for target in candidates[idx + 1 :]:
                if str(target.path) in visited:
                    continue
                if not _metadata_candidate(source, target, duration_tolerance_seconds):
                    continue
                similarity = _combined_similarity(source, target)
                if similarity >= similarity_threshold:
                    group.append(target)
                    min_similarity = min(min_similarity, similarity)

            if len(group) > 1:
                for item in group:
                    visited.add(str(item.path))
                groups.append(
                    DuplicateGroup(
                        items=sorted(group, key=lambda x: (x.path.name.lower(), x.size_bytes)),
                        similarity=min_similarity,
                        recommended_keep=_recommend_keep(group),
                    )
                )

    return groups


def _combined_similarity(a: VideoFingerprint, b: VideoFingerprint) -> float:
    d_sim = normalized_similarity(a.d_hash, b.d_hash)
    p_sim = normalized_similarity(a.p_hash, b.p_hash)

    duration_gap = abs(a.duration_seconds - b.duration_seconds)
    duration_penalty = min(duration_gap / max(a.duration_seconds, b.duration_seconds, 1.0), 1.0)
    return (d_sim * 0.35 + p_sim * 0.65) * (1.0 - duration_penalty * 0.3)


def _metadata_candidate(
    source: VideoFingerprint,
    target: VideoFingerprint,
    duration_tolerance_seconds: float,
) -> bool:
    if abs(source.duration_seconds - target.duration_seconds) > duration_tolerance_seconds:
        return False

    if abs(_size_bucket(source.size_bytes) - _size_bucket(target.size_bytes)) > 2:
        return False

    if abs(_resolution_bucket(source) - _resolution_bucket(target)) > 2:
        return False

    return True


def _size_bucket(size_bytes: int) -> int:
    return max(1, size_bytes).bit_length() // 2


def _resolution_bucket(fp: VideoFingerprint) -> int:
    pixels = max(1, fp.width * fp.height)
    return pixels.bit_length() // 2


def _recommend_keep(items: list[VideoFingerprint]) -> VideoFingerprint:
    return max(
        items,
        key=lambda item: (
            item.width * item.height,
            item.bitrate,
            item.size_bytes,
        ),
    )
