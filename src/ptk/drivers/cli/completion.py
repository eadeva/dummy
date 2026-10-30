"""Shell registration and read-only, project-aware completion callbacks."""

from pathlib import Path

import rich_click as click
from click.shell_completion import CompletionItem, get_completion_class

from ...application.use_cases.role import visible
from ...bootstrap import create_app
from ...domain.errors import PtkError
from .state import CliState, state_of


def _items(values, incomplete):
    return [
        CompletionItem(name, help=help_text)
        for name, help_text in sorted(values.items())
        if name.startswith(incomplete)
    ]


def jobs(ctx, param, incomplete):
    state = state_of(ctx)
    project = state.try_project()
    if project is None:
        return []
    from .access import in_maintainer

    execution = getattr(ctx.command, "name", None) == "run"
    return _items(
        {
            name: spec.help
            for name, spec in project.config.jobs.items()
            if visible(spec.audience, state.role())
            and (not spec.only_cx or project.ci)
            and (not execution or (spec.audience == "maintainer") == in_maintainer(ctx))
        },
        incomplete,
    )


def _variant_projects(ctx):
    state = state_of(ctx)
    current = ctx
    while current is not None:
        if getattr(current.command, "repository_boundary", False):
            return [state.try_project()]
        current = current.parent
    root = ctx.find_root()
    try:
        entries = (
            root.command._repositories(root)
            if hasattr(root.command, "_repositories")
            else None
        )
    except (PtkError, click.ClickException, OSError):
        return []
    if entries is None:
        return [state.try_project()]
    return [
        CliState(
            create_app(host=state.app.host, workspace=state.app.workspace),
            config=entry,
            completion=True,
        ).try_project()
        for entry in entries.values()
    ]


def variants(ctx, param, incomplete):
    # Comma-separated selections retain already entered variants. They are only
    # accepted by the global option; variant show/explain expect individual names.
    before, separator, partial = (
        incomplete.rpartition(",") if param.name == "variant" else ("", "", incomplete)
    )
    prefix = before + separator
    used = set(before.split(",")) if separator else set()
    values = {}
    for project in _variant_projects(ctx):
        line = project.config.variants if project else None
        if line is None:
            continue
        for name, spec in line.variants.items():
            if spec.abstract:
                continue
            for alias in (name, *spec.aliases):
                if alias not in used:
                    values[prefix + alias] = (
                        f"{project.config.repository.alias}: {spec.description or name}"
                    )
    return _items(values, prefix + partial)


def workflows(ctx, param, incomplete):
    from .workflows import can_view, catalog, matches_namespace

    try:
        parent, _, owners, available = catalog(ctx)
        return _items(
            {
                name: spec.help
                for name, (owner, spec, _) in available.items()
                if can_view(parent, owners, owner, spec)
                and (
                    getattr(param, "name", None) == "workflow"
                    or matches_namespace(ctx, owners, owner, spec)
                )
            },
            incomplete,
        )
    except (PtkError, click.ClickException, OSError):
        return []


def _job(ctx):
    state = state_of(ctx)
    project = state.try_project()
    if project is None:
        return None
    name = (
        getattr(ctx.command, "ptk_job", None)
        or ctx.params.get("job")
        or project.config.project.default_job
    )
    spec = project.config.jobs.get(name)
    return (
        spec
        if spec
        and visible(spec.audience, state.role())
        and (not spec.only_cx or project.ci)
        else None
    )


def steps(ctx, param, incomplete):
    job = _job(ctx)
    return (
        [
            CompletionItem(name, help=step.title or "Step")
            for name, step in job.steps.items()
            if name.startswith(incomplete)
        ]
        if job
        else []
    )


def passthrough_steps(ctx, param, incomplete):
    job = _job(ctx)
    values = {}

    if job:
        values = {
            name + "=": step.title or "Additional command arguments"
            for name, step in job.steps.items()
            if step.passthrough
        }
    return _items(values, incomplete)


def features(ctx, param, incomplete):
    project = state_of(ctx).try_project()
    line = project.config.variants if project else None
    if line is None:
        return []
    from ...domain.variants.model import component_symbol

    specs = {name: spec for _component, name, spec in line.iter_features()}
    components = {
        component_symbol(name): f"Select component {name}" for name in line.components
    }
    key, equals, _value = incomplete.partition("=")
    if not equals:
        return _items(
            {
                **{name + "=": spec.help for name, spec in specs.items()},
                **{name + "=": help for name, help in components.items()},
            },
            incomplete,
        )
    spec = specs.get(key)
    values = (
        ["true", "false"]
        if key in components or spec and spec.type == "bool"
        else spec.values
        if spec and spec.type == "enum"
        else []
    )
    return _items(
        {
            key + "=" + item: spec.help if spec else components[key]
            for item in values or []
        },
        incomplete,
    )


def parameters(ctx, param, incomplete):
    job = _job(ctx)
    if job is None:
        return []
    name, equals, partial = incomplete.partition("=")
    if not equals:
        return _items(
            {
                key + "=": spec.help
                for key, spec in job.params.items()
                if spec.type != "secret"
            },
            incomplete,
        )
    spec = job.params.get(name.replace("-", "_"))
    if spec is None or spec.type == "secret":
        return []
    values = (
        spec.choices
        if spec.type == "choice"
        else ["true", "false"]
        if spec.type == "bool"
        else []
    )
    return _items(
        {name + "=" + value: spec.help for value in values or []}, name + "=" + partial
    )


@click.command("completion")
@click.argument(
    "shell", type=click.Choice(["install", "powershell", "bash", "zsh", "fish"])
)
@click.option(
    "--executable",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="With 'install': shared PTK launcher. Defaults to uv's tool directory.",
)
@click.option(
    "--powershell-profile",
    multiple=True,
    type=click.Path(dir_okay=False, path_type=Path),
    help="With 'install': also register this current-user profile (used by the installer).",
)
@click.option(
    "--double-tab",
    is_flag=True,
    help="PowerShell: complete prefixes, then list matches on Tab (changes Tab for all commands).",
)
@click.option(
    "--install",
    "install_profile",
    type=click.Path(path_type=Path, dir_okay=False),
    metavar="PROFILE",
    help="PowerShell: persist completion in a profile, e.g. $PROFILE.CurrentUserAllHosts.",
)
@click.option(
    "--uninstall",
    "uninstall_profile",
    type=click.Path(path_type=Path, dir_okay=False),
    metavar="PROFILE",
    help="PowerShell: remove the managed completion block from this profile.",
)
@click.option(
    "-o",
    "--output",
    type=click.Path(path_type=Path, dir_okay=False),
    help="Write the registration script to this file instead of stdout.",
)
@click.pass_context
def completion_command(
    ctx,
    shell,
    executable,
    powershell_profile,
    double_tab,
    install_profile,
    uninstall_profile,
    output,
):
    """Install or generate terminal Tab completion (no project required).

    'ptk self-service completion install' configures Bash/Git Bash and detected
    PowerShell editions for this user. Both installers do this automatically.

    PowerShell: ptk self-service completion powershell --double-tab | Out-String | Invoke-Expression

    Use --install PROFILE with powershell to target just one profile.
    """
    if shell == "install":
        if install_profile or uninstall_profile or output:
            raise click.UsageError(
                "'install' discovers user profiles; do not combine it with --install, --uninstall or --output."
            )
        import subprocess

        from .shell_setup import install_all

        try:
            sources = {
                name: completion_source(ctx, name, name == "powershell")
                for name in ("bash", "powershell")
            }
            for path, changed in install_all(sources, executable, powershell_profile):
                click.echo(f"{'Updated' if changed else 'Already configured'}: {path}")
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            raise click.ClickException(f"Cannot install completion: {exc}") from None
        click.echo(
            "Completion configured for Bash/Git Bash and detected PowerShell editions. Open a new terminal; no venv activation is needed."
        )
        return
    if executable or powershell_profile:
        raise click.UsageError(
            "--executable and --powershell-profile require 'completion install'."
        )
    if (
        sum(value is not None for value in (install_profile, uninstall_profile, output))
        > 1
    ):
        raise click.UsageError("Choose only one of --install, --uninstall or --output.")
    if (install_profile or uninstall_profile) and shell != "powershell":
        raise click.UsageError(
            "Profile installation is supported for PowerShell; other shells can source --output files."
        )
    if uninstall_profile and double_tab:
        raise click.UsageError("--double-tab cannot be combined with --uninstall.")
    if uninstall_profile:
        _update_profile(uninstall_profile, None)
        return
    if double_tab and shell != "powershell":
        raise click.UsageError(
            "--double-tab is a PowerShell option; other shells use their own Tab bindings."
        )
    text = completion_source(ctx, shell, double_tab)
    if install_profile:
        _update_profile(install_profile, text)
    elif output:
        try:
            output.write_text(text + "\n", encoding="utf-8")
        except OSError as exc:
            raise click.ClickException(
                f"Cannot write completion script: {exc}"
            ) from None
        click.echo(f"Completion script written to {output}")
    else:
        click.echo(text)


def completion_source(ctx, shell, double_tab=False):
    engine = get_completion_class(shell)
    text = engine(ctx.find_root().command, {}, "ptk", "_PTK_COMPLETE").source()
    if double_tab:
        text += """
# Complete a unique prefix, then list remaining matches. This is a shell-wide binding.
if (Get-Command Set-PSReadLineKeyHandler -ErrorAction SilentlyContinue) {
    Set-PSReadLineKeyHandler -Key Tab -Function Complete
} else {
    Write-Warning 'PTK completion registered. Double-Tab listing requires PSReadLine in an interactive terminal.'
}
"""
    return text


def _update_profile(profile, source):
    from .completion_profiles import update_profile

    try:
        changed = update_profile(profile, source)
    except (OSError, ValueError) as exc:
        raise click.ClickException(
            f"Cannot update completion profile {profile}: {exc}"
        ) from None
    action = "installed" if source is not None else "removed"
    click.echo(
        f"Completion {action}: {profile}"
        if changed
        else f"Completion profile already up to date: {profile}"
    )
    click.echo("Open a new PowerShell terminal for this profile change to take effect.")
