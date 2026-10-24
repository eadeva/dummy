"""Unified execution-log reporting: parsing, classification, and pipeline run.

Extracted from the former ``ExecutionAction`` god-class (``execution_engine.py``).
Parses per-step JSONL logs written during action execution, classifies
findings (compiler/linker/CMake/Bazel/QAC/etc.), and drives the canonical
reporting pipeline (:func:`xc_ce_utils.core_engine.reporting.build_default_reporting_pipeline`)
at the end of every action run.
"""

from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from importlib import import_module
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from xc_ce_utils import logger
from xc_ce_utils.core_engine.adapters.execution.tool_installer_adapter import (
    filter_tool_requires_by_type,
)

if TYPE_CHECKING:
    from xc_ce_utils.core_engine.config.action_configuration import (
        ActionConfiguration,
    )

DEFAULT_EXECUTION_INDEX = 10**9


@dataclass(frozen=True)
class _LogEntryContext:
    level: str
    module: str
    function: str
    step_name: str
    step_type: str
    classifiers: Dict[str, re.Pattern]


@dataclass
class _RepositoryInfo:
    """Repository information for artifact metadata."""

    repository: str
    repository_type: str


@dataclass
class _StepFindingContext:
    """Context for parsing step execution artifacts."""

    step_name: str
    step_type: str
    script_hint: str
    parameters: Dict[str, Any]
    jsonl_path: Optional[Path]
    execution_index: int


@dataclass
class _ParsedStepArtifactResult:
    execution_index: int
    findings: List[Dict[str, Any]]
    scanned_logs: int
    missing_logs: int
    invalid_json_lines: int


@dataclass
class _LogFindingsStats:
    scanned_logs: int
    missing_logs: int
    invalid_json_lines: int


@dataclass(frozen=True)
class _UnifiedReportingInputs:
    reports_dir: Path
    report_name: str
    canonical_json_name: str
    output_formats: List[str]
    metadata: Dict[str, Any]


def _get_default_reporting_pipeline_builder() -> Any:
    module = import_module('xc_ce_utils.core_engine.reporting')
    return module.build_default_reporting_pipeline


def _get_version_getter() -> Any:
    module = import_module('xc_ce_utils._version')
    return module.get_version


def _repo_type_from_url(url: str) -> str:
    """Classify repository type from URL hostname."""
    host = ''
    if url:
        try:
            host = (urlparse(str(url)).hostname or '').strip().lower()
        except Exception:
            host = ''
    if host == 'rb-artifactory.bosch.com':
        return 'RB'
    if host == 'artifactory.boschdevcloud.com':
        return 'BDC'
    return 'OTHER'


def _normalize_requirement_item(item: Any) -> Optional[Dict[str, Any]]:
    """Normalize a single requirement item."""
    if not isinstance(item, dict):
        return None
    normalized = {
        'name': str(item.get('name', '')).strip(),
        'type': str(item.get('type', '')).strip(),
        'version': str(item.get('version', '')).strip(),
        'properties': {str(k): str(v) for k, v in (item.get('properties', {}) or {}).items()},
    }
    return normalized if normalized['name'] else None


def _normalize_log_message_static(message: str) -> str:
    """Strip nested logger wrappers from raw command-output lines."""
    text = str(message or '').strip()
    if not text:
        return ''

    wrappers = [
        re.compile(
            r'^\s*(TRACE|DEBUG|INFO|NOTE|PROGRESS|SUCCESS|PHASE|WARNING|ERROR|CRITICAL)\s*-\s*\[[^\]]+\]\s*[^-]*-\s*',
            re.IGNORECASE,
        ),
        re.compile(
            r'^\s*(TRACE|DEBUG|INFO|NOTE|PROGRESS|SUCCESS|PHASE|WARNING|ERROR|CRITICAL)\s*-\s*',
            re.IGNORECASE,
        ),
        re.compile(
            r'^\s*\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:,\d+)?\s*-\s*[^-]+\s*-\s*[^-]+\s*-\s*',
            re.IGNORECASE,
        ),
    ]

    changed = True
    while changed:
        changed = False
        for pattern in wrappers:
            updated = pattern.sub('', text, count=1).strip()
            if updated != text:
                text = updated
                changed = True

    return text


class ReportingOrchestrator:
    """Collects execution-step logs, classifies findings, and runs the
    unified reporting pipeline at the end of an action run."""

    def __init__(self, config: 'ActionConfiguration') -> None:
        self.config = config
        self._errors = False

    def run_unified_reporting(
        self,
        *,
        errors: bool,
        action_error: Optional[Exception] = None,
    ) -> None:
        """Generate the unified report for the just-completed action."""
        reporting_config = getattr(self.config, 'reporting_config', {})
        if not isinstance(reporting_config, dict):
            reporting_config = {}

        if not reporting_config.get('enabled', True):
            logger.info(
                '[UNIFIED REPORTING] Unified reporting is disabled in reporting.yml, skipping.'
            )
            return

        self._errors = errors
        reporting_inputs = self._build_unified_reporting_inputs(
            action_error=action_error,
        )

        self._collect_log_findings_artifact(
            reports_dir=reporting_inputs.reports_dir,
            artifact_name='log-findings.canonical.json',
            max_findings=2000,
        )

        build_default_reporting_pipeline = _get_default_reporting_pipeline_builder()
        pipeline = build_default_reporting_pipeline()
        generated = self._run_reporting_pipeline(
            pipeline=pipeline,
            reporting_inputs=reporting_inputs,
        )
        self._log_generated_report_artifacts(generated)

        from .report_uploader import ReportUploader  # noqa: PLC0415

        uploader = ReportUploader(self.config)
        uploader.upload_reports(generated)

    def _build_unified_reporting_inputs(
        self,
        *,
        action_error: Optional[Exception],
    ) -> _UnifiedReportingInputs:
        """Collect stable inputs used by the unified reporting pipeline."""
        action_name = self._resolve_reporting_action_name()

        reports_dir = Path(self.config.reports_folder)
        reports_dir.mkdir(parents=True, exist_ok=True)
        metadata = self._build_unified_reporting_metadata(
            action_name,
            action_error=action_error,
        )
        output_formats = self._resolve_report_formats()
        metadata['requested_formats'] = list(output_formats)

        report_name, canonical_json_name = self._build_report_artifact_names(
            action_name, metadata.get('variant', 'default')
        )

        return _UnifiedReportingInputs(
            reports_dir=reports_dir,
            report_name=report_name,
            canonical_json_name=canonical_json_name,
            output_formats=output_formats,
            metadata=metadata,
        )

    @staticmethod
    def _build_report_artifact_names(action_name: str, variant_alias: str) -> Tuple[str, str]:
        """Return (report_name, canonical_json_name) for an action."""
        report_name = f'{action_name}-{variant_alias}-report'
        return report_name, f'{report_name}.canonical.json'

    def _run_reporting_pipeline(
        self,
        *,
        pipeline: Any,
        reporting_inputs: _UnifiedReportingInputs,
    ) -> Dict[str, Any]:
        """Execute reporting pipeline with prepared inputs."""
        return pipeline.run(
            reports_dir=str(reporting_inputs.reports_dir),
            output_dir=str(reporting_inputs.reports_dir),
            report_name=reporting_inputs.report_name,
            output_formats=reporting_inputs.output_formats,
            glob_pattern='**/*',
            metadata=reporting_inputs.metadata,
            reporting_config=getattr(self.config, 'reporting_config', None),
            action_config=self.config,
            emit_canonical_json=True,
            canonical_json_name=reporting_inputs.canonical_json_name,
        )

    @staticmethod
    def _log_generated_report_artifacts(generated: Dict[str, Any]) -> None:
        """Log reporting outputs or a warning when none were generated."""
        if not generated:
            logger.warning('[UNIFIED REPORTING] No report artifacts were generated')
            return

        for fmt, path in generated.items():
            logger.success(f'[UNIFIED REPORTING] Generated {fmt}: {path}')

    def _build_unified_reporting_metadata(
        self,
        action_name: str,
        *,
        action_error: Optional[Exception],
    ) -> Dict[str, Any]:
        metadata = {
            'action': action_name,
            'variant': self.config.variant.get_variant_alias()
            if self.config.variant
            else 'default',
            'repo_root': str(self.config.repo_root),
            'status': 'failed' if action_error is not None or self._errors else 'success',
        }
        metadata.update(self._collect_reporting_dependency_metadata())
        return metadata

    @staticmethod
    def _resolve_repository_info(
        artifactories: Dict[str, Any],
        alias: str,
        explicit_repository: str = '',
        explicit_url: str = '',
    ) -> _RepositoryInfo:
        """Resolve repository information from alias and explicit values."""
        repository = str(explicit_repository or '').strip()
        resolved_url = str(explicit_url or '').strip()

        alias_key = str(alias or '').strip()
        if alias_key:
            maybe_conf = artifactories.get(alias_key, {})
            if isinstance(maybe_conf, dict):
                if not repository:
                    repository = str(maybe_conf.get('repository', '')).strip()
                if not resolved_url:
                    resolved_url = str(maybe_conf.get('url', '')).strip()

        return _RepositoryInfo(
            repository=repository,
            repository_type=_repo_type_from_url(resolved_url),
        )

    @staticmethod
    def _load_tool_reqs_payload(tool_reqs_file: Path) -> Any:
        return json.loads(tool_reqs_file.read_text(encoding='utf-8-sig'))

    @staticmethod
    def _normalize_requirement_items(raw_reqs: Any) -> List[Dict[str, Any]]:
        requirements: List[Dict[str, Any]] = []
        if not isinstance(raw_reqs, list):
            return requirements

        for item in raw_reqs:
            normalized = _normalize_requirement_item(item)
            if normalized:
                requirements.append(normalized)
        return requirements

    def _parse_tool_reqs_file(self) -> List[Dict[str, Any]]:
        """Parse tool_reqs.json and extract requirements."""
        requirements: List[Dict[str, Any]] = []
        tool_reqs_file = self.config.get_build_folder() / 'tool_reqs.json'

        if not tool_reqs_file.exists():
            return requirements

        try:
            raw_reqs = self._load_tool_reqs_payload(tool_reqs_file)
        except Exception as exc:
            logger.debug(f'[UNIFIED REPORTING] Failed to read {tool_reqs_file}: {exc}')
            return requirements

        return self._normalize_requirement_items(raw_reqs)

    def _extract_artifact_downloads_from_tool_reqs(
        self,
        requirements: List[Dict[str, Any]],
        artifact_tool_requires: Dict[str, Any],
        artifactories: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Extract artifact downloads from requirements list."""
        downloads: List[Dict[str, Any]] = []

        for normalized in requirements:
            if normalized['type'].lower() != 'artifact':
                continue

            artifact_conf = artifact_tool_requires.get(normalized['name'], {})
            if not isinstance(artifact_conf, dict):
                artifact_conf = {}

            repo_info = self._resolve_repository_info(
                artifactories=artifactories,
                alias=str(artifact_conf.get('artifactory', '')).strip(),
                explicit_repository=str(artifact_conf.get('repository', '')).strip(),
                explicit_url=str(artifact_conf.get('url', '')).strip(),
            )

            downloads.append(
                self._build_artifact_download_entry(
                    source='tool_requires',
                    repository_info=repo_info,
                    item=normalized,
                )
            )

        return downloads

    def _extract_artifact_downloads_from_build_deps(
        self,
        artifactories: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Extract artifact downloads from BUILD_ARTIFACT_DEPENDENCIES."""
        downloads: List[Dict[str, Any]] = []
        build_conf = self.config.get_action_config()

        if not isinstance(build_conf, dict):
            return downloads

        build_artifact_deps = build_conf.get('BUILD_ARTIFACT_DEPENDENCIES', {}) or {}
        if not isinstance(build_artifact_deps, dict):
            return downloads

        for name, conf in build_artifact_deps.items():
            if not isinstance(conf, dict):
                continue

            properties = {str(k): str(v) for k, v in (conf.get('properties', {}) or {}).items()}

            repo_info = self._resolve_repository_info(
                artifactories=artifactories,
                alias=str(conf.get('artifactory', '')).strip(),
                explicit_repository=str(conf.get('repository', '')).strip(),
                explicit_url=str(conf.get('url', '')).strip(),
            )

            downloads.append(
                self._build_artifact_download_entry(
                    source='build_artifact_dependencies',
                    repository_info=repo_info,
                    item={
                        'name': str(name).strip(),
                        'type': 'artifact',
                        'version': str(
                            conf.get('version') or properties.get('rb_version', '')
                        ).strip(),
                        'properties': properties,
                    },
                )
            )

        return downloads

    @staticmethod
    def _build_artifact_download_entry(
        *,
        source: str,
        repository_info: _RepositoryInfo,
        item: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Build a normalized artifact-download record for reporting."""
        result = dict(item)

        result.update(
            {
                'repository': repository_info.repository,
                'repository_type': repository_info.repository_type,
                'source': source,
            }
        )
        return result

    def _collect_artifactory_downloads(
        self,
        requirements: List[Dict[str, Any]],
        artifact_tool_requires: Dict[str, Any],
        artifactories: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Collect artifact download metadata from all supported sources."""
        downloads = self._extract_artifact_downloads_from_tool_reqs(
            requirements,
            artifact_tool_requires,
            artifactories,
        )
        downloads.extend(self._extract_artifact_downloads_from_build_deps(artifactories))
        return downloads

    def _get_safe_artifactories(self) -> Dict[str, Any]:
        try:
            artifactories = self.config.get_artifactories() or {}
            if isinstance(artifactories, dict):
                return artifactories
        except Exception:
            pass
        return {}

    def _get_safe_artifact_tool_requires(self) -> Dict[str, Any]:
        try:
            variant_tool_requires = self.config.get_variant().get_tool_requires()
            artifact_tool_requires = filter_tool_requires_by_type(
                requires=variant_tool_requires,
                type_='artifact',
                action_name=self.config.get_action_name(),
            )
            if isinstance(artifact_tool_requires, dict):
                return artifact_tool_requires
        except Exception:
            pass
        return {}

    @staticmethod
    def _resolve_xc_ce_utils_version() -> str:
        try:
            get_version = _get_version_getter()
            return str(get_version())
        except Exception as exc:
            logger.debug(f'[UNIFIED REPORTING] Failed to resolve XC-CE Utils version: {exc}')
            return 'unknown'

    def _collect_reporting_dependency_metadata(self) -> Dict[str, Any]:
        """Collect dependency/download metadata for unified reports."""
        artifactories = self._get_safe_artifactories()
        artifact_tool_requires = self._get_safe_artifact_tool_requires()
        requirements = self._parse_tool_reqs_file()

        artifactory_downloads = self._collect_artifactory_downloads(
            requirements,
            artifact_tool_requires,
            artifactories,
        )

        return {
            'xc_ce_utils_version': self._resolve_xc_ce_utils_version(),
            'requirements': requirements,
            'artifactory_downloads': artifactory_downloads,
        }

    def _resolve_reporting_action_name(self) -> str:
        """Resolve and sanitize action name used in report filenames."""
        raw_action_name = getattr(self.config, 'original_action', None)
        if not raw_action_name:
            raw_action_name = self.config.get_action_name()
        sanitized = re.sub(r'[^A-Za-z0-9._-]+', '-', str(raw_action_name))
        sanitized = sanitized.strip('-')
        return sanitized or 'action'

    def _resolve_report_formats(self) -> List[str]:
        """Resolve output report formats from REPORTING config with html default."""
        reporting_cfg = getattr(self.config, 'reporting_config', None)
        if isinstance(reporting_cfg, dict) and 'formats' in reporting_cfg:
            formats = self._normalize_report_formats(
                reporting_cfg.get('formats'),
                warning_message='[UNIFIED REPORTING] Invalid REPORTING.formats; defaulting to ["html"]',
            )
        else:
            # Backward-compatible fallback for older configs.
            configured = getattr(self.config, 'report_formats', None)
            formats = self._normalize_report_formats(
                configured,
                warning_message='[UNIFIED REPORTING] Invalid report_formats configuration; defaulting to ["html"]',
            )

        # if not is_running_in_ci():
        #     return formats
        if 'github_summary' not in formats:
            formats.append('github_summary')
        return formats

    @staticmethod
    def _normalize_report_formats(
        configured: Any,
        *,
        warning_message: str,
    ) -> List[str]:
        if configured is None:
            return ['html']

        if isinstance(configured, str):
            values = [configured]
        elif isinstance(configured, list):
            values = configured
        else:
            logger.warning(warning_message)
            return ['html']

        normalized: List[str] = []
        for fmt in values:
            item = str(fmt).strip().lower()
            if item and item not in normalized:
                normalized.append(item)

        return normalized or ['html']

    @staticmethod
    def _build_log_classifiers() -> Dict[str, re.Pattern]:
        return {
            'ignore_zero_failures': re.compile(
                r'\b0\s+(tests?\s+)?(failed|failures?)\b',
                re.IGNORECASE,
            ),
            'ignore_zero_errors': re.compile(r'\b0\s+errors?\b', re.IGNORECASE),
            'py_traceback': re.compile(
                r'traceback \(most recent call last\)',
                re.IGNORECASE,
            ),
            'py_exception': re.compile(
                r'\b(?:python\s+exception|[A-Za-z_][A-Za-z0-9_]*(?:Error|Exception))\b\s*:',
                re.IGNORECASE,
            ),
            'compiler_error': re.compile(
                r'(^[^:\n]+:\d+(?::\d+)?:\s*(?:fatal\s+)?error:)|\bcompiler\s+error\b|\bninja:\s+build\s+stopped:\s+subcommand\s+failed\b',
                re.IGNORECASE,
            ),
            'compiler_warning': re.compile(
                r'(^[^:\n]+:\d+(?::\d+)?:\s*warning:)|\bcompiler\s+warning\b',
                re.IGNORECASE,
            ),
            'linker_error': re.compile(
                r'\bundefined reference\b|\bcollect2:\s*error:\b|\bld(?:\.exe)?:\s*(?:fatal\s+)?error\b|\bLNK\d{4}\b',
                re.IGNORECASE,
            ),
            'linker_warning': re.compile(
                r'\bld(?:\.exe)?:\s*warning\b|\bLNK4\d{3}\b',
                re.IGNORECASE,
            ),
            'cmake_error': re.compile(r'\bcmake\s+error\b', re.IGNORECASE),
            'cmake_warning': re.compile(r'\bcmake\s+warning\b', re.IGNORECASE),
            'test_failure': re.compile(
                r'\bassert(?:ion)?\s+failed\b|\btest\b.*\bfailed\b|\bfailures?:\s*[1-9]\d*\b',
                re.IGNORECASE,
            ),
            'toolchain_error': re.compile(
                r'\b(toolchain|compiler|linker)\b.*\b(not found|missing|cannot find|failed to locate)\b',
                re.IGNORECASE,
            ),
            'generic_error': re.compile(r'\b(error|fatal)\b', re.IGNORECASE),
            'generic_failure': re.compile(r'\b(failed|failure)\b', re.IGNORECASE),
            'generic_warning': re.compile(
                r'\b(warning|warn|deprecated|deprecate|unable to find|not found)\b', re.IGNORECASE
            ),
            'compiler_command': re.compile(
                r'\b(cctri(?:\.exe)?|gcc|g\+\+|clang(?:\+\+)?|cl\.exe)\b',
                re.IGNORECASE,
            ),
            'linker_command': re.compile(
                r'\b(ld(?:\.exe)?|link\.exe|cctri(?:\.exe)?.*-T\b)\b',
                re.IGNORECASE,
            ),
            'compiler_command_strict': re.compile(
                r'\b(cctri(?:\.exe)?|gcc|g\+\+|clang(?:\+\+)?|cl\.exe)\b.*(\s-c\b|;-c;|/c\b)',
                re.IGNORECASE,
            ),
            'linker_command_strict': re.compile(
                r'\b(link\.exe|ld(?:\.exe)?|collect2)\b|\b(cctri(?:\.exe)?|gcc|g\+\+|clang(?:\+\+)?)\b.*(\s-T\b|;-T;|\.lcf\b|-Wl,)',
                re.IGNORECASE,
            ),
            'cmake_prefix': re.compile(r'^\s*cmake\b', re.IGNORECASE),
            'bazel_prefix': re.compile(r'^\s*bazel\b', re.IGNORECASE),
            'compiler_diag_line': re.compile(
                r'^\s*cmake\s+".*\.(c|cc|cpp|cxx|h|hpp|s|asm)",\s*line\s+\d+\s*:\s*(warning|error)\b',
                re.IGNORECASE,
            ),
            'linker_diag_line': re.compile(
                r'^\s*cmake\s+".*\.(lcf|ld|map)",\s*line\s+\d+\s*:\s*(warning|error)\b|\bundefined reference\b|\bmultiple definition\b',
                re.IGNORECASE,
            ),
        }

    @staticmethod
    def _load_execution_step_payload(
        execution_file: Path,
    ) -> Optional[Dict[str, Any]]:
        try:
            payload = json.loads(execution_file.read_text(encoding='utf-8'))
        except Exception:
            return None
        return payload if isinstance(payload, dict) else None

    @staticmethod
    def _extract_step_finding_context(
        payload: Dict[str, Any],
    ) -> _StepFindingContext:
        try:
            execution_index = int(payload.get('execution_index', DEFAULT_EXECUTION_INDEX))
        except Exception:
            execution_index = DEFAULT_EXECUTION_INDEX

        step = payload.get('step', {}) or {}
        artifacts = payload.get('artifacts', {}) or {}
        jsonl_path_raw = artifacts.get('step_jsonl') or artifacts.get('step_log_jsonl')
        text_log_raw = artifacts.get('step_log') or ''

        if not jsonl_path_raw and text_log_raw:
            jsonl_path_raw = str(Path(str(text_log_raw)).with_suffix('.jsonl'))

        jsonl_path = Path(str(jsonl_path_raw)) if jsonl_path_raw else None
        return _StepFindingContext(
            step_name=str(step.get('name', 'unknown')),
            step_type=str(step.get('step_type', 'step')),
            script_hint=str(step.get('script_ref', '') or '').strip(),
            parameters=payload.get('params', payload.get('parameters', {})) or {},
            jsonl_path=jsonl_path,
            execution_index=execution_index,
        )

    def _build_finding_from_log_entry(
        self,
        entry: Dict[str, Any],
        *,
        line_no: int,
        step_context: _StepFindingContext,
        execution_file: Path,
        classifiers: Dict[str, re.Pattern],
    ) -> Optional[Dict[str, Any]]:
        message = self._normalize_log_message(str(entry.get('message', '') or '').strip())
        if not message:
            return None

        issue_type, _classification = self._classify_log_entry(
            message=message,
            context=_LogEntryContext(
                level=str(entry.get('level', '') or ''),
                module=str(entry.get('module', '') or ''),
                function=str(entry.get('function', '') or ''),
                step_name=step_context.step_name,
                step_type=step_context.step_type,
                classifiers=classifiers,
            ),
        )
        if not issue_type:
            return None

        classification = self._resolve_log_classification(
            step_type=step_context.step_type,
            step_parameters=step_context.parameters,
            script_hint=step_context.script_hint,
        )
        return {
            'step': step_context.step_name,
            'type': issue_type,
            'classification': classification,
            'message': message[:1200],
            'file': str(step_context.jsonl_path),
            'line': line_no,
            'source_file': str(execution_file),
            'properties': {
                'step_name': step_context.step_name,
                'step_type': step_context.step_type,
                'log_level': str(entry.get('level', '') or ''),
                'module': str(entry.get('module', '') or ''),
                'function': str(entry.get('function', '') or ''),
            },
        }

    def _collect_step_jsonl_findings(
        self,
        *,
        step_context: _StepFindingContext,
        execution_file: Path,
        classifiers: Dict[str, re.Pattern],
    ) -> tuple[List[Dict[str, Any]], int]:
        findings: List[Dict[str, Any]] = []
        invalid_json_lines = 0
        jsonl_path = step_context.jsonl_path
        if jsonl_path is None:
            return findings, invalid_json_lines

        with jsonl_path.open('r', encoding='utf-8', errors='replace') as handle:
            for line_no, raw_line in enumerate(handle, start=1):
                entry_line = raw_line.strip()
                if not entry_line:
                    continue

                try:
                    entry = json.loads(entry_line)
                except Exception:
                    invalid_json_lines += 1
                    continue

                if not isinstance(entry, dict):
                    continue

                finding = self._build_finding_from_log_entry(
                    entry,
                    line_no=line_no,
                    step_context=step_context,
                    execution_file=execution_file,
                    classifiers=classifiers,
                )
                if finding is not None:
                    findings.append(finding)

        return findings, invalid_json_lines

    def _parse_execution_step_artifact(
        self,
        execution_file: Path,
        classifiers: Dict[str, re.Pattern],
    ) -> _ParsedStepArtifactResult:
        payload = self._load_execution_step_payload(execution_file)
        if payload is None:
            return self._build_step_artifact_result(
                execution_index=DEFAULT_EXECUTION_INDEX,
            )

        step_context = self._extract_step_finding_context(payload)
        if not self._has_step_jsonl(step_context):
            return self._build_step_artifact_result(
                execution_index=step_context.execution_index,
                missing_logs=1,
            )

        return self._parse_step_jsonl_from_context(
            step_context=step_context,
            execution_file=execution_file,
            classifiers=classifiers,
        )

    @staticmethod
    def _build_step_artifact_result(
        *,
        execution_index: int,
        findings: Optional[List[Dict[str, Any]]] = None,
        scanned_logs: int = 0,
        missing_logs: int = 0,
        invalid_json_lines: int = 0,
    ) -> _ParsedStepArtifactResult:
        """Build a standardized parsed-step-artifact result."""
        return _ParsedStepArtifactResult(
            execution_index=execution_index,
            findings=findings or [],
            scanned_logs=scanned_logs,
            missing_logs=missing_logs,
            invalid_json_lines=invalid_json_lines,
        )

    @staticmethod
    def _has_step_jsonl(step_context: _StepFindingContext) -> bool:
        """Return True when a step context references an existing JSONL log."""
        jsonl_path = step_context.jsonl_path
        return jsonl_path is not None and jsonl_path.exists()

    def _parse_step_jsonl_from_context(
        self,
        *,
        step_context: _StepFindingContext,
        execution_file: Path,
        classifiers: Dict[str, re.Pattern],
    ) -> _ParsedStepArtifactResult:
        """Parse one execution-step JSONL log and return normalized result."""
        try:
            findings, invalid_json_lines = self._collect_step_jsonl_findings(
                step_context=step_context,
                execution_file=execution_file,
                classifiers=classifiers,
            )
        except Exception:
            return self._build_step_artifact_result(
                execution_index=step_context.execution_index,
                scanned_logs=1,
            )

        return self._build_step_artifact_result(
            execution_index=step_context.execution_index,
            findings=findings,
            scanned_logs=1,
            invalid_json_lines=invalid_json_lines,
        )

    def _parse_step_artifacts_parallel(
        self,
        execution_step_files: List[Path],
        classifiers: Dict[str, re.Pattern],
    ) -> List[_ParsedStepArtifactResult]:
        worker_count = max(1, min(8, len(execution_step_files) or 1))
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = [
                executor.submit(
                    self._parse_execution_step_artifact,
                    execution_file,
                    classifiers,
                )
                for execution_file in execution_step_files
            ]
            return [future.result() for future in as_completed(futures)]

    @staticmethod
    def _aggregate_step_artifact_results(
        parsed_results: List[_ParsedStepArtifactResult],
    ) -> tuple[List[Dict[str, Any]], int, int, int]:
        findings: List[Dict[str, Any]] = []
        scanned_logs = 0
        missing_logs = 0
        invalid_json_lines = 0

        for result in sorted(parsed_results, key=lambda item: item.execution_index):
            findings.extend(result.findings)
            scanned_logs += result.scanned_logs
            missing_logs += result.missing_logs
            invalid_json_lines += result.invalid_json_lines

        return findings, scanned_logs, missing_logs, invalid_json_lines

    @staticmethod
    def _write_log_findings_artifact(
        reports_dir: Path,
        artifact_name: str,
        findings: List[Dict[str, Any]],
        stats: _LogFindingsStats,
    ) -> Path:
        artifact_dir = reports_dir / '_unified'
        artifact_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = artifact_dir / artifact_name
        artifact_payload = {
            'report_kind': 'log-findings',
            'schema_version': '1.0.0',
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'source': 'execution-step-jsonl',
            'scanned_logs': stats.scanned_logs,
            'missing_logs': stats.missing_logs,
            'invalid_json_lines': stats.invalid_json_lines,
            'total_findings': len(findings),
            'findings': findings,
        }
        artifact_path.write_text(
            json.dumps(artifact_payload, indent=2, ensure_ascii=False),
            encoding='utf-8',
        )
        return artifact_path

    @staticmethod
    def _discover_execution_step_files(reports_dir: Path) -> List[Path]:
        """Discover execution-step artifact descriptors in reports directory."""
        return sorted(reports_dir.glob('**/execution-step.json'))

    def _parse_log_findings(
        self,
        *,
        reports_dir: Path,
        max_findings: int,
    ) -> Tuple[List[Dict[str, Any]], _LogFindingsStats]:
        """Parse, aggregate and prioritize findings from step JSONL artifacts."""
        classifiers = self._build_log_classifiers()
        execution_step_files = self._discover_execution_step_files(reports_dir)
        parsed_results = self._parse_step_artifacts_parallel(
            execution_step_files,
            classifiers,
        )
        findings, scanned_logs, missing_logs, invalid_json_lines = (
            self._aggregate_step_artifact_results(parsed_results)
        )
        findings = self._prioritize_findings(
            findings=findings,
            max_findings=max(1, int(max_findings)),
        )
        return findings, _LogFindingsStats(
            scanned_logs=scanned_logs,
            missing_logs=missing_logs,
            invalid_json_lines=invalid_json_lines,
        )

    def _collect_log_findings_artifact(
        self,
        reports_dir: Path,
        artifact_name: str,
        max_findings: int,
    ) -> Path:
        """Scan per-step JSONL logs and write canonical log-findings artifact."""
        findings, stats = self._parse_log_findings(
            reports_dir=reports_dir,
            max_findings=max_findings,
        )

        artifact_path = self._write_log_findings_artifact(
            reports_dir,
            artifact_name,
            findings,
            stats,
        )
        logger.info(
            f'[UNIFIED REPORTING] Log findings artifact written: {artifact_path} '
            f'(findings={len(findings)}, scanned_logs={stats.scanned_logs}, invalid_json_lines={stats.invalid_json_lines})'
        )
        return artifact_path

    @staticmethod
    def _resolve_log_classification(
        step_type: str,
        step_parameters: Dict[str, Any],
        script_hint: str = '',
    ) -> str:
        """Build Log Analyzer classification from step type and parameters."""
        raw_type = str(step_type or '').strip()
        normalized_type = raw_type.lower()

        if normalized_type in {'custom_script', 'shell_run_command'}:
            script_ref = ReportingOrchestrator._resolve_script_reference(
                step_parameters=step_parameters,
                script_hint=script_hint,
            )

            if script_ref:
                return f'custom_script:{Path(script_ref).name}'
            return 'custom_script'

        return raw_type or 'step'

    @staticmethod
    def _resolve_script_reference(
        step_parameters: Dict[str, Any],
        script_hint: str,
    ) -> str:
        """Resolve script reference for custom-script style steps."""
        script_ref = str(script_hint or '').strip()
        if script_ref or not isinstance(step_parameters, dict):
            return script_ref

        script_ref = ReportingOrchestrator._first_non_empty_param(
            step_parameters,
            keys=('path', 'script', 'script_path'),
        )
        if script_ref:
            return script_ref

        command_value = ReportingOrchestrator._first_non_empty_param(
            step_parameters,
            keys=('command', 'cmd'),
        )
        if not command_value:
            return ''
        return command_value.split()[0].strip('"\'')

    @staticmethod
    def _first_non_empty_param(
        step_parameters: Dict[str, Any],
        *,
        keys: Tuple[str, ...],
    ) -> str:
        """Return the first non-empty parameter value for provided keys."""
        for key in keys:
            value = str(step_parameters.get(key, '') or '').strip()
            if value:
                return value
        return ''

    @staticmethod
    def _prioritize_findings(
        findings: List[Dict[str, Any]],
        max_findings: int,
    ) -> List[Dict[str, Any]]:
        """Keep the most important issue types when trimming oversized result sets."""
        if len(findings) <= max_findings:
            return findings

        type_rank = {
            'exception': 0,
            'error': 1,
            'warning': 2,
        }

        indexed = list(enumerate(findings))
        indexed.sort(
            key=lambda item: (
                type_rank.get(
                    str(item[1].get('type', 'warning')).strip().lower(),
                    3,
                ),
                item[0],
            )
        )

        selected = indexed[:max_findings]
        selected.sort(key=lambda item: item[0])
        return [item[1] for item in selected]

    @staticmethod
    def _normalize_log_message(message: str) -> str:
        """Strip nested logger wrappers from raw command-output lines."""
        return _normalize_log_message_static(message)

    def _classify_log_entry(
        self,
        message: str,
        context: _LogEntryContext,
    ):
        """Classify a structured JSON log entry into issue type + classification."""
        text = str(message or '').strip()
        classifiers = context.classifiers
        lowered = text.lower()
        classification_hint, is_qac_step = self._resolve_entry_classification_hint(
            text=text,
            step_type=context.step_type,
            step_name=context.step_name,
            classifiers=classifiers,
        )

        if self._should_ignore_log_entry(text, lowered, classifiers):
            return None, None

        module_name, function_name = self._normalized_origin_names(context)

        python_result = self._classify_python_exception(
            text=text,
            lowered=lowered,
            module_name=module_name,
            function_name=function_name,
            classifiers=classifiers,
        )
        if python_result is not None:
            return python_result

        pattern_result = self._classify_structured_patterns(
            text=text,
            classifiers=classifiers,
            classification_hint=classification_hint,
            is_qac_step=is_qac_step,
        )
        if pattern_result is not None:
            return pattern_result

        return self._classify_fallback_patterns(
            text=text,
            lowered=lowered,
            level=str(context.level or '').strip().upper(),
            classifiers=classifiers,
            classification_hint=classification_hint,
        )

    def _resolve_entry_classification_hint(
        self,
        *,
        text: str,
        step_type: str,
        step_name: str,
        classifiers: Dict[str, re.Pattern],
    ) -> Tuple[str, bool]:
        """Resolve refined classification hint and QAC-family marker."""
        default_classification = self._classify_step_family(
            step_type,
            step_name,
        )
        classification_hint = self._classify_message_family(
            text=text,
            default_classification=default_classification,
            classifiers=classifiers,
        )
        return classification_hint, default_classification == 'QAC'

    @staticmethod
    def _normalized_origin_names(context: _LogEntryContext) -> Tuple[str, str]:
        """Return normalized lower-case module/function names from log context."""
        return (
            str(context.module or '').strip().lower(),
            str(context.function or '').strip().lower(),
        )

    @staticmethod
    def _should_ignore_log_entry(
        text: str,
        lowered: str,
        classifiers: Dict[str, re.Pattern],
    ) -> bool:
        diag_config_only = ReportingOrchestrator._is_diag_config_only(lowered)
        zero_failure_or_error = ReportingOrchestrator._has_zero_failure_marker(
            text=text,
            lowered=lowered,
            classifiers=classifiers,
        )
        return any(
            (
                zero_failure_or_error,
                'output-on-failure' in lowered,
                diag_config_only,
            )
        )

    @staticmethod
    def _is_diag_config_only(lowered: str) -> bool:
        """Return True when line only carries diagnostic config switches."""
        return ('--diag_error=' in lowered or '--diag_warning=' in lowered) and (
            'warning #' not in lowered and 'error:' not in lowered and 'cmake error' not in lowered
        )

    @staticmethod
    def _has_zero_failure_marker(
        *,
        text: str,
        lowered: str,
        classifiers: Dict[str, re.Pattern],
    ) -> bool:
        """Return True for known successful-zero failures/errors markers."""
        return any(
            (
                '0 tests failed' in lowered,
                '0 test failed' in lowered,
                classifiers['ignore_zero_failures'].search(text),
                classifiers['ignore_zero_errors'].search(text),
            )
        )

    @staticmethod
    def _classify_python_exception(
        text: str,
        lowered: str,
        module_name: str,
        function_name: str,
        classifiers: Dict[str, re.Pattern],
    ) -> Optional[tuple[str, str]]:
        if classifiers['py_traceback'].search(text):
            return 'exception', 'XC-CE Utils'

        if not classifiers['py_exception'].search(text):
            return None

        py_context = ReportingOrchestrator._is_python_exception_context(
            lowered=lowered,
            module_name=module_name,
            function_name=function_name,
        )
        return ('exception', 'XC-CE Utils') if py_context else None

    @staticmethod
    def _is_python_exception_context(
        *,
        lowered: str,
        module_name: str,
        function_name: str,
    ) -> bool:
        """Return True when log context indicates Python runtime exception."""
        return any(
            (
                'python' in lowered,
                'traceback' in lowered,
                module_name.startswith('xc_ce_utils'),
                function_name in {'run', 'main', 'execute'},
            )
        )

    @staticmethod
    def _classify_structured_patterns(
        text: str,
        classifiers: Dict[str, re.Pattern],
        classification_hint: str,
        *,
        is_qac_step: bool,
    ) -> Optional[tuple[str, str]]:
        ordered_patterns = ReportingOrchestrator._structured_pattern_rules(
            classification_hint=classification_hint,
            is_qac_step=is_qac_step,
        )
        for pattern_key, result in ordered_patterns:
            if classifiers[pattern_key].search(text):
                return result
        return None

    @staticmethod
    def _structured_pattern_rules(
        *,
        classification_hint: str,
        is_qac_step: bool,
    ) -> Tuple[Tuple[str, Tuple[str, str]], ...]:
        """Return ordered rule table for structured log classification."""
        return (
            (
                'toolchain_error',
                ('error', 'QAC' if is_qac_step else 'XC-CE Utils'),
            ),
            ('linker_error', ('error', 'Linker')),
            ('compiler_error', ('error', 'Compiler')),
            ('cmake_error', ('error', 'CMake')),
            ('test_failure', ('error', classification_hint)),
            ('linker_warning', ('warning', 'Linker')),
            ('compiler_warning', ('warning', 'Compiler')),
            ('cmake_warning', ('warning', 'CMake')),
        )

    @staticmethod
    def _classify_generic_with_tool_hint(
        text: str,
        severity: str,
        classifiers: Dict[str, re.Pattern],
        fallback: str,
        order: tuple[str, str],
    ) -> tuple[str, str]:
        classifier_name = ReportingOrchestrator._first_matching_classifier(
            text=text,
            classifiers=classifiers,
            order=order,
        )
        if classifier_name is not None:
            return severity, ReportingOrchestrator._tool_family_from_classifier(classifier_name)
        return severity, fallback

    @staticmethod
    def _first_matching_classifier(
        *,
        text: str,
        classifiers: Dict[str, re.Pattern],
        order: tuple[str, str],
    ) -> Optional[str]:
        """Return first matching classifier key from ordered candidates."""
        for classifier_name in order:
            if classifiers[classifier_name].search(text):
                return classifier_name
        return None

    @staticmethod
    def _tool_family_from_classifier(classifier_name: str) -> str:
        """Map strict command classifier names to tool family labels."""
        if classifier_name == 'compiler_command_strict':
            return 'Compiler'
        return 'Linker'

    def _classify_fallback_patterns(
        self,
        text: str,
        lowered: str,
        level: str,
        classifiers: Dict[str, re.Pattern],
        classification_hint: str,
    ) -> tuple[Optional[str], Optional[str]]:
        level_result = self._classify_level_based_fallback(
            lowered=lowered,
            level=level,
            classification_hint=classification_hint,
        )
        if level_result is not None:
            return level_result

        generic_rules = self._generic_fallback_rules()
        for pattern_name, severity, order in generic_rules:
            if classifiers[pattern_name].search(text):
                return self._classify_generic_with_tool_hint(
                    text=text,
                    severity=severity,
                    classifiers=classifiers,
                    fallback=classification_hint,
                    order=order,
                )

        return None, None

    @staticmethod
    def _classify_level_based_fallback(
        *,
        lowered: str,
        level: str,
        classification_hint: str,
    ) -> Optional[tuple[str, str]]:
        """Classify by log level / exception marker before generic pattern checks."""
        if level in {'ERROR', 'CRITICAL'}:
            return 'error', classification_hint
        if level == 'WARNING':
            return 'warning', classification_hint
        if 'exception' in lowered:
            return 'exception', classification_hint
        return None

    @staticmethod
    def _generic_fallback_rules() -> Tuple[Tuple[str, str, Tuple[str, str]], ...]:
        """Return ordered rule table for generic fallback classification."""
        return (
            (
                'generic_error',
                'error',
                ('compiler_command_strict', 'linker_command_strict'),
            ),
            (
                'generic_failure',
                'error',
                ('linker_command_strict', 'compiler_command_strict'),
            ),
            (
                'generic_warning',
                'warning',
                ('compiler_command_strict', 'linker_command_strict'),
            ),
        )

    @staticmethod
    def _classify_step_family(step_type: str, step_name: str) -> str:
        """Map step identity to a coarse log classification family."""
        raw_type = str(step_type or '').strip().lower()
        raw_name = str(step_name or '').strip().lower()
        exact_map = ReportingOrchestrator._step_family_exact_map()
        if raw_type in exact_map:
            return exact_map[raw_type]

        if raw_name in {'definitions', 'build'}:
            return 'CMake' if raw_name == 'definitions' else 'Compiler'
        if raw_name in {'qac', 'sca', 'sfa'}:
            return 'QAC'

        text = f'{raw_type} {raw_name}'
        fuzzy_rules = ReportingOrchestrator._step_family_fuzzy_rules(text)
        for matches, family in fuzzy_rules:
            if matches:
                return family
        return 'XC-CE Utils'

    @staticmethod
    def _step_family_exact_map() -> Dict[str, str]:
        """Return exact step-type to family mappings."""
        return {
            'project_cmake_file_generation': 'CMake',
            'cmake_set-up': 'CMake',
            'cmake_setup': 'CMake',
            'cmake_build': 'Compiler',
            'qac': 'QAC',
            'sca': 'QAC',
            'sfa': 'QAC',
            'bazel_build': 'Bazel',
            'bazel_test': 'Bazel',
            'bazel_run': 'Bazel',
            'shell_run_command': 'Custom Script',
            'custom_script': 'Custom Script',
        }

    @staticmethod
    def _step_family_fuzzy_rules(text: str) -> Tuple[Tuple[bool, str], ...]:
        """Return ordered fuzzy matching rules for step family resolution."""
        return (
            (bool(re.search(r'\b(qac|sca|sfa)\b', text)), 'QAC'),
            ('bazel' in text, 'Bazel'),
            ('cmake' in text, 'CMake'),
            ('link' in text, 'Linker'),
            ('compiler' in text or 'compile' in text, 'Compiler'),
            (
                'script' in text or 'shell' in text or 'cmd' in text,
                'Custom Script',
            ),
        )

    @staticmethod
    def _classify_message_family(
        text: str,
        default_classification: str,
        classifiers: Dict[str, re.Pattern],
    ) -> str:
        """Refine classification using message content (commands/prefixes)."""
        if classifiers['bazel_prefix'].search(text):
            return 'Bazel'

        if classifiers['cmake_prefix'].search(text):
            return ReportingOrchestrator._classify_cmake_message(
                text=text,
                classifiers=classifiers,
            )

        command_family = ReportingOrchestrator._classify_command_family(
            text=text,
            classifiers=classifiers,
        )
        if command_family is not None:
            return command_family

        return default_classification

    @staticmethod
    def _classify_cmake_message(
        *,
        text: str,
        classifiers: Dict[str, re.Pattern],
    ) -> str:
        """Classify cmake-prefixed messages into CMake/Compiler/Linker."""
        if ReportingOrchestrator._has_linker_signal(
            text=text,
            classifiers=classifiers,
        ):
            return 'Linker'

        if ReportingOrchestrator._has_compiler_signal(
            text=text,
            classifiers=classifiers,
        ):
            return 'Compiler'

        return 'CMake'

    @staticmethod
    def _has_linker_signal(
        *,
        text: str,
        classifiers: Dict[str, re.Pattern],
    ) -> bool:
        """Return True when message carries linker command/diagnostic hints."""
        return bool(
            classifiers['linker_command_strict'].search(text)
            or classifiers['linker_diag_line'].search(text)
        )

    @staticmethod
    def _has_compiler_signal(
        *,
        text: str,
        classifiers: Dict[str, re.Pattern],
    ) -> bool:
        """Return True when message carries compiler command/diagnostic hints."""
        return any(
            (
                classifiers['compiler_command_strict'].search(text),
                classifiers['compiler_diag_line'].search(text),
                ReportingOrchestrator._contains_compiler_diag_hint(text),
            )
        )

    @staticmethod
    def _classify_command_family(
        *,
        text: str,
        classifiers: Dict[str, re.Pattern],
    ) -> Optional[str]:
        """Classify non-cmake messages by strict command hints."""
        classifier_name = ReportingOrchestrator._first_matching_classifier(
            text=text,
            classifiers=classifiers,
            order=('linker_command_strict', 'compiler_command_strict'),
        )
        if classifier_name is None:
            return None
        return ReportingOrchestrator._tool_family_from_classifier(classifier_name)

    @staticmethod
    def _contains_compiler_diag_hint(text: str) -> bool:
        """Return True if message contains compiler-style diagnostic markers."""
        lowered = text.lower()
        return 'warning #' in lowered or 'error #' in lowered
