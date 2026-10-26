"""Per-project built-in command visibility without mutating shared Click objects."""

import rich_click as click

from ...application.use_cases.role import command_allowed
from ...domain.errors import PtkError
from .state import guarded, state_of

ALIASES = {
    "config": "setup.config",
    "configs": "setup.configs",
    "creds": "setup.creds",
    "vscode": "setup.vscode",
    "self-setup": "setup.self",
    "doctor": "setup.doctor",
    "init": "setup.init",
}


def allowed(ctx, name):
    state = state_of(ctx)
    parts = [name]
    while ctx.parent is not None and not getattr(
        ctx.command, "repository_boundary", False
    ):
        parts.insert(0, ctx.info_name)
        ctx = ctx.parent
    if parts[0] in ALIASES:
        parts = ALIASES[parts[0]].split(".") + parts[1:]
    if (
        not getattr(ctx.command, "repository_boundary", False)
        and ctx.meta.get("vmr_repositories") is not None
    ):
        from pathlib import Path

        try:
            root = state.app.workspace.root(Path.cwd())
            role = state.app.workspace_role(root) if root else "user"
        except PtkError:
            role = "user"  # Invalid identity lists never expose mutation commands.
        return command_allowed(".".join(parts), role, {})
    project = state.try_project()
    return command_allowed(
        ".".join(parts),
        state.role(),
        project.config.command_audience if project else {},
    )


def require(ctx, name):
    """Check callback dispatches which do not go through Click resolution."""
    if not allowed(ctx, name):
        raise click.ClickException(f"'{name}' is a maintainer-only command")


def denied_command(name, kind="command"):
    @guarded
    def denied():
        raise PtkError(f"'{name}' is a maintainer-only {kind}")

    return click.RichCommand(
        name,
        callback=denied,
        hidden=True,
        context_settings={
            "ignore_unknown_options": True,
            "allow_extra_args": True,
            "help_option_names": [],
        },
    )


class AccessGroup(click.RichGroup):
    def list_commands(self, ctx):
        return [n for n in super().list_commands(ctx) if allowed(ctx, n)]

    def get_command(self, ctx, cmd_name):
        command = super().get_command(ctx, cmd_name)
        if command is not None and not allowed(ctx, cmd_name):
            return denied_command(cmd_name)
        return command
