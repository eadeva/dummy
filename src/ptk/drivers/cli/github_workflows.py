"""Generate callable GitHub workflows from the configured graph and cx.ptk.yml."""

import json
import shutil
from dataclasses import dataclass
from datetime import datetime

import rich_click as click
import yaml

from ...application.use_cases.matrix import ExportMatrix
from ...application.use_cases.role import visible
from ...application.use_cases.variants import VariantService
from ...application.use_cases.workflow_variants import WorkflowVariants
from ...bootstrap import create_app
from ...domain.credentials import key_for
from ...domain.errors import PtkError
from ...domain.workflows import workflow_job_id
from .state import CliState, guarded
from .workflows import catalog


class WorkflowDumper(yaml.SafeDumper):
    def ignore_aliases(self, data):
        return True


def _text(dumper, value):
    style = "|" if "\n" in value else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", value, style=style)


WorkflowDumper.add_representer(str, _text)


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
    ancestors = spec.ancestors()
    ordered = sorted(spec.jobs, key=lambda key: len(ancestors[key]))
    for selection in selections:
        variants = WorkflowVariants(owner_project, selection)
        if variants.selected in seen:
            continue
        seen.add(variants.selected)
        rows = {}
        for invocation in ordered:
            call = spec.jobs[invocation]
            if any(dep not in rows for dep in call.needs):
                continue
            alias, _, job = invocation.partition(":")
            if not job:
                alias, job = owner, alias
            state = member_state(parent, entries, owners, alias)
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
            if not eligible:
                continue
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
                "invocation": workflow_job_id(invocation),
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


MARKER = "# Generated by ptk maintainer gen-workflows."


def member_state(parent, entries, owners, alias):
    if alias in entries and alias not in owners:
        owners[alias] = CliState(
            create_app(
                host=parent.app.host,
                workspace=parent.app.workspace,
                started_at=parent.app.started_at,
            ),
            config=entries[alias],
            cx=parent.cx,
            overrides=parent.overrides,
        )
    if alias not in owners:
        raise PtkError(f"unknown repository {alias!r}; complete the VMR checkout first")
    return owners[alias]


def _secret(name):
    return "${{ secrets." + name + " }}"


@dataclass(frozen=True)
class CxSettings:
    """Resolved cx.ptk.yml values; secrets are referenced by name only."""

    runner_group: str
    image: str
    login: str
    token_secret: str
    pmt_repository: str
    pmt_version: str
    checkout: dict | None = None  # checkout-or-repo-init inputs of a VMR
    private_key_secret: str | None = None
    vmr: bool = False
    custom_checkout: dict | None = None
    upload_manifest: bool = False

    def action(self, name):
        return f"{self.pmt_repository}/.github/actions/{name}@{self.pmt_version}"


def cx_settings(project, *, vmr):
    config = project.config
    cx = config.cx
    alias = config.repository.alias if config.repository else config.project.name
    if cx is None:
        raise PtkError(
            f"{alias}: configure cx.ptk.yml (technical_user, runner_group, pmt.version) first"
        )
    docker = config.docker
    image = cx.image or (docker.image if docker else None)
    if image is None:
        raise PtkError(f"{alias}: set cx.image or docker.image")
    credential = cx.artifactory_credential or (docker.credential if docker else None)
    if credential is None:
        raise PtkError(f"{alias}: set cx.artifactory_credential or docker.credential")
    token = key_for(
        credential,
        "token",
        config.credentials[credential],
        project=config.project.name,
        user=cx.technical_user,
    ).env_var
    login = (docker.login_user if docker else "{user}").replace(
        "{user}", cx.technical_user
    )
    checkout = None
    if vmr and cx.checkout is None:
        if cx.vmr is None:
            raise PtkError(
                f"{alias} belongs to a virtual monorepo; configure cx.vmr (manifest_url, app_id, private_key)"
            )
        checkout = {
            "manifest-url": cx.vmr.manifest_url,
            "manifest-branch": "${{ inputs.manifest-branch }}",
            **({"manifest-name": cx.vmr.manifest_name} if cx.vmr.manifest_name else {}),
            "checkout-ref": "${{ inputs.checkout-ref }}",
            **({"owner": cx.vmr.owner} if cx.vmr.owner else {}),
            "app-id": str(cx.vmr.app_id),
            "private-key": _secret(cx.vmr.private_key),
            "artifactory-token": _secret(token),
        }
    return CxSettings(
        runner_group=cx.runner_group,
        image=image,
        login=login,
        token_secret=token,
        pmt_repository=cx.pmt.repository,
        pmt_version=cx.pmt.version,
        checkout=checkout,
        private_key_secret=cx.vmr.private_key if checkout else None,
        vmr=vmr,
        custom_checkout=cx.checkout,
        upload_manifest=bool(vmr and cx.vmr and cx.vmr.upload_manifest),
    )


def job_secrets(project, job, technical_user):
    """``{ENV: secret}`` for the job's step credentials, named like the CX env convention."""
    config = project.config
    refs = {
        ref.partition(".")[0]
        for step in config.jobs[job].steps.values()
        for ref in step.secrets.values()
    }
    env, optional = {}, set()
    for name in sorted(refs):
        spec = config.credentials.get(name)
        if spec is None:
            raise PtkError(f"job {job!r}: unknown credential {name!r}")
        for field_name in spec.fields:
            if field_name == spec.user_field:
                continue  # in CX the user ID is read from the variable name
            variable = key_for(
                name, field_name, spec, project=config.project.name, user=technical_user
            ).env_var
            env[variable] = _secret(variable)
            if spec.optional:
                optional.add(variable)
    return env, optional


def _execution(settings):
    return {
        "runs-on": {"group": settings.runner_group},
        "container": {
            "image": settings.image,
            "credentials": {
                "username": settings.login,
                "password": _secret(settings.token_secret),
            },
        },
    }


def _checkout(settings):
    step = (
        {"name": "Checkout", **settings.custom_checkout}
        if settings.custom_checkout
        else {
            "name": "Checkout",
            "uses": settings.action("checkout-or-repo-init"),
            # Version discovery reads Git tags and history.
            "with": settings.checkout or {"fetch-depth": "0", "tags": "true"},
        }
    )
    return [
        step,
        {
            "name": "Trust the checkout",
            "shell": "bash",
            "run": "git config --global --add safe.directory '*'\n",
        },
    ]


def _inputs(settings, extra):
    vmr = (
        {
            "manifest-branch": {
                "description": "Manifest branch, tag or commit; empty: the manifest's trunk",
                "type": "string",
                "default": "",
            },
            "checkout-ref": {
                "description": "Branch with an open PR to check out in every VMR repository",
                "type": "string",
                "default": "",
            },
        }
        if settings.vmr
        else {}
    )
    return {
        **extra,
        "no-cache-ptk": {
            "description": "Disable PTk output reuse",
            "type": "boolean",
            "default": False,
        },
        "additional-properties": {
            "description": "Extra Artifactory properties as a JSON object",
            "type": "string",
            "default": "{}",
        },
        **vmr,
    }


def _secrets(settings, env, optional):
    names = {settings.token_secret: True}
    if settings.private_key_secret:
        names[settings.private_key_secret] = True
    names.update({name: name not in optional for name in env})
    return {name: {"required": required} for name, required in names.items()}


def _document(title, on, jobs, comment):
    document = {"name": title, "on": {"workflow_call": on}, "jobs": jobs}
    return (
        f"{MARKER} Do not edit: changes are overwritten.\n"
        "# Remove the line above to keep manual changes; gen-workflows then leaves the file alone.\n"
        + comment
        + yaml.dump(document, Dumper=WorkflowDumper, sort_keys=False, width=110)
    )


def render_job(title, settings, env, optional):
    """Callable workflow running one PTk job for every row of the given matrix."""
    folder = "${{ matrix.working_directory }}"
    result = "${{ runner.temp }}/ptk-result.json"
    artifactory = {
        "PTK_ARTIFACT_USER": settings.login,
        "PTK_ARTIFACT_TOKEN": _secret(settings.token_secret),
    }

    def ptk(name, step_id, run, env, condition=None):
        step = {"name": name, "id": step_id} if step_id else {"name": name}
        if condition:
            step["if"] = condition
        return {
            **step,
            "shell": "bash",
            "working-directory": folder,
            "env": env,
            "run": run,
        }

    steps = [
        *_checkout(settings),
        ptk(
            "Download producer outputs",
            None,
            'ptk maintainer cx download --root "$GITHUB_WORKSPACE"\n',
            {
                "PTK_PRODUCERS": "${{ toJSON(matrix.producers) }}",
                "PTK_NEEDS": "${{ inputs.needs }}",
                **artifactory,
            },
            "${{ toJSON(matrix.producers) != '[]' }}",
        ),
        {
            **ptk(
                "Run PTk job",
                "run",
                "args=()\n"
                'if [[ -n "$PTK_VARIANT" ]]; then args+=(-V "$PTK_VARIANT"); fi\n'
                'if [[ "$PTK_NO_CACHE" == true ]]; then args+=(--no-cache-ptk); fi\n'
                'if [[ "$PTK_MAINTAINER" == true ]]; then args+=(maintainer); fi\n'
                'printf \'%s\' "$PTK_PARAMS" > "$PTK_PARAMS_FILE"\n'
                'ptk "${args[@]}" run "$PTK_JOB" --params "$PTK_PARAMS_FILE"\n',
                {
                    "PTK_JOB": "${{ matrix.job }}",
                    "PTK_VARIANT": "${{ matrix.variant }}",
                    "PTK_MAINTAINER": "${{ matrix.maintainer }}",
                    "PTK_PARAMS": "${{ toJSON(matrix.params) }}",
                    "PTK_PARAMS_FILE": "${{ runner.temp }}/ptk-params.json",
                    "PTK_NO_CACHE": "${{ inputs.no-cache-ptk }}",
                    "PTK_GITHUB_RESULT": result,
                    **env,
                },
            ),
            "continue-on-error": "${{ inputs.continue-on-error }}",
        },
        ptk(
            "Upload declared outputs",
            "upload",
            'ptk maintainer cx upload >> "$GITHUB_OUTPUT"\n',
            {
                "PTK_PRODUCER": "${{ toJSON(matrix) }}",
                "PTK_GITHUB_RESULT": result,
                "PTK_PROPERTIES": "${{ inputs.additional-properties }}",
                "PTK_JOB_OUTCOME": "${{ steps.run.outcome }}",
                **artifactory,
            },
            "${{ !cancelled() }}",
        ),
        {
            "name": "Enforce required output contract",
            "if": "${{ !cancelled() && inputs.continue-on-error }}",
            "shell": "bash",
            "env": {"PTK_OUTPUTS_VALID": "${{ steps.upload.outputs.outputs-valid }}"},
            "run": 'test "$PTK_OUTPUTS_VALID" = true || { echo "Producer output contract was not satisfied"; exit 1; }\n',
        },
    ]
    on = {
        "inputs": _inputs(
            settings,
            {
                "matrix": {
                    "description": 'Rows from "ptk maintainer matrix", as {"include": [...]}',
                    "type": "string",
                    "required": True,
                },
                "needs": {
                    "description": "toJSON(needs) of the caller; producers must be listed there",
                    "type": "string",
                    "default": "{}",
                },
                "max-parallel": {
                    "description": "Concurrent matrix jobs",
                    "type": "number",
                    "default": 4,
                },
                "continue-on-error": {
                    "description": "Tolerate a failed job, but never a failed output contract",
                    "type": "boolean",
                    "default": False,
                },
            },
        ),
        "secrets": _secrets(settings, env, optional),
    }
    jobs = {
        "run": {
            "name": "${{ matrix.job }}${{ matrix.variant && format(' ({0})', matrix.variant) || '' }}",
            **_execution(settings),
            "strategy": {
                "fail-fast": False,
                "max-parallel": "${{ inputs.max-parallel }}",
                "matrix": "${{ fromJSON(inputs.matrix) }}",
            },
            "steps": steps,
        }
    }
    return _document(
        f"PTk job {title}",
        on,
        jobs,
        "# Runs one PTk job per matrix row: restores producer outputs, runs the job and\n"
        "# uploads its declared outputs (also after a failure, for completed steps).\n",
    )


def render_workflow(
    name, spec, settings, *, job_files, env, optional, owner_directory="."
):
    """Callable workflow: setup exports the matrices, then one call-<job>.yml per entry."""
    spec.validate_job_targets()
    ids = {key: workflow_job_id(key) for key in spec.jobs}
    setup = {
        **_execution(settings),
        "outputs": {
            **{
                f"matrix_{key}": "${{ steps.matrix.outputs.matrix_" + key + " }}"
                for key in ids.values()
            },
            **{
                f"has_jobs_{key}": "${{ steps.matrix.outputs.has_jobs_" + key + " }}"
                for key in ids.values()
            },
        },
        "steps": [
            *_checkout(settings),
            {
                "name": "Export PTk variant matrix",
                "id": "matrix",
                "shell": "bash",
                "working-directory": "${{ inputs.project-directory }}",
                "env": {"PTK_WORKFLOW": name, "PTK_VARIANTS": "${{ inputs.variants }}"},
                "run": 'args=()\nif [[ -n "$PTK_VARIANTS" ]]; then args+=(-V "$PTK_VARIANTS"); fi\nptk "${args[@]}" maintainer matrix --workflow "$PTK_WORKFLOW" --format github >> "$GITHUB_OUTPUT"\n',
            },
        ],
    }
    passed = ["no-cache-ptk", "additional-properties"]
    if settings.vmr:
        passed += ["manifest-branch", "checkout-ref"]
    if settings.upload_manifest:
        setup["steps"].append(
            {
                "name": "Upload the VMR manifest",
                "shell": "bash",
                "working-directory": "${{ inputs.project-directory }}",
                "env": {
                    "PTK_WORKFLOW": name,
                    "PTK_VARIANTS": "${{ inputs.variants }}",
                    "PTK_ARTIFACT_USER": settings.login,
                    "PTK_ARTIFACT_TOKEN": _secret(settings.token_secret),
                },
                "run": 'args=()\nif [[ -n "$PTK_VARIANTS" ]]; then args+=(-V "$PTK_VARIANTS"); fi\n'
                'ptk vmr manifest -o "$RUNNER_TEMP/vmr_manifest.xml"\n'
                'ptk "${args[@]}" maintainer cx upload-file "$RUNNER_TEMP/vmr_manifest.xml" --artifact-type vmr_manifest\n',
            }
        )
    jobs = {"setup": setup}
    for target, call in spec.jobs.items():
        key = ids[target]
        dependencies = [ids[dep] for dep in call.needs]
        jobs[key] = {
            "name": target,
            "needs": ["setup", *dependencies],
            "if": "${{ !cancelled() && needs.setup.result == 'success' && needs.setup.outputs.has_jobs_"
            + key
            + " == 'true'"
            + "".join(
                " && needs." + dep + ".result == 'success'" for dep in dependencies
            )
            + " }}",
            "uses": f"./.github/workflows/{job_files[target]}",
            "with": {
                "matrix": "${{ needs.setup.outputs.matrix_" + key + " }}",
                "needs": "${{ toJSON(needs) }}",
                "max-parallel": spec.max_workers,
                "continue-on-error": call.continue_on_error,
                **{item: "${{ inputs." + item + " }}" for item in passed},
            },
            "secrets": "inherit",
        }
    on = {
        "inputs": _inputs(
            settings,
            {
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
            },
        ),
        "secrets": _secrets(settings, env, optional),
    }
    return _document(
        f"PTk {name}",
        on,
        jobs,
        "# Call it from a trigger workflow with `secrets: inherit`. A consumer waits for all\n"
        "# variants of each producer, then downloads its matching variant.\n",
    )


def _write(path, text, *, replace_unmarked, backup):
    # call-x.yaml and call-x.yml are the same workflow for GitHub callers.
    twin = path.with_suffix(".yaml")
    if twin.exists() and not path.exists():
        current = twin.read_text(encoding="utf-8")
        if not current.startswith(MARKER) and not replace_unmarked:
            click.echo(
                f"Warning: {twin} was not generated (or was reworked); left unchanged. "
                "Use --replace-unmarked to back it up and replace it.",
                err=True,
            )
            return
        backup.mkdir(parents=True, exist_ok=True)
        shutil.copy2(twin, backup / twin.name)
        click.echo(f"Backed up {twin} to {backup / twin.name}")
        twin.unlink()
    if path.exists():
        current = path.read_text(encoding="utf-8")
        if current == text:
            click.echo(f"Unchanged {path}")
            return
        if not current.startswith(MARKER):
            if not replace_unmarked:
                click.echo(
                    f"Warning: {path} was not generated (or was reworked); left unchanged. "
                    "Use --replace-unmarked to back it up and replace it.",
                    err=True,
                )
                return
            backup.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, backup / path.name)
            click.echo(f"Backed up {path} to {backup / path.name}")
        path.write_text(text, encoding="utf-8", newline="\n")
        click.echo(f"Updated {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    click.echo(f"Created {path}")


@click.command("gen-workflows")
@click.argument("names", nargs=-1)
@click.option(
    "--replace-unmarked",
    is_flag=True,
    help="Also replace existing files without the generated marker, after copying them to .github/workflows_backup/<date>/.",
)
@click.pass_context
@guarded
def gen_workflows(ctx, names, replace_unmarked):
    """Generate call-<workflow>.yml and one call-<job>.yml per job from cx.ptk.yml.

    Files with the generated marker are replaced; files without it are left alone.
    """
    parent, entries, owners, available = catalog(ctx)
    unknown = set(names) - available.keys()
    if unknown:
        raise PtkError("unknown workflows: " + ", ".join(sorted(unknown)))
    pending = {}
    for name in names or available:
        owner, spec, root = available[name]
        if owner is None:
            raise PtkError(
                f"{name}: generate workflows of a repository, not of the VMR root"
            )
        state = owners[owner]
        if state.role() != "maintainer":
            raise PtkError(f"{name}: generation is maintainer-only")
        project = state.project()
        workspace = parent.app.workspace.root(root)
        settings = cx_settings(project, vmr=workspace is not None)
        technical_user = project.config.cx.technical_user
        folder = root / ".github" / "workflows"
        job_files, env, optional = {}, {}, set()
        for target in spec.jobs:
            alias, _, job = target.partition(":")
            if not job:
                alias, job = owner, alias
            member = member_state(parent, entries, owners, alias).project()
            if job not in member.config.jobs:
                raise PtkError(f"{name}: {alias} has no job {job!r}")
            file = f"call-{job}.yml" if alias == owner else f"call-{alias}-{job}.yml"
            job_env, job_optional = job_secrets(member, job, technical_user)
            job_files[target] = file
            env.update(job_env)
            optional |= job_optional
            pending[folder / file] = render_job(target, settings, job_env, job_optional)
        directory = root.relative_to(workspace).as_posix() if workspace else "."
        local_name = name.split("/")[-1]
        pending[folder / f"call-{local_name}.yml"] = render_workflow(
            local_name,
            spec,
            settings,
            job_files=job_files,
            env=env,
            optional=optional,
            owner_directory=directory,
        )
    stamp = datetime.now().astimezone().strftime("%Y-%m-%d_%H%M%S")
    for path, text in pending.items():
        _write(
            path,
            text,
            replace_unmarked=replace_unmarked,
            backup=path.parent.parent / "workflows_backup" / stamp,
        )
