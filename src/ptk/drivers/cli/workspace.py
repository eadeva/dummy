"""VMR command routing, with an isolated application for each selected repository."""

from __future__ import annotations

import functools
from pathlib import Path

import rich_click as click

from ...bootstrap import create_app
from ...domain.errors import PtkError
from .jobs import ProjectGroup
from .state import CliState, state_of
from .workspace_commands import RESERVED, build_commands


class RepositoryGroup(ProjectGroup):
    repository_boundary = True

    def make_context(self, info_name, args, parent=None, **extra):
        parent_state = state_of(parent)
        extra["obj"] = CliState(
            app=create_app(
                workspace=parent_state.app.workspace,
                started_at=parent_state.app.started_at,
            ),
            config=self.entry_file,
            overrides=parent_state.overrides,
            ci=parent_state.ci,
            verbose=parent_state.verbose,
        )
        return super().make_context(info_name, args, parent=parent, **extra)


class WorkspaceGroup(ProjectGroup):
    def resolve_command(self, ctx, args):
        # Init resolves its scope itself, including members without PTK config.
        if args[:2] == ["setup", "init"] or args[:1] == ["init"]:
            ctx.meta["vmr_repositories"] = None
        return super().resolve_command(ctx, args)

    def _repositories(self, ctx):
        if "vmr_repositories" not in ctx.meta:
            # An explicit entry file intentionally selects standalone mode.
            try:
                discovery = state_of(ctx).app.workspace
                root = None if ctx.params.get("config") else discovery.root(Path.cwd())
                ctx.meta["vmr_repositories"] = (
                    discovery.repositories(root) if root else None
                )
            except (PtkError, OSError) as exc:
                raise click.ClickException(str(exc)) from None
        repos = ctx.meta["vmr_repositories"]
        if repos is not None and RESERVED.intersection(repos):
            raise click.ClickException(
                "repository alias conflicts with a workspace command: "
                + ", ".join(sorted(RESERVED.intersection(repos)))
            )
        return repos

    def list_commands(self, ctx):
        repos = self._repositories(ctx)
        if repos is not None:
            from .workflows import workspace_shortcuts

            workflows = {
                name
                for name, command in workspace_shortcuts(ctx).items()
                if not command.hidden
            }
            return sorted(set(repos) | RESERVED | workflows)
        return (
            sorted(set(repos) | RESERVED)
            if repos is not None
            else super().list_commands(ctx)
        )

    def get_command(self, ctx, cmd_name):
        repos = self._repositories(ctx)
        if repos is None:
            return super().get_command(ctx, cmd_name)
        if cmd_name in RESERVED:
            if "vmr_commands" not in ctx.meta:
                ctx.meta["vmr_commands"] = build_commands(ctx, repos)
            return ctx.meta["vmr_commands"].get(cmd_name)
        if cmd_name not in repos:
            from .workflows import workspace_shortcuts

            return workspace_shortcuts(ctx).get(cmd_name)

        @functools.wraps(self.callback)
        def selected_callback():
            return self.callback(config=None, overrides=(), ci=None, verbose=0)

        group = RepositoryGroup(
            cmd_name,
            commands=self.commands,
            callback=selected_callback,
            invoke_without_command=True,
            context_settings=self.context_settings,
            help=f"Commands for repository {cmd_name} ({repos[cmd_name].parent}).",
        )
        group.entry_file = repos[cmd_name]
        return group

    def format_help(self, ctx, formatter):
        if self._repositories(ctx) is None:
            return super().format_help(ctx, formatter)
        # ProjectGroup's panel builder assumes built-ins; VMR lists repositories.
        return click.RichGroup.format_help(self, ctx, formatter)
