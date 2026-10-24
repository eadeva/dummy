"""
Root CLI group factory for the dynamic CLI.

Builds the top-level ``click`` group with all global options
(--variant, --clean, --rebuild, --no-cache, --force-gen, --verbose,
--ignore-locks, --version) and the ``cli`` callback that populates
``ctx.obj`` and dispatches the default action when no subcommand is
invoked.

Extracted from :class:`DynamicCLIGenerator.create_cli` to slim the
facade.
"""

from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING

import rich_click as click

from xc_ce_utils import logger

if TYPE_CHECKING:  # pragma: no cover - typing only
    from xc_ce_utils.core_engine.cli.generator import DynamicCLIGenerator


def _print_version_banner(ctx: click.Context) -> None:
    """Print the formatted XC-CE version banner and exit."""
    from xc_ce_utils.utils.version import version_manager

    version_str = version_manager.get_version_string()

    click.echo(f'XC-CE Utils v{version_str:<15}')
    ctx.exit(0)


def _trigger_advanced_help(ctx: click.Context, generator: 'DynamicCLIGenerator') -> None:
    """Generate and open the interactive advanced help page and exit."""
    from xc_ce_utils.core_engine.reporting.application.advanced_help import run_advanced_help

    run_advanced_help(generator)
    generator.print_final_summary()
    ctx.exit(0)


def create_root_group(generator: 'DynamicCLIGenerator') -> click.Group:
    """Build the top-level ``click.Group`` with all global options."""

    conan_enabled = bool(generator.full_config.get('CONAN_ENABLED', True))

    @click.group(
        name='xc-ce-build',
        help=' XC-CE Utils',
        invoke_without_command=True,
    )
    @click.option(
        '--all-variants',
        '-all',
        is_flag=True,
        default=False,
        show_default=True,
        help=' Execute command for all variants (--variant will be ignored)',
    )
    @click.option(
        '--variant',
        '-var',
        type=str,
        default=generator.variant_matrix.get_default_variant_alias(),
        show_default=True,
        help=" Variant alias/path or comma/space-separated list (e.g., '1' or '1,2,3' or 'pl9 pl7' or 'platform/tc397,platform/tc399')",
    )
    @click.option(
        '--version',
        is_flag=True,
        default=False,
        help='Show xc-ce-utils version and exit',
    )
    @click.option(
        '--adv-help',
        '-ah',
        is_flag=True,
        default=False,
        help='Generate and open the interactive Advanced Help documentation page',
    )
    @click.option(
        '--clean',
        '-c',
        is_flag=True,
        default=False,
        help='Delete build folders and stop (-all for all)',
    )
    @click.option(
        '--rebuild',
        '-rb',
        is_flag=True,
        default=False,
        help=' Clean build folders before starting (rebuild from scratch)',
    )
    @click.option(
        '--no-cache',
        '-nc',
        is_flag=True,
        default=False,
        help=' Disable all caching (overrides --ccache, disables Bazel remote cache, triggers docascode clean rebuild)',
    )
    @click.option(
        '--force-gen',
        '-fg',
        is_flag=True,
        default=False,
        help=' Force code generation, ignoring all caches (applies only to generator steps)',
    )
    @click.option(
        '--verbose',
        '-v',
        count=True,
        default=0,
        help='Increase verbosity (-v for DEBUG, -vv for TRACE)',
    )
    @click.option(
        '--ignore-locks',
        '-i',
        is_flag=True,
        default=False,
        hidden=not conan_enabled,
        help=' Ignore Conan lock files and resolve dependencies freshly',
    )
    @click.pass_context
    def cli(
        ctx,
        all_variants,
        variant,
        version,
        adv_help,
        clean,
        rebuild,
        no_cache,
        force_gen,
        verbose,
        ignore_locks,
    ):
        """XC-CE Dynamic Build System."""
        ctx.ensure_object(dict)
        ctx.obj['all_variants'] = all_variants
        ctx.obj['variant'] = variant
        ctx.obj['clean'] = clean
        ctx.obj['rebuild'] = rebuild
        ctx.obj['no_cache'] = no_cache
        ctx.obj['force_gen'] = force_gen
        ctx.obj['verbose'] = verbose
        ctx.obj['ignore_locks'] = ignore_locks

        if version:
            _print_version_banner(ctx)

        if adv_help:
            _trigger_advanced_help(ctx, generator)

        if verbose >= 2:
            logger.set_level('TRACE')
            os.environ['XC_CE_UTILS_VERBOSE'] = 'true'
        elif verbose >= 1:
            logger.set_level('DEBUG')
            os.environ['XC_CE_UTILS_VERBOSE'] = 'true'
        else:
            os.environ['XC_CE_UTILS_VERBOSE'] = 'false'

        if ignore_locks and not conan_enabled:
            raise click.ClickException('--ignore-locks is unavailable when CONAN_ENABLED is false')

        if ignore_locks:
            os.environ['CONAN_IGNORE_LOCKS'] = 'true'
            logger.info(' Conan lock files will be ignored for this build')
        else:
            os.environ['CONAN_IGNORE_LOCKS'] = 'false'

        if ctx.invoked_subcommand is None:
            if generator.default_action:
                from xc_ce_utils.core_engine.cli import variant_executor

                variant_executor.execute_action_with_arguments(
                    generator, ctx, generator.default_action, {}
                )
            else:
                click.echo(ctx.get_help())
                sys.exit(0)

    return cli
