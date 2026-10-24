"""File and directory search steps."""

from pathlib import Path

from xc_ce_utils import logger
from xc_ce_utils.core_engine.domain.exceptions import (
    AbortError,
    ExecutionStepError,
    RuntimeConfigError,
)
from xc_ce_utils.core_engine.domain.step_registry import StepRegistry
from xc_ce_utils.core_engine.steps.base import (
    BaseStepParams,
    ExecutionStep,
    StepConfStatus,
    StepEvaluationStatus,
    StepExecutionStatus,
)
from xc_ce_utils.global_modules.find_regex_files_in_path import (
    find_regex_dirs_in_path,
    find_regex_files_in_path,
)


class FileFindStepParams(BaseStepParams):
    pass
    model_config = {'extra': 'forbid'}


@StepRegistry.register('file_find')
class FileFindStep(ExecutionStep):
    params_model = FileFindStepParams

    """Find files matching a regex pattern in a given path.

    Searches for files whose names match the supplied regular expression.
    The resolved absolute path of the first hit is stored in
    ``self.global_variables[output_variable]``.

    Config parameters:
        output_variable (str): Name of the global variable to store the result.
        regex (str):           Regular expression for matching file names.
        path (str):            Directory path to search in.
    """

    def execute(self) -> None:
        """Execute the file_find step."""
        try:
            self.pre_processing()
            parameters = self.config.get('params', {})

            output_variable = parameters['output_variable']
            file_regex = parameters['regex']
            path = parameters['path']

            logger.info(f'[{self.name}] Searching for files with regex: {file_regex}')
            hits = find_regex_files_in_path(path, file_regex)

            if len(hits) > 0:
                self.result_string.append('Found files:')
                for hit in hits:
                    self.result_string.append(str(hit))

                self.global_variables[output_variable] = str(Path(hits[0]).resolve())
                self.test_status = StepEvaluationStatus.PASSED
                logger.success(f'[{self.name}] Found files: {hits}')
            else:
                self.result_string.append('No hits found.')
                self.test_status = StepEvaluationStatus.FAILED
                logger.error(f'[{self.name}] No hits found')

            self.execution_status = StepExecutionStatus.EXECUTE_SUCCESS

        except RuntimeConfigError as e:
            self.execution_status = StepConfStatus.CONFIGURE_FAILED
            self.abort(e, abort_execution=True)
        except (ExecutionStepError, AbortError):
            self.execution_status = StepExecutionStatus.EXECUTE_FAILED
            raise
        except KeyboardInterrupt:
            message = f'[{self.name}] Interrupted by user'
            self.execution_status = StepExecutionStatus.USER_INTERRUPTED
            self.abort(AbortError(message, phase=self.name), abort_execution=True)
        except Exception as e:
            message = f'[{self.name}] Searching for files with regex: {e!s}'
            self.execution_status = StepExecutionStatus.EXECUTE_FAILED
            self.abort(
                ExecutionStepError(message, phase=self.name),
                abort_execution=self.game_stopper,
            )


class DirFindStepParams(BaseStepParams):
    pass
    model_config = {'extra': 'forbid'}


@StepRegistry.register('dir_find')
class DirFindStep(ExecutionStep):
    params_model = DirFindStepParams

    """Find directories matching a regex pattern in a given path.

    Searches for directories whose names match the supplied regular
    expression.  The list of hits is stored in
    ``self.global_variables[output_variable]``.

    Config parameters:
        output_variable (str): Name of the global variable to store the result.
        regex (str):           Regular expression for matching directory names.
        path (str):            Directory path to search in.
    """

    def execute(self) -> None:
        """Execute the dir_find step."""
        try:
            self.pre_processing()
            parameters = self.config.get('params', {})

            output_variable = parameters['output_variable']
            regex = parameters['regex']
            path = parameters['path']

            logger.info(f'[{self.name}] Searching for dirs with regex: {regex}')
            hits = find_regex_dirs_in_path(path, regex)
            self.global_variables[output_variable] = hits

            if len(hits) > 0:
                self.result_string.append('Found directories:')
                for hit in hits:
                    self.result_string.append(str(hit))

                self.test_status = StepEvaluationStatus.PASSED
                logger.success(f'[{self.name}] Found dirs: {hits}')
            else:
                self.result_string.append('No hits found.')
                self.test_status = StepEvaluationStatus.FAILED
                logger.error(f'[{self.name}] No hits found')

            self.execution_status = StepExecutionStatus.EXECUTE_SUCCESS

        except RuntimeConfigError as e:
            self.execution_status = StepConfStatus.CONFIGURE_FAILED
            self.abort(e, abort_execution=True)
        except (ExecutionStepError, AbortError):
            self.execution_status = StepExecutionStatus.EXECUTE_FAILED
            raise
        except KeyboardInterrupt:
            message = f'[{self.name}] Interrupted by user'
            self.execution_status = StepExecutionStatus.USER_INTERRUPTED
            self.abort(AbortError(message, phase=self.name), abort_execution=True)
        except Exception as e:
            message = f'[{self.name}] Searching for dirs with regex: {e!s}'
            self.execution_status = StepExecutionStatus.EXECUTE_FAILED
            self.abort(
                ExecutionStepError(message, phase=self.name),
                abort_execution=self.game_stopper,
            )


class FileTextLogScanStepParams(BaseStepParams):
    pass
    model_config = {'extra': 'forbid'}


@StepRegistry.register('file_text_log_scan')
class FileTextLogScanStep(ExecutionStep):
    params_model = FileTextLogScanStepParams

    """Scan a text/log file for expected strings.

    Opens a file and searches for a list of expected strings.  When
    ``order_relevant`` is True the strings must appear in the given order.

    Config parameters:
        file_path (str):        Path to the file to scan.
        expected_strs (list):   List of strings expected in the file.
        order_relevant (bool):  Whether the order of strings matters
                                (default False).
    """

    def execute(self) -> None:
        """Execute the file_text_log_scan step."""
        try:
            self.pre_processing()
            parameters = self.config.get('params', {})

            file_path = parameters['file_path']
            texts = parameters['expected_strs']
            order_relevant = parameters.get('order_relevant', False)

            with open(file_path, 'r') as file:
                content = file.read()

            logger.info(f'[{self.name}] Searching for strings in file: {file_path}')
            self.check_output(content, texts, order_relevant)
            self.execution_status = StepExecutionStatus.EXECUTE_SUCCESS

        except RuntimeConfigError as e:
            self.execution_status = StepConfStatus.CONFIGURE_FAILED
            self.abort(e, abort_execution=True)
        except (ExecutionStepError, AbortError):
            # For file_text_log_scan do not overwrite
            # execution_status when the action itself raised an execution
            # exception â€” preserve that behaviour.
            raise
        except KeyboardInterrupt:
            message = f'[{self.name}] Interrupted by user'
            self.execution_status = StepExecutionStatus.USER_INTERRUPTED
            self.abort(AbortError(message, phase=self.name), abort_execution=True)
        except Exception as e:
            message = f'[{self.name}] Unknown exception: {e!s}'
            self.execution_status = StepExecutionStatus.EXECUTE_FAILED
            self.abort(
                ExecutionStepError(message, phase=self.name),
                abort_execution=self.game_stopper,
            )
