"""Workspace folder layout (pure).

    <root>/_builds/<variant>/<job>/<set>/<step>/    working directory per step
    <root>/_bin/<variant>/                              binaries / artifacts per variant
    <root>/_logs/<variant>/<job>/run.log             whole run of a job
    <root>/_logs/<variant>/<job>/<set>/<step>.log    one log per step
    <root>/_reports/<variant>/<job>/<set>/<step>/    reports per step
    <root>/_reports/<variant>/<job>/report.*         job report

Without variants the ``<variant>`` level is ``default``. Folder names and the
root are configurable (``layout:``); names are sanitised for all platforms.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import PurePath

NO_VARIANT = "default"
_UNSAFE = re.compile(r"[^A-Za-z0-9_.-]")


def safe(name: str) -> str:
    cleaned = _UNSAFE.sub("_", name).strip(".")
    return cleaned or "_"


@dataclass(frozen=True)
class Layout:
    root: PurePath
    builds: str = "_builds"
    bin: str = "_bin"
    logs: str = "_logs"
    reports: str = "_reports"

    def _variant(self, variant: str | None) -> str:
        return safe(variant) if variant else NO_VARIANT

    def _steps(self, step_path: tuple[str, ...]) -> list[str]:
        return [safe(s) for s in step_path]

    def build_dir(
        self, variant: str | None, job: str, step_path: tuple[str, ...] = ()
    ) -> PurePath:
        return self.root.joinpath(
            self.builds, self._variant(variant), safe(job), *self._steps(step_path)
        )

    def bin_dir(self, variant: str | None) -> PurePath:
        return self.root.joinpath(self.bin, self._variant(variant))

    def job_log_dir(self, variant: str | None, job: str) -> PurePath:
        return self.root.joinpath(self.logs, self._variant(variant), safe(job))

    def run_log(self, variant: str | None, job: str) -> PurePath:
        return self.job_log_dir(variant, job) / "run.log"

    def step_log(
        self, variant: str | None, job: str, step_path: tuple[str, ...]
    ) -> PurePath:
        parts = self._steps(step_path)
        return self.job_log_dir(variant, job).joinpath(*parts[:-1], f"{parts[-1]}.log")

    def reports_dir(
        self, variant: str | None, job: str, step_path: tuple[str, ...] = ()
    ) -> PurePath:
        return self.root.joinpath(
            self.reports, self._variant(variant), safe(job), *self._steps(step_path)
        )

    def all_roots(self) -> list[PurePath]:
        return [
            self.root / name
            for name in (self.builds, self.bin, self.logs, self.reports)
        ]
