"""Small cross-platform advisory file lock used by logging and archival."""

from __future__ import annotations

import os
from pathlib import Path
from types import TracebackType
from typing import BinaryIO, Self


class InterProcessFileLock:
    """Serialize writers across processes without a third-party dependency."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._file: BinaryIO | None = None

    def __enter__(self) -> Self:
        self.acquire()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.release()

    def acquire(self) -> None:
        if self._file is not None:
            raise RuntimeError("file lock is already acquired")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lock_file = self.path.open("a+b")
        lock_file.seek(0, os.SEEK_END)
        if lock_file.tell() == 0:
            lock_file.write(b"\0")
            lock_file.flush()
        lock_file.seek(0)
        try:
            _lock_file(lock_file)
        except Exception:
            lock_file.close()
            raise
        self._file = lock_file

    def release(self) -> None:
        if self._file is None:
            return
        try:
            self._file.seek(0)
            _unlock_file(self._file)
        finally:
            self._file.close()
            self._file = None


if os.name == "nt":
    import msvcrt

    def _lock_file(file: BinaryIO) -> None:
        msvcrt.locking(file.fileno(), msvcrt.LK_LOCK, 1)

    def _unlock_file(file: BinaryIO) -> None:
        msvcrt.locking(file.fileno(), msvcrt.LK_UNLCK, 1)

else:
    import fcntl

    def _lock_file(file: BinaryIO) -> None:
        fcntl.flock(file.fileno(), fcntl.LOCK_EX)

    def _unlock_file(file: BinaryIO) -> None:
        fcntl.flock(file.fileno(), fcntl.LOCK_UN)

