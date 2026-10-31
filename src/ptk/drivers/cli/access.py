"""Per-project built-in command visibility without mutating shared Click objects."""

import copy
from pathlib import Path

import rich_click as click

from ...application.use_cases.role import command_allowed
from ...domain.errors import PtkError
from .options import SuggestedHelp
from .state import guarded, state_of


def can_switch_ci(ctx):
    """Use the current repository's identity, or the VMR root's own list."""
    state = state_of(ctx)
    current = ctx
    while current is not None:
        if getattr(current.command, "repository_boundary", False):
            return state.role() == "maintainer"
        current = current.parent
    try:
        workspace = None if state.config else state.app.workspace.root(Path.cwd())
        if workspace is not None:
            return state.app.workspace_role(workspace) == "maintainer"
    except PtkError:
        return False
    return state.role() == "maintainer"


class MaintainerOption(click.Option):
    """Context-local visibility, evaluated only for help/completion, never parsing."""

    access_context = None

    @property
    def hidden(self):
        return self._hidden or (
            self.access_context is not None and not can_switch_ci(self.access_context)
        )

    @hidden.setter
    def hidden(self, value):
        self._hidden = value


def in_maintainer(ctx):
    while ctx is not None and not getattr(ctx.command, "repository_boundary", False):
        if ctx.info_name == "maintainer":
            return True
        ctx = ctx.parent
    return False


def allowed(ctx, name):
    if ctx.meta.get("host_setup") and name in {
        "self-service",
        "completion",
        "extension",
    }:
        return True
    state = state_of(ctx)
    parts = [name]
    while ctx.parent is not None and not getattr(
        ctx.command, "repository_boundary", False
    ):
        parts.insert(0, ctx.info_name)
        ctx = ctx.parent
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
    # CX can read the matrix without a human maintainer login. This grants no
    # mutation capability or access to restricted jobs/other maintenance commands.
    if (
        project is not None
        and project.ci
        and ".".join(parts) in {"maintainer", "maintainer.matrix"}
    ):
        return True
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


class AccessGroup(SuggestedHelp, click.RichGroup):
    def get_params(self, ctx):
        params = super().get_params(ctx)
        if not hasattr(ctx, "_maintainer_options"):
            ctx._maintainer_options = {}
        result = []
        for param in params:
            if isinstance(param, MaintainerOption):
                if param.name not in ctx._maintainer_options:
                    local = copy.copy(param)
                    local.access_context = ctx
                    ctx._maintainer_options[param.name] = local
                param = ctx._maintainer_options[param.name]
            result.append(param)
        return result

    def list_commands(self, ctx):
        return [n for n in self.commands if allowed(ctx, n)]

    def get_command(self, ctx, cmd_name):
        command = super().get_command(ctx, cmd_name)
        if command is not None and not allowed(ctx, cmd_name):
            return denied_command(cmd_name)
        return command
