"""gopass (recommended with the age backend: no gpg-agent, works headless and on
Windows). Secrets go through stdin/stdout only - never as command arguments."""

from __future__ import annotations

import shutil
import subprocess

from ...domain.credentials import SecretKey
from ...domain.errors import PtkError

TIMEOUT = 60


class GopassProvider:
    name = "gopass"
    can_store = True

    def __init__(self, executable: str | None = None):
        self._exe = executable or shutil.which("gopass")

    def available(self) -> tuple[bool, str]:
        if not self._exe:
            return False, "gopass is not installed"
        return True, ""

    def _run(
        self, args: list[str], stdin: str | None = None
    ) -> subprocess.CompletedProcess:
        assert self._exe is not None
        return subprocess.run(
            [self._exe, *args],
            input=stdin,
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
            check=False,
        )

    def get(self, key: SecretKey) -> str | None:
        if not self._exe:
            return None
        result = self._run(["show", "--password", key.gopass_path])
        if result.returncode != 0:
            return None
        value = result.stdout.rstrip("\r\n")
        return value or None

    def store(self, key: SecretKey, value: str) -> None:
        if not self._exe:
            raise PtkError("gopass is not installed")
        result = self._run(["insert", "--force", key.gopass_path], stdin=value + "\n")
        if result.returncode != 0:
            raise PtkError(f"gopass insert failed: {result.stderr.strip()}")

    def remove(self, key: SecretKey) -> bool:
        if not self._exe:
            return False
        return self._run(["rm", "--force", key.gopass_path]).returncode == 0
