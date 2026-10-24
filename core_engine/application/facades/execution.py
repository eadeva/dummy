"""Application facade for action execution orchestration.

This module defines a UI-agnostic execution entrypoint intended to be
consumed by CLI/GUI adapters.
"""

from __future__ import annotations

import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Protocol

from xc_ce_utils import logger
from xc_ce_utils.conf_file_loader.conf_file_loader import get_logs_root
from xc_ce_utils.core_engine.domain.exceptions import is_reported


class GeneratorPort(Protocol):
    """Port describing the driving-adapter object this facade operates on.

    Defined locally rather than importing the concrete CLI
    ``DynamicCLIGenerator`` type, so the application layer has no
    compile-time or runtime dependency on any specific driving adapter
    (CLI, GUI, ...). Any object exposing this shape may be passed in.
    """

    verbose: int
    variant: Any
    variant_matrix: Any

    def start_execution(self) -> None: ...
    def add_error(self, message: str, operation: str) -> None: ...
    def print_final_summary(self) -> None: ...


@dataclass(frozen=True)
class ActionExecutionOptions:
    """Adapter-neutral options required to execute an action."""

    clean: bool = False
    rebuild: bool = False
    no_cache: bool = False
    force_gen: bool = False
    all_variants: bool = False
    variant_alias: str = ''
    verbose: int = 0
    kwargs: dict[str, Any] = field(default_factory=dict)


def execute_action(
    generator: GeneratorPort,
    action: str,
    options: ActionExecutionOptions,
    runtime: ExecutionRuntime,
) -> int:
    """Execute an action using canonical application orchestration.

    This function is intentionally adapter-neutral. Adapters inject concrete
    runtime dependencies and own process-level concerns such as ``sys.exit``.
    """

    generator.start_execution()
    logger.log_phase_header('XC-CE UTILS BUILD SYSTEM - START')
    generator.verbose = options.verbose

    variant_alias = _normalize_variant_alias(options.variant_alias)

    try:
        if options.all_variants or ',' in variant_alias:
            return _execute_multi_variant_action(
                generator,
                action,
                options,
                variant_alias,
                runtime,
            )

        _execute_single_variant_action(
            generator,
            action,
            options,
            variant_alias,
            runtime,
        )
        return 0
    except runtime.build_error_cls as error:
        _handle_build_error(generator, action, error, runtime)
        return 1
    except Exception as error:
        _handle_unexpected_error(
            generator,
            action,
            error,
            runtime,
        )
        return 1


VariantDescriptor = tuple[int, str, str, str]
VariantSuccess = tuple[str, str, str]
VariantFailure = tuple[str, str, str, int]


@dataclass(frozen=True)
class ExecutionRuntime:
    variant_executor: Any
    build_python_command: Callable[[str], int]
    build_error_cls: type[Exception]
    configuration_error_cls: type[Exception]
    unexpected_error_reporter: Callable[[Exception], None] | None = None


def _normalize_variant_alias(variant_alias: str) -> str:
    return ','.join(variant_alias.replace(',', ' ').split())


def _execute_multi_variant_action(
    generator: GeneratorPort,
    action: str,
    options: ActionExecutionOptions,
    variant_alias: str,
    runtime: ExecutionRuntime,
) -> int:
    allowed_variants = runtime.variant_executor.get_variants_to_execute(
        generator,
        action,
        all_variants=options.all_variants,
        variant_alias=variant_alias,
    )

    if not allowed_variants:
        msg = f'No variants are allowed for action {action}'
        raise runtime.configuration_error_cls(msg)

    variant_desc = (
        'all variants'
        if options.all_variants
        else f'{len(allowed_variants)} specified variant(s)'
    )
    logger.progress(f"Executing action '{action}' for {variant_desc}")
    logger.info(
        f"Running action '{action}' for {len(allowed_variants)} "
        'allowed variant(s)'
    )

    runtime.variant_executor.setup_cpu_cores(generator, all_variants=True)
    max_workers = runtime.variant_executor.get_max_parallel_builds(
        len(allowed_variants)
    )
    logger.info(f'Using {max_workers} parallel worker(s) for building variants')
    logger.info('=' * 100)

    os.environ['XC_CE_UTILS_PARALLEL_VARIANT_EXECUTION'] = 'true'

    variant_data = _build_variant_data(allowed_variants)
    variant_runner = _resolve_variant_runner(runtime.build_python_command)

    successful_variants, failed_variants = _run_variants_in_parallel(
        variant_data,
        max_workers,
        variant_runner,
    )

    _log_multi_variant_summary(
        successful_variants,
        failed_variants,
        total_variants=len(allowed_variants),
    )

    if failed_variants:
        logger.error(
            ' Build completed with '
            f'{len(failed_variants)} failure(s) out of '
            f'{len(allowed_variants)} variant(s)'
        )
        logger.log_phase_header('XC-CE UTILS BUILD SYSTEM - END WITH FAILURES')
        return 1

    logger.success(
        f' All {len(allowed_variants)} variant(s) built successfully!'
    )
    logger.log_phase_header('XC-CE UTILS BUILD SYSTEM - END')
    return 0


def _build_variant_data(
    allowed_variants: list[tuple[str, Any]],
) -> list[VariantDescriptor]:
    variant_data: list[VariantDescriptor] = []
    for index, (name, variant) in enumerate(allowed_variants, start=1):
        variant_data.append(
            (
                index,
                name,
                str(variant.get_variant_path()),
                str(variant.get_variant_alias()),
            )
        )
    return variant_data


def _resolve_variant_runner(
    build_python_command: Callable[[str], int],
) -> Callable[[str], int]:
    if getattr(sys, 'frozen', False):
        return _create_frozen_variant_runner(sys.argv[1:])
    return build_python_command


def _create_frozen_variant_runner(base_args: list[str]) -> Callable[[str], int]:
    def _run_variant(variant_alias: str) -> int:
        rewritten_args = _rewrite_args_for_variant(base_args, variant_alias)
        command = [sys.executable, *rewritten_args]
        logger.debug(f"Final command: {' '.join(command)}")
        result = subprocess.run(command, check=False)
        return int(result.returncode)

    return _run_variant


def _rewrite_args_for_variant(
    base_args: list[str], variant_alias: str
) -> list[str]:
    logger.debug(f'Original args for subprocess: {base_args}')

    final_args: list[str] = []
    index = 0
    replaced_variant = False

    while index < len(base_args):
        arg = base_args[index]

        if arg in {'-all', '--all-variants'}:
            index += 1
            continue

        if arg.startswith(('--variant=', '-var=')):
            value = arg.split('=', 1)[1]
            if ',' in value or ' ' in value:
                prefix = arg.split('=', 1)[0]
                final_args.append(f'{prefix}={variant_alias}')
            else:
                final_args.append(arg)
            replaced_variant = True
            index += 1
            continue

        if arg in {'-var', '--variant'} and index + 1 < len(base_args):
            value = base_args[index + 1]
            final_args.append(arg)
            if ',' in value or ' ' in value:
                final_args.append(variant_alias)
            else:
                final_args.append(value)
            replaced_variant = True
            index += 2
            continue

        final_args.append(arg)
        index += 1

    if not replaced_variant:
        final_args = ['-var', variant_alias, *final_args]

    logger.debug(f'Final args for subprocess: {final_args}')
    return final_args


def _run_variants_in_parallel(
    variant_data: list[VariantDescriptor],
    max_workers: int,
    variant_runner: Callable[[str], int],
) -> tuple[list[VariantSuccess], list[VariantFailure]]:
    successful_variants: list[VariantSuccess] = []
    failed_variants: list[VariantFailure] = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {
            executor.submit(variant_runner, alias): (idx, name, path, alias)
            for idx, name, path, alias in variant_data
        }

        for future in as_completed(future_map):
            idx, name, path, alias = future_map[future]
            return_code = _resolve_return_code(future, alias)

            if return_code == 0:
                successful_variants.append((name, path, alias))
                logger.success(
                    f'[{idx}/{len(variant_data)}]  SUCCESS: {path} ({alias}) '
                    f'- Total: {len(successful_variants)} OK, '
                    f'{len(failed_variants)} FAILED'
                )
            else:
                failed_variants.append((name, path, alias, return_code))
                logger.error(
                    f'[{idx}/{len(variant_data)}]  FAILED: {path} ({alias}) '
                    f'[exit code: {return_code}] - Total: '
                    f'{len(successful_variants)} OK, '
                    f'{len(failed_variants)} FAILED'
                )

    return successful_variants, failed_variants


def _resolve_return_code(future: Any, alias: str) -> int:
    try:
        return int(future.result())
    except Exception as exc:
        logger.error(f'Variant subprocess failed for alias {alias}: {exc}')
        return 1


def _log_multi_variant_summary(
    successful_variants: list[VariantSuccess],
    failed_variants: list[VariantFailure],
    *,
    total_variants: int,
) -> None:
    logger.info('=' * 100)
    logger.log_phase_header('BUILD SUMMARY - ALL VARIANTS')

    if successful_variants:
        logger.success(
            '\n SUCCESSFUL VARIANTS '
            f'({len(successful_variants)}/{total_variants}):'
        )
        for _name, path, alias in successful_variants:
            logger.success(f'    {path} ({alias})')

    if failed_variants:
        logger.error(
            '\n FAILED VARIANTS ' f'({len(failed_variants)}/{total_variants}):'
        )
        for _name, path, alias, code in failed_variants:
            logger.error(f'    {path} ({alias}) [exit code: {code}]')

    logger.info('=' * 100)


def _execute_single_variant_action(
    generator: GeneratorPort,
    action: str,
    options: ActionExecutionOptions,
    variant_alias: str,
    runtime: ExecutionRuntime,
) -> None:
    generator.variant = generator.variant_matrix.get_variant_by_alias_or_path(
        variant_alias
    )
    if not generator.variant:
        msg = f'Variant unknown: {variant_alias}'
        raise runtime.configuration_error_cls(msg)

    if not runtime.variant_executor.introspection.validate_variant_constraints(
        generator,
        action,
        generator.variant,
    ):
        variant_display = _resolve_variant_display_name(generator)
        msg = (
            f'Variant {variant_display} is not allowed for action {action} '
            '(run builder with option --help for more information)'
        )
        raise runtime.configuration_error_cls(msg)

    logger.progress(
        f'Executing action: {action.upper()} for variant '
        f'{generator.variant.get_variant_path()} '
        f'(alias {generator.variant.get_variant_alias()})'
    )

    kwargs_with_force_gen = options.kwargs.copy()
    kwargs_with_force_gen['force_gen'] = options.force_gen

    with logger.trace_context(action):
        runtime.variant_executor.execute_variant_action(
            generator,
            action,
            generator.variant,
            runtime.variant_executor.VariantActionOptions(
                clean=options.clean,
                rebuild=options.rebuild,
                no_cache=options.no_cache,
                kwargs=kwargs_with_force_gen,
            ),
        )

    logger.success(f'Executing action {action} finished successfully')
    logger.log_phase_header('XC-CE UTILS BUILD SYSTEM - END')
    generator.print_final_summary()


def _resolve_variant_display_name(generator: GeneratorPort) -> str:
    variant_name = None
    for name, variant in generator.variant_matrix.get_variants().items():
        if variant.get_variant_alias() == generator.variant.get_variant_alias():
            variant_name = name
            break

    if variant_name is not None:
        return variant_name

    return f'alias {generator.variant.get_variant_alias()}'


def _handle_build_error(
    generator: GeneratorPort,
    action: str,
    error: Exception,
    runtime: ExecutionRuntime,
) -> None:
    error_msg = f'Build failed: {error}'
    generator.add_error(error_msg, f'Build Action: {action}')
    _append_error_log(runtime, error)
    generator.print_final_summary()


def _handle_unexpected_error(
    generator: GeneratorPort,
    action: str,
    error: Exception,
    runtime: ExecutionRuntime,
) -> None:
    error_msg = f'Unexpected error: {error}'
    generator.add_error(error_msg, f'Build Action: {action}')

    if is_reported(error):
        pass
    elif runtime.unexpected_error_reporter is not None:
        runtime.unexpected_error_reporter(error)
    else:
        logger.error(f'Unexpected error: {error}')

    _append_error_log(runtime, error)
    generator.print_final_summary()


def _append_error_log(runtime: ExecutionRuntime, error: Exception) -> None:
    repo_root = Path(os.environ.get('REPO_PATH', str(Path.cwd())))
    logs_root_resolver = getattr(
        runtime.variant_executor, 'get_logs_root', None
    )
    if logs_root_resolver is None:
        logs_root_resolver = get_logs_root

    error_log = logs_root_resolver(repo_root) / 'error.log'
    error_log.parent.mkdir(parents=True, exist_ok=True)
    with error_log.open('a') as file_handle:
        file_handle.write(f'Builder ended with errors: {error}\n')
