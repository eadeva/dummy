"""Capture CMake invocations through the actual step environment and retain reports.

Direct configure commands are instrumented before execution. Scripts and compound
shell commands can supply evidence in PTK_BUILD_DIR; only changed caches are used
for their version provenance. Report regeneration never probes today's PATH.
"""

from __future__ import annotations

import json
import os
import re
import time
import uuid
from dataclasses import asdict, replace
from pathlib import Path

from ...application.ports import ProcessOutcome
from ...domain.execution.commands import split_words
from ...domain.execution.model import CommandSpec
from ...domain.reporting.cmake import normalized_message, same_diagnostic
from ...domain.reporting.model import CMakeReport, Contribution, LogFinding
from .cmake_importers import select
from .cmake_importers.common import (
    MAX_BYTES,
    READ_ERRORS,
    attempt,
    cache_values,
    cache_version,
    console_diagnostics,
    json_file,
    sarif_diagnostics,
    stamp,
    text_file,
    version_tuple,
)

SNAPSHOT = ".ptk-cmake"


def watch(root):
    """Record evidence metadata without walking compiler scratch trees or symlinks."""
    result = {}
    if not root.is_dir():
        return result
    for directory, dirs, files in os.walk(root, followlinks=False):
        folder = Path(directory)
        dirs[:] = [
            d
            for d in dirs
            if d not in (".git", ".cmake", "CMakeFiles")
            and not (folder / d).is_symlink()
        ]
        if "CMakeCache.txt" not in files and folder != root:
            continue
        candidates = [
            folder / "CMakeCache.txt",
            *(
                folder / "CMakeFiles" / name
                for name in (
                    "CMakeConfigureLog.yaml",
                    "CMakeOutput.log",
                    "CMakeError.log",
                )
            ),
        ]
        reply = folder / ".cmake/api/v1/reply"
        candidates += list(reply.glob("index-*.json")) + list(
            reply.glob("error-*.json")
        )
        for path in candidates:
            if current := stamp(path):
                result[str(path)] = current
    return result


def configure_command(command, os_name):
    if command.shell is not None:
        # Do not reinterpret expansion, pipelines, assignments, wrappers or scripts.
        if re.search(r"[\n\r&|;<>`$%*?]", command.shell):
            return None
        try:
            words = split_words(command.shell, os_name)
        except ValueError:
            return None
    else:
        words = list(command.argv or [])
    if not words or Path(words[0]).name.lower() not in ("cmake", "cmake.exe", "cmake3"):
        return None
    excluded = (
        "--build",
        "--install",
        "--workflow",
        "--open",
        "--version",
        "--help",
        "--system-information",
        "--find-package",
        "--list-presets",
    )
    if any(
        word in ("-E", "-P", "-N", "--")
        or word.startswith(excluded)
        or word.startswith("-P")
        for word in words[1:]
    ):
        return None
    cwd = Path(command.cwd).resolve()
    binary = None
    positional = []
    index = 1
    while index < len(words):
        word = words[index]
        if word in ("-B", "-S", "-H", "-D", "-U", "-G", "-A", "-T", "-C", "--preset"):
            if index + 1 >= len(words):
                return None
            if word == "-B":
                binary = words[index + 1]
            index += 2
            continue
        if word.startswith("-B"):
            binary = word[2:]
        elif not word.startswith("-"):
            positional.append(word)
        index += 1
    if binary is None and any(
        w == "--preset" or w.startswith("--preset=") for w in words
    ):
        return None  # Preset expansion belongs to CMake. Use an explicit -B to instrument it.
    build = (cwd / binary).resolve() if binary else cwd
    if (
        binary is None
        and positional
        and (cwd / positional[-1] / "CMakeCache.txt").is_file()
    ):
        build = (cwd / positional[-1]).resolve()
    return words, build


def prepare_query(build, version):
    if version < (3, 20, 0):
        return
    folder = build / ".cmake/api/v1/query/client-ptk"
    if not folder.resolve().is_relative_to(build.resolve()):
        raise ValueError("CMake File API query directory escapes the build directory")
    folder.mkdir(parents=True, exist_ok=True)
    names = ["codemodel-v2", "toolchains-v1"]
    if version >= (3, 26, 0):
        names.append("configureLog-v1")
    for name in names:
        (folder / name).touch()


class CMakeReportingRunner:
    def __init__(self, runner, os_name):
        self.runner, self.os_name = runner, os_name

    def run(self, command, on_output, cancel=None, *, mask, on_problem):
        build_root = Path(command.env["PTK_BUILD_DIR"]).resolve()
        target = Path(command.env["PTK_STEP_REPORTS_DIR"]) / SNAPSHOT
        step = command.env["PTK_STEP"]
        problems, records = [], []
        before = {}
        direct, version, executable, sarif, temporary_sarif = None, "", "", None, False
        effective = command
        preparation_start = time.monotonic()
        try:
            before = watch(build_root)
            direct = configure_command(command, self.os_name)
            if direct:
                words, build = direct
                path = next(
                    (v for k, v in command.env.items() if k.upper() == "PATH"), ""
                )
                program = (
                    str((Path(command.cwd) / words[0]).resolve())
                    if ("/" in words[0] or "\\" in words[0])
                    else words[0]
                )
                executable = self.runner.which(program, path=path) or program
                output = []
                checked = self.runner.run(
                    CommandSpec(
                        argv=[executable, "--version"],
                        cwd=command.cwd,
                        env=dict(command.env),
                        timeout=min(command.timeout or 10, 10),
                    ),
                    output.append,
                    cancel,
                )
                match = re.search(
                    r"\bcmake version ([0-9]+\.[0-9]+(?:\.[0-9]+)?[^\s]*)",
                    "\n".join(output),
                )
                if checked.exit_code or not match:
                    raise ValueError(
                        "cannot determine the version of the step's CMake executable"
                    )
                version = match[1]
                numeric = version_tuple(version)
                select(numeric)
                before.update(watch(build))
                prepare_query(build, numeric)
                words[0] = executable
                if numeric >= (4, 0, 0):
                    existing = next(
                        (
                            word.split("=", 1)[1]
                            for word in words
                            if word.startswith("--sarif-output=")
                        ),
                        None,
                    )
                    if "--sarif-output" in words:
                        existing = words[words.index("--sarif-output") + 1]
                    if existing:
                        sarif = (Path(command.cwd) / existing).resolve()
                    else:
                        target.mkdir(parents=True, exist_ok=True)
                        sarif = (target / (uuid.uuid4().hex + ".sarif")).resolve()
                        words.append("--sarif-output=" + str(sarif))
                        temporary_sarif = True
                    before[str(sarif)] = stamp(sarif)
                effective = replace(command, argv=words, shell=None)
        except READ_ERRORS as exc:
            problems.append(f"{step}: cannot prepare CMake reporting: {exc}")
        # The version check shares the step timeout budget with the configure run.
        remaining = (
            command.timeout - (time.monotonic() - preparation_start)
            if command.timeout is not None
            else None
        )
        if remaining is not None:
            effective = replace(effective, timeout=max(0.001, remaining))
        lines, captured = [], 0

        def output(line):
            nonlocal captured
            on_output(line)
            captured += len(line.encode("utf-8")) + 1
            if captured <= MAX_BYTES:
                lines.append(mask(line))

        started = time.monotonic()
        if cancel is not None and cancel.is_set():
            outcome = ProcessOutcome(1, cancelled=True)
        elif remaining is not None and remaining <= 0:
            outcome = ProcessOutcome(1, timed_out=True)
        else:
            outcome = self.runner.run(effective, output, cancel)
        duration = time.monotonic() - started
        try:
            builds = []
            if direct and version:
                builds.append((direct[1], version, executable))
            elif not direct:
                after = watch(build_root)
                for name, current in after.items():
                    if (
                        Path(name).name != "CMakeCache.txt"
                        or before.get(name) == current
                    ):
                        continue
                    cache = Path(name)
                    values = cache_values(text_file(cache, build_root))
                    detected = cache_version(values)
                    if not detected:
                        problems.append(
                            f"{step}: changed CMake cache has no recorded version: {cache}"
                        )
                        continue
                    builds.append(
                        (cache.parent, detected, values.get("CMAKE_COMMAND", ""))
                    )
            for build, detected, program in builds:
                numeric = version_tuple(detected)
                importer = select(numeric)
                report = CMakeReport(
                    step,
                    str(build),
                    detected,
                    importer.name,
                    executable=program,
                    status="cancelled"
                    if outcome.cancelled
                    else "passed"
                    if outcome.exit_code == 0
                    else "failed",
                    duration=duration,
                )
                importer.collect(report, build, before, numeric, problems)
                console = console_diagnostics(lines, step)
                report.diagnostics = merge_diagnostics([], console)
                report.availability["diagnostics"] = "Captured CMake console headers"
                if sarif and sarif.is_file() and stamp(sarif) != before.get(str(sarif)):

                    def read_sarif(report=report, console=console):
                        findings = sarif_diagnostics(
                            json_file(sarif, sarif.parent), step
                        )
                        report.diagnostics = merge_diagnostics(
                            findings,
                            console,
                            source_root=report.configuration.get(
                                "CMAKE_HOME_DIRECTORY", ""
                            ),
                        )
                        report.availability["diagnostics"] = (
                            "SARIF and console (matching findings merged)"
                        )

                    attempt(report, problems, "diagnostics", read_sarif)
                if captured > MAX_BYTES:
                    problems.append(
                        f"{step}: CMake console capture exceeds 100 MiB; diagnostics may be incomplete"
                    )
                records.append(asdict(report))
        except READ_ERRORS as exc:
            problems.append(f"{step}: cannot capture CMake reporting: {exc}")
        finally:
            if temporary_sarif:
                try:
                    sarif.unlink(missing_ok=True)
                except OSError as exc:
                    on_problem(f"cannot remove temporary CMake diagnostics: {exc}")
        if records or problems:
            try:
                target.mkdir(parents=True, exist_ok=True)
                # Each attempt gets its own immutable input, including failed retries.
                (target / f"{time.time_ns()}-{uuid.uuid4().hex}.json").write_text(
                    json.dumps(
                        mask_data({"cmake": records, "problems": problems}, mask),
                        ensure_ascii=False,
                        indent=2,
                    )
                    + "\n",
                    encoding="utf-8",
                )
            except OSError as exc:
                on_problem(f"cannot save CMake evidence: {exc}")
        return outcome


def mask_data(value, mask):
    if isinstance(value, str):
        return mask(value)
    if isinstance(value, dict):
        return {mask(str(key)): mask_data(item, mask) for key, item in value.items()}
    if isinstance(value, list):
        return [mask_data(item, mask) for item in value]
    return value


def merge_diagnostics(sarif, console, *, source_root=""):
    merged, counts = [], []
    for source, findings in (("CMake SARIF", sarif), ("CMake console", console)):
        for item in findings:
            item.message = normalized_message(item.message)
            index = next(
                (
                    i
                    for i, finding in enumerate(merged)
                    if same_diagnostic(finding, item, source_root)
                ),
                None,
            )
            if index is None:
                index = len(merged)
                item.context = []
                merged.append(item)
                counts.append({})
            finding = merged[index]
            label = "Source: " + source
            if label not in finding.context:
                finding.context.append(label)
            counts[index][source] = counts[index].get(source, 0) + 1
            finding.occurrences = max(counts[index].values())
            if source == "CMake console":
                finding.log_line = item.log_line
    return merged


def read(reports, step):
    result = Contribution(step)
    for path in sorted((reports / SNAPSHOT).glob("*.json")):
        try:
            data = json_file(path, reports)
            result.problems.extend(data["problems"])
            for item in data["cmake"]:
                item["diagnostics"] = [
                    LogFinding(**finding) for finding in item["diagnostics"]
                ]
                result.cmake.append(CMakeReport(**item))
        except READ_ERRORS as exc:
            result.problems.append(f"{step}: cannot read CMake snapshot: {exc}")
    return result
