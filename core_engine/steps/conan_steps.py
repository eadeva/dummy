"""Conan package manager build steps.
"""

from __future__ import annotations

import os
import shlex
from pathlib import Path
from typing import Any, List, Optional

from pydantic import Field

from xc_ce_utils.core_engine.domain.exceptions import (
    ConfigurationError,
    ExecutionStepError,
)
from xc_ce_utils.core_engine.domain.step_registry import StepRegistry
from xc_ce_utils.core_engine.steps.base import BaseStepParams, ExecutionStep
from xc_ce_utils.global_modules.aux_helper import run_command
from xc_ce_utils.global_modules.uv_sidecar import find_uvx


class ConanCommandStepParams(BaseStepParams):
    operation: Optional[Any] = Field(default=None)
    model_config = {'extra': 'forbid'}


@StepRegistry.register('conan_command')
class ConanCommandStep(ExecutionStep):
    params_model = ConanCommandStepParams

    """Run a generic Conan command.

    The command is executed directly through uvx-based Conan runtime.

    Config parameters:
        params (list[str] | str | dict): Conan CLI arguments after the ``conan`` token.
            Example: ``["list", "pkg/*"]`` or ``"list pkg/*"``.
            Dict form must include one of ``command`` or ``cmd``.
        operation (str): Optional operation label used for log file naming.
    """

    _DEFAULT_CONAN_UVX_SPEC = 'conan==2.12.0'

    @classmethod
    def _get_conan_uvx_spec(cls) -> str:
        """Return Conan package spec used by uvx (env-overridable)."""
        env_spec = os.environ.get('XC_CE_UTILS_CONAN_UVX_SPEC', '').strip()
        return env_spec or cls._DEFAULT_CONAN_UVX_SPEC

    @classmethod
    def _build_conan_command(cls, args: List[str]) -> List[str]:
        """Build uvx command line for Conan execution."""
        uvx_path = find_uvx()
        if uvx_path is None:
            msg = 'uvx executable not found'
            raise ExecutionStepError(msg)
        return [
            str(uvx_path),
            '--from',
            cls._get_conan_uvx_spec(),
            'conan',
            *args,
        ]

    @staticmethod
    def _normalize_params(params: Any) -> List[str]:
        """Normalize params into a non-empty list of strings."""
        if isinstance(params, dict):
            for key in ('command', 'cmd'):
                if key in params:
                    return ConanCommandStep._normalize_params(params[key])
            msg = "Conan command step 'params' dict must contain one of: command, cmd"
            raise ConfigurationError(msg)

        args = params
        if isinstance(args, str):
            parsed = shlex.split(args, posix=False)
            if not parsed:
                msg = "Conan command step requires non-empty 'params'"
                raise ConfigurationError(msg)
            return parsed

        if not isinstance(args, list):
            msg = "Conan command step 'params' must be a list[str], " 'string, or dict'
            raise ConfigurationError(msg)

        if not args:
            msg = "Conan command step requires non-empty 'params'"
            raise ConfigurationError(msg)

        if any(not isinstance(item, str) or not item.strip() for item in args):
            msg = "Conan command step 'params' entries must be non-empty strings"
            raise ConfigurationError(msg)

        return args

    def validate(self) -> None:
        """Validate Conan command configuration."""
        if 'params' not in self.config:
            msg = "Conan command step requires 'params' configuration"
            raise ConfigurationError(msg)

        self._normalize_params(self.config['params'])

    def execute(self) -> None:
        """Execute the configured Conan command."""
        step_build_folder = self.get_step_build_folder()
        step_log_folder = self.get_step_log_folder()
        step_build_folder.mkdir(parents=True, exist_ok=True)
        step_log_folder.mkdir(parents=True, exist_ok=True)

        args = self._normalize_params(self.config['params'])
        operation = self.config.get('operation', self.name)
        command = self._build_conan_command(args)
        run_command(
            command,
            log_file=step_log_folder / f'{operation}.log',
            cwd=Path(step_build_folder),
        )
