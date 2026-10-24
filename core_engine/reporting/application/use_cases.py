"""Reporting use-case orchestration."""

from __future__ import annotations

import fnmatch
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Dict, Iterable, List, Optional

import yaml

from xc_ce_utils import logger
from xc_ce_utils.core_engine.domain.layered_config import (
    deep_merge_layered_config,
)
from xc_ce_utils.core_engine.reporting.application.ports import (
    ReportDiscoveryPort,
    ReportExporterPort,
    ReportImporterPort,
)
from xc_ce_utils.core_engine.reporting.domain.models import CanonicalReport
from xc_ce_utils.core_engine.steps.quality_steps import DocasCodeStep

if TYPE_CHECKING:
    from xc_ce_utils.core_engine.config.action_configuration import (
        ActionConfiguration,
    )

_BASE_REPORTING_CONFIG_FILE = Path(__file__).resolve().parents[1] / 'base_reporting.yml'

_OUTPUT_SUFFIXES: dict[str, str] = {
    'html': 'html',
    'json': 'json',
    'junit': 'xml',
    'markdown': 'md',
    'github_summary': 'github-summary.md',
}

_DEFAULT_BASE_REPORTING_CONFIG: Dict[str, object] = {
    'formats': ['html'],
    'needs': False,
    'sbom': {
        # Keep copyleft licenses flagged by default in all projects.
        'flagged_licenses': [
            'GPL-2.0',
            'GPL-3.0',
            'AGPL-3.0',
            'LGPL-2.1',
            'LGPL-3.0',
        ]
    },
    'log_analyzer': {
        'white_list': [],
        'reclassify': {
            'exception': [],
            'error': [],
            'warning': [],
            'info': [],
            'low': [],
            'medium': [],
            'high': [],
            'critical': [],
        },
    },
}


def _load_base_reporting_config() -> Dict[str, object]:
    if not _BASE_REPORTING_CONFIG_FILE.exists():
        fallback = deep_merge_layered_config({}, _DEFAULT_BASE_REPORTING_CONFIG)
        if isinstance(fallback, dict):
            return fallback
        return {}

    try:
        with _BASE_REPORTING_CONFIG_FILE.open('r', encoding='utf-8') as handle:
            loaded = yaml.safe_load(handle) or {}
    except (OSError, yaml.YAMLError) as exc:
        logger.warning(
            f'[ReportingPipeline] Failed to load base reporting config from {_BASE_REPORTING_CONFIG_FILE}: {exc}'
        )
        fallback = deep_merge_layered_config({}, _DEFAULT_BASE_REPORTING_CONFIG)
        if isinstance(fallback, dict):
            return fallback
        return {}

    if not isinstance(loaded, dict):
        logger.warning(
            f'[ReportingPipeline] Base reporting config {_BASE_REPORTING_CONFIG_FILE} is not a mapping; using built-in defaults'
        )
        fallback = deep_merge_layered_config({}, _DEFAULT_BASE_REPORTING_CONFIG)
        if isinstance(fallback, dict):
            return fallback
        return {}

    merged = deep_merge_layered_config({}, loaded)
    if isinstance(merged, dict):
        return merged

    fallback = deep_merge_layered_config({}, _DEFAULT_BASE_REPORTING_CONFIG)
    if isinstance(fallback, dict):
        return fallback
    return {}


BASE_REPORTING_CONFIG = _load_base_reporting_config()


class FileSystemDiscovery:
    """Infrastructure adapter for report file discovery."""

    def discover(self, reports_dir: Path, glob_pattern: str) -> Iterable[Path]:
        if not reports_dir.exists():
            return []
        return sorted(reports_dir.glob(glob_pattern))


class ReportingPipeline:
    """Execute import-normalize-merge-export workflow."""

    def __init__(
        self,
        importers: List[ReportImporterPort],
        exporters: List[ReportExporterPort],
        discovery: Optional[ReportDiscoveryPort] = None,
    ):
        self._importers = importers
        self._exporters_by_name = {exporter.format_name: exporter for exporter in exporters}
        self._discovery = discovery or FileSystemDiscovery()

    def run(
        self,
        reports_dir: str,
        output_dir: str,
        report_name: str,
        output_formats: List[str],
        glob_pattern: str = '**/*',
        metadata: Optional[Dict[str, str]] = None,
        reporting_config: Optional[Dict[str, object]] = None,
        action_config: Optional[ActionConfiguration] = None,
        emit_canonical_json: bool = True,
        canonical_json_name: Optional[str] = None,
    ) -> Dict[str, str]:
        """Run the reporting pipeline and return generated artifacts."""
        reports_root = Path(reports_dir)
        output_root = Path(output_dir)
        output_root.mkdir(parents=True, exist_ok=True)
        effective_reporting_config = self._build_effective_reporting_config(reporting_config)
        resolved_formats = self._resolve_output_formats(output_formats, effective_reporting_config)

        report = CanonicalReport(metadata=dict(metadata or {}))
        report.metadata.setdefault('pipeline_generated_at', datetime.now(timezone.utc).isoformat())
        report.metadata.setdefault('reports_dir', str(reports_root))

        discovered = list(self._discovery.discover(reports_root, glob_pattern))
        logger.info(
            f'[ReportingPipeline] Discovered {len(discovered)} candidate file(s) in {reports_root}'
        )

        # --- Conditional needs generation ---
        junit_importer = next((imp for imp in self._importers if imp.name == 'junit-xml'), None)
        has_test_reports = False
        if junit_importer:
            has_test_reports = any(junit_importer.supports(f) for f in discovered)

        has_needs_json = any(f.name == 'needs.json' for f in discovered)

        needs_enabled = effective_reporting_config.get('needs', False) is True
        if needs_enabled and has_test_reports and not has_needs_json and action_config:
            logger.info(
                '[ReportingPipeline] Test reports found but no needs.json. Triggering docascode step to generate needs...'
            )
            try:
                needs_step = DocasCodeStep(
                    name='internal_needs_generation',
                    config={
                        'builder': 'needs',
                        'step_type': 'docascode',
                        'allow_unknown_config_keys': True,
                    },
                    context=action_config,
                )
                needs_step.execute()
                # Re-discover files to include the newly generated needs.json
                discovered = list(self._discovery.discover(reports_root, glob_pattern))
                logger.info(
                    f'[ReportingPipeline] Re-discovered {len(discovered)} files after needs generation.'
                )
            except Exception as e:
                logger.warning(f'[ReportingPipeline] Failed to generate needs.json internally: {e}')

        imported = 0
        skipped = 0
        for file_path in discovered:
            importers = self._find_importers(file_path)
            if not importers:
                skipped += 1
                continue

            imported += 1
            for importer in importers:
                try:
                    importer.import_file(file_path, report)
                except Exception as exc:
                    logger.warning(
                        f'[ReportingPipeline] Failed to import {file_path} with {importer.name}: {exc}'
                    )

        report.metadata['imported_files'] = imported
        report.metadata['skipped_files'] = skipped
        report.metadata['discovered_files'] = len(discovered)

        self._post_process_findings(
            report=report,
            metadata=metadata,
            reporting_config=effective_reporting_config,
        )

        generated: Dict[str, str] = {}

        formats = [fmt.lower() for fmt in resolved_formats]
        if emit_canonical_json and 'json' not in formats:
            formats = ['json'] + formats

        for fmt in formats:
            exporter = self._exporters_by_name.get(fmt)
            if exporter is None:
                logger.warning(f"[ReportingPipeline] No exporter registered for format '{fmt}'")
                continue

            extension = _OUTPUT_SUFFIXES.get(fmt, fmt)

            file_name = f'{report_name}.{extension}'
            if fmt == 'json' and canonical_json_name:
                file_name = canonical_json_name

            out_path = exporter.export(report, output_root / file_name)
            generated[fmt] = str(out_path)

        return generated

    def _find_importers(self, file_path: Path) -> List[ReportImporterPort]:
        """Return all registered importers that support the given file."""

        matches: List[ReportImporterPort] = []
        for importer in self._importers:
            if importer.supports(file_path):
                matches.append(importer)
        return matches

    def _resolve_output_formats(
        self,
        requested_formats: Optional[List[str]],
        reporting_config: Optional[Dict[str, object]],
    ) -> List[str]:
        cleaned_requested = [
            str(fmt).strip() for fmt in (requested_formats or []) if str(fmt or '').strip()
        ]
        if cleaned_requested:
            return cleaned_requested

        if isinstance(reporting_config, dict):
            configured = reporting_config.get('formats')
            if isinstance(configured, list):
                cleaned_configured = [
                    str(fmt).strip() for fmt in configured if str(fmt or '').strip()
                ]
                if cleaned_configured:
                    return cleaned_configured

        return ['html']

    def _build_effective_reporting_config(
        self, reporting_config: Optional[Dict[str, object]]
    ) -> Dict[str, object]:
        base = dict(BASE_REPORTING_CONFIG)
        if not isinstance(reporting_config, dict):
            return deep_merge_layered_config({}, base)

        merged = deep_merge_layered_config(base, reporting_config)
        if not isinstance(merged, dict):
            return deep_merge_layered_config({}, base)
        return merged

    def _post_process_findings(
        self,
        report: CanonicalReport,
        metadata: Optional[Dict[str, str]],
        reporting_config: Optional[Dict[str, object]],
    ) -> None:
        """Normalize findings and apply whitelist policy to log-analysis findings."""

        repo_root = ''
        if isinstance(metadata, dict):
            repo_root = str(metadata.get('repo_root', '') or '')

        for finding in report.findings:
            finding.file = self._to_repo_relative_path(finding.file, repo_root)
            finding.message = self._strip_logger_prefix(finding.message)

        self._apply_sbom_reporting_config(report, reporting_config)

        if not report.log_findings:
            return

        for finding in report.log_findings:
            finding.file = self._to_repo_relative_path(finding.file, repo_root)
            finding.message = self._strip_logger_prefix(finding.message)

        for finding in report.findings:
            if (finding.severity or '').strip().lower() not in {
                'critical',
                'high',
                'medium',
                'low',
                'info',
                'unknown',
            }:
                finding.severity = 'unknown'

        whitelist = self._get_findings_white_list(reporting_config)
        if not whitelist:
            return

        omitted = 0
        retyped = 0
        type_order = ['exception', 'error', 'warning']

        filtered = []
        for finding in report.log_findings:
            if self._matches_any_rule(finding, whitelist.get('omit', [])):
                omitted += 1
                continue

            for issue_type in type_order:
                rules = whitelist.get(issue_type, [])
                if self._matches_any_rule(finding, rules):
                    if (finding.type or '').strip().lower() != issue_type:
                        finding.type = issue_type
                        retyped += 1
                    break

            # Backward compatibility for existing severity-based whitelist entries.
            if self._matches_any_rule(
                finding, whitelist.get('critical', [])
            ) or self._matches_any_rule(finding, whitelist.get('high', [])):
                if (finding.type or '').strip().lower() != 'error':
                    finding.type = 'error'
                    retyped += 1
            elif (
                self._matches_any_rule(finding, whitelist.get('medium', []))
                or self._matches_any_rule(finding, whitelist.get('low', []))
                or self._matches_any_rule(finding, whitelist.get('info', []))
            ):
                if (finding.type or '').strip().lower() != 'warning':
                    finding.type = 'warning'
                    retyped += 1

            filtered.append(finding)

        report.log_findings = filtered
        report.metadata['log_findings_omitted'] = omitted
        report.metadata['log_findings_retyped'] = retyped
        # Keep legacy metadata keys populated for backwards compatibility.
        report.metadata['findings_omitted'] = omitted
        report.metadata['findings_reclassified'] = retyped

    def _get_findings_white_list(
        self, reporting_config: Optional[Dict[str, object]]
    ) -> Dict[str, list]:
        if not isinstance(reporting_config, dict):
            return {}

        # Preferred config shape:
        # log_analyzer:
        #   white_list: [ ... ]
        #   reclassify:
        #     low|medium|high|critical|info|warning|error|exception: [ ... ]
        # Legacy fallback:
        # findings.white_list / findings.whitelist (dict)
        log_analyzer_cfg = reporting_config.get('log_analyzer')
        if isinstance(log_analyzer_cfg, dict):
            normalized: Dict[str, list] = {}

            white_list = log_analyzer_cfg.get('white_list')
            if isinstance(white_list, list):
                normalized['omit'] = white_list
            elif isinstance(white_list, dict):
                normalized['omit'] = [white_list]

            reclassify_cfg = log_analyzer_cfg.get('reclassify')
            if isinstance(reclassify_cfg, dict):
                for key, value in reclassify_cfg.items():
                    name = str(key).strip().lower()
                    if isinstance(value, list):
                        normalized[name] = value
                    elif isinstance(value, dict):
                        normalized[name] = [value]
                    else:
                        normalized[name] = []

            if normalized:
                return normalized

        findings_cfg = reporting_config.get('findings')
        if not isinstance(findings_cfg, dict):
            return {}

        white_list = findings_cfg.get('white_list') or findings_cfg.get('whitelist')
        if not isinstance(white_list, dict):
            return {}

        normalized: Dict[str, list] = {}
        for key, value in white_list.items():
            name = str(key).strip().lower()
            if isinstance(value, list):
                normalized[name] = value
            elif isinstance(value, dict):
                normalized[name] = [value]
            else:
                normalized[name] = []
        return normalized

    def _apply_sbom_reporting_config(
        self,
        report: CanonicalReport,
        reporting_config: Optional[Dict[str, object]],
    ) -> None:
        if not isinstance(reporting_config, dict):
            return

        sbom_cfg = reporting_config.get('sbom')
        if not isinstance(sbom_cfg, dict):
            return

        raw_flagged = sbom_cfg.get('flagged_licenses', [])
        if not isinstance(raw_flagged, list):
            raw_flagged = []

        flagged_patterns = [str(item).strip() for item in raw_flagged if str(item or '').strip()]
        report.metadata['sbom_flagged_licenses'] = flagged_patterns

        cyclonedx = report.metadata.get('cyclonedx', {})
        if not isinstance(cyclonedx, dict):
            return

        components = cyclonedx.get('components', [])
        if not isinstance(components, list):
            components = []

        def _matches(pattern: str, license_name: str) -> bool:
            pattern_text = str(pattern or '').strip()
            candidate = str(license_name or '').strip()
            if not pattern_text or not candidate:
                return False

            try:
                if re.search(pattern_text, candidate, flags=re.IGNORECASE):
                    return True
            except re.error:
                pass

            if fnmatch.fnmatch(candidate.lower(), pattern_text.lower()):
                return True

            plain = pattern_text.lower().replace('*', '').replace('?', '')
            return bool(plain and plain in candidate.lower())

        flagged_found: set[str] = set()
        flagged_component_names: set[str] = set()
        for component in components:
            if not isinstance(component, dict):
                continue
            licenses_value = str(component.get('licenses', '') or '')
            component_flagged_licenses: set[str] = set()
            for license_name in [
                name.strip() for name in licenses_value.split(',') if name.strip()
            ]:
                if any(_matches(pattern, license_name) for pattern in flagged_patterns):
                    flagged_found.add(license_name)
                    component_flagged_licenses.add(license_name)

            component['flagged_licenses'] = sorted(
                component_flagged_licenses,
                key=lambda item: item.lower(),
            )
            component['flagged'] = bool(component_flagged_licenses)
            if component['flagged']:
                name = str(component.get('name', '') or '').strip()
                if name:
                    flagged_component_names.add(name)

        cyclonedx['flagged_licenses_total'] = len(flagged_found)
        cyclonedx['flagged_licenses_found'] = sorted(flagged_found, key=lambda item: item.lower())
        cyclonedx['flagged_components_total'] = sum(
            1
            for component in components
            if isinstance(component, dict) and bool(component.get('flagged'))
        )
        cyclonedx['flagged_components_found'] = sorted(
            flagged_component_names, key=lambda item: item.lower()
        )

    def _matches_any_rule(self, finding, rules: list) -> bool:
        if not rules:
            return False
        for rule in rules:
            if self._matches_rule(finding, rule):
                return True
        return False

    def _matches_rule(self, finding, rule: object) -> bool:
        if isinstance(rule, str):
            pattern = rule
        elif isinstance(rule, dict):
            pattern = rule.get('regex') or rule.get('pattern') or rule.get('contains') or ''
        else:
            return False

        pattern = str(pattern or '').strip()
        if not pattern:
            return False

        haystack = ' '.join(
            [
                str(getattr(finding, 'step', '') or ''),
                str(getattr(finding, 'type', '') or ''),
                str(getattr(finding, 'classification', '') or ''),
                str(getattr(finding, 'tool', '') or ''),
                str(getattr(finding, 'severity', '') or ''),
                str(getattr(finding, 'rule_id', '') or ''),
                str(getattr(finding, 'file', '') or ''),
                str(getattr(finding, 'message', '') or ''),
            ]
        )

        try:
            if re.search(pattern, haystack, flags=re.IGNORECASE):
                return True
        except re.error:
            pass

        lowered_haystack = haystack.lower()
        lowered_pattern = pattern.lower()
        if fnmatch.fnmatch(lowered_haystack, lowered_pattern):
            return True

        plain_pattern = lowered_pattern.replace('*', '').replace('?', '')
        return bool(plain_pattern and plain_pattern in lowered_haystack)

    def _strip_logger_prefix(self, message: str) -> str:
        text = str(message or '').strip()
        if not text:
            return ''

        wrappers = [
            re.compile(
                r'^\s*\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:,\d+)?\s+-\s+[^-]+\s+-\s+[^-]+\s+-\s+',
                re.IGNORECASE,
            ),
            re.compile(
                r'^\s*(TRACE|DEBUG|INFO|NOTE|PROGRESS|SUCCESS|PHASE|WARNING|ERROR|CRITICAL)\s*-\s*\[[^\]]+\]\s*[^-]*-\s*',
                re.IGNORECASE,
            ),
            re.compile(
                r'^\s*(TRACE|DEBUG|INFO|NOTE|PROGRESS|SUCCESS|PHASE|WARNING|ERROR|CRITICAL)\s*-\s*',
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

    def _to_repo_relative_path(self, file_path: str, repo_root: str) -> str:
        raw = str(file_path or '').strip()
        if not raw:
            return ''

        normalized = raw.replace('\\', '/')
        if not repo_root:
            return normalized

        try:
            repo = Path(repo_root).resolve()
            candidate = Path(raw)
            if candidate.is_absolute():
                try:
                    return candidate.resolve().relative_to(repo).as_posix()
                except Exception:
                    pass
        except Exception:
            return normalized

        repo_norm = str(repo_root).replace('\\', '/').rstrip('/')
        if normalized.lower().startswith(repo_norm.lower() + '/'):
            return normalized[len(repo_norm) + 1 :]

        if Path(raw).is_absolute():
            return Path(raw).name

        return normalized.lstrip('./')
