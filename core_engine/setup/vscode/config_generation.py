"""VS Code configuration generation mixin for environment setup.

This mixin keeps VS Code project configuration generation separate from
the main ``EnvironmentSetup`` orchestration class.
"""

from __future__ import annotations

import traceback

from xc_ce_utils.core_engine.adapters.dev_tooling.adapter import (
    create_copilot_instructions_manager,
    create_vscode_commands_generator,
)
from xc_ce_utils.rb_logger import logger


class VSCodeConfigGenerationMixin:
    """Provide VS Code configuration generation behavior.

    Expects the consuming class to define ``self.repo_path``.
    """

    def _generate_tasks_and_settings(self) -> dict[str, str]:
        commands_gen = create_vscode_commands_generator(  # type: ignore[attr-defined]
            repo_root=self.repo_path
        )
        return commands_gen.generate_vscode_config()

    def _generate_copilot_instructions(self) -> bool:
        copilot_gen = create_copilot_instructions_manager(  # type: ignore[attr-defined]
            repo_root=self.repo_path
        )
        return copilot_gen.process_instructions()

    @staticmethod
    def _log_generation_error(exc: Exception) -> None:
        if isinstance(exc, ImportError):
            logger.error(f'Could not import VS Code configurators: {exc}')
            logger.info('Ensure xc_ce_utils.vs_code_configurator is available')
            return
        logger.error(f'Failed to generate VS Code configuration: {exc}')
        logger.debug(traceback.format_exc())

    def generate_vscode_config(self) -> bool:
        """Generate VS Code configuration and Copilot instruction files."""
        logger.log_phase_header('VS CODE CONFIGURATION')

        logger.progress('Generating VS Code tasks and settings...')
        try:
            generated_files = self._generate_tasks_and_settings()
        except (
            ImportError,
            OSError,
            RuntimeError,
            ValueError,
            TypeError,
        ) as exc:
            self._log_generation_error(exc)
            return False

        if not generated_files:
            logger.error('Failed to generate VS Code tasks and settings')
            return False

        logger.progress('Generating GitHub Copilot instructions...')
        try:
            copilot_success = self._generate_copilot_instructions()
        except (
            ImportError,
            OSError,
            RuntimeError,
            ValueError,
            TypeError,
        ) as exc:
            self._log_generation_error(exc)
            return False

        if not copilot_success:
            logger.error('Failed to generate Copilot instructions')
            return False

        logger.success('VS Code configuration generated successfully')
        return True
