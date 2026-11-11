"""Shared VMR views and credential coordination; mutations retain repo context."""

import json
from pathlib import Path

import rich_click as click

from ...application.use_cases.role import command_allowed, visible
from ...bootstrap import create_app
from ...domain.errors import PtkError
from .access import AccessGroup
from .state import CliState, guarded, state_of

RESERVED = (
    "init",
    "variant",
    "report",
    "validate",
    "help",
    "repos",
    "jobs",
    "workflow",
    "self-service",
    "maintainer",
    "describe",
    "vmr-clean-all",
)

# Commands that act on every PTk repository of the VMR (help panel and docs).
VMR_COMMANDS = (
    ("jobs", "List the jobs of every repository"),
    ("validate", "Validate every repository's configuration"),
    ("variant list", "List the variants of every repository"),
    ("report list|summary", "Show recorded runs of every repository"),
    ("self-service doctor", "Check the machine and every repository"),
    ("self-service tools", "Check and install the tools of every repository"),
    (
        "self-service hooks install|uninstall|status",
        "Manage Git hooks in every repository",
    ),
    (
        "self-service creds list|set|remove|test|setup",
        "Combined credentials of all repositories",
    ),
    (
        "self-service creds lock|reset",
        "Lock or delete your vault (once for all repositories)",
    ),
    (
        "maintainer sync configs|agent",
        "Synchronize shared configs or the agent in every repository",
    ),
    ("maintainer config show", "Show the configuration of every repository"),
    (
        "maintainer configs-report",
        "Write the configuration deviation report of every repository",
    ),
    ("maintainer version show", "Show the discovered versions of every repository"),
    ("vmr-clean-all", "Remove generated outputs of every repository"),
    ("help", "Open the advanced HTML help of the whole VMR"),
)


def invoke_repository(root, alias, args):
    command = root.command.get_command(root, alias)
    with command.make_context(alias, list(args), parent=root) as child:
        if (
            args[:2] == ["variant", "list"]
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
    """Run a repository command in every selected repository.

    ``select(params)`` returns the aliases to visit; it may refuse before any run.
    """

    def __init__(self, original, path, entries, select=None):
        super().__init__(
            original.name,
            params=original.params,
            help=(original.help or "").strip() + "\n\nRuns in every PTk repository.",
            short_help=(original.get_short_help_str(60) + " (every repository)"),
        )
        self.path = path
        self.entries = entries
        self.select = select

    def make_context(self, info_name, args, **kwargs):
        raw = list(args)
        ctx = super().make_context(info_name, args, **kwargs)
        ctx.forward_args = raw
        return ctx

    def invoke(self, ctx):
        try:
            aliases = self.select(ctx.params) if self.select else sorted(self.entries)
        except PtkError as exc:
            raise click.ClickException(str(exc)) from None
        visit(
            ctx.find_root(),
            [(alias, [*self.path, *ctx.forward_args]) for alias in aliases],
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
                    cx=parent.cx,
                    verbose=parent.verbose,
                ),
            )

    def credentials():
        groups = {}
        for alias, state in states():
            project = state.project()
            policies = project.config.command_audience
            if state.role() != "maintainer" and any(
                policies.get(k) == "maintainer"
                for k in ("self-service", "self-service.creds")
            ):
                continue
            for name, spec in project.config.credentials.items():
                groups.setdefault(name, []).append((alias, state, spec))
        # One vault per user: every repository's NAME shares the same values.
        return {name: (name, owners) for name, owners in groups.items()}

    setup = AccessGroup(
        "self-service",
        invoke_without_command=True,
        callback=originals["self-service"].callback,
        help="Credentials, diagnostics, tools and Git hooks for every repository.",
    )
    setup.add_command(originals["self-service"].commands["completion"])
    setup.add_command(originals["self-service"].commands["extension"])
    validate = ForwardCommand(originals["validate"], ["validate"], entries)
    from .jobs import ProjectGroup

    maintainer = ProjectGroup(
        "maintainer",
        audience="maintainer",
        invoke_without_command=True,
        callback=originals["maintainer"].callback,
        help="Maintain the workspace and its repositories.",
    )
    config = AccessGroup(
        "config", help="Inspect repository configurations and export the schema."
    )
    config.add_command(
        ForwardCommand(
            originals["maintainer"].commands["config"].commands["show"],
            ["maintainer", "config", "show"],
            entries,
        )
    )
    config.add_command(originals["maintainer"].commands["config"].commands["schema"])
    maintainer.add_command(originals["maintainer"].commands["matrix"])
    maintainer.add_command(originals["maintainer"].commands["gen-workflows"])
    maintainer.add_command(config)
    maintainer.add_command(originals["maintainer"].commands["sync"])
    maintainer.add_command(originals["workflow"])

    def permitted(key, skip=None):
        """Refuse before any repository runs if one of them denies the command."""

        def select(params):
            selected = []
            for alias, state in states():
                project = state.project()
                if not command_allowed(
                    key, state.role(), project.config.command_audience
                ):
                    raise PtkError(
                        f"{alias}: 'ptk {key.replace('.', ' ')}' is a maintainer-only command"
                    )
                if skip is None or not skip(state, project, params):
                    selected.append(alias)
            return selected

        return select

    def without_hooks(state, project, params):
        return not state.app.hooks.command_config(project).is_file()

    hooks = AccessGroup(
        "hooks", help="Install, remove or inspect Git hooks in every repository."
    )
    for name in ("install", "uninstall", "status"):
        hooks.add_command(
            ForwardCommand(
                originals["self-service"].commands["hooks"].commands[name],
                ["self-service", "hooks", name],
                entries,
                permitted(f"self-service.hooks.{name}", without_hooks),
            )
        )
    setup.add_command(hooks)

    def tool_repositories(params):
        jobs = params.get("jobs") or ()
        selected = permitted(
            "self-service.tools",
            lambda state, project, _: not set(jobs) <= set(project.config.jobs),
        )(params)
        if jobs and not selected:
            raise PtkError(f"no repository defines job(s) {', '.join(jobs)}")
        return selected

    setup.add_command(
        ForwardCommand(
            originals["self-service"].commands["tools"],
            ["self-service", "tools"],
            entries,
            tool_repositories,
        )
    )
    maintainer.add_command(
        ForwardCommand(
            originals["maintainer"].commands["configs-report"],
            ["maintainer", "configs-report"],
            entries,
            permitted("maintainer.configs-report"),
        )
    )
    version = AccessGroup(
        "version", help="Show the discovered versions of every repository."
    )
    version.add_command(
        ForwardCommand(
            originals["maintainer"].commands["version"].commands["show"],
            ["maintainer", "version", "show"],
            entries,
            permitted(
                "maintainer.version.show",
                lambda state, project, _: project.config.versioning is None,
            ),
        )
    )
    maintainer.add_command(version)

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
                policies.get(k) == "maintainer"
                for k in ("self-service", "self-service.doctor")
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
    creds.add_command(originals["self-service"].commands["creds"].commands["setup"])

    @creds.command("list")
    @click.argument("name", required=False)
    @guarded
    def list_credentials(name):
        catalog = credentials()
        if name and name not in catalog:
            raise click.ClickException(
                f"unknown or ambiguous credential {name!r}; use self-service creds list"
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
        original = originals["self-service"].commands["creds"].commands[operation]

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
            args = ["self-service", "creds", operation, actual]
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
    # The vault belongs to the user, not to a repository: these run once.
    for name in ("lock", "reset"):
        creds.add_command(originals["self-service"].commands["creds"].commands[name])
    setup.add_command(creds)
    variant = click.RichGroup("variant", help="List variants in every repository.")
    for name in ("list",):
        variant.add_command(
            ForwardCommand(
                originals["variant"].commands[name], ["variant", name], entries
            )
        )
    report = click.RichGroup(
        "report",
        help="Read workspace-wide run status; exports remain repository-specific.",
    )

    report.add_command(originals["report"].commands["open"])

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

    @click.command("jobs")
    @guarded
    def list_jobs():
        """List the jobs of every repository that you may run there."""
        shown, failed = 0, False
        for alias, state in states():
            try:
                project, role = state.project(), state.role()
            except PtkError as exc:
                click.echo(f"{alias}: {exc}", err=True)
                failed = True
                continue
            for name, job in sorted(project.config.jobs.items()):
                if not visible(job.audience, role):
                    continue
                marks = "".join(
                    f" ({mark})"
                    for mark, active in (
                        ("maintainer", job.audience == "maintainer"),
                        ("gui", job.gui),
                    )
                    if active
                )
                click.echo(f"{alias}/{name}{marks}: {job.help}")
                shown += 1
        if not shown:
            click.echo("no jobs")
        if failed:
            raise click.exceptions.Exit(1)

    @click.command("help")
    @click.option(
        "-o",
        "--output",
        type=click.Path(path_type=Path, dir_okay=False),
        help="Where to write the page (default: .ptk/help.html in the VMR root).",
    )
    @click.option(
        "--no-open", is_flag=True, help="Only write the file, do not open the browser."
    )
    @guarded
    def workspace_help(output, no_open):
        """Open the advanced help of the whole VMR as a web page. Works offline."""
        from datetime import datetime

        from ...adapters.workflow_files import read_workflows
        from ...application.use_cases.help import HelpWorkspace, workflow_help
        from .main import (
            _assistant,
            _collect_commands,
            repository_help,
            write_and_open,
        )

        root_path = parent.app.workspace.root(Path.cwd())
        role = parent.app.workspace_role(root_path)
        commands = root.meta.get("vmr_commands") or build_commands(root, entries)
        repositories = []
        for alias, state in states():
            group = root.command.get_command(root, alias)
            with click.Context(group, info_name=alias, parent=root, obj=state) as child:
                _, doc = repository_help(child, state, alias)
            repositories.append(doc)
        workflows = []
        if (root_path / "workflows").is_dir():
            for name, spec in read_workflows(root_path / "workflows").workflows.items():
                if visible(spec.audience, role):
                    workflows.append(workflow_help(name, spec, spec.audience))
        assistant = _assistant(parent.app, None)
        if assistant is not None:
            assistant.installed_repositories = [
                doc.alias
                for doc in repositories
                if doc.assistant and doc.assistant.installed_version
            ]
        for doc in repositories:
            doc.assistant = None
        page = HelpWorkspace(
            version=parent.app.version,
            generated=datetime.now().astimezone().strftime("%Y-%m-%d %H:%M"),
            role=role,
            root=str(root_path),
            commands=_collect_commands(root.command, root, role, commands),
            workflows=workflows,
            repositories=repositories,
            assistant=assistant,
        )
        write_and_open(
            parent, page, output or root_path / ".ptk" / "help.html", no_open
        )

    from .cleanup import vmr_clean_all
    from .workflows import workflow_group

    return {
        c.name: c
        for c in (
            originals["init"],
            setup,
            maintainer,
            validate,
            variant,
            report,
            list_repositories,
            list_jobs,
            workspace_help,
            workflow_group,
            vmr_clean_all,
            originals["describe"],
        )
    }
