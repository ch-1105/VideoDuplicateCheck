import os
import threading
import time
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from pathlib import Path

import cv2
from PySide6.QtCore import QObject, Signal

from ..config import AppConfig
from ..core.comparator import DuplicateGroup, find_duplicate_groups
from ..core.database import FingerprintDatabase
from ..core.fingerprint import VideoFingerprint, extract_fingerprint
from ..core.scanner import VideoScanner


def _read_signature(path: Path) -> tuple[Path, float, int] | None:
    try:
        stat = path.stat()
    except OSError:
        return None
    return (path, stat.st_mtime, stat.st_size)


def _compute_fingerprint_workers(cpu_count: int, profile: str) -> int:
    cpu = max(1, cpu_count)
    if profile == "low":
        return 1
    if profile == "high":
        # 尽量拉满，预留 2 核给系统和 GUI 保证不卡死
        return max(2, cpu - 2)
    # medium: 保守策略，视频解码有内部多线程，worker 不宜过多
    return max(1, min(3, cpu // 6))


def _compute_metadata_workers(cpu_count: int, profile: str, total_files: int) -> int:
    cpu = max(1, cpu_count)
    base_by_profile = {
        "low": 2,
        "medium": 2,
        "high": 6,
    }
    cap_by_profile = {
        "low": 3,
        "medium": 4,
        "high": max(6, cpu // 2),
    }

    if total_files < 500:
        scale = 1
    elif total_files < 5000:
        scale = 2
    else:
        scale = 3

    base = base_by_profile.get(profile, 4)
    cap = cap_by_profile.get(profile, 8)
    planned = base + scale - 1
    return max(1, min(planned, cap, cpu, max(1, total_files)))


def _compute_opencv_threads(profile: str) -> int:
    if profile in {"low", "medium"}:
        return 1
    return 2


def _compute_inflight_limit(max_workers: int, profile: str) -> int:
    multiplier_by_profile = {
        "low": 2,
        "medium": 2,
        "high": 3,
    }
    multiplier = multiplier_by_profile.get(profile, 2)
    return max_workers * multiplier


class ScanWorker(QObject):
    progress = Signal(int, int)
    status = Signal(str)
    current_task = Signal(str)
    partial_groups = Signal(list, int, int)
    finished = Signal(list)
    stopped = Signal()
    failed = Signal(str)

    def __init__(self, root_dir: Path, config: AppConfig) -> None:
        super().__init__()
        self._root_dir = root_dir
        self._config = config
        self._pause_event = threading.Event()
        self._pause_event.set()
        self._stop_event = threading.Event()
        self._last_partial_emit_time = 0.0

    def request_pause(self) -> None:
        self._pause_event.clear()
        self.status.emit("任务已暂停")

    def request_resume(self) -> None:
        self._pause_event.set()
        self.status.emit("任务继续执行")

    def request_stop(self) -> None:
        self._stop_event.set()
        self._pause_event.set()
        self.status.emit("正在终止任务...")

    def is_paused(self) -> bool:
        return not self._pause_event.is_set()

    def _wait_if_paused(self) -> bool:
        while not self._pause_event.is_set():
            if self._stop_event.is_set():
                return False
            time.sleep(0.1)
        return not self._stop_event.is_set()

    def _assert_not_stopped(self) -> bool:
        if self._stop_event.is_set():
            self.status.emit("任务已终止")
            self.stopped.emit()
            return False
        return True

    def _maybe_emit_partial_groups(
        self,
        fingerprints: list[VideoFingerprint],
        processed: int,
        total: int,
        *,
        force: bool = False,
    ) -> None:
        if total <= 0:
            return
        if len(fingerprints) < 2:
            return

        batch_size = max(1, self._config.partial_result_batch_size)
        if not force and processed % batch_size != 0:
            return

        now = time.monotonic()
        min_interval = max(0.0, self._config.partial_result_min_interval_seconds)
        if not force and now - self._last_partial_emit_time < min_interval:
            return

        groups = find_duplicate_groups(
            fingerprints,
            similarity_threshold=self._config.similarity_threshold,
            duration_tolerance_seconds=self._config.duration_tolerance_seconds,
        )
        self.partial_groups.emit(groups, processed, total)
        self._last_partial_emit_time = now

    def run(self) -> None:
        try:
            if not self._assert_not_stopped():
                return

            self.status.emit("扫描目录中...")
            self.current_task.emit("递归扫描目录")
            cv2.setNumThreads(_compute_opencv_threads(self._config.performance_profile))
            scanner = VideoScanner(self._config.supported_extensions)
            files = scanner.scan(self._root_dir)
            total = len(files)
            self.status.emit(f"共发现 {total} 个视频文件")
            self.progress.emit(0, total)

            if not self._assert_not_stopped():
                return

            db = FingerprintDatabase(self._config.cache_db)
            fingerprints: list[VideoFingerprint] = []
            pending_paths: list[Path] = []
            processed = 0
            stat_batch_size = 200
            metadata_workers = _compute_metadata_workers(
                os.cpu_count() or 1,
                self._config.performance_profile,
                total,
            )

            self.status.emit("缓存校验中...")
            with ThreadPoolExecutor(max_workers=metadata_workers) as stat_pool:
                for batch_start in range(0, total, stat_batch_size):
                    if not self._wait_if_paused() or not self._assert_not_stopped():
                        db.close()
                        return

                    batch = files[batch_start : batch_start + stat_batch_size]
                    batch_end = min(total, batch_start + len(batch))
                    self.current_task.emit(f"缓存校验: {batch_end}/{total}")

                    signatures = [
                        sig for sig in stat_pool.map(_read_signature, batch) if sig is not None
                    ]
                    cached_map = db.get_cached_bulk(signatures)

                    for file_path in batch:
                        if not self._wait_if_paused() or not self._assert_not_stopped():
                            db.close()
                            return

                        cached = cached_map.get(str(file_path))
                        if cached is None:
                            pending_paths.append(file_path)
                        else:
                            fingerprints.append(
                                VideoFingerprint(
                                    path=cached.path,
                                    size_bytes=cached.size_bytes,
                                    duration_seconds=cached.duration_seconds,
                                    width=cached.width,
                                    height=cached.height,
                                    bitrate=cached.bitrate,
                                    d_hash=cached.d_hash,
                                    p_hash=cached.p_hash,
                                )
                            )
                            processed += 1
                            self.progress.emit(processed, total)
                            self._maybe_emit_partial_groups(fingerprints, processed, total)

                    missing = len(batch) - len(signatures)
                    if missing > 0:
                        processed += missing
                        self.progress.emit(processed, total)
                        self.status.emit(f"跳过无法读取元数据文件: {missing} 个")

            self.status.emit(f"开始多线程提取指纹: {len(pending_paths)} 个文件待处理")
            if pending_paths:
                max_workers = _compute_fingerprint_workers(
                    os.cpu_count() or 1,
                    self._config.performance_profile,
                )
                max_workers = min(max_workers, len(pending_paths))
                inflight_limit = _compute_inflight_limit(
                    max_workers,
                    self._config.performance_profile,
                )
                self.current_task.emit(
                    "指纹提取线程数: "
                    f"{max_workers} (档位: {self._config.performance_profile}, "
                    f"并发窗口: {inflight_limit}, OpenCV线程: {cv2.getNumThreads()})"
                )

                with ThreadPoolExecutor(max_workers=max_workers) as pool:
                    pending_iter = iter(pending_paths)
                    future_map: dict[Future[VideoFingerprint], Path] = {}

                    def submit_next() -> bool:
                        try:
                            source_path = next(pending_iter)
                        except StopIteration:
                            return False
                        future = pool.submit(
                            extract_fingerprint,
                            source_path,
                            self._config.frame_interval_seconds,
                        )
                        future_map[future] = source_path
                        return True

                    for _ in range(min(inflight_limit, len(pending_paths))):
                        submit_next()

                    while future_map:
                        if not self._wait_if_paused():
                            for future in future_map:
                                future.cancel()
                            db.close()
                            self.stopped.emit()
                            return

                        done, _ = wait(
                            set(future_map.keys()),
                            timeout=0.2,
                            return_when=FIRST_COMPLETED,
                        )
                        if not done:
                            continue

                        for future in done:
                            source_path = future_map.pop(future)
                            if self._stop_event.is_set():
                                for remaining in future_map:
                                    remaining.cancel()
                                db.close()
                                self.stopped.emit()
                                return

                            self.current_task.emit(f"提取指纹: {source_path.name}")
                            try:
                                fp = future.result()
                            except Exception as exc:  # noqa: BLE001
                                self.status.emit(f"跳过失败文件: {source_path.name} ({exc})")
                            else:
                                try:
                                    stat = source_path.stat()
                                except OSError as exc:
                                    self.status.emit(f"跳过缓存写入: {source_path.name} ({exc})")
                                else:
                                    db.upsert(fp, stat.st_mtime)
                                    fingerprints.append(fp)

                            processed += 1
                            self.progress.emit(processed, total)
                            self._maybe_emit_partial_groups(fingerprints, processed, total)

                            while len(future_map) < inflight_limit and submit_next():
                                continue

            db.flush()
            db.close()

            if not self._assert_not_stopped():
                return

            self._maybe_emit_partial_groups(fingerprints, processed, total, force=True)

            self.status.emit("正在进行相似度比较...")
            self.current_task.emit("比较指纹并聚类分组")
            groups: list[DuplicateGroup] = find_duplicate_groups(
                fingerprints,
                similarity_threshold=self._config.similarity_threshold,
                duration_tolerance_seconds=self._config.duration_tolerance_seconds,
            )
            self.status.emit(f"发现 {len(groups)} 组重复/近似视频")
            self.finished.emit(groups)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))
