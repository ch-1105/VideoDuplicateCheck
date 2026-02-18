from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal


PerformanceProfile = Literal["low", "medium", "high"]


@dataclass(slots=True)
class AppConfig:
    cache_db: Path = Path("video_cache.sqlite3")
    frame_interval_seconds: int = 10
    similarity_threshold: float = 0.9
    duration_tolerance_seconds: float = 2.0
    partial_result_batch_size: int = 100
    partial_result_min_interval_seconds: float = 2.0
    progress_emit_min_interval_seconds: float = 0.05
    task_emit_min_interval_seconds: float = 0.2
    performance_profile: PerformanceProfile = "medium"
    supported_extensions: set[str] = field(
        default_factory=lambda: {".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".webm"}
    )
