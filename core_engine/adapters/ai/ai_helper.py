"""
Shared helpers for AI troubleshooting adapters.
"""

from __future__ import annotations

import json
from pathlib import Path


def find_recent_log_findings(repo_root: Path) -> Path | None:
    """Find the most recently generated log-findings canonical JSON file."""
    reports_dir = repo_root / '_reports'
    if not reports_dir.exists():
        return None

    # Search recursively for log-findings.canonical.json files
    candidates = list(reports_dir.glob('**/log-findings.canonical.json'))
    if not candidates:
        return None

    # Sort by modification time (newest first)
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0]


def extract_error_context(repo_root: Path) -> str:
    """Extract a summary of the top errors from the most recent log findings."""
    log_file = find_recent_log_findings(repo_root)
    if not log_file or not log_file.exists():
        return ''

    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        findings = data.get('findings', []) or []
        # Filter for actual errors or exceptions
        errors = [f for f in findings if (f.get('type') or '').lower() in ('error', 'exception')]

        if not errors:
            return ''

        context = '\n\nHere are the specific errors captured in the log findings:\n'
        for i, err in enumerate(errors[:5], 1):
            step = err.get('step') or 'unknown'
            message = err.get('message') or 'No message'
            context += f'  {i}. [{step}] {message}\n'

        return context

    except Exception:
        # Graceful fallback on parse errors
        return ''


def get_report_paths_prompt_context(repo_root: Path) -> str:
    """Find recent canonical reports and format their absolute paths as prompt context."""
    reports_dir = repo_root / '_reports'
    if not reports_dir.exists():
        return ''

    context = ''

    # 1. Find main canonical report
    main_reports = list(reports_dir.glob('**/*-report.canonical.json'))
    if main_reports:
        main_reports.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        context += f'    - Main Canonical Report: {main_reports[0].resolve()}\n'

    # 2. Find log findings report
    log_reports = list(reports_dir.glob('**/log-findings.canonical.json'))
    if log_reports:
        log_reports.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        context += f'    - Log Findings Report: {log_reports[0].resolve()}\n'

    if context:
        return (
            f'\n\nHere are the absolute paths to the generated canonical report files:\n{context}'
        )
    return ''


def extract_failing_step_log_context(repo_root: Path) -> str:
    """Find the failing step in the most recent report, read its raw log tail, and return prompt context."""
    reports_dir = repo_root / '_reports'
    if not reports_dir.exists():
        return ''

    # Find the main canonical report
    main_reports = list(reports_dir.glob('**/*-report.canonical.json'))
    if not main_reports:
        return ''

    main_reports.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    report_file = main_reports[0]

    try:
        with open(report_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        failing_steps = []
        for step in data.get('execution_steps', []):
            if step.get('status') != 'SUCCESS':
                failing_steps.append(step.get('name'))

        if not failing_steps:
            return ''

        failing_step_name = failing_steps[0]

        # Now find the raw log file for this step in _logs/
        logs_dir = repo_root / '_logs'
        if not logs_dir.exists():
            return ''

        # Search recursively for <step>.jsonl or <step>.log inside the logs folder
        log_candidates = list(logs_dir.glob(f'**/{failing_step_name}.jsonl'))
        if not log_candidates:
            log_candidates = list(logs_dir.glob(f'**/{failing_step_name}.log'))
            if not log_candidates:
                return ''

        log_candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        log_file = log_candidates[0]

        # Read the last 30 lines
        with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()

        tail_lines = lines[-30:]

        log_tail_text = ''
        if log_file.suffix == '.jsonl':
            # Parse messages from JSONL entries
            for line in tail_lines:
                try:
                    entry = json.loads(line)
                    log_tail_text += (
                        f"  [{entry.get('level', 'INFO')}] {entry.get('message', '')}\n"
                    )
                except Exception:
                    log_tail_text += f'  {line}'
        else:
            log_tail_text = ''.join(f'  {line}' for line in tail_lines)

        return (
            f"\n\nHere is the absolute path to the failing step's raw log file:\n"
            f'  - Raw Log File: {log_file.resolve()}\n\n'
            f'Here is the tail (last 30 lines) of that raw log:\n'
            f'{log_tail_text}'
        )

    except Exception:
        return ''
