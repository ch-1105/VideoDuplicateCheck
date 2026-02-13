from collections.abc import Iterator
from pathlib import Path


class VideoScanner:
    def __init__(self, supported_extensions: set[str]) -> None:
        self._extensions = {ext.lower() for ext in supported_extensions}

    def scan(self, root: Path) -> list[Path]:
        return sorted(self.iter_scan(root))

    def iter_scan(self, root: Path) -> Iterator[Path]:
        if not root.exists() or not root.is_dir():
            return
        for path in root.rglob("*"):
            if path.is_file() and path.suffix.lower() in self._extensions:
                yield path
