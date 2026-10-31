"""Generate reviewable callable GitHub workflows from the configured graph."""

import json
import re

import rich_click as click
import yaml

from ...application.use_cases.matrix import ExportMatrix
from ...application.use_cases.role import visible
from ...application.use_cases.variants import VariantService
from ...application.use_cases.workflow_variants import WorkflowVariants
from ...bootstrap import create_app
from ...domain.errors import PtkError
from .state import CliState, guarded
from .workflows import catalog


class WorkflowDumper(yaml.SafeDumper):
    def ignore_aliases(self, data):
        return True


def workflow_matrix(ctx, name, *, at, event):
    parent, entries, owners, available = catalog(ctx)
    if name not in available:
        raise PtkError(f"unknown workflow {name!r}")
    owner, spec, root = available[name]
    owner_project = owners[owner].project() if owner else None
    role = owners[owner].role() if owner else parent.app.workspace_role(root)
    if not visible(spec.audience, role):
        raise PtkError(f"workflow {name!r} is maintainer-only")
    service = VariantService(owner_project) if owner_project else None
    selections = (
        parent.variant.split(",")
        if parent.variant
        else (service.line.buildable() if service and service.has_variants else [None])
    )
    workspace = parent.app.workspace.root(root)
    checkout = workspace or root
    matrices = {key: [] for key in spec.jobs}
    seen = set()
    bases = []
    for selection in selections:
        variants = WorkflowVariants(owner_project, selection)
        if variants.selected in seen:
            continue
        seen.add(variants.selected)
        rows = {}
        for invocation, call in spec.jobs.items():
            alias, _, job = call.job.partition(":")
            if not job:
                alias, job = owner, alias
            if alias in entries and alias not in owners:
                owners[alias] = CliState(
                    create_app(
                        host=parent.app.host,
                        workspace=parent.app.workspace,
                        started_at=parent.app.started_at,
                    ),
                    config=entries[alias],
                    ci=parent.ci,
                    overrides=parent.overrides,
                )
            if alias not in owners:
                raise PtkError(
                    f"unknown repository {alias!r}; complete the VMR checkout first"
                )
            state = owners[alias]
            project = state.project()
            job_spec = project.config.jobs.get(job)
            if job_spec and any(
                key in job_spec.params and job_spec.params[key].type == "secret"
                for key in call.params
            ):
                raise PtkError(
                    "secret parameters must not be stored in workflow configuration; use job credentials"
                )
            selected = variants.for_project(alias, project)
            data = ExportMatrix(state.app.artifacts()).execute(
                project,
                role=state.role(),
                variant=selected,
                jobs=(job,),
                event=event,
                at=at,
            )
            eligible = data["matrix"]["include"]
            if len(eligible) != 1:
                raise PtkError(
                    f"{invocation}: job is not eligible for workflow variant {variants.selected!r}"
                )
            row = eligible[0]
            if not row["upload"]:
                raise PtkError(
                    f"{invocation}: configure Artifactory destinations before running this template"
                )
            try:
                directory = project.root.relative_to(checkout).as_posix()
            except ValueError:
                raise PtkError(
                    f"{alias}: repository must be below the checked-out workspace"
                ) from None
            rows[invocation] = {
                **row,
                "invocation": invocation,
                "working_directory": directory,
                "params": call.params,
                "maintainer": "maintainer" in row["command"],
            }
            bases.append(
                {
                    "url": row["upload"]["base_url"],
                    "path": row["upload"]["base_path"],
                    "repository": row["upload"]["repository"],
                }
            )
        for invocation, row in rows.items():
            row["producers"] = [
                {
                    k: v
                    for k, v in rows[dep].items()
                    if k not in {"producers", "params", "command"}
                }
                for dep in spec.jobs[invocation].needs
            ]
            matrices[invocation].append(row)
    # A mapped producer may be shared by several owner variants. Execute it once,
    # but only when its dependency selectors and parameters are identical too.
    for key, rows in matrices.items():
        if not rows:
            raise PtkError("workflow has no concrete variants to execute")
        unique = {}
        identities = {}
        for row in rows:
            identity = (row["repository"], row["variant"], row["job"])
            encoded = json.dumps(row, sort_keys=True)
            if identity in identities and identities[identity] != encoded:
                raise PtkError(
                    f"{key}: mapped producer has conflicting inputs across owner variants; select one owner variant"
                )
            identities[identity] = encoded
            unique[encoded] = row
        if len(unique) > 256:
            raise PtkError(
                f"{key}: GitHub limits each matrix to 256 jobs; select fewer variants"
            )
        matrices[key] = {"include": list(unique.values())}
    return {
        "schema_version": 1,
        "jobs": matrices,
        "matrix": {"include": [r for m in matrices.values() for r in m["include"]]},
        "upload_base": bases[0]
        if bases and all(b == bases[0] for b in bases)
        else None,
    }


def render_workflow(
    name, spec, *, action_repository, action_ref, vmr=False, owner_directory="."
):
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", action_repository):
        raise PtkError("--action-repository must be OWNER/REPO")
    if not re.fullmatch(r"[A-Za-z0-9_./-]+", action_ref):
        raise PtkError("invalid --action-ref")
    if "setup" in spec.jobs:
        raise PtkError("workflow invocation ID 'setup' is reserved for matrix setup")
    for key in spec.jobs:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", key):
            raise PtkError(f"{key!r} is not a GitHub job ID")

    def action(kind):
        return f"{action_repository}/.github/actions/ptk-{kind}@{action_ref}"

    def checkout():
        if vmr:
            return [
                {
                    "name": "TODO: VMR checkout",
                    "shell": "bash",
                    "run": 'echo "TODO: replace this step with your VMR checkout, preserving the configured repository layout" >&2\nexit 1\n',
                }
            ]
        return [{"uses": "actions/checkout@v4"}]

    credentials = {
        "technical-user": "${{ secrets.PTK_ARTIFACT_USER }}",
        "token": "${{ secrets.PTK_ARTIFACT_TOKEN }}",
    }
    execution = {
        "runs-on": "${{ inputs.runner }}",
        "container": {"image": "${{ inputs.container-image }}"},
    }
    setup = {
        **execution,
        "outputs": {
            **{
                f"matrix_{key}": "${{ steps.matrix.outputs.matrix_" + key + " }}"
                for key in spec.jobs
            },
            "upload_base": "${{ steps.matrix.outputs.upload_base }}",
        },
        "steps": [
            *checkout(),
            {
                "name": "Export PTK variant matrix",
                "id": "matrix",
                "shell": "bash",
                "working-directory": "${{ inputs.project-directory }}",
                "env": {"PTK_WORKFLOW": name, "PTK_VARIANTS": "${{ inputs.variants }}"},
                "run": 'args=()\nif [[ -n "$PTK_VARIANTS" ]]; then args+=(-V "$PTK_VARIANTS"); fi\nptk "${args[@]}" maintainer matrix --workflow "$PTK_WORKFLOW" --format github >> "$GITHUB_OUTPUT"\n',
            },
        ],
    }
    jobs = {"setup": setup}
    for key, call in spec.jobs.items():
        steps = checkout()
        if call.needs:
            steps.append(
                {
                    "name": "Download producer outputs",
                    "uses": action("download"),
                    "with": {
                        **credentials,
                        "needs": "${{ toJSON(needs) }}",
                        "producers": "${{ toJSON(matrix.producers) }}",
                        "working-directory": ".",
                    },
                }
            )
        steps += [
            {
                "name": "Run PTK job",
                "id": "run",
                "uses": action("run-job"),
                "with": {
                    "job": "${{ matrix.job }}",
                    "variant": "${{ matrix.variant }}",
                    "params": "${{ toJSON(matrix.params) }}",
                    "maintainer": "${{ matrix.maintainer }}",
                    "working-directory": "${{ matrix.working_directory }}",
                    "no-cache": "${{ inputs.no-cache-ptk }}",
                },
            },
            {
                "name": "Upload declared outputs",
                "uses": action("upload"),
                "if": "${{ !cancelled() && steps.run.outputs.uploads-json != '' }}",
                "with": {
                    **credentials,
                    "base-url": "${{ matrix.upload.url }}",
                    "producer": "${{ toJSON(matrix) }}",
                    "uploads-json": "${{ steps.run.outputs.uploads-json }}",
                    "working-directory": "${{ matrix.working_directory }}",
                    "additional_properties": "${{ inputs.additional-properties }}",
                },
            },
        ]
        jobs[key] = {
            **execution,
            "needs": ["setup", *call.needs],
            "strategy": {
                "fail-fast": False,
                "max-parallel": spec.max_workers,
                "matrix": "${{ fromJSON(needs.setup.outputs.matrix_" + key + ") }}",
            },
            "steps": steps,
        }
        if call.continue_on_error:
            jobs[key]["continue-on-error"] = True
    document = {
        "name": f"PTK {name}",
        "on": {
            "workflow_call": {
                "inputs": {
                    "runner": {
                        "description": "TODO: select your Linux Docker-capable runner label",
                        "type": "string",
                        "required": True,
                    },
                    "container-image": {
                        "description": "TODO: image with PTK, Python 3.12+, bash, curl and project tools",
                        "type": "string",
                        "required": True,
                    },
                    "project-directory": {
                        "description": "Workflow owner directory inside the checkout/VMR",
                        "type": "string",
                        "default": owner_directory,
                    },
                    "variants": {
                        "description": "Owner variant names/aliases, comma-separated; empty selects all concrete variants",
                        "type": "string",
                        "default": "",
                    },
                    "no-cache-ptk": {
                        "description": "Disable PTK output reuse",
                        "type": "boolean",
                        "default": False,
                    },
                    "additional-properties": {
                        "description": "Extra Artifactory properties as a JSON object",
                        "type": "string",
                        "default": "{}",
                    },
                },
                "secrets": {
                    "PTK_ARTIFACT_USER": {"required": True},
                    "PTK_ARTIFACT_TOKEN": {"required": True},
                },
            }
        },
        "permissions": {"contents": "read"},
        "jobs": jobs,
    }
    return (
        "# Generated by ptk maintainer gen-workflows. Review and commit this template.\n"
        "# TODO: create a caller workflow with your push/PR/schedule events.\n"
        "# TODO: provide runner and container-image inputs; PTK must already be installed.\n"
        "# TODO: configure private Docker registry credentials/mounts if needed.\n"
        "# TODO: review and pin action refs to approved immutable commits.\n"
        "# All jobs depend on setup; only configured producer needs supply artifacts.\n"
        "# A consumer waits for all variants of each producer, then downloads its matching variant.\n"
        "# Downloads replace declared paths; do not declare source roots or overlapping outputs.\n"
        "# Upload runs after a failed job too, for outputs from successfully completed steps.\n"
        + (
            "# TODO: replace EVERY VMR checkout placeholder, including setup; no ordinary checkout is generated.\n"
            if vmr
            else ""
        )
        + yaml.dump(document, Dumper=WorkflowDumper, sort_keys=False, width=110)
    )


@click.command("gen-workflows")
@click.argument("names", nargs=-1)
@click.option(
    "--action-repository",
    default="eadeva/dummy",
    show_default=True,
    help="Repository containing the three composite Actions.",
)
@click.option(
    "--action-ref",
    default="codex/decentralized-configuration",
    show_default=True,
    help="Action revision; pin an approved commit before production use.",
)
@click.pass_context
@guarded
def gen_workflows(ctx, names, action_repository, action_ref):
    """Create callable workflow templates; never overwrite existing files."""
    parent, _, owners, available = catalog(ctx)
    unknown = set(names) - available.keys()
    if unknown:
        raise PtkError("unknown workflows: " + ", ".join(sorted(unknown)))
    pending = []
    for name in names or available:
        owner, spec, root = available[name]
        state = owners[owner] if owner else parent
        role = state.role() if owner else parent.app.workspace_role(root)
        if role != "maintainer":
            raise PtkError(f"{name}: generation is maintainer-only")
        workspace = parent.app.workspace.root(root)
        directory = root.relative_to(workspace).as_posix() if workspace else "."
        local_name = name.split("/")[-1]
        text = render_workflow(
            local_name,
            spec,
            action_repository=action_repository,
            action_ref=action_ref,
            vmr=workspace is not None,
            owner_directory=directory,
        )
        pending.append((root / ".github" / "workflows" / f"ptk-{local_name}.yml", text))
    for path, text in pending:
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with path.open("x", encoding="utf-8") as stream:
                stream.write(text)
        except FileExistsError:
            click.echo(
                f"Warning: workflow already exists; left unchanged: {path}", err=True
            )
        else:
            click.echo(f"Created {path}")
