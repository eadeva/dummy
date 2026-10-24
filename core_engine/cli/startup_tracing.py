"""Process-scoped startup timing trace helpers for the dynamic CLI.

Extracted from the former ``core_engine/dynamic_cli.py`` monolith.
"""

from __future__ import annotations

import os
from time import perf_counter
from typing import Optional

from xc_ce_utils import logger


def resolve_process_startup_anchor() -> float:
    """Return a process-scoped startup timer anchor.

    Reuses an existing anchor only when it belongs to the current PID to
    keep trace timestamps monotonic across modules loaded in the same process.
    """
    pid_key = 'XC_CE_UTILS_STARTUP_PID'
    t0_key = 'XC_CE_UTILS_STARTUP_T0'
    current_pid = str(os.getpid())
    now = perf_counter()

    if os.environ.get(pid_key) == current_pid:
        raw_t0 = os.environ.get(t0_key, '')
        try:
            anchor = float(raw_t0)
            if anchor <= now:
                return anchor
        except (TypeError, ValueError):
            pass

    os.environ[pid_key] = current_pid
    os.environ[t0_key] = str(now)
    return now


STARTUP_T0 = resolve_process_startup_anchor()
_STARTUP_STATE = {'last': STARTUP_T0}


def trace_startup(stage: str, *, t0: Optional[float] = None) -> float:
    """Emit startup timing checkpoints for dynamic CLI stages.

    The leading ``+... ms`` is always cumulative from process startup so
    values increase monotonically in call order.
    """
    now = perf_counter()
    cumulative_ms = (now - STARTUP_T0) * 1000
    step_base = _STARTUP_STATE['last'] if t0 is None else t0
    step_ms = (now - step_base) * 1000

    logger.trace(
        f'[startup] +{cumulative_ms:.1f} ms | step +{step_ms:.1f} ms | dynamic_cli: {stage}'
    )
    _STARTUP_STATE['last'] = now
    return now


trace_startup('module import complete')
