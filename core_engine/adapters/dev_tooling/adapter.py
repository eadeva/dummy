"""Adapter seam for developer-tooling integrations.

Core-engine code should call these helpers instead of importing concrete
implementation modules from ``xc_ce_utils.git_hooks`` or
``xc_ce_utils.vs_code_configurator`` directly.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from pathlib import Path

from xc_ce_utils.core_engine.adapters.dev_tooling.ports import (
    CopilotInstructionsManagerPort,
    DevToolingProviderPort,
    MCPServerConfiguratorPort,
    VSCodeCommandsGeneratorPort,
    VSCodeExtensionsInstallerPort,
)


class DefaultDevToolingProvider:
    """Default provider backed by in-repo implementation modules."""

    @staticmethod
    def configure_git_hooks(
        jira_project_key: str,
        *,
        regenerate_code_quality_configs: bool = True,
    ) -> None:
        hooks_module = importlib.import_module(
            'xc_ce_utils.git_hooks.hooks_setup'
        )

        hooks_module.configure_git_hooks(
            jira_project_key,
            regenerate_code_quality_configs=regenerate_code_quality_configs,
        )

    @staticmethod
    def create_mcp_server_configurator(
        repo_root: Path,
    ) -> MCPServerConfiguratorPort:
        mcp_module = importlib.import_module(
            'xc_ce_utils.vs_code_configurator.setup_mcp_servers'
        )
        return mcp_module.MCPServerConfigurator(repo_root=repo_root)

    @staticmethod
    def create_vscode_commands_generator(
        repo_root: Path,
    ) -> VSCodeCommandsGeneratorPort:
        commands_module = importlib.import_module(
            'xc_ce_utils.vs_code_configurator.generate_vscode_commands'
        )
        return commands_module.VSCodeCommandsGenerator(repo_root=repo_root)

    @staticmethod
    def create_vscode_extensions_installer(
        repo_root: Path,
    ) -> VSCodeExtensionsInstallerPort:
        extensions_module = importlib.import_module(
            'xc_ce_utils.vs_code_configurator.install_vscode_extensions'
        )
        return extensions_module.VSCodeExtensionsInstaller(repo_root=repo_root)

    @staticmethod
    def create_copilot_instructions_manager(
        repo_root: Path,
    ) -> CopilotInstructionsManagerPort:
        copilot_module = importlib.import_module(
            'xc_ce_utils.vs_code_configurator.copilot_vs_configurator'
        )
        return copilot_module.CopilotInstructionsManager(repo_root=repo_root)


@dataclass
class _ProviderState:
    """Mutable holder to avoid module-level global reassignment."""

    provider: DevToolingProviderPort


_provider_state = _ProviderState(DefaultDevToolingProvider())


def set_dev_tooling_provider(provider: DevToolingProviderPort) -> None:
    """Override provider implementation for extraction/tests."""
    _provider_state.provider = provider


def reset_dev_tooling_provider() -> None:
    """Restore default provider implementation."""
    _provider_state.provider = DefaultDevToolingProvider()


def configure_git_hooks(
    jira_project_key: str,
    *,
    regenerate_code_quality_configs: bool = True,
) -> None:
    """Run git-hooks setup through the extracted implementation module."""
    _provider_state.provider.configure_git_hooks(
        jira_project_key,
        regenerate_code_quality_configs=regenerate_code_quality_configs,
    )


def create_mcp_server_configurator(
    repo_root: Path,
) -> MCPServerConfiguratorPort:
    """Create the MCP server configurator instance."""
    return _provider_state.provider.create_mcp_server_configurator(
        repo_root=repo_root
    )


def create_vscode_commands_generator(
    repo_root: Path,
) -> VSCodeCommandsGeneratorPort:
    """Create the VS Code commands/settings generator instance."""
    return _provider_state.provider.create_vscode_commands_generator(
        repo_root=repo_root
    )


def create_vscode_extensions_installer(
    repo_root: Path,
) -> VSCodeExtensionsInstallerPort:
    """Create the VS Code extensions installer instance."""
    return _provider_state.provider.create_vscode_extensions_installer(
        repo_root=repo_root
    )


def create_copilot_instructions_manager(
    repo_root: Path,
) -> CopilotInstructionsManagerPort:
    """Create the Copilot instructions manager instance."""
    return _provider_state.provider.create_copilot_instructions_manager(
        repo_root=repo_root
    )


def create_copilot_vs_configurator(
    repo_root: Path,
) -> CopilotInstructionsManagerPort:
    """Backward-compatible alias for the Copilot instructions manager."""
    return create_copilot_instructions_manager(repo_root=repo_root)
