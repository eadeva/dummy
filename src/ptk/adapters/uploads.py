"""Snapshot declared outputs after execution for an external workflow uploader."""

import json
import os
import tempfile
from contextlib import suppress
from pathlib import Path

from ..domain.execution.model import Status


def write_upload(prepared, result):
    plan = prepared.plan
    records = []
    files = []
    step_paths = set()
    context = plan.report_context
    alias = context.get("repository_alias", plan.project)
    version = (
        context.get("versions", {}).get("projects", {}).get(alias, {}).get("value")
    )
    variants = list(
        dict.fromkeys(
            [plan.variant or "default", *context.get("variant", {}).get("aliases", [])]
        )
    )
    common = {
        "version": version,
        "commit": context.get("source_commit"),
        "variant_alias": variants,
        "job": plan.job,
    }

    def collect(paths, declarations, step, eligible, reused_from=""):
        for path, declaration in zip(paths, declarations, strict=True):
            path = Path(os.path.abspath(path))
            if step is None and str(path) in step_paths:
                continue  # The explicit step declaration provides better provenance.
            if step is not None:
                step_paths.add(str(path))
            artifact_type = getattr(declaration, "artifact_type", None)
            try:
                kind = (
                    "symlink"
                    if path.is_symlink()
                    else "file"
                    if path.is_file()
                    else "directory"
                    if path.is_dir()
                    else "other"
                    if path.exists()
                    else "missing"
                )
            except OSError:
                kind = "unreadable"
            reason = None if eligible else "producer did not complete successfully"
            if kind not in {"file", "directory"}:
                reason = kind
            properties = {**common, "step": step}
            if artifact_type is not None:
                properties["artifact_type"] = artifact_type
            item = {"path": str(path), "kind": kind, "properties": properties}
            # External local outputs intentionally have no portable path.
            with suppress(ValueError):
                item["relative_path"] = path.relative_to(
                    prepared.project.root.resolve()
                ).as_posix()
            if reused_from:
                item["reused_from"] = reused_from
            if prepared.mask_context(item) != item:
                reason = "contains masked values"
            records.append(
                prepared.mask_context(
                    {
                        "path": str(path),
                        "step": step,
                        "kind": kind,
                        "artifact_type": artifact_type,
                        "available": reason is None,
                        **({"reason": reason} if reason else {}),
                    }
                )
            )
            if reason is None:
                files.append(item)

    results = {step.name: step for step in result.steps}
    for step in plan.steps:
        outcome = results[step.name]
        if not step.outputs:
            continue
        collect(
            step.outputs,
            step.spec.outputs,
            step.name,
            outcome.status == Status.PASSED and outcome.launched_pid is None,
            outcome.reused_from,
        )
    selection = context.get("selection", {})
    complete = (
        result.ok
        and not plan.gui_step
        and not selection.get("only_step")
        and not selection.get("to")
        and all(step.status == Status.PASSED for step in result.steps)
    )
    collect(
        plan.outputs,
        prepared.project.config.jobs[plan.job].outputs,
        None,
        complete,
        result.reused_from,
    )
    result.outputs = records
    document = {
        "schema_version": 1,
        "run_id": plan.run_id,
        "repository": alias,
        "producer": {
            "repository": alias,
            "job": plan.job,
            "variant": plan.variant,
            "version": version,
            "commit": common["commit"],
        },
        "files": files,
    }
    destination = Path(plan.dirs["log_dir"]) / "upload.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=destination.parent, delete=False
        ) as stream:
            temporary = Path(stream.name)
            json.dump(
                prepared.mask_context(document), stream, ensure_ascii=False, indent=2
            )
            stream.write("\n")
        os.replace(temporary, destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    result.upload_file = prepared.mask(str(destination))
