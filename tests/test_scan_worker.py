from src.workers.scan_worker import (
    _compute_fingerprint_workers,
    _compute_inflight_limit,
    _compute_metadata_workers,
)


def test_compute_fingerprint_workers_profiles() -> None:
    assert _compute_fingerprint_workers(8, "low") == 1
    assert _compute_fingerprint_workers(8, "medium") == 1
    assert _compute_fingerprint_workers(8, "high") == 4
    assert _compute_fingerprint_workers(32, "high") == 6


def test_compute_metadata_workers_high_profile_is_capped() -> None:
    workers = _compute_metadata_workers(24, "high", 20000)
    assert workers <= 8
    assert workers >= 1


def test_compute_inflight_limit_profiles() -> None:
    assert _compute_inflight_limit(4, "low") == 4
    assert _compute_inflight_limit(4, "medium") == 8
    assert _compute_inflight_limit(4, "high") == 12
