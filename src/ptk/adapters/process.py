"""ProcessRunner adapter: subprocess with live output, timeout and process-tree kill."""

from __future__ import annotations

import contextlib
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Callable

from ..application.ports import CancelToken, ProcessOutcome
from ..domain.execution.model import CommandSpec

WINDOWS = sys.platform.startswith("win")
GRACE_SECONDS = 5.0


class SubprocessRunner:
    def which(self, program: str, path: str | None = None) -> str | None:
        return shutil.which(program, path=path)

    def run(
        self,
        command: CommandSpec,
        on_output: Callable[[str], None],
        cancel: CancelToken | None = None,
    ) -> ProcessOutcome:
        env = dict(command.env)
        kwargs: dict = {
            "cwd": command.cwd,
            "env": env,
            "stdin": subprocess.DEVNULL,
            "stdout": subprocess.PIPE,
            "stderr": subprocess.STDOUT,
        }
        if WINDOWS:
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            kwargs["start_new_session"] = (
                True  # own process group -> kill the whole tree
            )
        if command.shell is not None:
            args: str | list[str] = command.shell
            kwargs["shell"] = True
        else:
            argv = list(command.argv or [])
            # resolve the program with the *child's* PATH (also finds npm.cmd & co on Windows)
            found = shutil.which(argv[0], path=_path_of(env)) if argv else None
            if found:
                argv[0] = found
            args = argv
        if not os.path.isdir(command.cwd):
            return ProcessOutcome(
                1, error=f"working directory does not exist: {command.cwd}"
            )
        try:
            proc = subprocess.Popen(args, **kwargs)
        except FileNotFoundError:
            name = args if isinstance(args, str) else args[0]
            return ProcessOutcome(127, error=f"program not found: {name}")
        except OSError as exc:
            return ProcessOutcome(126, error=f"cannot start: {exc}")

        reader = threading.Thread(target=_pump, args=(proc, on_output), daemon=True)
        reader.start()
        deadline = time.monotonic() + command.timeout if command.timeout else None
        timed_out = cancelled = False
        while proc.poll() is None:
            if cancel is not None and cancel.is_set():
                cancelled = True
                _kill_tree(proc)
                break
            if deadline is not None and time.monotonic() > deadline:
                timed_out = True
                on_output(f"ptk: timeout after {command.timeout:g}s - terminating")
                _kill_tree(proc)
                break
            time.sleep(0.05)
        code = proc.wait()
        reader.join(timeout=GRACE_SECONDS)
        if timed_out or cancelled:
            code = code if code not in (0, None) else 1
        return ProcessOutcome(code, timed_out=timed_out, cancelled=cancelled)


def _path_of(env: dict[str, str]) -> str | None:
    for key, value in env.items():
        if key.upper() == "PATH":
            return value
    return None


def _pump(proc: subprocess.Popen, on_output: Callable[[str], None]) -> None:
    assert proc.stdout is not None
    for raw in iter(proc.stdout.readline, b""):
        on_output(raw.decode("utf-8", errors="replace").rstrip("\r\n"))
    proc.stdout.close()


def _kill_tree(proc: subprocess.Popen) -> None:
    if WINDOWS:
        subprocess.run(
            ["taskkill", "/T", "/F", "/PID", str(proc.pid)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return
    try:
        pgid = os.getpgid(proc.pid)
        os.killpg(pgid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        return
    # Reap the leader, but track the process group independently: descendants
    # may ignore TERM even when the leader exits immediately.
    deadline = time.monotonic() + GRACE_SECONDS
    while time.monotonic() < deadline:
        proc.poll()
        try:
            os.killpg(pgid, 0)
        except ProcessLookupError:
            return
        time.sleep(0.05)
    with contextlib.suppress(ProcessLookupError):
        os.killpg(pgid, signal.SIGKILL)
