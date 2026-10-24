"""Built-in steps that touch files (registered in the composition root).

``report.import``: copy tool results (JUnit, SARIF, Cobertura) into the step's
reports folder so they become part of the report::

    - results:
        uses: report.import
        with: {files: [build/test-results/*.xml, build/clang-tidy.sarif], optional: false}
"""

from __future__ import annotations

import glob
import shutil
from collections.abc import Callable
from pathlib import Path

from ..application.use_cases.run import BuiltinContext
from ..domain.errors import PtkError
from ..domain.execution.model import PlannedStep


def report_import(
    step: PlannedStep, out: Callable[[str], None], ctx: BuiltinContext
) -> int:
    patterns = step.with_.get("files", [])
    if isinstance(patterns, str):
        patterns = [patterns]
    if not patterns:
        raise PtkError("report.import needs 'with: {files: [...]}'")
    ctx.reports_dir.mkdir(parents=True, exist_ok=True)
    copied = 0
    for pattern in patterns:
        base = Path(pattern) if Path(pattern).is_absolute() else ctx.root / pattern
        for match in sorted(glob.glob(str(base), recursive=True)):
            source = Path(match)
            if not source.is_file():
                continue
            target = ctx.reports_dir / source.name
            n = 2
            while target.exists():
                target = ctx.reports_dir / f"{source.stem}-{n}{source.suffix}"
                n += 1
            shutil.copy2(source, target)
            out(f"imported {source} -> {target.name}")
            copied += 1
    if copied == 0 and not step.with_.get("optional", False):
        out(f"no files matched: {', '.join(map(str, patterns))}")
        return 1
    return 0
