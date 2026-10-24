"""Project configuration Advanced Help importer."""

from __future__ import annotations

import json
from pathlib import Path

from xc_ce_utils.core_engine.reporting.domain.models import CanonicalReport


class ConfigImporter:
    """Import project_config.json configuration files."""

    name = 'project-config'

    def supports(self, file_path: Path) -> bool:
        """Check if the given file is the project_config.json metadata."""
        return file_path.name == 'project_config.json'

    def import_file(self, file_path: Path, report: CanonicalReport) -> None:
        """Import the project configuration metadata into the report."""
        try:
            data = json.loads(file_path.read_text(encoding='utf-8'))
            report.metadata['project_config'] = data
            if 'build_context' in data:
                report.metadata['build_context'] = data['build_context']
        except Exception:
            pass
