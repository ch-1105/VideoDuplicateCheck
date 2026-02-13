import os
import threading
import time
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from ..config import AppConfig
from ..core.comparator import DuplicateGroup, find_duplicate_groups
from ..core.database import FingerprintDatabase
from ..core.fingerprint import VideoFingerprint, extract_fingerprint
from ..core.scanner import VideoScanner


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

            for file_path in files:
                if not self._wait_if_paused() or not self._assert_not_stopped():
                    db.close()
                    return

                self.current_task.emit(f"缓存校验: {file_path.name}")
                stat = file_path.stat()
                cached = db.get_cached(file_path, stat.st_mtime, stat.st_size)
                if cached is not None:
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
                else:
                    pending_paths.append(file_path)

            self.status.emit(f"开始多线程提取指纹: {len(pending_paths)} 个文件待处理")
            if pending_paths:
                max_workers = min(4, max(1, os.cpu_count() or 1))
                self.current_task.emit(f"指纹提取线程数: {max_workers}")

                with ThreadPoolExecutor(max_workers=max_workers) as pool:
                    future_map: dict[Future[VideoFingerprint], Path] = {
                        pool.submit(
                            extract_fingerprint, path, self._config.frame_interval_seconds
                        ): path
                        for path in pending_paths
                    }

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
                                stat = source_path.stat()
                                db.upsert(fp, stat.st_mtime)
                                fingerprints.append(fp)

                            processed += 1
                            self.progress.emit(processed, total)
                            self._maybe_emit_partial_groups(fingerprints, processed, total)

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
