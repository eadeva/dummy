"""
Gemini CLI analysis wrapper for action execution failures.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from xc_ce_utils import logger
from xc_ce_utils.core_engine.adapters.ai.ai_helper import (
    extract_error_context,
    extract_failing_step_log_context,
    get_report_paths_prompt_context,
)


def run_gemini_analysis(action_name: str, repo_root: Path) -> None:
    """Run Gemini CLI to analyze the log report using the central skill."""
    # 1. Extract actual error context, raw log tail, and paths from the canonical reports
    error_context = extract_error_context(repo_root)
    paths_context = get_report_paths_prompt_context(repo_root)
    log_tail_context = extract_failing_step_log_context(repo_root)

    # 2. Construct the detailed, constrained prompt
    prompt = (
        f'The xc-ce-utils action {action_name} failed.\n'
        f'Your task is to DIAGNOSE and EXPLAIN the problem, NOT to re-run the build.\n\n'
        f'CRITICAL RULES:\n'
        f'  1. DO NOT run any build commands, compiler commands, `pyinstaller`, or `build.ps1` blindly.\n'
        f'  2. Follow the diagnostic order in the skill file `.github/skills/xc-ce-log-report-analysis/SKILL.md`:\n'
        f'     - First, read the main canonical report file to find the failed step.\n'
        f'     - Second, read the log findings or the raw log file of the failed step to find the error.\n'
        f'  3. ASK QUESTIONS before proposing or doing any changes to files.\n'
        f'  4. DO NOT read the entire `*.canonical.json` or `*.jsonl` log files. They are extremely large (tens of megabytes) '
        f'and will exceed your token limit (1,048,576 tokens). The exact failure is already extracted for you in the '
        f"'Raw Log Tail' below. If you must read files, ONLY read specific, targeted lines or the first/last few lines. "
        f'Do NOT load full log files into your context.\n\n'
        f'The files and errors are already generated for you below.\n'
        f'{paths_context}'
        f'{log_tail_context}'
        f'{error_context}'
    )

    # 3. Safeguard: Truncate prompt if it exceeds 20,000 characters to protect against
    # CreateProcess argument limitations (32,767) and clean up the LLM input.
    max_prompt_len = 20000
    if len(prompt) > max_prompt_len:
        prompt = (
            prompt[:max_prompt_len]
            + '\n\n[Prompt truncated to protect command line length limits...]'
        )

    # Command execution
    # Using -i/--interactive opens an interactive session and pre-runs our prompt.
    # On Windows, executing .CMD files via subprocess triggers cmd.exe under the hood,
    # which enforces the 8,191 character limit.
    # To bypass this completely and use the 32,767 character CreateProcess limit,
    # we execute node.exe directly with the bundled javascript file if we detect a .CMD file.

    gemini_path = shutil.which('gemini')
    if gemini_path and gemini_path.lower().endswith('.cmd'):
        js_file = (
            Path(gemini_path).parent
            / 'node_modules'
            / '@google'
            / 'gemini-cli'
            / 'bundle'
            / 'gemini.js'
        )
        if js_file.is_file():
            cmd = ['node', str(js_file), '-m', 'gemini-3.5-flash', '-i', prompt]
        else:
            cmd = [gemini_path, '-m', 'gemini-3.5-flash', '-i', prompt]
    else:
        cmd = [gemini_path or 'gemini', '-m', 'gemini-3.5-flash', '-i', prompt]

    logger.progress('Executing: gemini -m gemini-3.5-flash -i "[error context and log tail]"')

    try:
        subprocess.run(
            cmd,
            shell=False,
            check=False,
            cwd=str(repo_root),
        )
    except Exception as e:
        logger.error(f'Failed to execute Gemini CLI: {e}')
