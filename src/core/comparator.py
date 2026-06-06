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

    ordered = sorted(fingerprints, key=lambda fp: fp.duration_seconds)
    # Union-find keeps transitive matches together, for example A~B and B~C.
    parent = list(range(len(ordered)))
    group_similarity: dict[int, float] = {}

    for source_idx, source in enumerate(ordered):
        for target_idx in range(source_idx + 1, len(ordered)):
            target = ordered[target_idx]
            if target.duration_seconds - source.duration_seconds > duration_tolerance_seconds:
                break
            if not _metadata_candidate(source, target, duration_tolerance_seconds):
                continue

            similarity = _combined_similarity(source, target)
            if similarity >= similarity_threshold:
                source_root = _find(parent, source_idx)
                target_root = _find(parent, target_idx)
                previous = min(
                    group_similarity.pop(source_root, 1.0),
                    group_similarity.pop(target_root, 1.0),
                )
                root = _union(parent, source_root, target_root)
                group_similarity[root] = min(previous, similarity)

    grouped: dict[int, list[VideoFingerprint]] = {}
    for idx, fingerprint in enumerate(ordered):
        root = _find(parent, idx)
        grouped.setdefault(root, []).append(fingerprint)

    groups: list[DuplicateGroup] = []
    for root, items in grouped.items():
        if len(items) < 2:
            continue
        sorted_items = sorted(items, key=lambda x: (x.path.name.lower(), x.size_bytes))
        groups.append(
            DuplicateGroup(
                items=sorted_items,
                similarity=group_similarity.get(root, 1.0),
                recommended_keep=_recommend_keep(sorted_items),
            )
        )

    return groups


def _find(parent: list[int], idx: int) -> int:
    while parent[idx] != idx:
        parent[idx] = parent[parent[idx]]
        idx = parent[idx]
    return idx


def _union(parent: list[int], a: int, b: int) -> int:
    root_a = _find(parent, a)
    root_b = _find(parent, b)
    if root_a == root_b:
        return root_a
    parent[root_b] = root_a
    return root_a


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
