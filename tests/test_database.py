from pathlib import Path

from src.core.database import FingerprintDatabase
from src.core.fingerprint import FINGERPRINT_ALGORITHM_VERSION, VideoFingerprint


def _open_database(
    db_path: Path,
    frames_per_minute: int = 3,
    min_sample_frames: int = 12,
    max_sample_frames: int = 180,
) -> FingerprintDatabase:
    return FingerprintDatabase(
        db_path,
        FINGERPRINT_ALGORITHM_VERSION,
        frames_per_minute,
        min_sample_frames,
        max_sample_frames,
    )


def _build_fingerprint(path: Path) -> VideoFingerprint:
    return VideoFingerprint(
        path=path,
        size_bytes=123,
        duration_seconds=9.5,
        width=1920,
        height=1080,
        bitrate=2048,
        d_hash=11,
        p_hash=22,
    )


def test_database_upsert_and_get_cached(tmp_path: Path) -> None:
    db_path = tmp_path / "cache.sqlite3"
    video_path = tmp_path / "sample.mp4"
    video_path.write_text("x", encoding="utf-8")

    db = _open_database(db_path)
    try:
        fp = _build_fingerprint(video_path)
        mtime = 1234.5

        db.upsert(fp, mtime)

        cached = db.get_cached(video_path, mtime, fp.size_bytes)
        assert cached is not None
        assert cached.path == video_path
        assert cached.mtime == mtime
        assert cached.size_bytes == fp.size_bytes
        assert cached.duration_seconds == fp.duration_seconds
        assert cached.width == fp.width
        assert cached.height == fp.height
        assert cached.bitrate == fp.bitrate
        assert cached.d_hash == fp.d_hash
        assert cached.p_hash == fp.p_hash
    finally:
        db.close()


def test_database_uses_wal_mode(tmp_path: Path) -> None:
    db_path = tmp_path / "cache.sqlite3"
    db = _open_database(db_path)
    try:
        journal_mode = db._conn.execute("PRAGMA journal_mode").fetchone()[0]
        synchronous = db._conn.execute("PRAGMA synchronous").fetchone()[0]
        busy_timeout = db._conn.execute("PRAGMA busy_timeout").fetchone()[0]

        assert str(journal_mode).lower() == "wal"
        assert int(synchronous) == 1
        assert int(busy_timeout) == 5000
    finally:
        db.close()


def test_database_cache_depends_on_sampling_settings(tmp_path: Path) -> None:
    db_path = tmp_path / "cache.sqlite3"
    video_path = tmp_path / "sample.mp4"
    video_path.write_text("x", encoding="utf-8")
    fp = _build_fingerprint(video_path)
    mtime = 1234.5

    db = _open_database(db_path, frames_per_minute=3)
    try:
        db.upsert(fp, mtime)
    finally:
        db.close()

    changed_db = _open_database(db_path, frames_per_minute=6)
    try:
        cached = changed_db.get_cached(video_path, mtime, fp.size_bytes)
        assert cached is None
    finally:
        changed_db.close()
