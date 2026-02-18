from pathlib import Path

from src.core.database import FingerprintDatabase
from src.core.fingerprint import VideoFingerprint


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

    db = FingerprintDatabase(db_path)
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
    db = FingerprintDatabase(db_path)
    try:
        journal_mode = db._conn.execute("PRAGMA journal_mode").fetchone()[0]
        synchronous = db._conn.execute("PRAGMA synchronous").fetchone()[0]
        busy_timeout = db._conn.execute("PRAGMA busy_timeout").fetchone()[0]

        assert str(journal_mode).lower() == "wal"
        assert int(synchronous) == 1
        assert int(busy_timeout) == 5000
    finally:
        db.close()
