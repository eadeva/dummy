"""Execution-step canonical JSON importer."""

import json
from pathlib import Path

from xc_ce_utils.core_engine.reporting.domain.models import (
    CanonicalReport,
    ExecutionStepRecord,
)


class ExecutionStepImporter:
    """Import per-step execution artifacts into canonical execution records."""

    name = 'execution-step'

    def supports(self, file_path: Path) -> bool:
        if file_path.suffix.lower() != '.json':
            return False
        try:
            with file_path.open('r', encoding='utf-8') as handle:
                data = json.load(handle)
        except Exception:
            return False
        return data.get('report_kind') == 'execution-step'

    def import_file(self, file_path: Path, report: CanonicalReport) -> None:
        with file_path.open('r', encoding='utf-8') as handle:
            data = json.load(handle)

        step = data.get('step', {})
        status = data.get('status', {})
        timing = data.get('timing', {})
        parameters = data.get('params', data.get('parameters', {})) or {}

        record = ExecutionStepRecord(
            name=str(step.get('name', 'unknown')),
            step_type=self._resolve_step_type(
                step_type=step.get('step_type', ''),
                parameters=parameters,
                script_hint=step.get('script_ref', ''),
            ),
            status=str(status.get('execution_status', 'UNKNOWN')),
            execution_index=self._opt_int(data.get('execution_index')),
            test_status=str(status.get('test_status', 'n.a.')),
            elapsed_seconds=self._opt_float(timing.get('elapsed_seconds')),
            elapsed_human=str(timing.get('elapsed_human', '')),
            parameters=parameters,
            results=[str(item) for item in data.get('results', [])],
            artifacts={
                str(k): str(v)
                for k, v in (data.get('artifacts', {}) or {}).items()
            },
            source_file=str(file_path),
        )
        report.execution_steps.append(record)

    def _resolve_step_type(self, step_type, parameters, script_hint='') -> str:
        raw_type = str(step_type or '').strip()
        normalized_type = raw_type.lower()
        if normalized_type not in {'custom_script', 'shell_run_command'}:
            return raw_type

        script_ref = str(script_hint or '').strip()
        if isinstance(parameters, dict):
            if not script_ref:
                script_ref = str(
                    parameters.get('path')
                    or parameters.get('script')
                    or parameters.get('script_path')
                    or parameters.get('file')
                    or ''
                ).strip()

        if script_ref:
            return f'custom_script:{Path(script_ref).name}'
        return 'custom_script'

    def _opt_float(self, value):
        if value is None or value == '':
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _opt_int(self, value):
        if value is None or value == '':
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
