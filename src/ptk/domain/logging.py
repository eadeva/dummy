"""Log levels and run-history rules (pure).

ptk's own messages have a level; the console shows messages at or above the
effective level (info by default, ``-v`` = debug, ``-vv`` =
trace, ``--quiet`` = warning). Log files always keep debug and above (trace
too with -vv). Command output is not levelled: it always goes
to the step log and, unless quiet, to the console.
"""

from __future__ import annotations

from collections.abc import Iterable
from enum import IntEnum


class Level(IntEnum):
    TRACE = 5
    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40

    @property
    def label(self) -> str:
        return self.name.lower()


def parse_level(name: str) -> Level:
    try:
        return Level[name.strip().upper()]
    except KeyError:
        options = ", ".join(level.label for level in Level)
        raise ValueError(f"unknown log level {name!r} (use {options})") from None


def console_level(configured: str, *, verbose: int = 0, quiet: bool = False) -> Level:
    if quiet:
        return Level.WARNING
    if verbose >= 2:
        return Level.TRACE
    if verbose == 1:
        return min(Level.DEBUG, parse_level(configured))
    return parse_level(configured)


def file_level(configured: str) -> Level:
    return min(Level.DEBUG, parse_level(configured))


def runs_to_prune(run_ids: Iterable[str], keep: int) -> list[str]:
    """Oldest history entries beyond ``keep`` (run ids sort chronologically)."""
    ordered = sorted(run_ids)
    return ordered[: max(0, len(ordered) - keep)]


def history_name(run_id: str, taken: Iterable[str]) -> str:
    """``run_id``, or ``run_id-2``, ``-3`` ... if two runs started in the same second."""
    existing = set(taken)
    if run_id not in existing:
        return run_id
    n = 2
    while f"{run_id}-{n}" in existing:
        n += 1
    return f"{run_id}-{n}"
