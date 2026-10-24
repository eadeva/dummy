"""Bazel build steps.
"""

import os
from typing import Any, Dict, Optional

from pydantic import Field

from xc_ce_utils.core_engine.domain.exceptions import ConfigurationError
from xc_ce_utils.core_engine.domain.step_registry import StepRegistry
from xc_ce_utils.core_engine.generators.definitions_generator import (
    DefinitionsGenerator,
)
from xc_ce_utils.core_engine.steps.base import BaseStepParams, WrappedStep


class _BazelStepBase(WrappedStep):
    """Shared helpers for Bazel-based steps."""

    WRAPPER_NAME = 'bazel'

    def _create_bazel_wrapper(
        self,
        *,
        workspace_dir: Optional[str] = None,
        deploy_binaries: Optional[bool] = None,
        use_cache: Optional[bool] = None,
    ) -> Any:
        """Create a Bazel wrapper with common context-driven defaults."""
        wrapper_cls = self.get_wrapper()

        option_kwargs: Dict[str, Any] = {'bin_folder': self.context.bin_folder}
        if deploy_binaries is not None:
            option_kwargs['deploy_binaries'] = deploy_binaries
        if use_cache is not None:
            option_kwargs['use_cache'] = use_cache

        return wrapper_cls(
            log_folder=self.get_step_log_folder(),
            workspace_dir=workspace_dir or self.context.repo_path,
            options=wrapper_cls.Options(**option_kwargs),
        )


class BazelExecutionStepParams(BaseStepParams):
    deploy_binaries: Optional[Any] = Field(default=None)
    target: Optional[Any] = Field(default=None)
    model_config = {'extra': 'forbid'}


@StepRegistry.register('bazel_build')
class BazelExecutionStep(_BazelStepBase):
    params_model = BazelExecutionStepParams

    """Bazel build step."""

    def validate(self) -> None:
        """Validate Bazel build configuration."""
        # Target and additional_args are optional, so no strict validation needed
        pass

    def execute(self) -> None:
        """Execute Bazel build."""
        self._generate_native_definitions_if_needed()

        target = self.config.get('target', '//...')
        params = self.config.get('params', [])
        deploy_binaries = self.config.get('deploy_binaries', True)

        bazel = self._create_bazel_wrapper(
            workspace_dir=os.environ['REPO_PATH'],
            deploy_binaries=deploy_binaries,
            use_cache=not self.context.no_cache,
        )

        # Execute build
        bazel.build(
            target=target,
            compilation_mode=self._resolve_compilation_mode(self.context.build_type),
            additional_args=params,
            clean=self.context.rebuild,
        )

    def _generate_native_definitions_if_needed(self) -> None:
        """Generate native definitions unless Conan toolchain is active."""
        if self.config.get('conan_toolchain', False):
            return
        generator = DefinitionsGenerator(self.context)
        generator.write_bazel(self.context.build_folder)

    @staticmethod
    def _resolve_compilation_mode(build_type: Optional[str]) -> str:
        """Map CMake-like build types to Bazel compilation mode."""
        compilation_mode_map = {
            'Debug': 'dbg',
            'Release': 'opt',
            'RelWithDebInfo': 'fastbuild',
            'MinSizeRel': 'opt',
        }
        resolved_build_type = build_type or 'Release'
        return compilation_mode_map.get(resolved_build_type, 'opt')


class BazelTestStepParams(BaseStepParams):
    additional_args: Optional[Any] = Field(default=None)
    target: Optional[Any] = Field(default=None)
    test_output: Optional[Any] = Field(default=None)
    model_config = {'extra': 'forbid'}


@StepRegistry.register('bazel_test')
class BazelTestStep(_BazelStepBase):
    params_model = BazelTestStepParams

    """Bazel test step."""

    def validate(self) -> None:
        """Validate Bazel test configuration."""
        pass

    def execute(self) -> None:
        """Execute Bazel tests."""
        target = self.config.get('target', '//...')
        test_output = self.config.get('test_output', 'errors')
        additional_args = self.config.get('additional_args', [])

        bazel = self._create_bazel_wrapper()

        # Execute tests
        bazel.test(
            target=target,
            test_output=test_output,
            additional_args=additional_args,
        )


class BazelRunStepParams(BaseStepParams):
    additional_bazel_args: Optional[Any] = Field(default=None)
    target: Optional[Any] = Field(default=None)
    model_config = {'extra': 'forbid'}


@StepRegistry.register('bazel_run')
class BazelRunStep(_BazelStepBase):
    params_model = BazelRunStepParams

    """Bazel run step."""

    def validate(self) -> None:
        """Validate Bazel run configuration."""
        if 'target' not in self.config:
            msg = "Bazel run step requires 'target' configuration"
            raise ConfigurationError(msg)

    def execute(self) -> None:
        """Execute Bazel run."""
        target = self.config['target']
        params = self.config.get('params', [])
        additional_bazel_args = self.config.get('additional_bazel_args', [])

        bazel = self._create_bazel_wrapper()

        # Execute run
        bazel.run(
            target=target,
            args=params,
            additional_bazel_args=additional_bazel_args,
        )


class BazelCleanStepParams(BaseStepParams):
    expunge: Optional[Any] = Field(default=None)
    model_config = {'extra': 'forbid'}


@StepRegistry.register('bazel_clean')
class BazelCleanStep(_BazelStepBase):
    params_model = BazelCleanStepParams

    """Bazel clean step."""

    def validate(self) -> None:
        """Validate Bazel clean configuration."""
        pass

    def execute(self) -> None:
        """Execute Bazel clean."""
        expunge = self.config.get('expunge', False)
        bazel = self._create_bazel_wrapper()

        # Execute clean
        bazel.clean(expunge=expunge)


class BazelQueryStepParams(BaseStepParams):
    additional_args: Optional[Any] = Field(default=None)
    output_format: Optional[Any] = Field(default=None)
    query_expression: Optional[Any] = Field(default=None)
    model_config = {'extra': 'forbid'}


@StepRegistry.register('bazel_query')
class BazelQueryStep(_BazelStepBase):
    params_model = BazelQueryStepParams

    """Bazel query step."""

    def validate(self) -> None:
        """Validate Bazel query configuration."""
        if 'query_expression' not in self.config:
            msg = "Bazel query step requires 'query_expression' configuration"
            raise ConfigurationError(msg)

    def execute(self) -> None:
        """Execute Bazel query."""
        query_expression = self.config['query_expression']
        output_format = self.config.get('output_format', 'label')
        additional_args = self.config.get('additional_args', [])

        bazel = self._create_bazel_wrapper()

        # Execute query
        bazel.query(
            query_expression=query_expression,
            output_format=output_format,
            additional_args=additional_args,
        )
