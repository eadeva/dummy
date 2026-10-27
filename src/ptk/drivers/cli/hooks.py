"""Repository-scoped pre-commit commands; hook execution stays in the adapter."""

import rich_click as click

from .access import AccessGroup
from .state import guarded, state_of


@click.group("pre-commit", cls=AccessGroup, invoke_without_command=True)
@click.pass_context
def pre_commit_group(ctx):
    """Run checks and manage this repository's local Git hooks."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


def run_options(command):
    command = click.option(
        "--verbose", "-v", is_flag=True, help="Show hook output even when it passes."
    )(command)
    command = click.option(
        "--show-diff-on-failure",
        is_flag=True,
        help="Show the Git diff when checks fail.",
    )(command)
    command = click.option(
        "--hook-stage",
        type=click.Choice(["pre-commit", "pre-push", "manual"]),
        help="Hook stage to run (default: pre-commit).",
    )(command)
    return click.argument("hook", required=False)(command)


@pre_commit_group.command("run")
@run_options
@click.option("--all-files", "-a", is_flag=True, help="Check every tracked file.")
@click.option(
    "--file",
    "-f",
    "files",
    multiple=True,
    type=click.Path(dir_okay=False),
    help="Check this file, relative to the repository root; repeat for more files.",
)
@click.option("--from-ref", help="Check changes from this Git ref (requires --to-ref).")
@click.option("--to-ref", help="Check changes to this Git ref (requires --from-ref).")
@click.pass_context
@guarded
def run(ctx, **options):
    """Run all checks, or one HOOK, on staged files. Hooks may fix files."""
    state = state_of(ctx)
    project = state.project()
    ctx.exit(state.app.hooks.run(project, click.echo, **options))


@pre_commit_group.command("check")
@run_options
@click.pass_context
@guarded
def check(ctx, **options):
    """Run checks on all tracked files (run --all-files). Hooks may fix files."""
    state = state_of(ctx)
    project = state.project()
    ctx.exit(state.app.hooks.run(project, click.echo, all_files=True, **options))


@pre_commit_group.command("install")
@click.pass_context
@guarded
def install(ctx):
    """Install or repair the configured Git hook scripts without running checks."""
    state = state_of(ctx)
    project = state.project()
    state.app.hooks.install(project, click.echo)
    click.echo(state.app.hooks.inspect(project).detail)


@pre_commit_group.command("uninstall")
@click.pass_context
@guarded
def uninstall(ctx):
    """Remove pre-commit scripts, restoring any hooks saved during installation.

    With configs.pre-commit.enabled, the next local job installs them again.
    """
    state = state_of(ctx)
    project = state.project()
    state.app.hooks.uninstall(project, click.echo)
    click.echo("Pre-commit uninstall complete.")
    if state.app.hooks.config(project) is not None:
        click.echo(
            "Automatic installation is enabled; the next local job will install the hooks again."
        )


@pre_commit_group.command("status")
@click.pass_context
@guarded
def status(ctx):
    """Inspect Git hook installation without changing anything; exit 1 if missing."""
    state = state_of(ctx)
    project = state.project()
    service = state.app.hooks
    click.echo(f"config: {service.command_config(project)}")
    automatic = (
        "enabled for local jobs" if service.config(project) is not None else "disabled"
    )
    click.echo(f"automatic installation: {automatic}")
    result = service.inspect(project)
    click.echo(result.detail)
    ctx.exit(0 if result.installed else 1)


@pre_commit_group.command("validate")
@click.pass_context
@guarded
def validate(ctx):
    """Validate the pre-commit configuration without running checks or installing hooks."""
    state = state_of(ctx)
    project = state.project()
    code = state.app.hooks.validate(project, click.echo)
    if code == 0:
        click.echo("pre-commit configuration is valid")
    ctx.exit(code)
