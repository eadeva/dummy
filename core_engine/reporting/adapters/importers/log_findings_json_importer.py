"""Importer for canonical log findings JSON artifacts."""

import json
from pathlib import Path

from xc_ce_utils.core_engine.reporting.domain.models import (
    CanonicalReport,
    LogFinding,
)


class LogFindingsJsonImporter:
    """Import log-findings canonical JSON into report.log_findings."""

    name = 'log-findings-json'

    def supports(self, file_path: Path) -> bool:
        if file_path.suffix.lower() != '.json':
            return False
        try:
            with file_path.open('r', encoding='utf-8') as handle:
                data = json.load(handle)
        except Exception:
            return False
        return data.get('report_kind') == 'log-findings'

    def import_file(self, file_path: Path, report: CanonicalReport) -> None:
        with file_path.open('r', encoding='utf-8') as handle:
            data = json.load(handle)

        for item in data.get('findings', []) or []:
            properties = self._to_dict(item.get('properties'))
            report.log_findings.append(
                LogFinding(
                    step=self._resolve_step(item, properties),
                    type=self._resolve_type(item),
                    classification=self._resolve_classification(
                        item, properties
                    ),
                    message=str(item.get('message', '')),
                    file=str(item.get('file', '')),
                    line=self._to_int(item.get('line')),
                    source_file=str(item.get('source_file', str(file_path))),
                    properties=properties,
                )
            )

    def _to_int(self, value) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    def _to_dict(self, value):
        if isinstance(value, dict):
            return {str(k): str(v) for k, v in value.items()}
        return {}

    def _resolve_step(self, item: dict, properties: dict) -> str:
        return str(
            item.get('step')
            or properties.get('step_name')
            or item.get('tool')
            or 'unknown'
        )

    def _resolve_type(self, item: dict) -> str:
        issue_type = str(item.get('type', '')).strip().lower()
        if issue_type in {'warning', 'error', 'exception'}:
            return issue_type

        severity = str(item.get('severity', '')).strip().lower()
        if severity in {'critical', 'high', 'medium'}:
            return 'error'
        if severity in {'low', 'info'}:
            return 'warning'
        return 'error'

    def _resolve_classification(self, item: dict, properties: dict) -> str:
        value = str(item.get('classification', '')).strip()
        if value:
            return value

        step_type = str(properties.get('step_type', '')).lower()
        if 'cmake' in step_type:
            return 'CMake'
        if 'bazel' in step_type:
            return 'Bazel'
        if 'link' in step_type:
            return 'Linker'
        if 'compiler' in step_type or 'compile' in step_type:
            return 'Compiler'
        if 'script' in step_type or 'shell' in step_type:
            return 'Custom Script'
        return 'XC-CE Utils'
