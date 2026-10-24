"""Port interfaces for reporting adapters."""

from pathlib import Path
from typing import Dict, Iterable, Protocol

from xc_ce_utils.core_engine.reporting.domain.models import CanonicalReport


class ReportImporterPort(Protocol):
    """Port for importing one external report file into canonical model."""

    name: str

    def supports(self, file_path: Path) -> bool:
        """Return True when this importer can parse the given file."""

    def import_file(self, file_path: Path, report: CanonicalReport) -> None:
        """Parse file and mutate canonical report."""


class ReportExporterPort(Protocol):
    """Port for exporting canonical report to a specific format."""

    format_name: str

    def export(self, report: CanonicalReport, output_path: Path) -> Path:
        """Write report to output path and return the written path."""


class ReportDiscoveryPort(Protocol):
    """Port for discovering candidate input files."""

    def discover(self, reports_dir: Path, glob_pattern: str) -> Iterable[Path]:
        """Yield candidate report files."""


class PipelineResult(Dict[str, str]):
    """Map of output format to generated file path."""
