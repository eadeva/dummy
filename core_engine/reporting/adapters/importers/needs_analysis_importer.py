"""Importer for DocAsCode needs analysis artifacts."""

import json
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from xc_ce_utils.core_engine.reporting.domain.models import CanonicalReport


class NeedsAnalysisImporter:
    """Import needs analysis summaries for docascode runs."""

    name = 'needs-analysis'
    _REQ_STATUS_ORDER = {
        'accepted': 0,
        'under review': 1,
        'in clarification': 2,
        'draft': 3,
        'rejected': 4,
        'obsolete': 5,
        '(empty)': 98,
        'none': 98,
        'unknown': 99,
    }

    def supports(self, file_path: Path) -> bool:
        if file_path.name.lower() != 'execution-step.json':
            return False
        try:
            with file_path.open('r', encoding='utf-8') as handle:
                data = json.load(handle)
        except Exception:
            return False

        if data.get('report_kind') != 'execution-step':
            return False

        step = data.get('step', {}) or {}
        step_type = str(step.get('step_type', '')).strip().lower()
        if step_type != 'docascode':
            return False

        params = data.get('params', data.get('parameters', {})) or {}
        builder = str(params.get('builder', '')).strip().lower()
        return builder in {'', 'needs'}

    def import_file(self, file_path: Path, report: CanonicalReport) -> None:
        with file_path.open('r', encoding='utf-8') as handle:
            step_data = json.load(handle)

        needs_dir = self._resolve_needs_dir(step_data, report)
        violations_file = self._resolve_violations_file(step_data, needs_dir)
        if needs_dir is None and violations_file is None:
            return

        payload: Dict[str, object] = {
            'available': True,
            'needs_dir': str(needs_dir) if needs_dir is not None else '',
        }

        needs_file = needs_dir / 'needs.json' if needs_dir is not None else None
        if needs_file is not None and needs_file.exists():
            analysis_payload, needs = self._parse_needs_file(needs_file)
            payload.update(analysis_payload)
            report.needs.extend(needs)

        if violations_file is not None:
            payload.update(self._parse_violations_file(violations_file))

        report.metadata['needs_analysis'] = self._finalize_payload(payload)

    @staticmethod
    def _resolve_violations_file(
        step_data: Dict[str, object], needs_dir: Optional[Path]
    ) -> Optional[Path]:
        """Find schema_violations.json: step log folder (moved there after the build), else needs dir."""
        candidates: List[Path] = []
        artifacts = step_data.get('artifacts', {})
        if isinstance(artifacts, dict):
            step_log = str(artifacts.get('step_log', '') or '').strip()
            if step_log:
                candidates.append(Path(step_log).parent / 'schema_violations.json')
        if needs_dir is not None:
            candidates.append(needs_dir / 'schema_violations.json')
        return next((candidate for candidate in candidates if candidate.is_file()), None)

    def _finalize_payload(self, payload: Dict[str, object]) -> Dict[str, object]:
        normalized: Dict[str, object] = dict(payload)

        requirements_total = self._to_int(normalized.get('requirements_total', 0))
        req_requirements_total = self._to_int(normalized.get('req_requirements_total', 0))
        validated_needs_count = self._to_int(normalized.get('validated_needs_count', 0))
        validated_needs_per_second = self._to_int(normalized.get('validated_needs_per_second', 0))
        violations_total = self._to_int(normalized.get('violations_total', 0))

        req_type_counts = self._normalize_count_rows(normalized.get('req_type_counts', []))
        if not req_type_counts:
            req_type_counts = [
                row
                for row in self._normalize_count_rows(normalized.get('type_counts', []))
                if str(row.get('name', '')).strip().lower().startswith('req-')
            ]

        if req_requirements_total <= 0:
            req_requirements_total = sum(int(row.get('count', 0) or 0) for row in req_type_counts)

        req_status_counts = self._normalize_count_rows(normalized.get('req_status_counts', []))
        req_status_counts = self._sort_status_rows(req_status_counts)
        if not req_status_counts:
            req_status_counts = self._sort_status_rows(
                self._normalize_count_rows(normalized.get('status_counts', []))
            )

        req_status_total = sum(int(row.get('count', 0) or 0) for row in req_status_counts)
        if req_status_total <= 0:
            req_status_total = req_requirements_total

        req_status_by_type = self._normalize_req_status_by_type(
            normalized.get('req_status_by_type', [])
        )
        if not req_status_by_type:
            req_status_by_type = [
                {
                    'type': str(row.get('name', '') or '').strip(),
                    'total': int(row.get('count', 0) or 0),
                    'status_counts': [
                        {
                            'name': '(all)',
                            'count': int(row.get('count', 0) or 0),
                        }
                    ],
                }
                for row in req_type_counts
                if int(row.get('count', 0) or 0) > 0
            ]

        normalized['requirements_total'] = requirements_total
        normalized['req_requirements_total'] = req_requirements_total
        normalized['validated_needs_count'] = validated_needs_count
        normalized['validated_needs_per_second'] = validated_needs_per_second
        normalized['violations_total'] = violations_total
        normalized['req_type_counts'] = req_type_counts
        normalized['req_status_counts'] = req_status_counts
        normalized['req_status_total'] = req_status_total
        normalized['req_status_by_type'] = req_status_by_type
        return normalized

    def _normalize_count_rows(self, rows: object) -> List[Dict[str, object]]:
        normalized: List[Dict[str, object]] = []
        if not isinstance(rows, list):
            return normalized

        for row in rows:
            if not isinstance(row, dict):
                continue
            name = str(row.get('name', '') or '').strip()
            count = self._to_int(row.get('count', 0))
            if not name or count <= 0:
                continue
            normalized.append({'name': name, 'count': count})
        return normalized

    def _sort_status_rows(self, rows: List[Dict[str, object]]) -> List[Dict[str, object]]:
        return sorted(
            rows,
            key=lambda item: (
                self._REQ_STATUS_ORDER.get(
                    str(item.get('name', '')).strip().lower(),
                    90,
                ),
                str(item.get('name', '')).strip().lower(),
            ),
        )

    def _normalize_req_status_by_type(self, rows: object) -> List[Dict[str, object]]:
        normalized: List[Dict[str, object]] = []
        if not isinstance(rows, list):
            return normalized

        for item in rows:
            if not isinstance(item, dict):
                continue
            req_type_name = str(item.get('type', '') or '').strip()
            if not req_type_name:
                continue

            status_counts = self._sort_status_rows(
                self._normalize_count_rows(item.get('status_counts', []))
            )
            total = self._to_int(item.get('total', 0))
            if total <= 0:
                total = sum(int(row.get('count', 0) or 0) for row in status_counts)
            if total <= 0:
                continue

            normalized.append(
                {
                    'type': req_type_name,
                    'total': total,
                    'status_counts': status_counts,
                }
            )

        normalized.sort(
            key=lambda item: (
                -int(item.get('total', 0) or 0),
                str(item.get('type', '')).lower(),
            )
        )
        return normalized

    def _to_int(self, value: object, default: int = 0) -> int:
        try:
            return int(value)
        except Exception:
            return default

    def _resolve_needs_dir(
        self, step_data: Dict[str, object], report: CanonicalReport
    ) -> Optional[Path]:
        candidates: List[Path] = []
        seen: set[str] = set()

        def _push(path: Optional[Path]) -> None:
            if path is None:
                return
            key = str(path)
            if key in seen:
                return
            seen.add(key)
            candidates.append(path)

        params = step_data.get('params', step_data.get('parameters', {}))
        builder = ''
        if isinstance(params, dict):
            builder = str(params.get('builder', '') or '').strip()

        artifacts = step_data.get('artifacts', {})
        if isinstance(artifacts, dict):
            step_build_folder = str(artifacts.get('step_build_folder', '') or '').strip()
            if step_build_folder:
                build_path = Path(step_build_folder)
                action_root = build_path.parent

                # Preferred resolution requested by user:
                # _builds/<variant>/<action>/<builder>
                if builder:
                    _push(action_root / builder)

                _push(build_path / 'needs')
                _push(action_root / 'needs')
                _push(build_path)
                _push(action_root)

                # If builder is not explicit, probe direct action subfolders
                # for needs outputs (for example html, sphinx, needs).
                try:
                    if action_root.exists() and action_root.is_dir():
                        for child in sorted(action_root.iterdir()):
                            if child.is_dir():
                                _push(child)
                except Exception:
                    pass

        action = str(step_data.get('action', '') or report.metadata.get('action', '')).strip()
        variant = str(step_data.get('variant', '') or report.metadata.get('variant', '')).strip()
        repo_root = str(report.metadata.get('repo_root', '') or '').strip()
        if repo_root and action and variant:
            action_root = Path(repo_root) / '_builds' / variant / action
            if builder:
                _push(action_root / builder)
            _push(action_root / 'needs')
            _push(action_root)
            try:
                if action_root.exists() and action_root.is_dir():
                    for child in sorted(action_root.iterdir()):
                        if child.is_dir():
                            _push(child)
            except Exception:
                pass

        for candidate in candidates:
            try:
                if (candidate / 'needs.json').exists() or (
                    candidate / 'schema_violations.json'
                ).exists():
                    return candidate
            except Exception:
                continue

        return None

    def _parse_needs_file(self, needs_file: Path) -> Tuple[Dict[str, object], List['Need']]:
        from xc_ce_utils.core_engine.reporting.domain.models import Need

        analysis_result: Dict[str, object] = {
            'project': '',
            'current_version': '',
            'requirements_total': 0,
            'requirements_total_declared': 0,
            'req_requirements_total': 0,
            'req_type_counts': [],
            'req_status_counts': [],
            'req_status_by_type': [],
            'type_counts': [],
            'status_counts': [],
            'top_documents': [],
        }
        needs_list: List[Need] = []
        try:
            with needs_file.open('r', encoding='utf-8-sig') as handle:
                data = json.load(handle)
        except Exception as exc:
            analysis_result['needs_parse_error'] = str(exc)
            return analysis_result, needs_list
        if not isinstance(data, dict):
            analysis_result['needs_parse_error'] = 'Unexpected needs.json root type'
            return analysis_result, needs_list
        analysis_result['project'] = str(data.get('project', '') or '')
        current_version = str(data.get('current_version', '') or '')
        analysis_result['current_version'] = current_version
        versions = data.get('versions', {})
        version_payload = {}
        if isinstance(versions, dict):
            version_payload = versions.get(current_version, {}) or {}
        if not isinstance(version_payload, dict):
            version_payload = {}
        needs_payload = version_payload.get('needs', {})
        if isinstance(needs_payload, dict):
            needs_items = list(needs_payload.items())
            needs_count = len(needs_payload)
        elif isinstance(needs_payload, list):
            needs_items = [(None, item) for item in needs_payload]
            needs_count = len(needs_payload)
        else:
            needs_items = []
            needs_count = 0
        analysis_result['requirements_total'] = needs_count

        declared = version_payload.get('needs_amount', needs_count)
        try:
            analysis_result['requirements_total_declared'] = int(declared)
        except Exception:
            analysis_result['requirements_total_declared'] = needs_count

        type_counter: Counter = Counter()
        status_counter: Counter = Counter()
        doc_counter: Counter = Counter()
        req_type_counter: Counter = Counter()
        req_status_counter: Counter = Counter()
        req_status_by_type: Dict[str, Counter] = {}
        for need_key, need_data in needs_items:
            if not isinstance(need_data, dict):
                continue

            needs_list.append(
                Need(
                    id=need_data.get('id', ''),
                    type=need_data.get('type', ''),
                    title=need_data.get('title', ''),
                    description=need_data.get('description', ''),
                    status=need_data.get('status', ''),
                    tags=need_data.get('tags', []),
                    links=need_data.get('links_back', []),
                    source_file=need_data.get('docname', ''),
                    source_line=need_data.get('lineno', 0),
                )
            )

            type_value = (
                str(need_data.get('type', need_data.get('need_type', '')) or '').strip()
                or '(empty)'
            )
            status_value = str(need_data.get('status', '') or '').strip() or '(empty)'

            doc_value = str(need_data.get('docname', '') or '').strip() or '(empty)'
            type_counter[type_value] += 1
            status_counter[status_value] += 1
            doc_counter[doc_value] += 1
            if self._is_req_need(
                need_key, need_data, type_value
            ) and not self._is_excluded_req_type(type_value):
                req_type_counter[type_value] += 1
                req_status_counter[status_value] += 1
                if type_value not in req_status_by_type:
                    req_status_by_type[type_value] = Counter()
                req_status_by_type[type_value][status_value] += 1

        analysis_result['type_counts'] = self._counter_to_rows(type_counter)
        analysis_result['status_counts'] = self._counter_to_rows(status_counter)
        analysis_result['top_documents'] = self._counter_to_rows(doc_counter, top=15)
        analysis_result['req_type_counts'] = self._counter_to_rows(req_type_counter)
        analysis_result['req_status_counts'] = self._counter_to_rows(req_status_counter)
        analysis_result['req_requirements_total'] = int(sum(req_type_counter.values()))
        req_status_by_type_rows: List[Dict[str, object]] = []
        for req_type_name, status_counter in req_status_by_type.items():
            req_status_by_type_rows.append(
                {
                    'type': str(req_type_name),
                    'total': int(sum(status_counter.values())),
                    'status_counts': self._counter_to_rows(status_counter),
                }
            )
        req_status_by_type_rows.sort(
            key=lambda item: (
                -int(item.get('total', 0)),
                str(item.get('type', '')).lower(),
            )
        )
        analysis_result['req_status_by_type'] = req_status_by_type_rows
        return analysis_result, needs_list

    def _parse_violations_file(self, violations_file: Path) -> Dict[str, object]:
        result: Dict[str, object] = {
            'validation_summary': '',
            'validated_needs_count': 0,
            'validated_needs_per_second': 0,
            'violations_total': 0,
            'violations': [],
        }

        try:
            with violations_file.open('r', encoding='utf-8-sig') as handle:
                data = json.load(handle)
        except Exception as exc:
            result['violations_parse_error'] = str(exc)
            return result

        if not isinstance(data, dict):
            result['violations_parse_error'] = 'Unexpected schema_violations.json root type'
            return result

        result['validation_summary'] = str(data.get('validation_summary', '') or '')

        try:
            result['validated_needs_count'] = int(data.get('validated_needs_count', 0) or 0)
        except Exception:
            result['validated_needs_count'] = 0

        try:
            result['validated_needs_per_second'] = int(
                data.get('validated_needs_per_second', 0) or 0
            )
        except Exception:
            result['validated_needs_per_second'] = 0

        warnings = data.get('validation_warnings', {})
        violations = self._flatten_validation_warnings(warnings)
        result['violations'] = violations
        result['violations_total'] = sum(item['count'] for item in violations)
        return result

    def _normalize_needs_payload(self, payload: object) -> Tuple[Iterable[Dict[str, object]], int]:
        if isinstance(payload, dict):
            return payload.values(), len(payload)
        if isinstance(payload, list):
            return payload, len(payload)
        return [], 0

    def _counter_to_rows(
        self, counter: Counter, top: Optional[int] = None
    ) -> List[Dict[str, object]]:
        rows = [{'name': str(name), 'count': int(count)} for name, count in counter.items()]
        rows.sort(key=lambda item: (-item['count'], item['name'].lower()))
        if top is not None:
            return rows[:top]
        return rows

    def _flatten_validation_warnings(self, warnings: object) -> List[Dict[str, object]]:
        if not isinstance(warnings, dict):
            return []

        rows: List[Dict[str, object]] = []
        for name, details in warnings.items():
            violation_name = str(name or 'unknown')
            count = 0
            sample = ''

            if isinstance(details, list):
                count = len(details)
                if details:
                    sample = str(details[0])
            elif isinstance(details, dict):
                raw_count = details.get('count')
                if raw_count is not None:
                    try:
                        count = int(raw_count)
                    except Exception:
                        count = 0
                if count == 0 and isinstance(details.get('violations'), list):
                    count = len(details.get('violations', []))

                for key in ['message', 'reason', 'error', 'description']:
                    value = details.get(key)
                    if value is not None and str(value).strip():
                        sample = str(value).strip()
                        break

                if not sample:
                    violations = details.get('violations')
                    if isinstance(violations, list) and violations:
                        sample = str(violations[0])

                if count == 0 and details:
                    count = 1
            else:
                text = str(details).strip()
                if text:
                    count = 1
                    sample = text

            rows.append(
                {
                    'name': violation_name,
                    'count': int(count),
                    'sample': sample,
                }
            )

        rows.sort(key=lambda item: (-item['count'], item['name'].lower()))
        return rows

    def _is_req_need(self, need_key: object, need: Dict[str, object], need_type: str) -> bool:
        def _starts_req(value: object) -> bool:
            return str(value or '').strip().lower().startswith('req-')

        if _starts_req(need_type):
            return True

        for value in [
            need_key,
            need.get('id'),
            need.get('need_id'),
            need.get('name'),
            need.get('title'),
        ]:
            if _starts_req(value):
                return True

        return False

    def _is_excluded_req_type(self, need_type: str) -> bool:
        return str(need_type or '').strip().lower() in {'mm-class'}
