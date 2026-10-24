"""Make build steps.
"""

from typing import Any, Optional

from pydantic import Field

from xc_ce_utils.core_engine.domain.step_registry import StepRegistry
from xc_ce_utils.core_engine.steps.base import BaseStepParams, WrappedStep


class MakeCleanStepParams(BaseStepParams):
    pass
    model_config = {'extra': 'forbid'}


@StepRegistry.register('make_clean')
class MakeCleanStep(WrappedStep):
    params_model = MakeCleanStepParams

    """Make clean build step."""

    WRAPPER_NAME = 'make'

    def execute(self) -> None:
        """Execute make clean."""
        if not self.context.make_wrapper:
            RBMakeWrapper = self.get_wrapper()
            step_log_folder = self.get_step_log_folder()
            self.context.make_wrapper = RBMakeWrapper(log_folder=step_log_folder)

        self.context.make_wrapper.clean()


class MakeStepParams(BaseStepParams):
    conan_toolchain: Optional[Any] = Field(default=None)
    target: Optional[Any] = Field(default=None)
    variables: Optional[Any] = Field(default=None)
    model_config = {'extra': 'forbid'}


@StepRegistry.register('make')
class MakeStep(WrappedStep):
    params_model = MakeStepParams

    """Make build step."""

    WRAPPER_NAME = 'make'

    def execute(self) -> None:
        """Execute make build."""
        if not self.context.make_wrapper:
            RBMakeWrapper = self.get_wrapper()
            step_log_folder = self.get_step_log_folder()
            self.context.make_wrapper = RBMakeWrapper(log_folder=step_log_folder)

        # Generate native definitions file (skipped when conan_toolchain is used)
        if not self.config.get('conan_toolchain', False):
            from xc_ce_utils.core_engine.generators.definitions_generator import (
                DefinitionsGenerator,
            )

            gen = DefinitionsGenerator(self.context)
            gen.write_make(self.context.build_folder)

        target = self.config.get('target', 'all')
        make_variables = self.config.get('variables', None)
        self.context.make_wrapper.build(target, variables=make_variables)
