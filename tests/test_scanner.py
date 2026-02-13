from pathlib import Path

from src.core.scanner import VideoScanner


def test_scan_only_video_files(tmp_path: Path) -> None:
    (tmp_path / "a.mp4").write_text("x", encoding="utf-8")
    (tmp_path / "b.mkv").write_text("x", encoding="utf-8")
    (tmp_path / "c.txt").write_text("x", encoding="utf-8")

    scanner = VideoScanner({".mp4", ".mkv"})
    files = scanner.scan(tmp_path)

    assert [f.name for f in files] == ["a.mp4", "b.mkv"]
