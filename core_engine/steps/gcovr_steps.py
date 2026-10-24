"""gcovr coverage steps executed through uvx."""

import json
import os
import re
import shlex
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import Field

from xc_ce_utils import logger
from xc_ce_utils.core_engine.domain.exceptions import ExecutionStepError
from xc_ce_utils.core_engine.domain.step_registry import StepRegistry
from xc_ce_utils.core_engine.steps.base import BaseStepParams, ExecutionStep
from xc_ce_utils.global_modules.aux_helper import run_command


class GcovrStepParams(BaseStepParams):
    version: Optional[Any] = Field(default=None)
    working_dir: Optional[Any] = Field(default=None)
    model_config = {'extra': 'forbid'}


@StepRegistry.register('gcovr', category='Testing')
class GcovrStep(ExecutionStep):
    params_model = GcovrStepParams

    """Run gcovr through uvx.

    Config parameters:
        version (str):
            gcovr package version to execute, for example "8.5".
        params (dict | list[str] | str):
            Additional CLI parameters passed directly to gcovr, for example
            ["--exclude", ".*/_deps/.*", "--sonarqube", "coverage.xml"].
            Dict form is converted to CLI options.
            When provided as a string it is split with shell-like parsing.
        working_dir (str, optional):
            Working directory for gcovr execution. Defaults to repo root.
    """

    def _normalize_additional_parameters(self, value: Any) -> List[str]:
        if value is None:
            return []

        if isinstance(value, str):
            return shlex.split(value)

        if isinstance(value, list):
            return [str(item) for item in value]

        raise ExecutionStepError(f'[{self.name}] params must be a string, list, or dict')

    def _dict_to_cli_parameters(self, value: Dict[str, Any]) -> List[str]:
        args: List[str] = []
        for name, item in value.items():
            option = f'{name}' if str(name).startswith('-') else f'--{name}'
            if item is None:
                continue
            if isinstance(item, bool):
                if item:
                    args.append(option)
                continue
            if isinstance(item, list):
                for sub in item:
                    args.append(option)
                    args.append(str(sub))
                continue
            args.append(option)
            args.append(str(item))
        return args

    def _normalize_params(self, value: Any) -> List[str]:
        if isinstance(value, dict):
            return self._dict_to_cli_parameters(value)
        return self._normalize_additional_parameters(value)

    def validate(self) -> None:
        """Validate gcovr configuration."""
        version = str(self.config.get('version', '')).strip()
        if not version:
            raise ExecutionStepError(f'[{self.name}] Missing required gcovr version parameter')

        params = self.config.get('params', [])
        if not isinstance(params, (dict, list, str)):
            raise ExecutionStepError(f'[{self.name}] params must be a dict, list, or string')

    def _build_sanitized_env(self) -> Dict[str, str]:
        """Build a clean environment for uvx tool execution.

        Running inside the xc-ce-utils virtualenv can leak Python path variables
        into uvx and make gcovr import wrong site-packages.
        """
        env = dict(os.environ)
        env.pop('PYTHONPATH', None)
        env.pop('PYTHONHOME', None)
        return env

    def _prepare_output_directories(
        self, additional_parameters: List[str], working_dir: str
    ) -> None:
        """Create parent directories for gcovr output file parameters."""
        output_options = {
            '--output',
            '--sonarqube',
            '--html',
            '--html-details',
            '--xml',
            '--xml-pretty',
            '--json',
            '--json-pretty',
            '--csv',
            '--txt',
        }

        idx = 0
        while idx < len(additional_parameters):
            arg = additional_parameters[idx]
            output_target = None

            if arg.startswith('--') and '=' in arg:
                option, value = arg.split('=', 1)
                if option in output_options:
                    output_target = value
            elif arg in output_options and idx + 1 < len(additional_parameters):
                output_target = additional_parameters[idx + 1]
                idx += 1

            if output_target and output_target != '-' and '://' not in output_target:
                out_path = Path(output_target)
                if not out_path.is_absolute():
                    out_path = Path(working_dir) / out_path
                out_path.parent.mkdir(parents=True, exist_ok=True)

            idx += 1

    def _get_option_value(self, additional_parameters: List[str], option: str) -> Optional[str]:
        """Return the configured value for an option from argument list."""
        idx = 0
        while idx < len(additional_parameters):
            arg = additional_parameters[idx]
            if arg == option and idx + 1 < len(additional_parameters):
                return additional_parameters[idx + 1]
            if arg.startswith(f'{option}='):
                return arg.split('=', 1)[1]
            idx += 1
        return None

    def _parse_sonarqube_coverage(self, coverage_xml: Path) -> Dict[str, float]:
        """Parse gcovr SonarQube XML and compute aggregate metrics."""
        tree = ET.parse(coverage_xml)
        root = tree.getroot()

        lines_total = 0
        lines_covered = 0
        branches_total = 0
        branches_covered = 0

        for line_el in root.findall('.//lineToCover'):
            lines_total += 1

            covered = str(line_el.attrib.get('covered', 'false')).lower()
            if covered in {'true', '1', 'yes'}:
                lines_covered += 1

            branches_to_cover = int(line_el.attrib.get('branchesToCover', '0'))
            covered_branches = int(line_el.attrib.get('coveredBranches', '0'))
            branches_total += branches_to_cover
            branches_covered += covered_branches

        def _pct(covered: int, total: int) -> float:
            if total <= 0:
                return 100.0
            return round((covered / total) * 100.0, 2)

        return {
            'lines_total': float(lines_total),
            'lines_covered': float(lines_covered),
            'line_coverage_pct': _pct(lines_covered, lines_total),
            'branches_total': float(branches_total),
            'branches_covered': float(branches_covered),
            'branch_coverage_pct': _pct(branches_covered, branches_total),
        }

    def _parse_console_function_coverage(self, command_output: str) -> Optional[Dict[str, float]]:
        """Extract function coverage summary from gcovr console output."""
        match = re.search(
            r'functions:\s*([0-9]+(?:\.[0-9]+)?)%\s*\((\d+)\s+out of\s+(\d+)\)',
            command_output,
            flags=re.IGNORECASE,
        )
        if not match:
            return None

        pct = float(match.group(1))
        covered = float(match.group(2))
        total = float(match.group(3))
        return {
            'functions_total': total,
            'functions_covered': covered,
            'function_coverage_pct': round(pct, 2),
        }

    def _write_summary_json(
        self,
        output_path: Path,
        coverage_xml: Path,
        metrics: Dict[str, float],
        function_metrics: Optional[Dict[str, float]],
    ) -> None:
        """Write normalized gcovr coverage metrics for reporting_v2 import."""
        payload: Dict[str, Any] = {
            'report_kind': 'gcovr-summary',
            'tool': 'gcovr',
            'source_file': str(coverage_xml),
            'metrics': {
                'lines_total': int(metrics.get('lines_total', 0)),
                'lines_covered': int(metrics.get('lines_covered', 0)),
                'line_coverage_pct': float(metrics.get('line_coverage_pct', 100.0)),
                'branches_total': int(metrics.get('branches_total', 0)),
                'branches_covered': int(metrics.get('branches_covered', 0)),
                'branch_coverage_pct': float(metrics.get('branch_coverage_pct', 100.0)),
            },
        }

        if function_metrics:
            payload['metrics'].update(
                {
                    'functions_total': int(function_metrics['functions_total']),
                    'functions_covered': int(function_metrics['functions_covered']),
                    'function_coverage_pct': float(function_metrics['function_coverage_pct']),
                }
            )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(payload, indent=2),
            encoding='utf-8',
        )

    def execute(self) -> None:
        """Execute gcovr via uvx with pinned version and custom parameters."""
        if shutil.which('uvx') is None:
            raise ExecutionStepError(f'[{self.name}] uvx executable not found in PATH')

        version = str(self.config.get('version', '')).strip()
        additional_parameters = self._normalize_params(self.config.get('params', []))

        working_dir = self.config.get('working_dir', str(self.context.repo_root))
        self._prepare_output_directories(additional_parameters, working_dir)
        command = [
            'uvx',
            '--isolated',
            '--from',
            f'gcovr=={version}',
            'gcovr',
            *additional_parameters,
        ]

        logger.info(f'[{self.name}] Running gcovr via uvx (version {version})')
        command_output = run_command(
            command,
            log_file=self.get_step_log_folder() / 'gcovr.log',
            cwd=working_dir,
            env=self._build_sanitized_env(),
            capture_output=True,
        )

        reports_folder = self.get_step_reports_folder()
        reports_folder.mkdir(parents=True, exist_ok=True)

        sonarqube_path = self._get_option_value(additional_parameters, '--sonarqube')
        if sonarqube_path:
            coverage_xml = Path(sonarqube_path)
            if not coverage_xml.is_absolute():
                coverage_xml = Path(working_dir) / coverage_xml

            if coverage_xml.exists():
                try:
                    metrics = self._parse_sonarqube_coverage(coverage_xml)
                    function_metrics = self._parse_console_function_coverage(command_output)
                    stale_junit = reports_folder / 'gcovr-junit.xml'
                    if stale_junit.exists():
                        stale_junit.unlink()
                        logger.info(
                            f'[{self.name}] Removed stale coverage JUnit summary: {stale_junit}'
                        )

                    summary_json = reports_folder / 'gcovr-summary.json'
                    self._write_summary_json(
                        output_path=summary_json,
                        coverage_xml=coverage_xml,
                        metrics=metrics,
                        function_metrics=function_metrics,
                    )
                    logger.info(f'[{self.name}] Coverage summary JSON written: {summary_json}')

                    logger.info(
                        f"[{self.name}] Coverage summary from {coverage_xml}: "
                        f"line={metrics['line_coverage_pct']}% "
                        f"({int(metrics['lines_covered'])}/{int(metrics['lines_total'])}), "
                        f"branch={metrics['branch_coverage_pct']}% "
                        f"({int(metrics['branches_covered'])}/{int(metrics['branches_total'])})"
                    )
                    if function_metrics:
                        logger.info(
                            f"[{self.name}] Function coverage from gcovr output: "
                            f"{function_metrics['function_coverage_pct']}% "
                            f"({int(function_metrics['functions_covered'])}/"
                            f"{int(function_metrics['functions_total'])})"
                        )
                    self.result_string.append(f'Coverage source report: {coverage_xml}')
                    self.result_string.append(f'Coverage summary json: {summary_json}')
                except Exception as exc:
                    logger.warning(f'[{self.name}] Failed to parse SonarQube coverage XML: {exc}')
            else:
                logger.warning(f'[{self.name}] SonarQube coverage XML not found at {coverage_xml}')

        self.result_string.append(f'gcovr executed with uvx (version={version})')
