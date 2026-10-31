"""Describe CLI options consistently for terminal help and editor clients."""

import copy

import rich_click as click
from rich.markup import escape


def cache_option():
    return click.Option(
        ["--no-cache-ptk"],
        is_flag=True,
        help="Disable PTK's optional built-in output cache for all jobs and steps in this execution. Tool-native caches are unchanged.",
    )


def workflow_run_options(ctx):
    return [describe_parameter(ctx, cache_option())]


def suggestions(ctx, param):
    """Only declared completion callbacks supply dynamic values; never scan paths."""
    if isinstance(param.type, click.Choice):
        return [{"value": str(value), "help": ""} for value in param.type.choices]
    if getattr(param, "_custom_shell_complete", None) is None:
        return []
    return [
        {"value": item.value, "help": item.help or ""}
        for item in param.shell_complete(ctx, "")
        if item.type == "plain"
    ]


class SuggestedOption(click.Option):
    def with_values(self, ctx):
        items = suggestions(ctx, self)
        if not items:
            return self
        option = copy.copy(self)
        values = ", ".join(escape(item["value"]) for item in items[:12])
        suffix = f" (+{len(items) - 12} more; use Tab)" if len(items) > 12 else ""
        option.help = f"{self.help or ''} Possible values: {values}{suffix}."
        return option


class SuggestedHelp:
    def format_options(self, ctx, formatter):
        ctx.ptk_option_help = True
        try:
            return super().format_options(ctx, formatter)
        finally:
            ctx.ptk_option_help = False

    def get_params(self, ctx):
        params = super().get_params(ctx)
        if getattr(ctx, "ptk_option_help", False):
            return [
                param.with_values(ctx) if isinstance(param, SuggestedOption) else param
                for param in params
            ]
        return params


class SuggestedCommand(SuggestedHelp, click.RichCommand):
    pass


def describe_parameter(ctx, param):
    option = isinstance(param, click.Option)
    items = suggestions(ctx, param)
    finite = isinstance(param.type, click.Choice) or param.name in {
        "only_step",
        "end",
        "job",
        "name",
        "variant",
        "workflow",
    }
    return {
        "name": param.name,
        "kind": "option" if option else "argument",
        "help": getattr(param, "help", None) or "",
        "required": param.required,
        "type": param.type.name,
        "choices": [item["value"] for item in items] if finite else [],
        "suggestions": items,
        "nargs": param.nargs,
        "multiple": getattr(param, "multiple", False),
        "is_flag": getattr(param, "is_flag", False),
        "option": next(
            (opt for opt in param.opts if opt.startswith("--")), param.opts[0]
        )
        if option
        else None,
        "secondary_option": next(iter(param.secondary_opts), None) if option else None,
    }


def describe_execution(ctx, project):
    """Use the same job options/step completion as the executable Click commands."""
    from .jobs import job_command
    from .state import state_of

    specs = state_of(ctx).project().config.jobs
    project["variant_help"] = next(
        param.help
        for param in ctx.find_root().command.params
        if param.name == "variant"
    )
    for job in project["jobs"]:
        command = job_command(job["name"], specs[job["name"]], hidden=False)
        with click.Context(command, info_name=job["name"], parent=ctx) as child:
            job["run_options"] = [
                describe_parameter(child, param)
                for param in command.params
                if isinstance(param, click.Option)
                and not param.name.startswith("param__")
                and param.name
                not in {"all_variants", "dry_run", "params_path", "graph"}
            ]
    for workflow in project["workflows"]:
        workflow["run_options"] = workflow_run_options(ctx)
