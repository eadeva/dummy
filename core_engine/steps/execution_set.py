"""
ExecutionSet — composite node that contains child steps or nested sets.

Supports sequential (default) and parallel execution via ThreadPoolExecutor.
"""

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterator, List, Optional, Tuple

from xc_ce_utils import logger
from xc_ce_utils.core_engine.domain.exceptions import (
    AbortError,
    BuildError,
    ContinueWithErrorsError,
    is_reported,
)
from xc_ce_utils.core_engine.steps.base import (
    ExecutionNode,
    StepExecutionStatus,
)


def _detail(error: BaseException) -> str:
    """Return ``': <error>'`` unless the error was already printed."""
    return '' if is_reported(error) else f': {error}'


@dataclass(frozen=True)
class ExecutionSetSharedState:
    """Shared mutable execution state passed to set and child nodes."""

    resources: Dict[str, Any]
    global_variables: Dict[str, Any]


class ExecutionSet(ExecutionNode):
    """Composite node containing an ordered list of child execution nodes.

    Implements the Composite pattern: an ExecutionSet is itself an
    ExecutionNode, so sets can be nested inside other sets.

    Supports two execution modes:
    - **Sequential** (default): children run one after another.
    - **Parallel** (``parallel=True``): children run concurrently via ThreadPoolExecutor.

    Children are created lazily from config dicts using a ``step_factory``
    callable so that runtime config changes from earlier steps are visible
    to later ones (important for sequential mode).

    Args:
        name: Set name.
        config: Set configuration dict (from YAML/JSON config).
        context: Execution context (``ActionConfiguration``).
        step_factory: Callable ``(name, config) -> ExecutionNode`` used
            to create child nodes.
        shared_state: Shared resource/global-variable state.
    """

    SharedState = ExecutionSetSharedState

    def __init__(
        self,
        name: str,
        config: Dict[str, Any],
        context: Any,
        step_factory: Callable[[str, Dict[str, Any]], ExecutionNode],
        shared_state: Optional[ExecutionSetSharedState] = None,
    ):
        super().__init__(name, config, context)

        self.parallel: bool = config.get('parallel', False)
        self.step_factory = step_factory
        self.children_config: Dict[str, Dict[str, Any]] = config.get(
            'steps', {}
        )
        self.children: List[ExecutionNode] = []
        self.errors = False

        resolved_shared_state = shared_state or ExecutionSetSharedState(
            resources=getattr(context, 'resources', {}),
            global_variables=getattr(context, 'global_variables', {}),
        )
        self.resources: Dict = resolved_shared_state.resources
        self.global_variables: Dict = resolved_shared_state.global_variables

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Run all child nodes sequentially or in parallel."""
        if self.omitted:
            logger.info(
                f'[SET:{self.name}] Set is omitted based on configuration. Skipping.'
            )
            return

        logger.log_phase_header(f'SET {self.name.upper()}')
        try:
            self._run_children()
        except (AbortError, BuildError):
            self.execution_status = StepExecutionStatus.EXECUTE_FAILED
            raise
        except Exception as e:
            self.execution_status = StepExecutionStatus.EXECUTE_FAILED
            msg = f"Set '{self.name}' failed: {e}"
            raise BuildError(msg) from e
        else:
            self._finalize_execution_status()
        finally:
            logger.log_phase_header(f'SET {self.name.upper()} - END')

    def _run_children(self) -> None:
        """Dispatch child execution according to set mode."""
        if self.parallel:
            self._run_parallel()
            return
        self._run_sequential()

    def _finalize_execution_status(self) -> None:
        """Emit terminal set status once child execution ends."""
        if self.errors:
            logger.warning(f'[SET:{self.name}] Completed with errors')
            return

        self.execution_status = StepExecutionStatus.EXECUTE_SUCCESS
        logger.success(f'[SET:{self.name}] Completed successfully')

    # ------------------------------------------------------------------
    # Sequential execution
    # ------------------------------------------------------------------

    def _run_sequential(self) -> None:
        """Create and execute children one at a time (lazy creation)."""
        for step_name, step_conf in self._iter_enabled_children():
            try:
                node = self._create_child_node(step_name, step_conf)
                if node is None:
                    continue
                self._run_child_node(node, step_conf)

            except AbortError as e:
                logger.critical(f'[SET:{self.name}] Abort{_detail(e)}')
                msg = f"Set '{self.name}' aborted: {e}"
                raise BuildError(msg) from e
            except ContinueWithErrorsError:
                self.errors = True
                logger.warning(
                    f'[SET:{self.name}][{step_name}] Continuing after error'
                )
                continue
            except KeyboardInterrupt as e:
                logger.critical(f'[SET:{self.name}] Interrupted by user')
                msg = f"Set '{self.name}' interrupted by user"
                raise BuildError(msg) from e
            except Exception as e:
                self._handle_sequential_step_error(step_name, step_conf, e)

    def _create_child_node(
        self,
        step_name: str,
        step_conf: Dict[str, Any],
    ) -> Optional[ExecutionNode]:
        """Inject shared state and lazily create a child node."""
        step_conf.setdefault('_resources', self.resources)
        step_conf.setdefault('_global_variables', self.global_variables)
        node = self.step_factory(step_name, step_conf)
        if node is None:
            return None
        self.children.append(node)
        return node

    def _run_child_node(
        self,
        node: ExecutionNode,
        step_conf: Dict[str, Any],
    ) -> None:
        """Execute a child node in blocking or non-blocking mode."""
        if step_conf.get('non_blocking', False):
            self._execute_non_blocking(node)
            return
        node.run()

    def _handle_sequential_step_error(
        self,
        step_name: str,
        step_conf: Dict[str, Any],
        error: Exception,
    ) -> None:
        """Handle sequential child errors according to game-stopper policy."""
        if not step_conf.get('game_stopper', True):
            self.errors = True
            logger.warning(
                f'[SET:{self.name}][{step_name}] Failed (non-critical){_detail(error)}'
            )
            return

        logger.critical(
            f'[SET:{self.name}][{step_name}] Game stopper - aborting{_detail(error)}'
        )
        msg = f"Set '{self.name}' step '{step_name}' failed: {error}"
        raise BuildError(msg) from error

    # ------------------------------------------------------------------
    # Parallel execution
    # ------------------------------------------------------------------

    def _run_parallel(self) -> None:
        """Create all children eagerly, then execute them in parallel via ThreadPoolExecutor."""
        nodes = self._collect_parallel_nodes()

        if not nodes:
            logger.info(f'[SET:{self.name}] No steps to execute')
            return

        self._log_parallel_start(nodes)
        errors, game_stopper_hit = self._execute_parallel_nodes(nodes)

        if game_stopper_hit:
            msg = (
                f"Set '{self.name}' parallel execution failed: "
                f'{len(errors)} error(s) - {errors[0]}'
            )
            raise BuildError(msg)

    def _collect_parallel_nodes(self) -> List[ExecutionNode]:
        """Create all runnable child nodes for parallel execution."""
        nodes: List[ExecutionNode] = []
        for step_name, step_conf in self._iter_enabled_children():
            node = self._create_child_node(step_name, step_conf)
            if node is not None:
                nodes.append(node)
        return nodes

    def _log_parallel_start(self, nodes: List[ExecutionNode]) -> None:
        """Log the list of child nodes being started in parallel mode."""
        node_names = [node.name for node in nodes]
        logger.info(
            f"[SET:{self.name}] Running {len(nodes)} steps in parallel: {', '.join(node_names)}"
        )

    def _execute_parallel_nodes(
        self,
        nodes: List[ExecutionNode],
    ) -> Tuple[List[Exception], bool]:
        """Execute parallel nodes and return (errors, game_stopper_hit)."""
        errors: List[Exception] = []
        game_stopper_hit = False

        with ThreadPoolExecutor(max_workers=len(nodes)) as executor:
            future_to_node = {executor.submit(node.run): node for node in nodes}
            try:
                for future in as_completed(future_to_node):
                    node = future_to_node[future]
                    if self._handle_parallel_future(node, future, errors):
                        game_stopper_hit = True
            except KeyboardInterrupt as error:
                self._cancel_parallel_futures(future_to_node)
                msg = f"Set '{self.name}' interrupted by user"
                raise BuildError(msg) from error

        return errors, game_stopper_hit

    def _handle_parallel_future(
        self,
        node: ExecutionNode,
        future,
        errors: List[Exception],
    ) -> bool:
        """Handle a single completed parallel future.

        Returns True when a game-stopper error was detected.
        """
        try:
            future.result()
            return False
        except (AbortError, BuildError) as error:
            errors.append(error)
            logger.critical(
                f'[SET:{self.name}][{node.name}] Game stopper in parallel{_detail(error)}'
            )
            return True
        except ContinueWithErrorsError as error:
            self.errors = True
            errors.append(error)
            logger.warning(
                f'[SET:{self.name}][{node.name}] Error (non-critical){_detail(error)}'
            )
            return False
        except Exception as error:
            errors.append(error)
            if getattr(node, 'game_stopper', True):
                logger.critical(
                    f'[SET:{self.name}][{node.name}] Game stopper in parallel{_detail(error)}'
                )
                return True

            self.errors = True
            logger.warning(
                f'[SET:{self.name}][{node.name}] Failed (non-critical){_detail(error)}'
            )
            return False

    @staticmethod
    def _cancel_parallel_futures(
        future_to_node: Dict[Any, ExecutionNode],
    ) -> None:
        """Cancel all outstanding parallel futures."""
        for future in future_to_node:
            future.cancel()

    # ------------------------------------------------------------------
    # Non-blocking execution (background thread for sequential mode)
    # ------------------------------------------------------------------

    def _execute_non_blocking(self, node: ExecutionNode) -> None:
        """Execute a node in a background thread (non-blocking mode)."""
        step_id = node.config.get('id', node.name)

        stop_signal = threading.Event()
        self.resources.setdefault('threads', {})
        self.resources['threads'][step_id] = {'stop_signal': stop_signal}

        if hasattr(node, 'resources'):
            node.resources = self.resources

        new_thread = threading.Thread(target=node.run, daemon=True)
        self.resources['threads'][step_id]['thread'] = new_thread

        logger.info(
            f'[{node.name}] Starting non-blocking execution (thread: {step_id})'
        )
        new_thread.start()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _iter_enabled_children(self) -> Iterator[Tuple[str, Dict[str, Any]]]:
        """Yield child configs that satisfy execute_if constraints."""
        for step_name, step_conf in self.children_config.items():
            if self._check_execute_if(step_conf.get('execute_if')):
                yield step_name, step_conf
                continue

            logger.info(f'[SET:{self.name}][{step_name}] Skipped (execute_if)')

    def _check_execute_if(
        self, execute_if_config: Optional[Dict[str, Any]]
    ) -> bool:
        """Evaluate execute_if conditions against global_variables."""
        if execute_if_config is None:
            return True

        for variable_name, variable_value in execute_if_config.items():
            if variable_name not in self.global_variables:
                return False
            if self.global_variables[variable_name] != variable_value:
                return False

        return True

    @property
    def type(self) -> str:
        return 'set'

    @property
    def category(self) -> str:
        return 'Set'

    def __str__(self) -> str:
        return f'ExecutionSet({self.name}, children={len(self.children)}, parallel={self.parallel})'
