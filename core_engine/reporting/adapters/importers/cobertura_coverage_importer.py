"""Cobertura XML coverage importer adapter."""

import re
import xml.etree.ElementTree as ET
from pathlib import Path

from xc_ce_utils.core_engine.reporting.domain.models import (
    CanonicalReport,
    CoverageSummary,
)


class CoberturaCoverageImporter:
    """Import Cobertura coverage XML into canonical coverage model."""

    name = 'cobertura-coverage'

    def supports(self, file_path: Path) -> bool:
        if file_path.suffix.lower() != '.xml':
            return False
        try:
            root = ET.parse(file_path).getroot()
        except ET.ParseError:
            return False

        if self._local_name(root.tag) != 'coverage':
            return False

        return 'lines-valid' in root.attrib

    def import_file(self, file_path: Path, report: CanonicalReport) -> None:
        root = ET.parse(file_path).getroot()

        for class_el in root.findall('.//class'):
            filename = class_el.attrib.get('filename', '')
            if not filename:
                continue

            lines_total = 0
            lines_covered = 0
            branches_total = 0
            branches_covered = 0

            # 1. Parse lines
            for line_el in class_el.findall('.//lines/line'):
                lines_total += 1
                hits = int(line_el.attrib.get('hits', '0') or 0)
                if hits > 0:
                    lines_covered += 1

                # 2. Parse branches from condition-coverage (e.g. "50% (1/2)")
                is_branch = str(line_el.attrib.get('branch', 'false')).lower() == 'true'
                if is_branch:
                    cond = line_el.attrib.get('condition-coverage', '')
                    match = re.search(r'\((\d+)/(\d+)\)', cond)
                    if match:
                        branches_covered += int(match.group(1))
                        branches_total += int(match.group(2))

            # Parse function (method) coverage for this file (class)
            functions_total = 0
            functions_covered = 0
            for method_el in class_el.findall('.//method'):
                functions_total += 1
                line_rate = float(method_el.attrib.get('line-rate', '0.0') or 0.0)
                if line_rate > 0.0:
                    functions_covered += 1

            functions_total_opt = functions_total if functions_total > 0 else None
            functions_covered_opt = functions_covered if functions_total > 0 else None
            function_coverage_pct_opt = (
                self._pct(functions_covered, functions_total) if functions_total > 0 else None
            )

            summary = CoverageSummary(
                lines_total=lines_total,
                lines_covered=lines_covered,
                line_coverage_pct=self._pct(lines_covered, lines_total),
                branches_total=branches_total,
                branches_covered=branches_covered,
                branch_coverage_pct=self._pct(branches_covered, branches_total),
                functions_total=functions_total_opt,
                functions_covered=functions_covered_opt,
                function_coverage_pct=function_coverage_pct_opt,
                source_file=filename,
            )

            existing = next(
                (cov for cov in report.coverage if cov.source_file == summary.source_file),
                None,
            )
            if existing is None:
                report.coverage.append(summary)
            else:
                existing.lines_total = summary.lines_total
                existing.lines_covered = summary.lines_covered
                existing.line_coverage_pct = summary.line_coverage_pct
                existing.branches_total = summary.branches_total
                existing.branches_covered = summary.branches_covered
                existing.branch_coverage_pct = summary.branch_coverage_pct
                existing.functions_total = summary.functions_total
                existing.functions_covered = summary.functions_covered
                existing.function_coverage_pct = summary.function_coverage_pct

    def _pct(self, covered: int, total: int) -> float:
        if total <= 0:
            return 100.0
        return round((covered / total) * 100.0, 2)

    def _local_name(self, xml_tag: str) -> str:
        if '}' in xml_tag:
            return xml_tag.rsplit('}', 1)[1]
        return xml_tag
