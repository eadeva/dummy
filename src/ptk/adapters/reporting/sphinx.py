"""Capture Sphinx-Needs 8.5 evidence from step build folders, then read snapshots.

No Sphinx runtime dependency or execution of project configuration. Only the
current_version in needs.json is imported. JSON artifacts are bounded; HTML
documentation remains a link to the recorded build output, not a copied site.
"""

from __future__ import annotations

import copy
import json
import os
import shutil
from dataclasses import asdict
from pathlib import Path, PurePosixPath

from ...domain.reporting.model import Contribution, Need, NeedsViolation, SphinxReport

SNAPSHOT = ".ptk-sphinx"
MAX_JSON_BYTES = 32 * 1024 * 1024
ARTIFACTS = {"needs.json", "schema_violations.json"}


def _object(value, description):
    if not isinstance(value, dict):
        raise TypeError(f"{description} must be an object")
    return value


def _text(value):
    return "" if value is None else str(value)


def parse_needs(data, report):
    data = _object(data, "needs export")
    version = data.get("current_version")
    versions = _object(data.get("versions"), "versions")
    if not isinstance(version, str) or version not in versions:
        raise ValueError("current_version must identify an exported version")
    selected = _object(versions[version], "selected version")
    needs = _object(selected.get("needs"), "needs")
    properties = _object(
        selected.get("needs_schema", {}).get("properties", {}), "schema properties"
    )
    defaults = (
        {
            key: copy.deepcopy(value["default"])
            for key, value in properties.items()
            if isinstance(value, dict) and "default" in value
        }
        if selected.get("needs_defaults_removed") is True
        else {}
    )
    parsed = []
    for key, value in needs.items():
        fields = {**copy.deepcopy(defaults), **_object(value, f"need {key}")}
        if fields.get("id", key) != key:
            raise ValueError(f"need {key}: id does not match its export key")
        tags = fields.get("tags") or []
        if not isinstance(tags, list) or not all(isinstance(tag, str) for tag in tags):
            raise ValueError(f"need {key}: tags must be a list of strings")
        parsed.append(
            Need(
                id=key,
                title=_text(fields.get("title")),
                type=_text(fields.get("type")),
                type_name=_text(fields.get("type_name")),
                status=_text(fields.get("status")),
                tags=tags,
                docname=_text(fields.get("docname")),
                line=fields.get("lineno")
                if isinstance(fields.get("lineno"), int)
                else None,
                fields=fields,
            )
        )
    report.project = _text(data.get("project"))
    report.version = version
    report.needs = parsed
    report.needs_imported = True


def parse_violations(data, report):
    data = _object(data, "schema violations export")
    warnings = _object(data.get("validation_warnings"), "validation_warnings")
    parsed = []
    for need_id, records in warnings.items():
        if not isinstance(records, list):
            raise TypeError(f"violations for {need_id} must be a list")
        for record in records:
            record = _object(record, f"violation for {need_id}")
            details = _object(record.get("details"), "violation details")
            severity = details.get("severity", "violation")
            if severity not in ("violation", "warning", "info"):
                raise ValueError(f"unknown schema severity: {severity}")
            children = record.get("children", [])
            if not isinstance(children, list):
                raise TypeError("violation children must be a list")
            parsed.append(
                NeedsViolation(
                    need_id=need_id,
                    level={"violation": "error", "warning": "warning", "info": "note"}[
                        severity
                    ],
                    rule=_text(record.get("subtype")),
                    message=_text(
                        details.get("user_msg")
                        or details.get("validation_msg")
                        or "Schema violation"
                    ),
                    details=details,
                    children=children,
                )
            )
    report.violations = parsed
    report.violations_imported = True
    count = data.get("validated_needs_count")
    report.validated_needs = count if isinstance(count, int) and count >= 0 else None
    report.validation_summary = _text(data.get("validation_summary"))


def _contained_file(path, root):
    return (
        path.is_file()
        and not path.is_symlink()
        and path.resolve().is_relative_to(root.resolve())
    )


def _docs_index(folder, build):
    candidates = [folder / "index.html", folder / "html/index.html"]
    if folder.name == "needs":
        candidates.append(folder.parent / "html/index.html")
    for path in candidates:
        if _contained_file(path, build):
            return path
    return None


def _page(index, docname):
    name = PurePosixPath(docname)
    if (
        not docname
        or name.is_absolute()
        or any(p in ("..", ".") or ":" in p or "\\" in p for p in name.parts)
    ):
        return ""
    path = index.parent.joinpath(*name.parts[:-1], name.name + ".html")
    return str(path) if _contained_file(path, index.parent) else ""


def capture(build: Path, reports: Path, step: str, status: str):
    """Called after an executed, report-visible step's job finishes, before rotation.

    Snapshots sit with other step report inputs, so normal history and workflow
    retention also retain them. Missing exports are not assumed to mean success.
    """
    if not build.is_dir():
        return
    folders = set()
    problems = []

    def scan_error(exc):
        problems.append(f"{step}: cannot scan Sphinx build evidence: {exc}")

    for directory, dirs, files in os.walk(build, followlinks=False, onerror=scan_error):
        dirs[:] = [
            d
            for d in dirs
            if d not in (".doctrees", ".git") and not (Path(directory) / d).is_symlink()
        ]
        if ARTIFACTS.intersection(files):
            folders.add(Path(directory))
    if not folders and not problems:
        return
    target = reports / SNAPSHOT
    target.mkdir(parents=True, exist_ok=True)
    snapshots = []
    for index, folder in enumerate(sorted(folders)):
        report = SphinxReport(step, folder.relative_to(build).as_posix())
        for name, attribute, parser in (
            ("needs.json", "needs_file", parse_needs),
            ("schema_violations.json", "violations_file", parse_violations),
        ):
            source = folder / name
            if not source.exists():
                continue
            try:
                if not _contained_file(source, build):
                    raise ValueError(
                        "artifact must be a regular file inside the step build folder"
                    )
                if source.stat().st_size > MAX_JSON_BYTES:
                    raise ValueError("JSON artifact exceeds 32 MiB")
                destination = target / str(index) / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
                setattr(report, attribute, destination.relative_to(target).as_posix())
                parser(json.loads(destination.read_text(encoding="utf-8-sig")), report)
            except (
                OSError,
                ValueError,
                TypeError,
                AttributeError,
                RecursionError,
            ) as exc:
                problems.append(f"{step}: cannot import {report.source}/{name}: {exc}")
        docs = _docs_index(folder, build) if status == "passed" else None
        if docs:
            report.docs_index = str(docs)
            for need in report.needs:
                need.page = _page(docs, need.docname)
        snapshots.append(asdict(report))
    (target / "report.json").write_text(
        json.dumps({"sphinx": snapshots, "problems": problems}, indent=2) + "\n",
        encoding="utf-8",
    )


def read(reports: Path, step: str):
    target = reports / SNAPSHOT
    result = Contribution(step)
    path = target / "report.json"
    if not path.is_file():
        return result
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        result.problems.extend(data["problems"])
        for item in data["sphinx"]:
            item["needs"] = [Need(**need) for need in item["needs"]]
            item["violations"] = [
                NeedsViolation(**violation) for violation in item["violations"]
            ]
            for key in ("needs_file", "violations_file"):
                if item[key]:
                    item[key] = str(target / item[key])
            result.sphinx.append(SphinxReport(**item))
    except (OSError, ValueError, TypeError, KeyError) as exc:
        result.problems.append(f"{step}: cannot read Sphinx snapshot: {exc}")
    return result
