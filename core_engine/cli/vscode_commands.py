"""
VS Code setup for the dynamic CLI.

Generates VS Code configuration files, installs VS Code extensions,
processes Copilot instructions and configures MCP servers.

Originally extracted from :class:`DynamicCLIGenerator` in Phase 4 sub-commit 5
of PR #47.  In Phase 5 we additionally exposed each sub-step as a public
helper so the maintainer-only ``regen-*`` commands and the developer-facing
``refresh-extensions`` command can reuse them without duplicating
console/error-tracking glue.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from rich.console import Console

from xc_ce_utils import logger
from xc_ce_utils.core_engine.application import (
    create_copilot_instructions_manager,
    create_mcp_server_configurator,
    create_vscode_commands_generator,
    create_vscode_extensions_installer,
)

if TYPE_CHECKING:  # pragma: no cover - typing only
    from xc_ce_utils.core_engine.cli.generator import DynamicCLIGenerator


def _get_console() -> Console:
    """Return a local rich console instance.

    Keeps this module decoupled from ``dynamic_cli`` internals.
    """
    return Console()


def _generate_vscode_shared_files(
    generator: 'DynamicCLIGenerator',
) -> dict[str, str]:
    logger.info('Initializing VS Code configuration generator...')
    vs_generator = create_vscode_commands_generator(
        repo_root=generator.repo_root
    )
    logger.info('Generating VS Code configuration files...')
    return vs_generator.generate_vscode_config()


def _build_extension_install_result(installer) -> tuple[int, int, int] | None:
    logger.info('Merging base and project extensions...')
    if installer.copy_extensions_config():
        logger.success(' Extensions configuration created successfully!')
    else:
        logger.warning(' Failed to create extensions.json')

    logger.info('Checking for VS Code CLI...')
    if not installer.check_vscode_cli_available():
        return None

    logger.info('VS Code CLI detected, installing missing extensions...')
    return installer.install_missing_extensions()


def _process_copilot_instructions(generator: 'DynamicCLIGenerator') -> bool:
    copilot_manager = create_copilot_instructions_manager(
        repo_root=generator.repo_root
    )
    return copilot_manager.process_instructions()


def _process_mcp_configuration(generator: 'DynamicCLIGenerator') -> bool:
    mcp_configurator = create_mcp_server_configurator(
        repo_root=generator.repo_root
    )
    return mcp_configurator.run()


# ---------------------------------------------------------------------------
# Granular helpers — each one mutates exactly one slice of generated state.
# These are public API: command_factory builds the maintainer-only regen-*
# commands and the developer refresh-extensions command on top of them.
# ---------------------------------------------------------------------------


def regen_vscode_shared(generator: 'DynamicCLIGenerator') -> bool:
    """Regenerate committed ``.vscode/`` files (tasks/extensions/settings).

    Returns ``True`` on success, ``False`` when any sub-step failed. Errors
    are tracked on ``generator`` so callers can surface them in the final
    summary.
    """
    console = _get_console()

    print()
    console.print(' [bold cyan]VS Code Configuration Generator[/bold cyan]')
    print()

    start = time.time()
    try:
        generated_files = _generate_vscode_shared_files(generator)
    except Exception as e:
        duration = time.time() - start
        error_msg = f'Failed to generate VS Code configuration: {e}'
        logger.error(error_msg)
        generator.add_error(error_msg, 'VS Code Configuration')
        generator.track_operation('VS Code Configuration', 'error', duration)
        return False

    duration = time.time() - start
    console.print(
        ' [bold green]VS Code configuration files generated successfully![/bold green]'
    )
    console.print('[bold]Generated files:[/bold]')
    for config_type, file_path in generated_files.items():
        console.print(f'  \u2022 [cyan]{config_type}[/cyan]: {file_path}')
    generator.track_operation('VS Code Configuration', 'success', duration)
    return True


def refresh_vscode_extensions(generator: 'DynamicCLIGenerator') -> bool:
    """Install / refresh VS Code extensions (user-local; no repo writes).

    Returns ``True`` on success or graceful skip, ``False`` on hard
    failures. Missing ``code`` CLI is treated as a graceful skip with an
    actionable hint, *not* as a failure — see the matching outcome
    handling in ``setup/vscode/extensions.py``.
    """
    console = _get_console()

    print()
    console.print(' [bold cyan]Installing VS Code Extensions[/bold cyan]')
    logger.info('Initializing VS Code extension installer...')

    start = time.time()
    try:
        installer = create_vscode_extensions_installer(
            repo_root=generator.repo_root
        )
        install_result = _build_extension_install_result(installer)
    except Exception as e:
        duration = time.time() - start
        error_msg = f'Failed to install VS Code extensions: {e}'
        logger.error(error_msg)
        generator.add_error(error_msg, 'VS Code Extensions')
        generator.track_operation('VS Code Extensions', 'error', duration)
        return False

    duration = time.time() - start
    if install_result is None:
        logger.warning(
            ' VS Code CLI not available, skipping extension installation'
        )
        logger.info(' To enable automatic extension installation:')
        logger.info('   1. Install VS Code from https://code.visualstudio.com')
        logger.info(
            "   2. Run 'Shell Command: Install code command in PATH' from VS Code"
        )
        logger.info('   3. Or add VS Code to your system PATH manually')
        generator.track_operation('VS Code Extensions', 'success', duration)
        return True

    _installed, _already_installed, failed = install_result
    if failed > 0:
        logger.warning(
            f' Extension installation completed with {failed} failure(s)'
        )
        generator.track_operation('VS Code Extensions', 'warning', duration)
        generator.add_warning(
            f'{failed} extension(s) failed to install',
            'VS Code Extensions',
        )
        return False

    logger.success(' Extension installation completed successfully!')
    generator.track_operation('VS Code Extensions', 'success', duration)
    return True


def regen_copilot_instructions(generator: 'DynamicCLIGenerator') -> bool:
    """Regenerate ``.github/copilot-instructions.md`` (committed file)."""
    console = _get_console()

    print()
    console.print(' [bold cyan]Processing Copilot Instructions[/bold cyan]')
    logger.info('Initializing Copilot instructions manager...')

    start = time.time()
    try:
        copilot_success = _process_copilot_instructions(generator)
    except FileNotFoundError as e:
        duration = time.time() - start
        warning_msg = f'Copilot configuration not found: {e}'
        logger.warning(warning_msg)
        generator.add_warning(warning_msg, 'Copilot Instructions')
        generator.track_operation('Copilot Instructions', 'warning', duration)
        return False
    except Exception as e:
        duration = time.time() - start
        error_msg = f'Failed to process Copilot instructions: {e}'
        logger.error(error_msg)
        generator.add_error(error_msg, 'Copilot Instructions')
        generator.track_operation('Copilot Instructions', 'error', duration)
        return False

    duration = time.time() - start
    if copilot_success:
        logger.success(' Copilot instructions processed successfully!')
        generator.track_operation('Copilot Instructions', 'success', duration)
        return True

    logger.warning(' Copilot instructions processing completed with warnings')
    generator.track_operation('Copilot Instructions', 'warning', duration)
    generator.add_warning(
        'Copilot instructions processing completed with warnings',
        'Copilot Instructions',
    )
    return False


def regen_mcp_json(generator: 'DynamicCLIGenerator') -> bool:
    """Regenerate committed ``.vscode/mcp.json`` from the MCP server registry."""
    console = _get_console()

    print()
    console.print(' [bold cyan]Configuring MCP Servers[/bold cyan]')
    logger.info('Initializing MCP server configurator...')

    start = time.time()
    try:
        mcp_success = _process_mcp_configuration(generator)
    except Exception as e:
        duration = time.time() - start
        error_msg = f'Failed to configure MCP servers: {e}'
        logger.error(error_msg)
        generator.add_error(error_msg, 'MCP Configuration')
        generator.track_operation('MCP Configuration', 'error', duration)
        return False

    duration = time.time() - start
    if mcp_success:
        logger.success(' MCP servers configured successfully!')
        generator.track_operation('MCP Configuration', 'success', duration)
        return True

    logger.warning(' MCP server configuration completed with warnings')
    generator.track_operation('MCP Configuration', 'warning', duration)
    generator.add_warning(
        'MCP server configuration completed with warnings',
        'MCP Configuration',
    )
    return False


# ---------------------------------------------------------------------------
# Orchestrator — retained as an internal helper for composing multiple
# VS Code setup operations.
# ---------------------------------------------------------------------------


def run_setup(generator: 'DynamicCLIGenerator') -> None:
    """Generate VS Code configuration files for the build system."""
    generator.start_execution()

    regen_vscode_shared(generator)
    refresh_vscode_extensions(generator)
    regen_copilot_instructions(generator)
    regen_mcp_json(generator)

    logger.success('You can now:')
    logger.info(
        "  \u2022 Use Ctrl+Shift+P \u2192 'Tasks: Run Task' for build tasks"
    )
    logger.info('  \u2022 Access MCP servers in GitHub Copilot Chat')
    generator.print_final_summary()
