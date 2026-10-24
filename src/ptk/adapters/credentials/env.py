"""Environment variables (CI). Read-only."""

from __future__ import annotations

from collections.abc import Mapping

from ...domain.credentials import SecretKey
from ...domain.errors import PtkError


class EnvProvider:
    name = "env"
    can_store = False

    def __init__(self, environ: Mapping[str, str]):
        self._environ = environ

    def available(self) -> tuple[bool, str]:
        return True, ""

    def get(self, key: SecretKey) -> str | None:
        return self._environ.get(key.env_var) or None

    def store(self, key: SecretKey, value: str) -> None:
        raise PtkError(f"set the environment variable {key.env_var} instead")

    def remove(self, key: SecretKey) -> bool:
        return False
