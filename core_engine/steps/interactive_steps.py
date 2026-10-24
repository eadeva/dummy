"""Interactive steps - user prompts and choice selection.

Provides step types for interactive workflows where developers select
options or enter values at runtime. In CI mode (non-interactive),
defaults are used automatically.
"""

import os
from typing import Any, Optional

from pydantic import Field

from xc_ce_utils import logger
from xc_ce_utils.core_engine.domain.exceptions import (
    AbortError,
    ExecutionStepError,
)
from xc_ce_utils.core_engine.domain.step_registry import StepRegistry
from xc_ce_utils.core_engine.steps.base import (
    BaseStepParams,
    ExecutionStep,
    StepExecutionStatus,
)
from xc_ce_utils.core_engine.steps.execution_set import ExecutionSet
from xc_ce_utils.global_modules.aux_helper import is_running_in_ci


class ChoiceStepParams(BaseStepParams):
    choice_steps: Optional[Any] = Field(default=None)
    cx_default_choice: Optional[Any] = Field(default=None)
    default_choice: Optional[Any] = Field(default=None)
    model_config = {'extra': 'forbid'}


@StepRegistry.register('choice')
class ChoiceStep(ExecutionStep):
    params_model = ChoiceStepParams

    """Present a list of choices to the user and execute the selected sub-step.

    In CI mode, the ``default_choice`` is selected automatically.
    In interactive mode, the user is prompted to select by number.

    Config example::

        step_type: choice
        description: Choose gw_2wp source
        default_choice: local_binaries
        cx_default_choice: download_latest_dev
        choice_steps:
          local_binaries:
            step_type: user_input
            description: Enter path to local gw_2wp binaries
            ...
          download_from_artifactory:
            step_type: art_download_central
            description: Download latest artifact
            ...

    Parameters (in config, not under ``parameters``):
        description (str): Prompt description shown to the user.
        default_choice (str): Key of the default choice_step (used locally and as CI fallback).
        cx_default_choice (str, optional): Key used in CI mode. Falls back to ``default_choice``.
        choice_steps (dict): Mapping of choice keys to step configs.
    """

    def execute(self) -> None:
        description = self.config.get('description', 'Select an option')
        default_choice = self.config.get('default_choice')
        cx_default_choice = self.config.get('cx_default_choice')
        choice_steps = self.config.get('choice_steps', {})

        if not choice_steps:
            msg = f"[{self.name}] 'choice_steps' is empty or missing"
            raise ExecutionStepError(
                msg,
                phase=self.name,
            )

        # Build ordered list of choices
        choices = list(choice_steps.keys())

        if default_choice and default_choice not in choices:
            msg = f"[{self.name}] default_choice '{default_choice}' " 'not found in choice_steps'
            raise ExecutionStepError(
                msg,
                phase=self.name,
            )

        if cx_default_choice and cx_default_choice not in choices:
            msg = (
                f"[{self.name}] cx_default_choice '{cx_default_choice}' "
                'not found in choice_steps'
            )
            raise ExecutionStepError(
                msg,
                phase=self.name,
            )

        # Determine selection
        if is_running_in_ci():
            # Non-interactive: use cx_default_choice if available, else default_choice
            ci_choice = cx_default_choice or default_choice
            if not ci_choice:
                msg = (
                    f'[{self.name}] Running in CI but no '
                    "'cx_default_choice' or 'default_choice' configured"
                )
                raise ExecutionStepError(
                    msg,
                    phase=self.name,
                )
            selected_key = ci_choice
            logger.info(f'[{self.name}] CI mode - auto-selecting: {selected_key}')
        else:
            selected_key = self._prompt_user(description, choices, default_choice, choice_steps)

        # Execute the selected choice
        selected_config = choice_steps[selected_key]
        logger.info(f'[{self.name}] Selected: {selected_key}')

        self._execute_child(selected_key, selected_config)
        self.execution_status = StepExecutionStatus.EXECUTE_SUCCESS

    def _prompt_user(self, description, choices, default_choice, choice_steps):
        """Show interactive prompt and return selected key."""
        default_idx = choices.index(default_choice) + 1 if default_choice else None

        print()
        logger.info(f'[{self.name}] {description}')
        print()

        for i, key in enumerate(choices, start=1):
            step_desc = choice_steps[key].get('description', key)
            marker = ' [DEFAULT]' if key == default_choice else ''
            print(f'  {i}. {step_desc}{marker}')

        print()

        while True:
            try:
                prompt = f'  Enter choice [1-{len(choices)}]'
                if default_idx:
                    prompt += f' (default={default_idx})'
                prompt += ': '

                user_input = input(prompt).strip()

                if not user_input and default_idx:
                    return choices[default_idx - 1]

                selection = int(user_input)
                if 1 <= selection <= len(choices):
                    return choices[selection - 1]

                print(f'  Invalid selection. Please enter a number between 1 and {len(choices)}.')
            except ValueError:
                print(f'  Invalid input. Please enter a number between 1 and {len(choices)}.')
            except KeyboardInterrupt as error:
                msg = f'[{self.name}] Interrupted by user'
                raise AbortError(msg, phase=self.name) from error

    def _execute_child(self, child_name, child_config):
        """Create and execute the selected child step/set."""
        self._inject_child_shared_state(child_config)

        logger.trace(
            f"[{self.name}] _execute_child('{child_name}') resources id={id(self.resources)}, "
            f"downloaders={list(self.resources.get('artifactory_downloaders', {}).keys())}"
        )

        # If the child has nested steps, treat it as a set.
        # If it has a step_type, treat it as a leaf step.
        # Use the execution engine's step factory pattern.

        if 'steps' in child_config or 'choice_steps' in child_config:
            # Composite - has sub-steps (could be another choice or a sequence)
            if 'choice_steps' in child_config and 'steps' not in child_config:
                # It's another nested choice - create as leaf step via registry
                step_type = child_config.get('step_type')
                if step_type:
                    child = self._create_leaf_child(
                        child_name,
                        child_config,
                        missing_type_message=(
                            f"[{self.name}] Selected choice '{child_name}' " "has no 'step_type'"
                        ),
                    )
                    child.run()
                    return

            # Has explicit `steps` -> run as ExecutionSet
            node = self._create_execution_set(
                name=child_name,
                config=child_config,
            )
            node.run()
        else:
            # Leaf step - look up by step_type
            child = self._create_leaf_child(
                child_name,
                child_config,
                missing_type_message=(
                    f"[{self.name}] Selected choice '{child_name}' " "has no 'step_type'"
                ),
            )
            child.run()

    def _child_factory(self, name, config):
        """Step factory for creating child nodes within ExecutionSet."""
        self._inject_child_shared_state(config)

        logger.trace(
            f"[{self.name}] _child_factory('{name}') resources id={id(self.resources)}, "
            f"downloaders={list(self.resources.get('artifactory_downloaders', {}).keys())}"
        )

        if 'steps' in config:
            return self._create_execution_set(
                name=name,
                config=config,
            )

        return self._create_leaf_child(
            name,
            config,
            missing_type_message=f"[{self.name}] Child '{name}' has no 'step_type'",
        )

    def _create_execution_set(self, name, config):
        """Create an ExecutionSet child using current shared runtime state."""
        return ExecutionSet(
            name=name,
            config=config,
            context=self.context,
            step_factory=self._child_factory,
            shared_state=ExecutionSet.SharedState(
                resources=self.resources,
                global_variables=self.global_variables,
            ),
        )

    def _inject_child_shared_state(self, config):
        """Inject shared resources and globals into child config."""
        config.setdefault('_resources', self.resources)
        config.setdefault('_global_variables', self.global_variables)

    def _create_leaf_child(self, name, config, missing_type_message):
        """Create a leaf step child from registry metadata."""
        step_type = config.get('step_type')
        if not step_type:
            raise ExecutionStepError(
                missing_type_message,
                phase=self.name,
            )
        step_class = StepRegistry.get(step_type)
        return step_class(name, config, self.context)


class UserInputStepParams(BaseStepParams):
    cx_default_value: Optional[Any] = Field(default=None)
    default_value: Optional[Any] = Field(default=None)
    model_config = {'extra': 'forbid'}


@StepRegistry.register('user_input')
class UserInputStep(ExecutionStep):
    params_model = UserInputStepParams

    """Prompt the user for a value and store it in an env or global variable.

    In CI mode, the ``default_value`` is used automatically.

    Config example::

        step_type: user_input
        description: Enter path to local gw_2wp binaries
        default_value: _bin/$ENV{XC_CE_UTILS_VARIANT_ALIAS}/build
        cx_default_value: _bin/$ENV{XC_CE_UTILS_VARIANT_ALIAS}/build
        parameters:
          target_env_variable: ARTIFACT_GW_2WP

    Parameters:
        target_env_variable (str): Store the value in ``os.environ[name]``.
        target_global_variable (str): Store the value in ``self.global_variables[name]``.
        At least one of the above must be specified.

    Optional:
        default_value (str): Default shown to user (used locally and as CI fallback).
        cx_default_value (str): Value used in CI mode. Falls back to ``default_value``.
    """

    def execute(self) -> None:
        description = self.config.get('description', 'Enter value')
        default_value = self.config.get('default_value', '')
        cx_default_value = self.config.get('cx_default_value')
        parameters = self.config.get('params', {})

        target_env = parameters.get('target_env_variable')
        target_global = parameters.get('target_global_variable')

        if not target_env and not target_global:
            msg = f"[{self.name}] Must specify 'target_env_variable' or " "'target_global_variable'"
            raise ExecutionStepError(
                msg,
                phase=self.name,
            )

        # Determine value
        if is_running_in_ci():
            # Use cx_default_value if available, else default_value
            ci_value = cx_default_value if cx_default_value is not None else default_value
            if not ci_value:
                msg = (
                    f'[{self.name}] Running in CI but no '
                    "'cx_default_value' or 'default_value' configured"
                )
                raise ExecutionStepError(
                    msg,
                    phase=self.name,
                )
            value = ci_value
            logger.info(f'[{self.name}] CI mode - using: {value}')
        else:
            value = self._prompt_user(description, default_value)

        # Store the value
        if target_env:
            os.environ[target_env] = value
            logger.info(f'[{self.name}] Set env variable: {target_env}={value}')

        if target_global:
            self.global_variables[target_global] = value
            logger.info(f'[{self.name}] Set global variable: {target_global}={value}')

        self.execution_status = StepExecutionStatus.EXECUTE_SUCCESS

    def _prompt_user(self, description, default_value):
        """Show interactive prompt and return entered value."""
        print()
        logger.info(f'[{self.name}] {description}')

        try:
            prompt = '  Enter value'
            if default_value:
                prompt += f' (default: {default_value})'
            prompt += ': '

            user_input = input(prompt).strip()

            if not user_input and default_value:
                return default_value

            return user_input if user_input else default_value
        except KeyboardInterrupt as error:
            msg = f'[{self.name}] Interrupted by user'
            raise AbortError(msg, phase=self.name) from error
