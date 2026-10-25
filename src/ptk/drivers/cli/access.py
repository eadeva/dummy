"""Per-project built-in command visibility without mutating shared Click objects."""

import rich_click as click

from .state import state_of

ALIASES = {
    "config": "setup.config",
    "configs": "setup.configs",
    "creds": "setup.creds",
    "vscode": "setup.vscode",
    "self-setup": "setup.self",
    "doctor": "setup.doctor",
    "init": "setup.init",
    "migrate": "setup.migrate",
}


def allowed(ctx, name):
    state = state_of(ctx)
    project = state.try_project()
    if project is None or state.role() == "maintainer":
        return True
    parts = [name]
    while ctx.parent is not None:
        parts.insert(0, ctx.info_name)
        ctx = ctx.parent
    if parts[0] in ALIASES:
        parts = ALIASES[parts[0]].split(".") + parts[1:]
    policies = project.config.command_audience
    return all(
        policies.get(".".join(parts[:i])) != "maintainer"
        for i in range(1, len(parts) + 1)
    )


class AccessGroup(click.RichGroup):
    def list_commands(self, ctx):
        return [n for n in super().list_commands(ctx) if allowed(ctx, n)]

    def get_command(self, ctx, cmd_name):
        command = super().get_command(ctx, cmd_name)
        if command is not None and not allowed(ctx, cmd_name):

            def denied():
                raise click.ClickException(f"'{cmd_name}' is a maintainer-only command")

            return click.RichCommand(
                cmd_name,
                callback=denied,
                hidden=True,
                context_settings={
                    "ignore_unknown_options": True,
                    "allow_extra_args": True,
                    "help_option_names": [],
                },
            )
        return command
