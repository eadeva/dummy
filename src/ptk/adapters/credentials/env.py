"""Environment variables (CX). Read-only."""

from __future__ import annotations

import re
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
        value = self._environ.get(key.env_var)
        if not value and key.env_pattern:
            match = self.match(key)
            value = self._environ.get(match[0]) if match else None
        for name in key.env_fallbacks:
            value = value or self._environ.get(name)
        return value or None

    def match(self, key: SecretKey) -> tuple[str, str] | None:
        """(variable, user ID) of the one convention variable set for ``key`` (any user)."""
        if not key.env_pattern:
            return None
        pattern = re.compile(key.env_pattern)
        found = sorted(
            (name, m.group(1).lower())
            for name, value in self._environ.items()
            if value and (m := pattern.match(name))
        )
        if len(found) > 1:
            raise PtkError(
                f"{key.ref}: several users set it ({', '.join(name for name, _ in found)})"
            )
        return found[0] if found else None

    def store(self, key: SecretKey, value: str) -> None:
        raise PtkError(f"set the environment variable {key.env_var} instead")

    def remove(self, key: SecretKey) -> bool:
        return False
