import sqlite3
from dataclasses import dataclass
from pathlib import Path

from .fingerprint import VideoFingerprint


@dataclass(slots=True)
class CachedFingerprint:
    path: Path
    mtime: float
    size_bytes: int
    duration_seconds: float
    width: int
    height: int
    bitrate: int
    d_hash: int
    p_hash: int


class FingerprintDatabase:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def close(self) -> None:
        self._conn.close()

    def _init_schema(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS fingerprints (
                path TEXT PRIMARY KEY,
                mtime REAL NOT NULL,
                size_bytes INTEGER NOT NULL,
                duration_seconds REAL NOT NULL,
                width INTEGER NOT NULL,
                height INTEGER NOT NULL,
                bitrate INTEGER NOT NULL,
                d_hash TEXT NOT NULL,
                p_hash TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        self._conn.commit()

    def get_cached(self, path: Path, mtime: float, size_bytes: int) -> CachedFingerprint | None:
        row = self._conn.execute(
            "SELECT * FROM fingerprints WHERE path = ? AND mtime = ? AND size_bytes = ?",
            (str(path), mtime, size_bytes),
        ).fetchone()
        if row is None:
            return None
        return CachedFingerprint(
            path=Path(row["path"]),
            mtime=row["mtime"],
            size_bytes=row["size_bytes"],
            duration_seconds=row["duration_seconds"],
            width=row["width"],
            height=row["height"],
            bitrate=row["bitrate"],
            d_hash=int(row["d_hash"]),
            p_hash=int(row["p_hash"]),
        )

    def upsert(self, fingerprint: VideoFingerprint, mtime: float) -> None:
        self._conn.execute(
            """
            INSERT INTO fingerprints
            (path, mtime, size_bytes, duration_seconds, width, height, bitrate, d_hash, p_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(path) DO UPDATE SET
              mtime=excluded.mtime,
              size_bytes=excluded.size_bytes,
              duration_seconds=excluded.duration_seconds,
              width=excluded.width,
              height=excluded.height,
              bitrate=excluded.bitrate,
              d_hash=excluded.d_hash,
              p_hash=excluded.p_hash,
              updated_at=CURRENT_TIMESTAMP
            """,
            (
                str(fingerprint.path),
                mtime,
                fingerprint.size_bytes,
                fingerprint.duration_seconds,
                fingerprint.width,
                fingerprint.height,
                fingerprint.bitrate,
                str(fingerprint.d_hash),
                str(fingerprint.p_hash),
            ),
        )
        self._conn.commit()
