"""Backward-compatible shim for renamed VS Code CLI helpers.

Canonical module: ``xc_ce_utils.core_engine.cli.vscode_commands``.
This shim keeps external imports stable while the codebase migrates.
"""

from xc_ce_utils.core_engine.cli.vscode_commands import (
    refresh_vscode_extensions,
    regen_copilot_instructions,
    regen_mcp_json,
    regen_vscode_shared,
    run_setup,
)

__all__ = [
    'refresh_vscode_extensions',
    'regen_copilot_instructions',
    'regen_mcp_json',
    'regen_vscode_shared',
    'run_setup',
]
