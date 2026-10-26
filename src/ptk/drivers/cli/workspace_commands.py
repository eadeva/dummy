"""Shared VMR views and credential coordination; mutations retain repo context."""

import json

import rich_click as click

from ...bootstrap import create_app
from .access import AccessGroup
from .state import CliState, guarded, state_of

RESERVED = {"setup", "variant", "report", "help", "repos", "workflow"}


def invoke_repository(root, alias, args):
    command = root.command.get_command(root, alias)
    with command.make_context(alias, list(args), parent=root) as child:
        if (
            args[:2] in (["variant", "list"], ["variant", "check"])
            and state_of(child).project().config.variants is None
        ):
            click.echo("no variants configured")
            return None
        return command.invoke(child)


def visit(root, invocations):
    failed = 0
    for alias, args in invocations:
        click.echo(f"[{alias}]")
        try:
            invoke_repository(root, alias, args)
        except click.ClickException as exc:
            exc.show()
            failed = max(failed, exc.exit_code)
        except (SystemExit, click.exceptions.Exit) as exc:
            failed = max(
                failed, getattr(exc, "exit_code", getattr(exc, "code", 1)) or 0
            )
    if failed:
        raise click.exceptions.Exit(failed)


class ForwardCommand(click.RichCommand):
    def __init__(self, original, path, entries):
        super().__init__(original.name, params=original.params, help=original.help)
        self.path = path
        self.entries = entries

    def make_context(self, info_name, args, **kwargs):
        raw = list(args)
        ctx = super().make_context(info_name, args, **kwargs)
        ctx.forward_args = raw
        return ctx

    def invoke(self, ctx):
        visit(
            ctx.find_root(),
            [
                (alias, [*self.path, *ctx.forward_args])
                for alias in sorted(self.entries)
            ],
        )


def build_commands(root, entries):
    originals = root.command.commands
    parent = state_of(root)

    def states():
        for alias, entry in sorted(entries.items()):
            yield (
                alias,
                CliState(
                    create_app(workspace=parent.app.workspace),
                    config=entry,
                    overrides=parent.overrides,
                    ci=parent.ci,
                    verbose=parent.verbose,
                ),
            )

    def credentials():
        groups = {}
        for alias, state in states():
            project = state.project()
            policies = project.config.command_audience
            if state.role() != "maintainer" and any(
                policies.get(k) == "maintainer" for k in ("setup", "setup.creds")
            ):
                continue
            for name, spec in project.config.credentials.items():
                groups.setdefault(name, []).append((alias, state, spec))
        catalog = {}
        for name, owners in groups.items():
            if all(o[2] == owners[0][2] for o in owners):
                catalog[name] = (name, owners)
            else:
                for owner in owners:
                    catalog[f"{owner[0]}/{name}"] = (name, [owner])
        return catalog

    setup = AccessGroup(
        "setup",
        help="Initialize missing configs; shared credentials, validation and diagnostics. Install tools under a repository.",
    )
    setup.add_command(originals["setup"].commands["init"])
    config = click.RichGroup(
        "config", help="Inspect and validate all repository configurations."
    )
    for name in ("show", "validate"):
        config.add_command(
            ForwardCommand(
                originals["setup"].commands["config"].commands[name],
                ["setup", "config", name],
                entries,
            )
        )
    config.add_command(originals["setup"].commands["config"].commands["schema"])
    setup.add_command(config)
    from .workflows import workspace_vscode_group

    setup.add_command(workspace_vscode_group(root, entries))

    @setup.command("doctor")
    @guarded
    def doctor():
        failed = False
        click.echo("[machine]")
        for check in parent.app.doctor.run(None, None, None, "user"):
            if check.area != "configuration":
                click.echo(f"{check.area}: {check.status}: {check.detail}")
                failed |= check.status == "problem"
        for alias, state in states():
            project = state.project()
            policies = project.config.command_audience
            if state.role() != "maintainer" and any(
                policies.get(k) == "maintainer" for k in ("setup", "setup.doctor")
            ):
                continue
            click.echo(f"[{alias}]")
            for check in state.app.doctor.run(
                project,
                None,
                state.app.credentials(project),
                state.role(),
                include_machine=False,
            ):
                click.echo(f"{check.area}: {check.status}: {check.detail}")
                failed |= check.status == "problem"
        if failed:
            raise click.exceptions.Exit(1)

    creds = click.RichGroup(
        "creds",
        help="Combined credential definitions; conflicting names use REPOSITORY/NAME.",
    )
    creds.add_command(originals["setup"].commands["creds"].commands["setup"])

    @creds.command("list")
    @click.argument("name", required=False)
    @guarded
    def list_credentials(name):
        catalog = credentials()
        if name and name not in catalog:
            raise click.ClickException(
                f"unknown or ambiguous credential {name!r}; use setup creds list"
            )
        for key in [name] if name else sorted(catalog):
            original, owners = catalog[key]
            owner_names = ", ".join(o[0] for o in owners)
            state = owners[0][1]
            for row in state.app.credentials(state.project()).status(original):
                click.echo(
                    f"{key}.{row.key.field} [{owner_names}]: {row.provider or 'missing'}; env={row.key.env_var}; {'; '.join(row.notes)}"
                )
        if not catalog:
            click.echo("no accessible credentials configured")

    def credential_command(operation):
        original = originals["setup"].commands["creds"].commands[operation]

        @click.pass_context
        @guarded
        def callback(ctx, **options):
            name = options["name"]
            catalog = credentials()
            if name not in catalog:
                raise click.ClickException(
                    f"unknown or ambiguous credential {name!r}; use REPOSITORY/NAME for conflicts"
                )
            actual, owners = catalog[name]
            args = ["setup", "creds", operation, actual]
            if options.get("field"):
                args.append(options["field"])
            if options.get("store"):
                args.extend(["--store", options["store"]])
            # Tests belong to repositories; identical stored definitions need one write.
            targets = owners if operation == "test" else owners[:1]
            visit(ctx.find_root(), [(owner[0], args) for owner in targets])

        return click.RichCommand(
            operation, params=original.params, callback=callback, help=original.help
        )

    for name in ("set", "remove", "test"):
        creds.add_command(credential_command(name))
    setup.add_command(creds)
    variant = click.RichGroup(
        "variant", help="List and validate variants in every repository."
    )
    for name in ("list", "check"):
        variant.add_command(
            ForwardCommand(
                originals["variant"].commands[name], ["variant", name], entries
            )
        )
    report = click.RichGroup(
        "report",
        help="Read workspace-wide run status; exports remain repository-specific.",
    )

    def summaries(history=False):
        from ...application.use_cases.run import layout_of

        for alias, state in states():
            project = state.project()
            if (
                state.role() != "maintainer"
                and project.config.command_audience.get("report") == "maintainer"
            ):
                continue
            layout = layout_of(project)
            folder = layout.root / layout.logs
            pattern = "*/*/**/run.json" if history else "*/*/run.json"
            for path in sorted(folder.glob(pattern)):
                data = json.loads(path.read_text(encoding="utf-8"))
                yield alias, data

    @report.command("list")
    @click.option("--history", is_flag=True)
    @guarded
    def list_reports(history):
        for alias, data in summaries(history):
            click.echo(
                f"{alias} {data['job']} {data['variant']} {data['run_id']}: {data['status']}"
            )

    @report.command("summary")
    @guarded
    def summary_reports():
        totals = {}
        for alias, data in summaries():
            totals[data["status"]] = totals.get(data["status"], 0) + 1
            click.echo(f"{alias}/{data['job']}/{data['variant']}: {data['status']}")
        click.echo("Totals: " + json.dumps(totals, sort_keys=True))

    @click.command("repos")
    def list_repositories():
        for alias, entry in sorted(entries.items()):
            click.echo(f"{alias}: {entry.parent}")

    @click.command("help")
    def workspace_help():
        click.echo(root.get_help())

    from .workflows import workflow_group

    return {
        c.name: c
        for c in (
            setup,
            variant,
            report,
            list_repositories,
            workspace_help,
            workflow_group,
        )
    }
