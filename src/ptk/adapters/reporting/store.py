"""ReportStore adapter: run summaries from the logs, reports into _reports."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from pathlib import Path

from ...domain.errors import PtkError
from ...domain.reporting.model import Contribution, Report
from . import exporters, html, importers

FILES = {
    "json": "report.json",
    "junit": "report.xml",
    "html": "report.html",
    "markdown": "report.md",
}


class FileReportStore:
    def __init__(self, environ: Mapping[str, str], reporters=None, contributors=None):
        self._environ = environ
        self._reporters = reporters or {}
        self._contributors = contributors or {}

    def read_summary(self, log_dir: Path, run_id: str | None = None) -> dict:
        folder = log_dir / "_history" / run_id if run_id else log_dir
        summary = folder / "run.json"
        if not summary.is_file():
            if run_id:
                runs = (
                    sorted(p.name for p in (log_dir / "_history").glob("*"))
                    if log_dir.is_dir()
                    else []
                )
                hint = f" (kept runs: {', '.join(runs)})" if runs else ""
                raise PtkError(f"no run {run_id}{hint}")
            raise PtkError(f"no run found in {log_dir} - run the action first")
        return json.loads(summary.read_text(encoding="utf-8"))

    def contributions(self, reports_dir: Path, labels: list[str]) -> list[Contribution]:
        results = importers.scan(reports_dir, importers.step_folders(labels))
        for handler in self._contributors.values():
            results.extend(handler(reports_dir, labels))
        return [r for r in results if r.step in labels]

    def write(self, report: Report, formats: list[str], target: Path) -> list[Path]:
        unknown = set(formats) - (set(FILES) | {"github"} | set(self._reporters))
        if unknown:
            raise PtkError(f"unknown report format(s): {sorted(unknown)}")
        target.mkdir(parents=True, exist_ok=True)
        written: list[Path] = []
        for fmt in formats:
            if fmt in self._reporters:
                written.append(Path(self._reporters[fmt](report, target)))
                continue
            if fmt == "github":
                path = self._environ.get("GITHUB_STEP_SUMMARY")
                if path:
                    with open(path, "a", encoding="utf-8") as handle:
                        handle.write(exporters.to_markdown(report) + "\n")
                    written.append(Path(path))
                continue
            file = target / FILES[fmt]
            if fmt == "json":
                text = exporters.to_json(report)
            elif fmt == "junit":
                text = exporters.to_junit(report)
            elif fmt == "markdown":
                text = exporters.to_markdown(report)
            else:
                text = html.render(report, link_root=target)
            tmp = file.with_suffix(file.suffix + ".tmp")
            tmp.write_text(text, encoding="utf-8")
            os.replace(tmp, file)
            written.append(file)
        return written
