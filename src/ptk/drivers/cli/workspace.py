"""VMR command routing, with an isolated application for each selected repository."""

from __future__ import annotations

import functools
from pathlib import Path

import rich_click as click

from ...bootstrap import create_app
from ...domain.errors import PtkError
from .access import allowed, denied_command
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
            variant=parent_state.variant,
            clean=parent_state.clean,
            re_run=parent_state.re_run,
            no_cache_ptk=parent_state.no_cache_ptk,
        )
        if parent_state.ci is not None and extra["obj"].role() != "maintainer":
            raise click.ClickException("--ci/--no-ci is a maintainer-only option")
        return super().make_context(info_name, args, parent=parent, **extra)


class WorkspaceGroup(ProjectGroup):
    def resolve_command(self, ctx, args):
        if (
            len(args) >= 2
            and args[0] == "self-service"
            and args[1] in {"completion", "extension"}
        ):
            ctx.meta["vmr_repositories"] = None
            ctx.meta["host_setup"] = True
        # Init resolves its scope itself, including members without PTK config.
        if args[:1] == ["init"]:
            ctx.meta["vmr_repositories"] = None
        if args[:1] == ["describe"]:
            try:
                self._repositories(ctx)
            except click.ClickException:
                # The editor must be able to report malformed marker metadata.
                # Let its normal project loader return structured diagnostics.
                ctx.meta["vmr_repositories"] = None
        return super().resolve_command(ctx, args)

    def _repositories(self, ctx):
        if "vmr_repositories" not in ctx.meta:
            try:
                discovery = state_of(ctx).app.workspace
                root = discovery.root(Path.cwd())
                ctx.meta["vmr_repositories"] = (
                    discovery.repositories(root) if root else None
                )
            except (PtkError, OSError) as exc:
                if ctx.resilient_parsing:
                    ctx.meta["vmr_repositories"] = None
                    return None
                raise click.ClickException(str(exc)) from None
        repos = ctx.meta["vmr_repositories"]
        if repos is not None and set(RESERVED).intersection(repos):
            if ctx.resilient_parsing:
                ctx.meta["vmr_repositories"] = None
                return None
            raise click.ClickException(
                "repository alias conflicts with a workspace command: "
                + ", ".join(sorted(set(RESERVED).intersection(repos)))
            )
        return repos

    def list_commands(self, ctx):
        repos = self._repositories(ctx)
        if repos is not None:
            from .workflows import workspace_shortcuts

            try:
                workflows = {
                    name
                    for name, command in workspace_shortcuts(ctx).items()
                    if not command.hidden
                }
            except (PtkError, click.ClickException, OSError):
                if not ctx.resilient_parsing:
                    raise
                workflows = set()
            return [
                *sorted(repos),
                *sorted(workflows),
                *[
                    name
                    for name in RESERVED
                    if self.get_command(ctx, name) is not None and allowed(ctx, name)
                ],
            ]
        return super().list_commands(ctx)

    def get_command(self, ctx, cmd_name):
        repos = self._repositories(ctx)
        if repos is None:
            return super().get_command(ctx, cmd_name)
        if cmd_name in RESERVED:
            if not allowed(ctx, cmd_name):
                return denied_command(cmd_name)
            if "vmr_commands" not in ctx.meta:
                ctx.meta["vmr_commands"] = build_commands(ctx, repos)
            return ctx.meta["vmr_commands"].get(cmd_name)
        if cmd_name not in repos:
            from .workflows import workspace_shortcuts

            return workspace_shortcuts(ctx).get(cmd_name)

        @functools.wraps(self.callback)
        def selected_callback():
            return self.callback(overrides=(), ci=None, verbose=0, variant=None)

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
        from .access import can_switch_ci

        if ctx.params.get("ci") is not None and not can_switch_ci(ctx):
            raise click.ClickException("--ci/--no-ci is a maintainer-only option")
        try:
            repos = self._repositories(ctx)
        except click.ClickException:
            # Help remains available when a marker or member index is broken.
            ctx.meta["vmr_repositories"] = None
            repos = None
        if repos is None:
            return super().format_help(ctx, formatter)
        # ProjectGroup's panel builder assumes built-ins; VMR lists repositories.
        names = self.list_commands(ctx)
        config = getattr(formatter, "config", None)
        if config is not None:
            config.command_groups = {
                ctx.command_path: [
                    {"name": title, "commands": commands}
                    for title, commands in (
                        ("Repositories", [n for n in names if n in repos]),
                        (
                            "Workflows",
                            [n for n in names if n not in repos and n not in RESERVED],
                        ),
                        (
                            "Commands",
                            [
                                n
                                for n in names
                                if n in RESERVED
                                and n not in {"self-service", "maintainer"}
                            ],
                        ),
                        ("Self-service", [n for n in names if n == "self-service"]),
                        ("Maintenance", [n for n in names if n == "maintainer"]),
                    )
                    if commands
                ]
            }
        return click.RichGroup.format_help(self, ctx, formatter)
