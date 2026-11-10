"""Portable exclusive locks for short filesystem transactions."""

import os
import sys
import time
from collections.abc import Callable
from contextlib import contextmanager
from pathlib import Path

from ..domain.errors import PtkError


def _alive(pid: int) -> bool:
    if sys.platform == "win32":
        import ctypes

        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        handle = kernel32.OpenProcess(0x1000, False, pid)  # QUERY_LIMITED_INFORMATION
        if not handle:
            return kernel32.GetLastError() == 5  # access denied: exists
        code = ctypes.c_ulong()
        kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
        kernel32.CloseHandle(handle)
        return code.value == 259  # STILL_ACTIVE
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _stale(path: Path) -> bool:
    """True when the lock names a local owner process that no longer exists."""
    try:
        text = path.read_text(encoding="utf-8").strip()
    except OSError:
        return False
    return text.isdigit() and int(text) != os.getpid() and not _alive(int(text))


@contextmanager
def file_lock(
    path: Path, timeout: float = 10, waiting: Callable[[str], None] | None = None
):
    path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout
    told = False
    while True:
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            break
        except FileExistsError:
            if _stale(path):
                path.unlink(missing_ok=True)
                continue
            if time.monotonic() >= deadline:
                raise PtkError(
                    f"resource is locked: {path}; if its owner exited, remove the stale lock"
                ) from None
            if waiting is not None and not told:
                waiting(f"waiting for another PTk process holding {path}")
                told = True
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
