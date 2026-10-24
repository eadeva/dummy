"""Backward-compatible shim for renamed VS Code setup mixin module.

Canonical module: ``xc_ce_utils.core_engine.setup.vscode``.
This shim keeps external imports stable while the codebase migrates.
"""

from xc_ce_utils.core_engine.setup.vscode import (
    VSCodeExtensionsOutcome,
    VSCodeSetupMixin,
)

__all__ = [
    'VSCodeExtensionsOutcome',
    'VSCodeSetupMixin',
]
