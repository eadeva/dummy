"""GN generation diagnostics and native JSON target models, retained per attempt."""

from __future__ import annotations

import json
import os
import re
import time
import uuid
from dataclasses import asdict, replace
from graphlib import TopologicalSorter
from pathlib import Path

from ...domain.execution.commands import split_words
from ...domain.reporting.gn import identity, message
from ...domain.reporting.log_analysis import ANSI, diagnostic
from ...domain.reporting.model import Contribution, GNReport, LogFinding
from .evidence import mask_data

MAX_BYTES = 100 * 1024 * 1024
MAX_GRAPH_TARGETS = 2000
READ_ERRORS = (OSError, ValueError, TypeError, KeyError, AttributeError, RecursionError)
SNAPSHOT = ".ptk-gn"
GENERATED = ".ptk.gn-project.json"


def bounded_text(path, root):
    if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("GN evidence path is a symlink or escapes its root")
    with path.open("rb") as stream:
        content = stream.read(MAX_BYTES + 1)
    if len(content) > MAX_BYTES:
        raise ValueError("GN evidence exceeds 100 MiB")
    return content.decode("utf-8-sig")


def stamp(path):
    try:
        stat = path.stat()
        return stat.st_mtime_ns, stat.st_ctime_ns, stat.st_size
    except OSError:
        return None


def project_name(name):
    return name == "project.json" or name.endswith(".gn-project.json")


def discover(roots):
    result = {}
    for root in roots:
        for directory, dirs, files in os.walk(root, followlinks=False):
            folder = Path(directory)
            dirs[:] = [
                d
                for d in dirs
                if d
                not in (
                    ".git",
                    ".cmake",
                    "CMakeFiles",
                    SNAPSHOT,
                    ".ptk-cmake",
                    ".ptk-bazel",
                )
                and not (folder / d).is_symlink()
            ]
            for name in files:
                if name.endswith(".gn-project.json"):
                    path = folder / name
                    result[path] = (root, stamp(path))
    return result


def invocation(command, os_name):
    if command.shell is not None:
        if re.search(r"[\n\r&|;<>`$%*?]", command.shell):
            return None
        words = split_words(command.shell, os_name)
    else:
        words = list(command.argv or [])
    name = words[0].replace("\\", "/").rsplit("/", 1)[-1] if words else ""
    if not re.fullmatch(r"gn(?:-\d[\w.-]*)?(?:\.exe)?", name, re.IGNORECASE):
        return None
    if "--" in words or any(w in ("--help", "--version", "-h") for w in words):
        return None
    positional = [w for w in words[1:] if not w.startswith("-")]
    if len(positional) != 2 or positional[0] != "gen":
        return None  # GN value switches use --name=value; do not guess a wrapper.
    values = {}
    for word in words[1:]:
        if word.startswith("--"):
            name, _, value = word.partition("=")
            values.setdefault(name, []).append(value)
    cwd = Path(command.cwd).resolve()
    if "--root" in values:
        root = (cwd / values["--root"][-1]).resolve()
    else:
        root = next((p for p in (cwd, *cwd.parents) if (p / ".gn").is_file()), None)
    output = positional[1]
    if output.startswith("//"):
        build = (root / output[2:]).resolve() if root else None
    else:
        build = (cwd / output).resolve()
    return words, values, root, build


def console(report, lines, source="GN console"):
    groups, current = {}, None
    for number, line in enumerate(lines, 1):
        clean = ANSI.sub("", line).strip()
        value = diagnostic(line)
        if value:
            value["message"] = message(lines, number - 1, value["message"])
            finding = LogFinding(tool="GN", step=report.step, **value)
            key = identity(finding, report.root)
            if key not in groups:
                finding.context = ["Source: " + source, "GN header: " + clean]
                finding.log_line = number
                finding.log_lines = [number]
                report.diagnostics.append(finding)
                groups[key] = finding
            else:
                groups[key].occurrences += 1
                if (
                    "GN header: " + clean not in groups[key].context
                    and len(groups[key].context) < 25
                ):
                    groups[key].context.append("GN header: " + clean)
                if len(groups[key].log_lines) < 50:
                    groups[key].log_lines.append(number)
            current = groups[key]
        elif clean.startswith(("Done.", "Generating ")):
            current = None
        elif (
            current
            and clean
            and clean not in current.context
            and len(current.context) < 25
        ):
            current.context.append(clean[:500])


def parse_project(report, path, root):
    data = json.loads(bounded_text(path, root))
    settings, targets = data["build_settings"], data["targets"]
    if not isinstance(settings, dict) or not isinstance(targets, dict):
        raise TypeError("expected GN build_settings and targets objects")
    report.root = str(settings["root_path"])
    output = str(settings["build_dir"])
    report.build_dir = (
        str(Path(report.root) / output[2:]) if output.startswith("//") else output
    )
    report.configuration = {
        "Default toolchain": settings.get("default_toolchain", ""),
        "Generation input files": len(settings.get("gen_input_files", [])),
    }
    records = []
    for name, value in sorted(targets.items()):
        if not isinstance(value, dict) or not isinstance(value.get("type"), str):
            raise TypeError(f"invalid GN target: {name}")
        deps = value.get("deps", [])
        if not isinstance(deps, list) or any(not isinstance(d, str) for d in deps):
            raise ValueError(f"invalid GN dependencies: {name}")
        records.append(
            {
                "id": name,
                "type": value["type"],
                "toolchain": value.get("toolchain", ""),
                "testonly": bool(value.get("testonly", False)),
                "needs": sorted(set(deps)),
            }
        )
    report.targets = records
    report.source = str(path)
    report.availability["targets"] = (
        "GN native project JSON; configured targets, not compilation results"
    )
    nodes = {
        t["id"]: {
            "id": t["id"],
            "label": t["type"],
            "kind": "gn-target",
            "needs": t["needs"],
            "toolchain": t["toolchain"],
            "status": "configured",
            "message": "Test-only target."
            if t["testonly"]
            else "Generated target; no compilation result recorded.",
        }
        for t in records
    }
    for target in records:
        for dep in target["needs"]:
            if dep not in nodes:
                nodes[dep] = {
                    "id": dep,
                    "needs": [],
                    "status": "unavailable",
                    "message": "Target not included in the GN JSON export; its dependencies are unavailable.",
                }
    if len(nodes) > MAX_GRAPH_TARGETS:
        report.availability["target graph"] = (
            f"Not displayed: exceeds {MAX_GRAPH_TARGETS} targets; target records remain available"
        )
        return
    tuple(
        TopologicalSorter(
            {name: node["needs"] for name, node in nodes.items()}
        ).static_order()
    )
    report.graph = {
        "nodes": list(nodes.values()),
        "caption": "Target dependencies: prerequisites → dependents. Shared targets appear once.",
        "notice": "GN's native target model includes linked and data dependencies. Files and toolchain implementation details are omitted. This describes generation, not which targets compiled successfully. Filtered-out targets are marked unavailable.",
    }
    report.availability["target graph"] = "Native GN JSON dependencies"


def probe(runner, command, executable, args, cancel):
    lines, size = [], 0

    def output(line):
        nonlocal size
        size += len(line.encode("utf-8")) + 1
        if size <= 128 * 1024:
            lines.append(line)

    result = runner.run(
        replace(command, argv=[executable, *args], shell=None, timeout=10),
        output,
        cancel,
    )
    return (
        "\n".join(lines)
        if result.exit_code == 0 and not result.timed_out and not result.cancelled
        else ""
    )


class GNReportingRunner:
    def __init__(self, runner, os_name):
        self.runner, self.os_name = runner, os_name

    def run(self, command, on_output, cancel=None, *, mask, on_problem, execute=None):
        execute = execute or self.runner.run
        reports = Path(command.env["PTK_STEP_REPORTS_DIR"]).resolve()
        step = command.env["PTK_STEP"]
        roots = [Path(command.env["PTK_BUILD_DIR"]).resolve(), reports]
        records, problems, before = [], [], {}
        effective, direct, project, report = command, None, None, None
        prepared = time.monotonic()
        try:
            before = discover(roots)
            direct = invocation(command, self.os_name)
            if direct:
                words, values, root, build = direct
                child_path = next(
                    (v for k, v in command.env.items() if k.upper() == "PATH"), ""
                )
                program = (
                    str((Path(command.cwd) / words[0]).resolve())
                    if "/" in words[0] or "\\" in words[0]
                    else words[0]
                )
                executable = self.runner.which(program, path=child_path) or program
                report = GNReport(
                    step,
                    "Captured GN console",
                    executable=executable,
                    root=str(root or ""),
                    build_dir=str(build or ""),
                )
                records.append(report)
                report.version = probe(
                    self.runner, command, executable, ["--version"], cancel
                ).strip()[:256]
                report.availability["version"] = (
                    "Selected executable --version"
                    if report.version
                    else "Unavailable from selected executable"
                )
                report.availability["target graph"] = (
                    "Unavailable: no native JSON export"
                )
                ide = values.get("--ide", [])
                if "json" in ide:
                    name = (
                        values.get("--json-file-name", ["project.json"])[-1]
                        or "project.json"
                    )
                    if name.startswith("//"):
                        project = root / name[2:] if root else None
                    elif build is not None:
                        project = build / name
                elif (
                    not ide
                    and not any(
                        k in values
                        for k in (
                            "--json-file-name",
                            "--json-ide-script",
                            "--json-ide-script-args",
                        )
                    )
                    and build is not None
                ):
                    help_text = probe(
                        self.runner, command, executable, ["help", "gen"], cancel
                    )
                    if "--json-file-name" in help_text and '"json"' in help_text:
                        project = build / GENERATED
                        if project.is_symlink():
                            raise ValueError("reserved GN JSON output is a symlink")
                        # GN persists these switches in its Ninja regeneration
                        # rule. Use a stable build-tree artifact, never a temp path.
                        words += ["--ide=json", "--json-file-name=" + GENERATED]
                    else:
                        report.availability["target graph"] = (
                            "Unavailable: native JSON export was not advertised by this GN executable"
                        )
                else:
                    report.availability["target graph"] = (
                        "Existing IDE/script options preserved; use --ide=json for target evidence"
                    )
                if project is not None:
                    project = project.parent.resolve() / project.name
                    before[project] = (project.parent, stamp(project))
                effective = replace(command, argv=words, shell=None)
        except READ_ERRORS as exc:
            problems.append(f"{step}: cannot prepare GN reporting: {exc}")
        preparation_duration = time.monotonic() - prepared
        lines, size = [], 0

        def output(line):
            nonlocal size
            on_output(line)
            if direct:
                size += len(line.encode("utf-8")) + 1
                if size <= MAX_BYTES:
                    lines.append(line)

        start = time.monotonic()
        outcome = execute(effective, output, cancel)
        duration = time.monotonic() - start
        collecting = time.monotonic()
        candidates = {}
        try:
            candidates = {
                path: root
                for path, (root, current) in discover(roots).items()
                if before.get(path, (None, None))[1] != current
            }
            if report is not None:
                report.status = (
                    "cancelled"
                    if outcome.cancelled
                    else "passed"
                    if outcome.exit_code == 0
                    else "failed"
                )
                report.exit_code, report.duration = outcome.exit_code, duration
                console(report, lines)
                # GN only rewrites changed JSON. A successful direct generation
                # with explicit JSON export may legitimately retain identical bytes.
                if project is not None:
                    candidates.pop(project, None)
                    if (
                        outcome.exit_code == 0
                        and not outcome.cancelled
                        and not outcome.timed_out
                    ):
                        try:
                            parse_project(report, project, project.parent)
                        except READ_ERRORS as exc:
                            report.availability["target graph"] = (
                                "Unavailable: native JSON could not be imported"
                            )
                            problems.append(
                                f"{step}: cannot import GN project JSON: {exc}"
                            )
                    else:
                        report.availability["target graph"] = (
                            "Unavailable: generation failed or was cancelled; previous JSON is not reused"
                        )
                if size > MAX_BYTES:
                    problems.append(
                        f"{step}: GN console capture exceeds 100 MiB; diagnostics may be incomplete"
                    )
            for path, root in candidates.items():
                item = GNReport(step, str(path))
                try:
                    parse_project(item, path, root)
                    item.availability["version"] = (
                        "Not present in native GN JSON; current PATH is not queried"
                    )
                    records.append(item)
                except READ_ERRORS as exc:
                    problems.append(f"{step}: cannot import GN evidence {path}: {exc}")
            if records or problems:
                folder = reports / SNAPSHOT
                folder.mkdir(parents=True, exist_ok=True)
                data = {
                    "gn": [asdict(r) for r in records],
                    "problems": problems,
                    "captured_files": [
                        str(path.relative_to(reports))
                        for path in dict.fromkeys([*before, *candidates])
                        if path.is_relative_to(reports)
                    ],
                }
                text = (
                    json.dumps(mask_data(data, mask), ensure_ascii=False, indent=2)
                    + "\n"
                )
                if len(text.encode("utf-8")) > MAX_BYTES:
                    raise ValueError("normalized GN evidence exceeds 100 MiB")
                (folder / f"{time.time_ns()}-{uuid.uuid4().hex}.json").write_text(
                    text, encoding="utf-8"
                )
        except READ_ERRORS as exc:
            on_problem(f"cannot collect GN reporting: {exc}")
        return replace(
            outcome,
            reporting_duration=outcome.reporting_duration
            + preparation_duration
            + time.monotonic()
            - collecting,
        )


def read(reports, step):
    result, captured = Contribution(step), set()
    for path in sorted((reports / SNAPSHOT).glob("*.json")):
        try:
            data = json.loads(bounded_text(path, reports))
            result.problems.extend(data["problems"])
            captured.update(data["captured_files"])
            for item in data["gn"]:
                item["diagnostics"] = [LogFinding(**f) for f in item["diagnostics"]]
                result.gn.append(GNReport(**item))
        except READ_ERRORS as exc:
            result.problems.append(f"{step}: cannot read GN snapshot: {exc}")
    consumed = set(captured)
    for path in sorted(reports.glob("*")):
        if not project_name(path.name) or path.name in captured:
            continue
        item = GNReport(step, str(path))
        try:
            parse_project(item, path, reports)
            stem = (
                path.name.removesuffix(".gn-project.json")
                if path.name.endswith(".gn-project.json")
                else path.stem
            )
            log = path.with_name(stem + ".gn.log")
            item.availability["version"] = (
                "Not recorded in native GN JSON; current PATH is not queried"
            )
            result.gn.append(item)
            if log.name not in consumed and log.is_file():
                consumed.add(log.name)
                console(item, bounded_text(log, reports).splitlines(), log.name)
        except READ_ERRORS as exc:
            result.problems.append(f"{step}: cannot read GN report {path.name}: {exc}")
    for path in sorted(reports.glob("*.gn.log")):
        if path.name not in consumed:
            try:
                item = GNReport(step, str(path))
                console(item, bounded_text(path, reports).splitlines(), path.name)
                result.gn.append(item)
            except READ_ERRORS as exc:
                result.problems.append(f"{step}: cannot read GN log: {exc}")
    return result
