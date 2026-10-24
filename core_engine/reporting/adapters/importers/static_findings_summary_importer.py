"""Importer that computes static findings summary metadata for HTML rendering."""

import re
from collections import Counter
from pathlib import Path

from xc_ce_utils.core_engine.reporting.domain.models import CanonicalReport


class StaticFindingsSummaryImporter:
    """Build static findings summary from canonical findings/execution steps."""

    name = 'static-findings-summary'

    def supports(self, file_path: Path) -> bool:
        return file_path.name.lower() == 'qacli-view-analysis.csv'

    def import_file(self, file_path: Path, report: CanonicalReport) -> None:
        _ = file_path

        is_delta_static_analysis = False
        sfa_thresholds: dict[str, str] = {}

        for step in report.execution_steps:
            step_type = (
                str(getattr(step, 'step_type', '') or '').strip().lower()
            )
            if 'qac' not in step_type:
                continue
            params = (
                step.parameters if isinstance(step.parameters, dict) else {}
            )
            if not bool(params.get('sfa')):
                continue

            is_delta_static_analysis = True
            violation_gate = params.get('violation_gate', {}) or {}
            thresholds = violation_gate.get('thresholds', {}) or {}
            if isinstance(thresholds, dict):
                sfa_thresholds = {
                    str(k).strip(): str(v).strip()
                    for k, v in thresholds.items()
                }
            break

        section_title = (
            'Delta Static Code Analysis'
            if is_delta_static_analysis
            else 'Full Static Code Analysis'
        )

        static_severity_counts: Counter = Counter()
        producer_severity_counts: Counter = Counter()

        for finding in report.findings:
            raw_props = (
                finding.properties
                if isinstance(finding.properties, dict)
                else {}
            )
            severity_value = str(
                raw_props.get('Severity')
                or raw_props.get('severity')
                or finding.severity
                or ''
            ).strip()
            if not severity_value:
                continue

            static_severity_counts[severity_value] += 1

            producer_message = str(
                raw_props.get('Producer component:Message number')
                or raw_props.get('producer component:message number')
                or finding.rule_id
                or ''
            ).strip()
            producer_component = (
                producer_message.split(':', 1)[0].strip()
                if producer_message
                else 'unknown'
            )
            producer_severity_counts[producer_component, severity_value] += 1

        severity_cards = []
        for severity, count in sorted(
            static_severity_counts.items(),
            key=lambda item: self._severity_sort_key(str(item[0])),
        ):
            threshold = self._threshold_for_severity(
                str(severity), sfa_thresholds
            )
            severity_cards.append(
                {
                    'severity': str(severity),
                    'count': int(count),
                    'tone': self._severity_card_tone(str(severity)),
                    'threshold': threshold,
                    'ungated': bool(
                        is_delta_static_analysis and threshold == 'not-gated'
                    ),
                }
            )

        producer_rows = []
        for (producer, severity), count in sorted(
            producer_severity_counts.items(),
            key=lambda item: (
                self._severity_sort_key(str(item[0][1])),
                str(item[0][0]).lower(),
            ),
        ):
            producer_rows.append(
                {
                    'producer': str(producer).strip().lower() or 'unknown',
                    'severity': str(severity).strip().lower(),
                    'threshold': self._threshold_for_severity(
                        str(severity), sfa_thresholds
                    ),
                    'violations': int(count),
                }
            )

        report.metadata['static_findings_analysis'] = {
            'available': True,
            'is_delta_static_analysis': is_delta_static_analysis,
            'section_title': section_title,
            'sfa_thresholds': sfa_thresholds,
            'severity_cards': severity_cards,
            'producer_rows': producer_rows,
            'severity_values': [
                str(name)
                for name, _ in sorted(
                    static_severity_counts.items(),
                    key=lambda item: self._severity_sort_key(str(item[0])),
                )
            ],
        }

    def _severity_card_tone(self, level: str) -> str:
        value = str(level or '').strip().lower()
        if value in {
            'critical',
            'high',
            'error',
            'exception',
            '9',
            '8',
            '7',
            '1',
        }:
            return 'danger'
        if value in {'warning', 'warn', 'medium', '6', '5', '4', '2'}:
            return 'warn'
        if value in {'info', 'low', '3', '0'}:
            return 'info'
        return 'neutral'

    def _severity_sort_key(self, level: str) -> tuple:
        value = str(level or '').strip().lower()
        try:
            return (0, float(value), value)
        except Exception:
            pass
        named = {
            'critical': 1,
            'high': 2,
            'medium': 3,
            'low': 4,
            'info': 5,
        }
        return (1, named.get(value, 99), value)

    def _threshold_for_severity(
        self, level: str, sfa_thresholds: dict[str, str]
    ) -> str:
        if not sfa_thresholds:
            return 'not-gated'

        raw = str(level or '').strip()
        candidates = [raw, raw.lower()]
        if re.fullmatch(r'\d+(?:\.0+)?', raw):
            try:
                candidates.append(str(int(float(raw))))
            except Exception:
                pass

        for candidate in candidates:
            if candidate in sfa_thresholds:
                return str(sfa_thresholds[candidate])
        return 'not-gated'
