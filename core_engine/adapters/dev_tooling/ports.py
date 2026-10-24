"""Port interfaces for developer-tooling integrations.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, Tuple


class MCPServerConfiguratorPort(Protocol):
    """Port for MCP server setup and DEVMATE PAT operations."""

    def run(self) -> bool:
        """Run MCP server configuration."""

    def validate_devmate_pat(self, token: str) -> bool:
        """Validate DEVMATE_PAT token."""

    def setup_persistent_devmate_pat(self, pat: str) -> bool:
        """Persist DEVMATE_PAT to environment."""

    def prompt_and_store_devmate_pat(self) -> str | None:
        """Prompt user for DEVMATE_PAT and validate it."""


class VSCodeCommandsGeneratorPort(Protocol):
    """Port for VS Code tasks/settings generation."""

    def generate_vscode_config(self) -> dict[str, str]:
        """Generate VS Code config files and return file map."""


class VSCodeExtensionsInstallerPort(Protocol):
    """Port for VS Code extension installation management."""

    def copy_extensions_config(self) -> bool:
        """Create merged extensions configuration."""

    def check_vscode_cli_available(self) -> bool:
        """Return True when VS Code CLI is available."""

    def install_missing_extensions(self) -> Tuple[int, int, int]:
        """Install missing extensions.

        Returns:
            Tuple of ``(installed, already_installed, failed)``.
        """


class CopilotInstructionsManagerPort(Protocol):
    """Port for Copilot instructions generation/refresh."""

    def process_instructions(self) -> bool:
        """Generate or refresh Copilot instructions."""


class DevToolingProviderPort(Protocol):
    """Provider abstraction for extracted dev-tooling modules."""

    def configure_git_hooks(
        self,
        jira_project_key: str,
        *,
        regenerate_code_quality_configs: bool = True,
    ) -> None:
        """Configure repository git hooks."""

    def create_mcp_server_configurator(
        self,
        repo_root: Path,
    ) -> MCPServerConfiguratorPort:
        """Create MCP server configurator."""

    def create_vscode_commands_generator(
        self,
        repo_root: Path,
    ) -> VSCodeCommandsGeneratorPort:
        """Create VS Code commands generator."""

    def create_vscode_extensions_installer(
        self,
        repo_root: Path,
    ) -> VSCodeExtensionsInstallerPort:
        """Create VS Code extensions installer."""

    def create_copilot_instructions_manager(
        self,
        repo_root: Path,
    ) -> CopilotInstructionsManagerPort:
        """Create Copilot instructions manager."""
