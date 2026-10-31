"""Read-only editor inventory. Never resolve versions, tools or credentials."""

from dataclasses import asdict
from math import isfinite
from pathlib import Path

from ...domain.config import tree as t
from ...domain.config.layout import editor_layout
from ...domain.config.model import JobSpec
from ...domain.config.template_variables import catalogue
from ...domain.graphs import describe_graph
from ...domain.workflows import WorkflowSpec
from .project import ExportSchema
from .role import command_allowed, visible
from .variants import VariantService


def describe_configuration(
    tree, root, files, error=None, fingerprints=None, environment_names=()
):
    """Authored model and schema from the installed PTK, never an editor loader."""
    sources = []
    locked = []

    def portable(value, path=()):
        if isinstance(value, dict):
            return {key: portable(child, (*path, key)) for key, child in value.items()}
        if isinstance(value, list):
            return [
                portable(child, (*path, index)) for index, child in enumerate(value)
            ]
        if value is None or isinstance(value, (str, bool)):
            return value
        if (
            isinstance(value, int)
            and abs(value) <= 2**53 - 1
            or isinstance(value, float)
            and isfinite(value)
            and abs(value) <= 2**53 - 1
        ):
            return value
        # Preserve precise YAML values in their source; JSON/JavaScript cannot
        # round-trip dates, binary data, infinities or arbitrarily large integers.
        locked.append(list(path))
        return str(value)

    value = portable(t.to_plain(tree)) if tree is not None else None
    if tree is not None:
        for path, location in t.provenance(tree).items():
            file = Path(location.file)
            if not file.is_absolute():
                file = root / file
            sources.append(
                {"path": list(path), "file": str(file), "line": location.line}
            )
    graphs = []
    for section, model, child in (
        ("jobs", JobSpec, "steps"),
        ("workflows", WorkflowSpec, "jobs"),
    ):
        entries = value.get(section, {}) if isinstance(value, dict) else {}
        if not isinstance(entries, dict):
            continue
        for name, authored in entries.items():
            path = [section, name, child]
            try:
                spec = model.model_validate(authored)
                if isinstance(spec, WorkflowSpec):
                    repository = value.get("repository")
                    spec.validate_job_targets(
                        repository.get("alias")
                        if isinstance(repository, dict)
                        else None
                    )
                graphs.append({"path": path, **describe_graph(getattr(spec, child))})
            except ValueError as exc:
                graphs.append(
                    {"path": path, "nodes": [], "tree": [], "error": str(exc)}
                )
    schema = ExportSchema().execute()
    return {
        "version": 5,
        "graphs": graphs,
        "fingerprints": fingerprints or {},
        **editor_layout(root / ".main.ptk.yml", tree, schema),
        "schema": schema,
        "variables": catalogue(value, environment_names),
        "value": value,
        "locked": locked,
        "sources": sources,
        "files": [str(file) for file in files],
        "error": error,
    }


def describe_project(project, role, *, configuration=False, environment_names=()):
    """Expose only permitted operations and authored, non-secret parameter metadata."""
    config = project.config
    capabilities = {
        name: command_allowed(path, role, config.command_audience)
        for name, path in {
            "validate": "validate",
            "variants": "variant",
            "reports": "report",
            "maintenance": "maintainer.sync",
        }.items()
    }
    variants = VariantService(project)
    items = (
        variants.list() if variants.has_variants and capabilities["variants"] else []
    )
    return {
        "alias": config.repository.alias,
        "name": config.project.name,
        "root": str(project.root),
        "entry_file": str(project.main_file),
        "config_files": [str(path) for path in project.files],
        **(
            {
                "configuration": describe_configuration(
                    project.authored_tree or project.tree,
                    project.root,
                    project.files,
                    fingerprints=project.fingerprints,
                    environment_names=environment_names,
                )
            }
            if configuration
            else {}
        ),
        "role": role,
        "capabilities": capabilities,
        "default_variant": next((item.name for item in items if item.default), None),
        "variants": [asdict(item) for item in items],
        "jobs": [
            {
                "name": name,
                "help": spec.help,
                "gui": spec.gui,
                "command": [
                    *(["maintainer"] if spec.audience == "maintainer" else []),
                    "run",
                    name,
                ],
                "help_command": [
                    *(["maintainer"] if spec.audience == "maintainer" else []),
                    name,
                ],
                "default": name == config.project.default_job,
                "params": [
                    {
                        "name": key,
                        "type": param.type,
                        "required": param.required,
                        "choices": param.choices or [],
                        "help": param.help,
                        "default": param.default,
                        "env": param.env,
                        "default_is_template": param.default_is_template,
                    }
                    for key, param in spec.params.items()
                    if param.type != "secret"
                ],
            }
            for name, spec in config.jobs.items()
            if visible(spec.audience, role) and (not spec.only_cx or project.ci)
        ],
        "workflows": [
            {
                "name": name,
                "help": spec.help,
                "command": [
                    *(
                        ["maintainer"]
                        if spec.audience == "maintainer"
                        or config.command_audience.get("workflow") == "maintainer"
                        else []
                    ),
                    "workflow",
                    "run",
                    name,
                ],
            }
            for name, spec in config.workflows.items()
            if visible(spec.audience, role)
            and command_allowed("workflow", role, config.command_audience)
        ],
    }
