"""Canonical JSON exporter."""

import json
from pathlib import Path

from xc_ce_utils.core_engine.reporting.domain.models import CanonicalReport


class JsonReportExporter:
    """Export canonical report envelope as JSON."""

    format_name = 'json'

    def export(self, report: CanonicalReport, output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open('w', encoding='utf-8') as handle:
            json.dump(report.to_dict(), handle, indent=2)
            handle.write('\n')
        return output_path.resolve()
