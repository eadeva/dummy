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


def _list(value, name):
    if isinstance(value, str):
        return [value]
    if not isinstance(value, list) or not all(isinstance(s, str) for s in value):
        raise PtkError(f"{name} must be a string or list of strings")
    return value


def _inside(root: Path, path: str) -> Path:
    target = (root / path).resolve()
    if not target.is_relative_to(root.resolve()) or target == root.resolve():
        raise PtkError(f"path must be inside {root}: {path}")
    return target


def files_copy(step, out, ctx):
    patterns = _list(step.with_.get("files", []), "files")
    destination = _inside(ctx.root, step.with_.get("to", str(ctx.build_dir)))
    sources = [
        Path(p)
        for pattern in patterns
        for p in sorted(glob.glob(str(ctx.root / pattern), recursive=True))
        if Path(p).is_file()
    ]
    if not sources and not step.with_.get("optional", False):
        raise PtkError("files.copy matched no files")
    targets = []
    for source in sources:
        target = _inside(ctx.root, str(destination / source.name))
        if target in targets:
            raise PtkError(f"files.copy destination collision: {target.name}")
        if target.exists() and not step.with_.get("overwrite", False):
            raise PtkError(f"refusing to overwrite {target}")
        targets.append(target)
    destination.mkdir(parents=True, exist_ok=True)
    for source, target in zip(sources, targets, strict=True):
        if ctx.cancel is not None and ctx.cancel.is_set():
            return 1
        shutil.copy2(source, target)
        out(f"copied {source} -> {target}")
    return 0


def file_cleaner(roots):
    def clean(step, out, ctx):
        paths = _list(step.with_.get("paths", []), "paths")
        targets = []
        for path in paths:
            target = (ctx.root / path).resolve()
            if not any(
                target.is_relative_to(r.resolve()) and target != r.resolve()
                for r in roots
            ):
                raise PtkError(
                    f"files.clean only permits descendants of configured workspace folders: {path}"
                )
            targets.append(target)
        for target in targets:
            if ctx.cancel is not None and ctx.cancel.is_set():
                return 1
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink(missing_ok=True)
            out(f"cleaned {target}")
        return 0

    return clean
