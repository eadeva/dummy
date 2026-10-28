"""Serialize logical-model test fixtures into the public document layout.

Runtime/loader tests write literal files directly. Execution tests use this
builder so their inputs describe the behavior under test, without repeating
filesystem setup for every job, feature and variant.
"""

import textwrap

import yaml


def project_files(text, extra=None):
    model = yaml.safe_load(textwrap.dedent(text)) or {}
    model.setdefault("repository", {"alias": "demo", "config_path": "."})
    folder = model["repository"]["config_path"]

    def file(name):
        return name if folder == "." else f"{folder}/{name}"

    marker_keys = {"repository", "virtual_monorepo", "schema_version", "ptk_version"}
    sections = {
        "layout": "folder_structure",
        "artifactory": "artifactory_paths",
        "credentials": "credentials",
        "tools": "tools",
        "versioning": "versioning",
        "configs": "configs",
    }
    files = {".main.ptk.yml": {k: v for k, v in model.items() if k in marker_keys}}
    project = dict(model.get("project", {}))
    for key, value in model.items():
        if key not in marker_keys | set(sections) | {
            "project",
            "jobs",
            "workflows",
            "variants",
        }:
            project[key] = value
    files[file("project.ptk.yml")] = project
    for key, name in sections.items():
        if key in model:
            files[file(name + ".ptk.yml")] = model[key]
    variants = model.get("variants") or {}
    if isinstance(variants, dict):
        settings = {
            k: v for k, v in variants.items() if k not in {"components", "variants"}
        }
        if settings:
            files[file("project.variants.ptk.yml")] = settings
        for name, component in variants.get("components", {}).items():
            directory = f"components/{name}"
            project.setdefault("components", {})[name] = {"path": directory}
            files[f"{directory}/component.variants.ptk.yml"] = component
        for name, variant in variants.get("variants", {}).items():
            files[file(f"variants/{name}.ptk.yml")] = variant
    else:
        files[file("project.variants.ptk.yml")] = variants
    for section in ("jobs", "workflows"):
        for name, value in model.get(section, {}).items():
            files[file(f"{section}/{name}.ptk.yml")] = value
    result = {
        path: yaml.safe_dump(value, sort_keys=False, allow_unicode=True)
        for path, value in files.items()
    }
    result.update(extra or {})
    return result


_written = {}


def write_project(entry, model, *, encoding="utf-8"):
    """Create conventional files for a logical test model; return its marker."""
    if not isinstance(model, str):
        model = yaml.safe_dump(model, sort_keys=False)
    files = project_files(model)
    for relative in _written.get(entry, set()) - files.keys():
        (entry.parent / relative).unlink(missing_ok=True)
    for relative, text in files.items():
        path = entry.parent / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    _written[entry] = set(files)
    return entry


def read_project(entry):
    """Read the authored logical model through the actual PTK loader."""
    from ptk.bootstrap import create_app
    from ptk.domain.config.tree import to_plain

    return to_plain(
        create_app(environ={}).load_project.execute(config_file=entry).authored_tree
    )


def write_workflows(folder, workflows):
    folder.mkdir(parents=True, exist_ok=True)
    for name, spec in workflows.items():
        (folder / f"{name}.ptk.yml").write_text(yaml.safe_dump(spec, sort_keys=False))
