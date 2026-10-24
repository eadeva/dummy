"""Importer for the Fossfile discovery report written by the ``sbom`` step."""

import json
from pathlib import Path

from xc_ce_utils.core_engine.reporting.domain.models import CanonicalReport

DISCOVERY_FILE_NAME = 'sbom_discovery.json'


class SbomDiscoveryImporter:
    """Import ``sbom_discovery.json`` (uncovered build input folders) into ``metadata['sbom_discovery']``."""

    name = 'sbom-discovery'

    def supports(self, file_path: Path) -> bool:
        return file_path.name.lower() == DISCOVERY_FILE_NAME

    def import_file(self, file_path: Path, report: CanonicalReport) -> None:
        discovery = report.metadata.setdefault(
            'sbom_discovery', {'available': True, 'uncovered_dirs': [], 'discovery_files': []}
        )
        discovery['discovery_files'].append(str(file_path))
        try:
            data = json.loads(file_path.read_text(encoding='utf-8'))
        except (OSError, ValueError) as exc:
            discovery['parse_error'] = str(exc)
            return
        if not isinstance(data, dict):
            return
        uncovered = data.get('uncovered_dirs') or []
        if isinstance(uncovered, list):
            merged = {item['path']: item for item in discovery['uncovered_dirs']}
            for item in uncovered:
                entry = item if isinstance(item, dict) else {'path': str(item), 'files': None}
                if entry.get('path'):
                    merged[str(entry['path'])] = {'path': str(entry['path']), 'files': entry.get('files')}
            discovery['uncovered_dirs'] = [merged[path] for path in sorted(merged)]
        discovery['uncovered_ignored_files'] = max(
            discovery.get('uncovered_ignored_files', 0), int(data.get('uncovered_ignored_files') or 0)
        )
        inputs = data.get('inputs')
        if isinstance(inputs, dict) and inputs.get('discovery'):
            discovery['discovery'] = str(inputs['discovery'])
