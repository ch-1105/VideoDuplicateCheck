import ctypes
from ctypes import wintypes
from pathlib import Path
import shutil


FO_DELETE = 0x0003
FOF_ALLOWUNDO = 0x0040
FOF_NOCONFIRMATION = 0x0010
FOF_NOERRORUI = 0x0400
FOF_SILENT = 0x0004


class SHFILEOPSTRUCTW(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("wFunc", wintypes.UINT),
        ("pFrom", wintypes.LPCWSTR),
        ("pTo", wintypes.LPCWSTR),
        ("fFlags", ctypes.c_ushort),
        ("fAnyOperationsAborted", wintypes.BOOL),
        ("hNameMappings", ctypes.c_void_p),
        ("lpszProgressTitle", wintypes.LPCWSTR),
    ]


def ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def move_file(path: Path, destination_dir: Path) -> Path:
    ensure_directory(destination_dir)
    target = destination_dir / path.name
    if target.exists():
        stem = path.stem
        suffix = path.suffix
        idx = 1
        while target.exists():
            target = destination_dir / f"{stem}_{idx}{suffix}"
            idx += 1
    shutil.move(str(path), str(target))
    return target


def delete_file(path: Path) -> None:
    path.unlink(missing_ok=True)


def move_to_recycle_bin(path: Path) -> bool:
    if not path.exists():
        return False

    source = f"{path}\0\0"
    file_op = SHFILEOPSTRUCTW()
    file_op.wFunc = FO_DELETE
    file_op.pFrom = source
    file_op.fFlags = FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_NOERRORUI | FOF_SILENT

    result = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(file_op))
    return result == 0 and not file_op.fAnyOperationsAborted
