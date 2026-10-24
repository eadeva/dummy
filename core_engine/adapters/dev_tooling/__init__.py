"""Developer-tooling adapter modules.
"""

from .adapter import (
    configure_git_hooks,
    create_copilot_instructions_manager,
    create_copilot_vs_configurator,
    create_mcp_server_configurator,
    create_vscode_commands_generator,
    create_vscode_extensions_installer,
    reset_dev_tooling_provider,
    set_dev_tooling_provider,
)

__all__ = [
    'configure_git_hooks',
    'create_copilot_instructions_manager',
    'create_copilot_vs_configurator',
    'create_mcp_server_configurator',
    'create_vscode_commands_generator',
    'create_vscode_extensions_installer',
    'reset_dev_tooling_provider',
    'set_dev_tooling_provider',
]
