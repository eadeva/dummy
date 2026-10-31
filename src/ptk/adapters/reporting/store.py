"""ReportStore adapter: run summaries from the logs, reports into _reports."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from pathlib import Path

from ...domain.errors import PtkError, RunNotFoundError
from ...domain.reporting.model import Contribution, Report
from . import diagnostics, exporters, html, importers

FILES = {
    "json": "report.json",
    "junit": "report.xml",
    "html": "report.html",
    "markdown": "report.md",
}


class FileReportStore:
    def __init__(self, environ: Mapping[str, str]):
        self._environ = environ

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
                raise RunNotFoundError(f"no run {run_id}{hint}")
            raise RunNotFoundError(f"no run found in {log_dir} - run the job first")
        return json.loads(summary.read_text(encoding="utf-8"))

    def contributions(self, reports_dir: Path, labels: list[str]) -> list[Contribution]:
        results = importers.scan(reports_dir, importers.step_folders(labels))
        return [r for r in results if r.step in labels]

    def analyze_logs(self, summary):
        from .log_analysis import analyze

        return analyze(summary)

    def write(self, report: Report, formats: list[str], target: Path) -> list[Path]:
        unknown = set(formats) - (set(FILES) | {"github"})
        if unknown:
            raise PtkError(f"unknown report format(s): {sorted(unknown)}")
        target.mkdir(parents=True, exist_ok=True)
        written: list[Path] = []
        for fmt in formats:
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
        dedicated = target / "diagnostics.html"
        full = target / "report.html" if "html" in formats else None
        text = diagnostics.page(
            diagnostics.collect(report, html.owner(report), target),
            name=report.job,
            identity=html.owner(report),
            status=report.status,
            full_report=full,
            root=target,
        )
        temporary = dedicated.with_suffix(".html.tmp")
        temporary.write_text(text, encoding="utf-8")
        os.replace(temporary, dedicated)
        written.append(dedicated)
        return written
