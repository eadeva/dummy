"""VS Code setup components for environment bootstrap.
"""

from xc_ce_utils.core_engine.setup.vscode.config_generation import (
    VSCodeConfigGenerationMixin,
)
from xc_ce_utils.core_engine.setup.vscode.extensions import (
    VSCodeExtensionsOutcome,
    VSCodeSetupMixin,
)

__all__ = [
    'VSCodeConfigGenerationMixin',
    'VSCodeExtensionsOutcome',
    'VSCodeSetupMixin',
]
