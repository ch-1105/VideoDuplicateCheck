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
    def __init__(
        self,
        db_path: Path,
        fingerprint_version: int,
        frames_per_minute: int,
        min_sample_frames: int,
        max_sample_frames: int,
    ) -> None:
        self._db_path = db_path
        self._fingerprint_version = fingerprint_version
        self._frames_per_minute = frames_per_minute
        self._min_sample_frames = min_sample_frames
        self._max_sample_frames = max_sample_frames
        self._conn = sqlite3.connect(db_path, timeout=5.0)
        self._conn.row_factory = sqlite3.Row
        self._configure_connection()
        self._pending_writes = 0
        self._commit_batch_size = 50
        self._init_schema()

    def _configure_connection(self) -> None:
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute("PRAGMA temp_store=MEMORY")
        self._conn.execute("PRAGMA busy_timeout=5000")

    def close(self) -> None:
        self.flush()
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
                fingerprint_version INTEGER NOT NULL DEFAULT 0,
                frames_per_minute INTEGER NOT NULL DEFAULT 0,
                min_sample_frames INTEGER NOT NULL DEFAULT 0,
                max_sample_frames INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        # Existing user caches may predate sampling parameters, so migrate in place.
        self._ensure_column("fingerprint_version", "INTEGER NOT NULL DEFAULT 0")
        self._ensure_column("frames_per_minute", "INTEGER NOT NULL DEFAULT 0")
        self._ensure_column("min_sample_frames", "INTEGER NOT NULL DEFAULT 0")
        self._ensure_column("max_sample_frames", "INTEGER NOT NULL DEFAULT 0")
        self._conn.commit()

    def _ensure_column(self, name: str, definition: str) -> None:
        columns = {
            row["name"] for row in self._conn.execute("PRAGMA table_info(fingerprints)").fetchall()
        }
        if name in columns:
            return
        self._conn.execute(f"ALTER TABLE fingerprints ADD COLUMN {name} {definition}")

    def get_cached(self, path: Path, mtime: float, size_bytes: int) -> CachedFingerprint | None:
        row = self._conn.execute(
            """
            SELECT * FROM fingerprints
            WHERE path = ?
              AND mtime = ?
              AND size_bytes = ?
              AND fingerprint_version = ?
              AND frames_per_minute = ?
              AND min_sample_frames = ?
              AND max_sample_frames = ?
            """,
            (
                str(path),
                mtime,
                size_bytes,
                self._fingerprint_version,
                self._frames_per_minute,
                self._min_sample_frames,
                self._max_sample_frames,
            ),
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

    def get_cached_bulk(
        self,
        signatures: list[tuple[Path, float, int]],
    ) -> dict[str, CachedFingerprint]:
        if not signatures:
            return {}

        by_path: dict[str, tuple[float, int]] = {
            str(path): (mtime, size) for path, mtime, size in signatures
        }
        placeholders = ",".join("?" for _ in by_path)
        rows = self._conn.execute(
            f"SELECT * FROM fingerprints WHERE path IN ({placeholders})",
            tuple(by_path.keys()),
        ).fetchall()

        cached: dict[str, CachedFingerprint] = {}
        for row in rows:
            path = row["path"]
            expected = by_path.get(path)
            if expected is None:
                continue

            mtime, size_bytes = expected
            if row["mtime"] != mtime or row["size_bytes"] != size_bytes:
                continue

            if (
                row["fingerprint_version"] != self._fingerprint_version
                or row["frames_per_minute"] != self._frames_per_minute
                or row["min_sample_frames"] != self._min_sample_frames
                or row["max_sample_frames"] != self._max_sample_frames
            ):
                continue

            cached[path] = CachedFingerprint(
                path=Path(path),
                mtime=row["mtime"],
                size_bytes=row["size_bytes"],
                duration_seconds=row["duration_seconds"],
                width=row["width"],
                height=row["height"],
                bitrate=row["bitrate"],
                d_hash=int(row["d_hash"]),
                p_hash=int(row["p_hash"]),
            )
        return cached

    def upsert(self, fingerprint: VideoFingerprint, mtime: float) -> None:
        self._conn.execute(
            """
            INSERT INTO fingerprints
            (
                path,
                mtime,
                size_bytes,
                duration_seconds,
                width,
                height,
                bitrate,
                d_hash,
                p_hash,
                fingerprint_version,
                frames_per_minute,
                min_sample_frames,
                max_sample_frames
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(path) DO UPDATE SET
              mtime=excluded.mtime,
              size_bytes=excluded.size_bytes,
              duration_seconds=excluded.duration_seconds,
              width=excluded.width,
              height=excluded.height,
              bitrate=excluded.bitrate,
              d_hash=excluded.d_hash,
              p_hash=excluded.p_hash,
              fingerprint_version=excluded.fingerprint_version,
              frames_per_minute=excluded.frames_per_minute,
              min_sample_frames=excluded.min_sample_frames,
              max_sample_frames=excluded.max_sample_frames,
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
                self._fingerprint_version,
                self._frames_per_minute,
                self._min_sample_frames,
                self._max_sample_frames,
            ),
        )
        self._pending_writes += 1
        if self._pending_writes >= self._commit_batch_size:
            self.flush()

    def flush(self) -> None:
        if self._pending_writes <= 0:
            return
        self._conn.commit()
        self._pending_writes = 0
