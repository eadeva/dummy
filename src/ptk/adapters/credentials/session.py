"""Keeps the vault unlocked for a while (default 8 hours, ``PTK_VAULT_UNLOCK_HOURS``).

Stores the derived vault key, never the master password:

* Windows: ``%LOCALAPPDATA%\\ptk\\sessions``, encrypted with DPAPI (only this Windows user can read it)
* Linux: ``$XDG_RUNTIME_DIR/ptk`` (per-user tmpfs, removed at logout), owner-only file;
  without ``XDG_RUNTIME_DIR`` nothing is kept
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import sys
import time
from collections.abc import Callable, Mapping
from pathlib import Path

from ...domain.errors import PtkError

WINDOWS = sys.platform == "win32"


def _dpapi(data: bytes, protect: bool) -> bytes:
    import ctypes
    from ctypes import wintypes

    class Blob(ctypes.Structure):
        _fields_ = [
            ("cbData", wintypes.DWORD),
            ("pbData", ctypes.POINTER(ctypes.c_char)),
        ]

    crypt32 = ctypes.windll.crypt32  # type: ignore[attr-defined]
    kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
    buffer = ctypes.create_string_buffer(data, len(data))
    source = Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char)))
    result = Blob()
    ui_forbidden = 0x1
    if protect:
        ok = crypt32.CryptProtectData(
            ctypes.byref(source), "ptk vault session", None, None, None,
            ui_forbidden, ctypes.byref(result),
        )  # fmt: skip
    else:
        ok = crypt32.CryptUnprotectData(
            ctypes.byref(source), None, None, None, None,
            ui_forbidden, ctypes.byref(result),
        )  # fmt: skip
    if not ok:
        raise OSError("DPAPI failed")
    try:
        return ctypes.string_at(result.pbData, result.cbData)
    finally:
        kernel32.LocalFree(result.pbData)


class VaultSession:
    def __init__(
        self,
        vault_path: Path,
        environ: Mapping[str, str],
        *,
        now: Callable[[], float] = time.time,
        windows: bool = WINDOWS,
    ):
        raw = environ.get("PTK_VAULT_UNLOCK_HOURS", "8")
        try:
            self.ttl = float(raw) * 3600
        except ValueError:
            raise PtkError(
                f"PTK_VAULT_UNLOCK_HOURS must be a number of hours, not '{raw}'"
            ) from None
        self._now = now
        self._windows = windows
        self._vault = str(vault_path.resolve())
        if windows:
            base = environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
            folder: Path | None = Path(base) / "ptk" / "sessions"
        else:
            runtime = environ.get("XDG_RUNTIME_DIR")
            folder = Path(runtime) / "ptk" if runtime else None
        digest = hashlib.sha256(self._vault.encode("utf-8")).hexdigest()[:16]
        self.file = folder / f"vault-{digest}.session" if folder else None

    @property
    def enabled(self) -> bool:
        return self.file is not None and self.ttl > 0

    def load(self) -> tuple[bytes, bytes] | None:
        """``(salt, key)`` of a valid session, else None."""
        if not self.enabled or self.file is None or not self.file.is_file():
            return None
        try:
            data = self.file.read_bytes()
            if self._windows:
                data = _dpapi(data, protect=False)
            doc = json.loads(data)
            if doc["vault"] != self._vault or doc["expires"] <= self._now():
                raise ValueError("expired")
            return base64.b64decode(doc["salt"]), base64.b64decode(doc["key"])
        except (OSError, ValueError, KeyError, TypeError):
            self.clear()
            return None

    def save(self, salt: bytes, key: bytes) -> None:
        if not self.enabled or self.file is None:
            return
        doc = {
            "vault": self._vault,
            "expires": self._now() + self.ttl,
            "salt": base64.b64encode(salt).decode("ascii"),
            "key": base64.b64encode(key).decode("ascii"),
        }
        data = json.dumps(doc).encode("utf-8")
        try:
            if self._windows:
                data = _dpapi(data, protect=True)
            self.file.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            self.file.unlink(missing_ok=True)
            fd = os.open(self.file, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
        except OSError:
            self.clear()  # unlocking still works, it is just asked again next run

    def clear(self) -> bool:
        if self.file is None or not self.file.is_file():
            return False
        self.file.unlink(missing_ok=True)
        return True
