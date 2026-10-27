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


@contextmanager
def job_lock(root: Path, variant: str | None, job: str):
    """Register a running job while excluding repository-wide cleanup."""
    from contextlib import ExitStack

    from ..domain.layout import safe

    with ExitStack() as stack:
        with file_lock(root / ".ptk" / "output-cleanup.lock"):
            stack.enter_context(
                file_lock(
                    root
                    / ".ptk"
                    / "locks"
                    / safe(variant or "default")
                    / (safe(job) + ".lock"),
                    timeout=0,
                )
            )
        yield


@contextmanager
def output_cleanup_lock(roots):
    """Prevent new jobs from starting and refuse to delete active job outputs."""
    from contextlib import ExitStack

    with ExitStack() as stack:
        for root in sorted(set(roots)):
            stack.enter_context(file_lock(root / ".ptk" / "output-cleanup.lock"))
            active = list((root / ".ptk" / "locks").rglob("*.lock"))
            if active:
                raise PtkError(f"cannot clean while a job is locked: {active[0]}")
        yield
