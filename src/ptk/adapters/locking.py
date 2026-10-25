"""Portable exclusive locks for short filesystem transactions."""

import os
import time
from contextlib import contextmanager
from pathlib import Path

from ..domain.errors import PtkError


@contextmanager
def file_lock(path: Path, timeout: float = 10):
    path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout
    while True:
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            break
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise PtkError(
                    f"resource is locked: {path}; if its owner exited, remove the stale lock"
                ) from None
            time.sleep(0.05)
    try:
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        yield
    finally:
        path.unlink(missing_ok=True)
