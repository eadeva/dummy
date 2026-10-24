"""
Execution tracking for the dynamic CLI.

Encapsulates start time, warnings, errors, operation summary and the
final summary print. Extracted from :class:`DynamicCLIGenerator` to
slim the facade.
"""

from __future__ import annotations

import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from xc_ce_utils import logger
from xc_ce_utils.global_modules.aux_helper import is_running_in_ci

MAX_SUMMARY_ITEMS = 5  # Maximum number of warnings/errors to display in summary

REPORT_OPENING_VALUES = ('always', 'on-errors', 'never')
DEFAULT_REPORT_OPENING = 'on-errors'


def resolve_report_opening(full_config: Dict[str, Any]) -> str:
    """Return BEHAVIOUR_REPORT_OPENING from the main configuration (default: on-errors)."""
    raw = full_config.get('BEHAVIOUR_REPORT_OPENING')
    if raw is None or not str(raw).strip():
        return DEFAULT_REPORT_OPENING
    value = str(raw).strip().lower()
    if value not in REPORT_OPENING_VALUES:
        logger.warning(
            f"Invalid BEHAVIOUR_REPORT_OPENING '{raw}' (allowed: {', '.join(REPORT_OPENING_VALUES)}); "
            f"using '{DEFAULT_REPORT_OPENING}'"
        )
        return DEFAULT_REPORT_OPENING
    return value


class ExecutionTracker:
    """Tracks execution lifetime metrics for a single CLI invocation."""

    def __init__(
        self, *, interactive_failure_assistance: bool = True, report_opening: Optional[str] = None
    ) -> None:
        self.start_time: Optional[float] = None
        self.warnings: List[Dict[str, Any]] = []
        self.errors: List[Dict[str, Any]] = []
        self.operation_summary: Dict[str, Dict[str, Any]] = {}
        self.interactive_failure_assistance = interactive_failure_assistance
        self.report_opening = report_opening or DEFAULT_REPORT_OPENING

    @classmethod
    def from_config(cls, full_config: Dict[str, Any]) -> 'ExecutionTracker':
        """Create a tracker from the main configuration."""
        return cls(
            interactive_failure_assistance=bool(
                full_config.get('INTERACTIVE_FAILURE_ASSISTANCE', True)
            ),
            report_opening=resolve_report_opening(full_config),
        )

    def _should_open_report(self) -> bool:
        if self.report_opening == 'always':
            return True
        if self.report_opening == 'on-errors':
            return bool(self.errors)
        return False

    def start_execution(self) -> None:
        """Start tracking execution time."""
        self.start_time = time.time()

    def add_warning(self, message: str, operation: str = 'General') -> None:
        """Add a warning to the tracking list."""
        self.warnings.append(
            {
                'message': message,
                'operation': operation,
                'timestamp': datetime.now(),
            }
        )

    def add_error(self, message: str, operation: str = 'General') -> None:
        """Add an error to the tracking list."""
        self.errors.append(
            {
                'message': message,
                'operation': operation,
                'timestamp': datetime.now(),
            }
        )

    def track_operation(
        self, operation: str, status: str, duration: Optional[float] = None
    ) -> None:
        """Track completion status of an operation."""
        self.operation_summary[operation] = {
            'status': status,
            'timestamp': datetime.now(),
            'duration': duration,
        }

    def print_final_summary(self) -> None:
        """Print final execution summary with warnings, errors, and timing."""
        if not self.start_time:
            return

        total_duration = time.time() - self.start_time
        duration_str = str(timedelta(seconds=int(total_duration)))

        logger.log_phase_header('EXECUTION SUMMARY')

        if self.operation_summary:
            logger.info('Operations completed:')
            for operation, details in self.operation_summary.items():
                duration_info = f" ({details['duration']:.1f}s)" if details['duration'] else ''
                logger.info(f"  {operation}: {details['status']}{duration_info}")

        if self.warnings:
            logger.progress(f'Warnings ({len(self.warnings)}):')
            for warning in self.warnings[-MAX_SUMMARY_ITEMS:]:
                logger.warning(f"  * [{warning['operation']}] {warning['message']}")
            if len(self.warnings) > MAX_SUMMARY_ITEMS:
                logger.info(f'  ... and {len(self.warnings) - MAX_SUMMARY_ITEMS} more warnings')

        if self.errors:
            logger.progress(f'Errors ({len(self.errors)}):')
            for error in self.errors[-MAX_SUMMARY_ITEMS:]:
                logger.error(f"  * [{error['operation']}] {error['message']}")
            if len(self.errors) > MAX_SUMMARY_ITEMS:
                logger.info(f'  ... and {len(self.errors) - MAX_SUMMARY_ITEMS} more errors')

        if self.errors:
            logger.error(
                f'Execution completed with {len(self.errors)} error(s) and {len(self.warnings)} warning(s)'
            )
        elif self.warnings:
            logger.warning(f'Execution completed with {len(self.warnings)} warning(s)')
        else:
            logger.success('Execution completed successfully')

        action = os.environ.get('XC_CE_UTILS_ACTION')
        variant_alias = os.environ.get('XC_CE_UTILS_VARIANT_ALIAS')
        report_path = None
        if action and variant_alias:
            report_path = (
                Path('_reports') / variant_alias / action / f'{action}-{variant_alias}-report.html'
            )
        else:
            # Non-blocking opening of advanced help report if triggered
            adv_help_path = os.environ.get('XC_CE_UTILS_ADVANCED_HELP_HTML')
            if adv_help_path and Path(adv_help_path).is_file():
                report_path = Path(adv_help_path)

        if report_path and report_path.exists():
            logger.note(f'Report generated at: {report_path.resolve()}')
            logger.note('You can view the report in a browser')

        if (
            report_path
            and report_path.exists()
            and not is_running_in_ci()
            and self._should_open_report()
        ):
            logger.progress('Opening report in browser...')
            import webbrowser

            abs_path = str(Path(report_path).resolve())
            try:
                if sys.platform == 'win32':
                    os.startfile(abs_path)
                else:
                    webbrowser.open(Path(abs_path).as_uri())
                time.sleep(
                    0.2
                )  # Give OS shell Execute thread a fraction of a second to spawn before Python exits
            except Exception as e:
                logger.warning(f'Could not open browser automatically: {e}')
        elif report_path and report_path.exists() and not is_running_in_ci():
            logger.note(
                f'Report not opened (BEHAVIOUR_REPORT_OPENING: {self.report_opening}). '
                'Open it manually in a browser when needed.'
            )

        logger.progress(f'Total execution time: {duration_str}')
