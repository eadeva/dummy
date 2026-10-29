"""Build and write reports (use case ``ReportService``).

A report is built from the canonical run summary plus the tool results the
steps left in their reports folders, so it can be regenerated at any time.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ...domain.reporting.model import Report, from_summary
from ..ports import ReportStore
from .project import Project
from .run import layout_of
from .variants import VariantService


class ReportService:
    def __init__(self, store: ReportStore, version: str):
        self._store = store
        self._version = version

    @property
    def version(self) -> str:
        return self._version

    def build(self, project: Project, summary: dict[str, Any]) -> Report:
        summary = {
            **summary,
            "steps": [s for s in summary.get("steps", []) if s.get("report", True)],
        }
        reports_dir = self._reports_dir(project, summary)
        labels = [s["step"] for s in summary.get("steps", [])]
        contributions = self._store.contributions(reports_dir, labels)
        report = from_summary(summary, contributions, self._version)
        if summary.get("log_analysis", {}).get("enabled", False):
            analysis = self._store.analyze_logs(summary)
            report.log_analysis_enabled = True
            report.log_findings.extend(analysis.log_findings)
            report.problems.extend(analysis.problems)
        return report

    def write(
        self,
        project: Project,
        summary: dict[str, Any],
        formats: list[str] | None = None,
        target: Path | None = None,
    ) -> tuple[Report, list[Path]]:
        report = self.build(project, summary)
        formats = list(
            formats if formats is not None else project.config.report_formats
        )
        out = target or self.output_dir(project, report.variant, report.job)
        return report, self._store.write(report, formats, out)

    def latest(
        self,
        project: Project,
        job: str,
        variant: str | None,
        run_id: str | None = None,
    ) -> dict[str, Any]:
        layout = layout_of(project)
        name = self._variant(project, variant)
        return self._store.read_summary(Path(layout.job_log_dir(name, job)), run_id)

    def output_dir(self, project: Project, variant: str | None, job: str) -> Path:
        layout = layout_of(project)
        name = None if variant in (None, "default") else variant
        return Path(layout.reports_dir(name, job))

    def _reports_dir(self, project: Project, summary: dict[str, Any]) -> Path:
        if summary.get("reports_dir"):
            return Path(summary["reports_dir"])
        variant = summary.get("variant")
        layout = layout_of(project)
        return Path(
            layout.reports_dir(
                None if variant == "default" else variant, summary["job"]
            )
        )

    @staticmethod
    def _variant(project: Project, variant: str | None) -> str | None:
        service = VariantService(project)
        return service.name_of(variant) if service.has_variants else None
