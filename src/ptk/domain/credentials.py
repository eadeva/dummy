"""Credential conventions (pure)."""

from __future__ import annotations

import re


def default_variable(credential: str, field: str) -> str:
    """Environment variable read by the env provider when ``env:`` maps nothing: PTK_CRED_<NAME>_<FIELD>."""

    def ident(text: str) -> str:
        return re.sub(r"[^0-9A-Za-z_]", "_", text).upper()

    return f"PTK_CRED_{ident(credential)}_{ident(field)}"
