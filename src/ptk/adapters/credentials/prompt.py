"""Asking the person at the terminal (never in CX or without a terminal)."""

from __future__ import annotations

import getpass
import sys
from collections.abc import Callable
from typing import Any

from ...domain.credentials import SecretKey
from ...domain.errors import PtkError


class ConsolePrompter:
    def __init__(self, is_cx: Callable[[], bool]):
        self._is_cx = is_cx

    def interactive(self) -> bool:
        return sys.stdin.isatty() and not self._is_cx()

    def secret(self, question: str) -> str:
        if not self.interactive():
            raise PtkError(
                f"cannot ask for '{question}': no terminal (or running in CX)"
            )
        return getpass.getpass(f"{question}: ")


class PromptProvider:
    """Asks once per ptk run; the service stores the answer when the credential has ``remember``."""

    name = "prompt"
    can_store = False

    def __init__(self, prompter: Any):
        self._prompter = prompter

    def available(self) -> tuple[bool, str]:
        if not self._prompter.interactive():
            return False, "not interactive (no terminal, or CX)"
        return True, ""

    def get(self, key: SecretKey) -> str | None:
        if not self._prompter.interactive():
            return None
        return self._prompter.secret(key.ref) or None

    def store(self, key: SecretKey, value: str) -> None:
        raise PtkError("the prompt cannot store secrets")

    def remove(self, key: SecretKey) -> bool:
        return False
