"""Build and write reports (use case ``ReportService``).

A report is built from the canonical run summary plus the tool results the
steps left in their reports folders, including Sphinx evidence captured from
build folders. Retained inputs allow regeneration without current build outputs.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ...domain.config.model import LogAnalysisSpec
from ...domain.reporting.bazel import merge_log_evidence as merge_bazel_logs
from ...domain.reporting.cmake import merge_log_evidence, merge_sarif_evidence
from ...domain.reporting.log_analysis import disposition
from ...domain.reporting.model import Finding, Report, from_summary
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
        reports_dir = self._reports_dir(project, summary)
        visible = [s for s in summary.get("steps", []) if s.get("report", True)]
        labels = [s["step"] for s in visible]
        contributions = self._store.contributions(reports_dir, labels)
        report = from_summary(summary, contributions, self._version)
        policy = LogAnalysisSpec.model_validate(summary.get("log_analysis", {}))
        rules = [(rule, re.compile(rule.match.message_regex)) for rule in policy.rules]
        for finding in report.findings:
            disposition(finding, rules)
        log_files = {step["step"]: step.get("log_file", "") for step in visible}
        for bazel in report.bazel:
            for finding in bazel.diagnostics:
                finding.source_log = log_files.get(bazel.step, "")
                disposition(finding, rules)
        for cmake in report.cmake:
            for finding in cmake.diagnostics:
                finding.source_log = log_files.get(cmake.step, "")
                disposition(finding, rules)
        for suite in report.suites:
            for case in suite.cases:
                if case.status in ("failed", "error"):
                    match = Finding(
                        "JUnit",
                        suite.name,
                        "error",
                        case.message or case.name,
                        step=suite.step,
                    )
                    disposition(match, rules)
                    case.disposition, case.suppression_rule, case.reason = (
                        match.disposition,
                        match.suppression_rule,
                        match.reason,
                    )
        for doc in report.sphinx:
            for violation in doc.violations:
                match = Finding(
                    "Sphinx-Needs",
                    violation.rule,
                    violation.level,
                    violation.message,
                    step=doc.step,
                )
                disposition(match, rules)
                violation.disposition, violation.suppression_rule, violation.reason = (
                    match.disposition,
                    match.suppression_rule,
                    match.reason,
                )
        if summary.get("log_analysis", {}).get("enabled", False):
            analysis = self._store.analyze_logs({**summary, "steps": visible})
            report.log_analysis_enabled = True
            report.log_findings.extend(analysis.log_findings)
            report.problems.extend(analysis.problems)
        merge_sarif_evidence(report)
        merge_log_evidence(report)
        merge_bazel_logs(report)
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
        return report, self.export(report, formats, out)

    def export(self, report: Report, formats: list[str], target: Path) -> list[Path]:
        """Export an already collected snapshot without reading evidence again."""
        return self._store.write(report, formats, target)

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
