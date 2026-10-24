"""Importer for arch2needs (architecture needs generation) logs and validation report."""

import json
import re
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional

from xc_ce_utils.core_engine.reporting.domain.models import CanonicalReport

VALIDATION_REPORT_NAME = 'architecture_validation.json'
LOG_FILE_NAME = 'arch2needs.log'
MAX_LOG_MESSAGES = 500
_REPORTED_LEVELS = frozenset({'WARNING', 'ERROR', 'CRITICAL'})
# findings of the validation report are also logged; they are listed from the report
_VALIDATION_LOGGER = 'xc_ce_utils.docascode.arch2needs.model_validation'
_LOG_LINE = re.compile(
    r'^(?P<time>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}) - (?P<logger>\S+) - '
    r'(?P<level>DEBUG|INFO|WARNING|ERROR|CRITICAL) - (?P<message>.*)$'
)


class Arch2NeedsImporter:
    """Import arch2needs results of docascode steps.

    Supports a docascode ``execution-step.json`` (the files are looked up in the step's log
    folder and its parent, the action log folder) or an ``architecture_validation.json``.
    """

    name = 'arch2needs'

    def supports(self, file_path: Path) -> bool:
        if file_path.name.lower() == VALIDATION_REPORT_NAME:
            return True
        if file_path.name.lower() != 'execution-step.json':
            return False
        try:
            with file_path.open('r', encoding='utf-8') as handle:
                data = json.load(handle)
        except Exception:
            return False
        if not isinstance(data, dict) or data.get('report_kind') != 'execution-step':
            return False
        step = data.get('step', {}) or {}
        return str(step.get('step_type', '')).strip().lower() == 'docascode'

    def import_file(self, file_path: Path, report: CanonicalReport) -> None:
        if file_path.name.lower() == VALIDATION_REPORT_NAME:
            folders = [file_path.parent]
        else:
            with file_path.open('r', encoding='utf-8') as handle:
                folders = self._log_folders(json.load(handle))

        report_file = self._first_file(folders, VALIDATION_REPORT_NAME)
        log_file = self._first_file(folders, LOG_FILE_NAME)
        if report_file is None and log_file is None:
            return

        payload: Dict[str, object] = {
            'available': True,
            'report_file': str(report_file) if report_file else '',
            'log_file': str(log_file) if log_file else '',
        }
        payload.update(self._parse_report(report_file))
        payload.update(self._parse_log(log_file))
        report.metadata['arch2needs'] = payload

    @staticmethod
    def _log_folders(step_data: object) -> List[Path]:
        if not isinstance(step_data, dict):
            return []
        artifacts = step_data.get('artifacts', {})
        step_log = (
            str(artifacts.get('step_log', '') or '').strip() if isinstance(artifacts, dict) else ''
        )
        if not step_log:
            return []
        step_folder = Path(step_log).parent
        return [step_folder, step_folder.parent]

    @staticmethod
    def _first_file(folders: List[Path], name: str) -> Optional[Path]:
        return next((folder / name for folder in folders if (folder / name).is_file()), None)

    @staticmethod
    def _parse_report(report_file: Optional[Path]) -> Dict[str, object]:
        result: Dict[str, object] = {'errors': 0, 'warnings': 0, 'findings': [], 'codes': []}
        if report_file is None:
            return result
        try:
            data = json.loads(report_file.read_text(encoding='utf-8'))
        except Exception as exc:
            result['report_parse_error'] = str(exc)
            return result
        raw_findings = data.get('findings', []) if isinstance(data, dict) else []
        findings = [
            {
                key: str(item.get(key, '') or '')
                for key in ('severity', 'code', 'message', 'file', 'location')
            }
            for item in raw_findings
            if isinstance(item, dict)
        ]
        counts = Counter((finding['severity'], finding['code']) for finding in findings)
        result['findings'] = findings
        result['errors'] = sum(1 for finding in findings if finding['severity'] == 'error')
        result['warnings'] = sum(1 for finding in findings if finding['severity'] == 'warning')
        result['codes'] = [
            {'severity': severity, 'code': code, 'count': count}
            for (severity, code), count in sorted(
                counts.items(), key=lambda item: (item[0][0] != 'error', -item[1], item[0][1])
            )
        ]
        return result

    @staticmethod
    def _parse_log(log_file: Optional[Path]) -> Dict[str, object]:
        result: Dict[str, object] = {
            'log_level_counts': {},
            'log_messages': [],
            'log_messages_truncated': False,
        }
        if log_file is None:
            return result
        try:
            lines = log_file.read_text(encoding='utf-8', errors='replace').splitlines()
        except OSError as exc:
            result['log_parse_error'] = str(exc)
            return result

        entries: List[Dict[str, str]] = []
        for line in lines:
            match = _LOG_LINE.match(line)
            if match:
                entries.append(match.groupdict())
            elif entries:
                entries[-1]['message'] += '\n' + line

        level_counts = Counter(entry['level'] for entry in entries)
        messages = [
            entry
            for entry in entries
            if entry['level'] in _REPORTED_LEVELS and entry['logger'] != _VALIDATION_LOGGER
        ]
        result['log_level_counts'] = dict(level_counts)
        result['log_messages'] = messages[:MAX_LOG_MESSAGES]
        result['log_messages_truncated'] = len(messages) > MAX_LOG_MESSAGES
        return result
