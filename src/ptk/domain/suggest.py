"""'Did you mean ...' helper used for every unknown name."""

from __future__ import annotations

import difflib
from collections.abc import Iterable


def did_you_mean(name: str, candidates: Iterable[str]) -> str:
    match = difflib.get_close_matches(name, list(candidates), n=1, cutoff=0.6)
    return f" (did you mean '{match[0]}'?)" if match else ""


def known(candidates: Iterable[str], limit: int = 12) -> str:
    items = sorted(candidates)
    shown = ", ".join(items[:limit])
    return shown + (", ..." if len(items) > limit else "") if items else "none"
