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
    return _items(
        {
            name: spec.help
            for name, spec in project.config.jobs.items()
            if visible(spec.audience, state.role()) and (not spec.only_cx or project.ci)
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
        entries = root.command._repositories(root)
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
    # accepted by the global option; variant show/check expect individual names.
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
    from .workflows import can_view, catalog

    try:
        parent, _, owners, available = catalog(ctx)
        return _items(
            {
                name: spec.help
                for name, (owner, spec, _) in available.items()
                if can_view(parent, owners, owner, spec)
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
        _items({step.name: "Top-level step" for step in job.steps}, incomplete)
        if job
        else []
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
@click.argument("shell", type=click.Choice(["powershell", "bash", "zsh", "fish"]))
@click.option(
    "--double-tab",
    is_flag=True,
    help="PowerShell: complete prefixes, then list matches on Tab (changes Tab for all commands).",
)
@click.option(
    "-o",
    "--output",
    type=click.Path(path_type=Path, dir_okay=False),
    help="Write the registration script to this file instead of stdout.",
)
@click.pass_context
def completion_command(ctx, shell, double_tab, output):
    """Generate terminal Tab completion for ptk (no project required).

    PowerShell: ptk setup completion powershell --double-tab | Out-String | Invoke-Expression

    Put the same line in $PROFILE to enable completion in future terminals.
    """
    if double_tab and shell != "powershell":
        raise click.UsageError(
            "--double-tab is a PowerShell option; other shells use their own Tab bindings."
        )
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
    if output:
        try:
            output.write_text(text + "\n", encoding="utf-8")
        except OSError as exc:
            raise click.ClickException(
                f"Cannot write completion script: {exc}"
            ) from None
        click.echo(f"Completion script written to {output}")
    else:
        click.echo(text)
