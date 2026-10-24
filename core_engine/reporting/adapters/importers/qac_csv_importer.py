"""QAC CSV importer adapter."""

import csv
from pathlib import Path

from xc_ce_utils.core_engine.reporting.domain.classification import (
    normalize_severity,
)
from xc_ce_utils.core_engine.reporting.domain.models import (
    CanonicalReport,
    Finding,
)


class QacCsvImporter:
    """Import Helix QAC CSV reports into canonical findings model."""

    name = 'qac-csv'

    _TARGET_FILE_NAME = 'qacli-view-analysis.csv'

    _COLUMN_FILENAME = 'Filename'
    _COLUMN_LINE = 'Line number'
    _COLUMN_COLUMN = 'Column number'
    _COLUMN_PRODUCER_MSG = 'Producer component:Message number'
    _COLUMN_MESSAGE = 'Message text'
    _COLUMN_CRITICALITY = 'Criticality'
    _COLUMN_SEVERITY = 'Severity'
    _COLUMN_SUPPRESSION_MASK = 'Suppression type bitmask'
    _COLUMN_SUPPRESSION_JUSTIFICATION = 'Suppression justification'
    _COLUMN_RULE_GROUP = 'Rule Group'
    _COLUMN_RULE_SCOPE = 'Rule Scope'
    _COLUMN_RULE_TEXT = 'Rule Text'

    _REQUIRED_COLUMNS = {
        _COLUMN_FILENAME,
        _COLUMN_LINE,
        _COLUMN_COLUMN,
        _COLUMN_PRODUCER_MSG,
        _COLUMN_MESSAGE,
        _COLUMN_CRITICALITY,
        _COLUMN_SEVERITY,
        _COLUMN_SUPPRESSION_MASK,
        _COLUMN_SUPPRESSION_JUSTIFICATION,
        _COLUMN_RULE_GROUP,
        _COLUMN_RULE_SCOPE,
        _COLUMN_RULE_TEXT,
    }

    def supports(self, file_path: Path) -> bool:
        if file_path.suffix.lower() != '.csv':
            return False

        if file_path.name.lower() != self._TARGET_FILE_NAME:
            return False

        try:
            with file_path.open('r', encoding='utf-8', newline='') as handle:
                reader = csv.reader(handle)
                header = next(reader, [])
        except Exception:
            return False

        available = {self._normalize_key(h) for h in header if h}
        required = {
            self._normalize_key(name) for name in self._REQUIRED_COLUMNS
        }
        return required.issubset(available)

    def import_file(self, file_path: Path, report: CanonicalReport) -> None:
        with file_path.open('r', encoding='utf-8', newline='') as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                properties = {
                    self._COLUMN_FILENAME: self._pick(
                        row, [self._COLUMN_FILENAME]
                    ),
                    self._COLUMN_LINE: self._pick(row, [self._COLUMN_LINE]),
                    self._COLUMN_COLUMN: self._pick(row, [self._COLUMN_COLUMN]),
                    self._COLUMN_PRODUCER_MSG: self._pick(
                        row, [self._COLUMN_PRODUCER_MSG]
                    ),
                    self._COLUMN_MESSAGE: self._pick(
                        row, [self._COLUMN_MESSAGE]
                    ),
                    self._COLUMN_CRITICALITY: self._pick(
                        row, [self._COLUMN_CRITICALITY]
                    ),
                    self._COLUMN_SEVERITY: self._pick(
                        row, [self._COLUMN_SEVERITY]
                    ),
                    self._COLUMN_SUPPRESSION_MASK: self._pick(
                        row, [self._COLUMN_SUPPRESSION_MASK]
                    ),
                    self._COLUMN_SUPPRESSION_JUSTIFICATION: self._pick(
                        row, [self._COLUMN_SUPPRESSION_JUSTIFICATION]
                    ),
                    self._COLUMN_RULE_GROUP: self._pick(
                        row, [self._COLUMN_RULE_GROUP]
                    ),
                    self._COLUMN_RULE_SCOPE: self._pick(
                        row, [self._COLUMN_RULE_SCOPE]
                    ),
                    self._COLUMN_RULE_TEXT: self._pick(
                        row, [self._COLUMN_RULE_TEXT]
                    ),
                }

                severity_raw = properties.get(self._COLUMN_SEVERITY, '')

                finding = Finding(
                    tool='qac',
                    category='static-analysis',
                    rule_id=properties.get(self._COLUMN_PRODUCER_MSG, ''),
                    severity=normalize_severity(severity_raw),
                    message=properties.get(self._COLUMN_MESSAGE, ''),
                    file=properties.get(self._COLUMN_FILENAME, ''),
                    line=self._to_int(properties.get(self._COLUMN_LINE, '')),
                    column=self._to_int(
                        properties.get(self._COLUMN_COLUMN, '')
                    ),
                    status='open',
                    source_file=str(file_path),
                    properties=properties,
                )
                report.findings.append(finding)

    def _pick(self, row: dict, candidates: list) -> str:
        lowered = {self._normalize_key(k): v for k, v in row.items()}
        for key in candidates:
            normalized_key = self._normalize_key(key)
            if (
                normalized_key in lowered
                and lowered[normalized_key] is not None
            ):
                return str(lowered[normalized_key]).strip()
        return ''

    def _normalize_key(self, value: str) -> str:
        return str(value or '').lstrip('\ufeff').strip().lower()

    def _to_int(self, value: str) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0
