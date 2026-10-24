"""OS keyring (optional: ``ptk[keyring]``): Windows Credential Manager, macOS
Keychain, Secret Service on Linux desktops. Skipped when the package is missing
or no real backend exists (e.g. Linux servers without a desktop session)."""

from __future__ import annotations

from typing import Any

from ...domain.credentials import SecretKey
from ...domain.errors import PtkError

SERVICE = "ptk"


def _load() -> tuple[Any | None, str]:
    try:
        import keyring  # type: ignore[import-not-found]
        from keyring.errors import (
            KeyringError,  # type: ignore[import-not-found]  # noqa: F401
        )
    except ImportError:
        return None, 'not installed (uv tool install "ptk[keyring]")'
    try:
        backend = keyring.get_keyring()
    except Exception as exc:  # noqa: BLE001 - any backend problem means "not usable"
        return None, f"no usable backend ({exc})"
    name = type(backend).__module__ + "." + type(backend).__name__
    priority = getattr(backend, "priority", 1)
    if (
        "fail" in name.lower()
        or "null" in name.lower()
        or (priority is not None and priority <= 0)
    ):
        return None, "no usable keyring backend on this machine"
    return keyring, ""


class KeyringProvider:
    name = "keyring"
    can_store = True

    def __init__(self) -> None:
        self._module: Any | None = None
        self._reason = ""
        self._loaded = False

    def _keyring(self) -> Any | None:
        if not self._loaded:
            self._module, self._reason = _load()
            self._loaded = True
        return self._module

    def available(self) -> tuple[bool, str]:
        return (self._keyring() is not None), self._reason

    def get(self, key: SecretKey) -> str | None:
        keyring = self._keyring()
        if keyring is None:
            return None
        try:
            return keyring.get_password(SERVICE, key.ref) or None
        except Exception:  # noqa: BLE001 - a broken backend must not stop the chain
            return None

    def store(self, key: SecretKey, value: str) -> None:
        keyring = self._keyring()
        if keyring is None:
            raise PtkError(f"keyring: {self._reason}")
        keyring.set_password(SERVICE, key.ref, value)

    def remove(self, key: SecretKey) -> bool:
        keyring = self._keyring()
        if keyring is None:
            return False
        try:
            keyring.delete_password(SERVICE, key.ref)
        except Exception:  # noqa: BLE001 - not stored
            return False
        return True
