"""gcovr SonarQube XML coverage importer."""

import xml.etree.ElementTree as ET
from pathlib import Path

from xc_ce_utils.core_engine.reporting.domain.models import (
    CanonicalReport,
    CoverageSummary,
)


class SonarQubeCoverageImporter:
    """Import SonarQube coverage XML into canonical coverage model."""

    name = 'sonarqube-coverage'

    def supports(self, file_path: Path) -> bool:
        if file_path.suffix.lower() != '.xml':
            return False
        try:
            root = ET.parse(file_path).getroot()
        except ET.ParseError:
            return False

        if self._local_name(root.tag) != 'coverage':
            return False

        return root.find('.//lineToCover') is not None

    def import_file(self, file_path: Path, report: CanonicalReport) -> None:
        root = ET.parse(file_path).getroot()

        for file_el in root.findall('.//file'):
            file_path_str = file_el.attrib.get('path', '')
            if not file_path_str:
                continue

            lines_total = 0
            lines_covered = 0
            branches_total = 0
            branches_covered = 0

            for line_el in file_el.findall('.//lineToCover'):
                lines_total += 1
                covered = str(line_el.attrib.get('covered', 'false')).lower()
                if covered in {'true', '1', 'yes'}:
                    lines_covered += 1

                branches_to_cover = int(line_el.attrib.get('branchesToCover', '0') or 0)
                covered_branches = int(line_el.attrib.get('coveredBranches', '0') or 0)
                branches_total += branches_to_cover
                branches_covered += covered_branches

            # Parse function (method) coverage conditionally if present in XML for this file
            functions_total = 0
            functions_covered = 0
            for method_el in file_el.findall('.//method'):
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
                source_file=file_path_str,
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
