from __future__ import annotations

import os
import subprocess
import sys

import pytest

from ptk.adapters.locking import file_lock
from ptk.domain.errors import PtkError


def dead_pid() -> int:
    process = subprocess.Popen([sys.executable, "-c", "pass"])
    process.wait()
    return process.pid


def test_lock_of_an_exited_owner_is_taken_over(tmp_path):
    lock = tmp_path / "tool.lock"
    lock.write_text(str(dead_pid()))
    with file_lock(lock, timeout=0):
        assert lock.read_text() == str(os.getpid())
    assert not lock.exists()


def test_lock_of_a_live_owner_waits_and_reports(tmp_path):
    lock = tmp_path / "tool.lock"
    owner = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        lock.write_text(str(owner.pid))
        lines = []
        with (
            pytest.raises(PtkError, match="resource is locked"),
            file_lock(lock, timeout=0.2, waiting=lines.append),
        ):
            pass
        assert lines == [f"waiting for another PTk process holding {lock}"]
    finally:
        owner.kill()
        owner.wait()
