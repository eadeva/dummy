"""Built-in vault: one encrypted file per user, no external tools.

* file: ``%APPDATA%\\ptk\\vault.json`` (Windows) or ``$XDG_CONFIG_HOME/ptk/vault.json``
  (default ``~/.config/ptk``); ``PTK_VAULT_FILE`` overrides
* key: scrypt(master password, random salt); content: AES-256-GCM, so names and
  values are both encrypted and any tampering is detected
* master password: ``PTK_VAULT_PASSWORD`` (automation) or asked once per ptk run
* written atomically, readable by the owner only (POSIX)
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import sys
import tempfile
from collections.abc import Callable, Mapping
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from ...domain.credentials import SecretKey
from ...domain.errors import PtkError
from ..locking import file_lock

AAD = b"ptk-vault-v1"
SCRYPT = {"n": 2**15, "r": 8, "p": 1}


def default_vault_file(environ: Mapping[str, str]) -> Path:
    if environ.get("PTK_VAULT_FILE"):
        return Path(environ["PTK_VAULT_FILE"])
    if sys.platform.startswith("win"):
        base = Path(environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    else:
        base = Path(environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / "ptk" / "vault.json"


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _derive(password: str, salt: bytes, params: Mapping[str, int]) -> bytes:
    return hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=params["n"],
        r=params["r"],
        p=params["p"],
        maxmem=128 * 1024 * 1024,
        dklen=32,
    )


class Vault:
    """The encrypted file. ``password`` is asked lazily, at most once."""

    def __init__(self, path: Path, password: Callable[[bool], str]):
        self.path = path
        self._password = password  # password(confirm) -> str
        self._key: bytes | None = None
        self._salt: bytes | None = None
        self._entries: dict[str, str] | None = None

    @property
    def exists(self) -> bool:
        return self.path.is_file()

    def create(self) -> None:
        with file_lock(self.path.with_suffix(".lock")):
            self._create()

    def _create(self) -> None:
        if self.exists:
            raise PtkError(f"a vault already exists at {self.path}")
        password = self._password(True)
        if len(password) < 8:
            raise PtkError("the master password needs at least 8 characters")
        self._salt = os.urandom(16)
        self._key = _derive(password, self._salt, SCRYPT)
        self._entries = {}
        self._save()

    def entries(self) -> dict[str, str]:
        if self._entries is None:
            self._open()
        assert self._entries is not None
        return self._entries

    def set(self, name: str, value: str) -> None:
        with file_lock(self.path.with_suffix(".lock")):
            if not self.exists:
                self._create()
            else:
                self._open()  # refresh under lock; never save a stale snapshot
            self.entries()[name] = value
            self._save()

    def remove(self, name: str) -> bool:
        with file_lock(self.path.with_suffix(".lock")):
            if not self.exists:
                return False
            self._open()
            if name not in self.entries():
                return False
            del self.entries()[name]
            self._save()
            return True

    # -- internals ---------------------------------------------------------------------

    def _open(self) -> None:
        if not self.exists:
            raise PtkError(
                f"no vault yet ({self.path}); create one with 'ptk self-service creds setup'"
            )
        try:
            doc = json.loads(self.path.read_text(encoding="utf-8"))
            kdf = doc["kdf"]
            salt = base64.b64decode(kdf["salt"])
            nonce = base64.b64decode(doc["nonce"])
            data = base64.b64decode(doc["data"])
        except (ValueError, KeyError) as exc:
            raise PtkError(f"{self.path} is not a ptk vault ({exc})") from None
        key = self._key if self._salt == salt else None
        key = key or _derive(self._password(False), salt, kdf)
        try:
            plain = AESGCM(key).decrypt(nonce, data, AAD)
        except InvalidTag:
            raise PtkError(
                "wrong vault password (or the vault file was modified)"
            ) from None
        self._key, self._salt = key, salt
        self._entries = json.loads(plain.decode("utf-8"))["entries"]

    def _save(self) -> None:
        assert self._key is not None and self._salt is not None
        nonce = os.urandom(12)
        plain = json.dumps({"entries": self._entries or {}}).encode("utf-8")
        doc = {
            "format": "ptk-vault",
            "version": 1,
            "kdf": {"name": "scrypt", **SCRYPT, "salt": _b64(self._salt)},
            "cipher": "AES-256-GCM",
            "nonce": _b64(nonce),
            "data": _b64(AESGCM(self._key).encrypt(nonce, plain, AAD)),
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(
            dir=self.path.parent, prefix=".vault-", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(doc, handle, indent=2)
            if not sys.platform.startswith("win"):
                os.chmod(tmp, 0o600)
            os.replace(tmp, self.path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise


class VaultProvider:
    name = "vault"
    can_store = True

    def __init__(self, vault: Vault):
        self.vault = vault

    def available(self) -> tuple[bool, str]:
        if not self.vault.exists:
            return (
                False,
                "no vault yet ('ptk self-service creds setup' or 'ptk self-service creds set' creates one)",
            )
        return True, ""

    def get(self, key: SecretKey) -> str | None:
        if not self.vault.exists:
            return None
        return self.vault.entries().get(key.storage_ref)

    def store(self, key: SecretKey, value: str) -> None:
        self.vault.set(key.storage_ref, value)

    def remove(self, key: SecretKey) -> bool:
        return self.vault.remove(key.storage_ref)
