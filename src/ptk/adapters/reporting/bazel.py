"""Capture the actual Bazel invocation and preserve immutable reporting inputs."""

from __future__ import annotations

import json
import os
import re
import time
import uuid
from dataclasses import asdict, replace
from pathlib import Path

from ...domain.execution.commands import split_words
from ...domain.reporting.model import BazelReport, Contribution, LogFinding
from .bazel_bep import MAX_BYTES, READ_ERRORS, Findings, bounded_text, parse, stamp
from .bazel_graph import collect
from .evidence import mask_data

SNAPSHOT = ".ptk-bazel"
SUFFIXES = (".bep.json", ".bep.jsonl")
COMMANDS = {"build", "test", "coverage", "run"}
STARTUP_VALUES = {
    "--output_base",
    "--output_user_root",
    "--install_base",
    "--bazelrc",
    "--host_jvm_args",
    "--server_javabase",
    "--connect_timeout_secs",
    "--max_idle_secs",
    "--io_nice_level",
    "--command_port",
    "--digest_function",
    "--failure_detail_out",
    "--invocation_policy",
}
STARTUP_SWITCHES = {
    "--" + prefix + name
    for prefix in ("", "no")
    for name in (
        "batch",
        "ignore_all_rc_files",
        "system_rc",
        "workspace_rc",
        "home_rc",
        "write_command_log",
        "watchfs",
        "fatal_event_bus_exceptions",
        "windows_enable_symlinks",
        "client_debug",
        "host_jvm_debug",
        "batch_cpu_scheduling",
        "block_for_lock",
        "preemptible",
        "shutdown_on_low_sys_mem",
        "idle_server_tasks",
        "unlimit_coredumps",
        "autodetect_server_javabase",
    )
}


def invocation(command, os_name):
    if command.shell is not None:
        if re.search(r"[\n\r&|;<>`$%*?]", command.shell):
            return None
        try:
            words = split_words(command.shell, os_name)
        except ValueError:
            return None
    else:
        words = list(command.argv or [])
    name = words[0].replace("\\", "/").rsplit("/", 1)[-1] if words else ""
    if not re.fullmatch(r"bazel(?:isk)?(?:-\d[\w.-]*)?(?:\.exe)?", name, re.IGNORECASE):
        return None
    index = 1
    while index < len(words):
        word = words[index]
        if word in COMMANDS:
            return words, index
        if not word.startswith("--"):
            return None
        if word in STARTUP_VALUES:
            index += 1
        elif "=" not in word and word not in STARTUP_SWITCHES:
            return None  # An unknown startup option might consume the command word.
        index += 1
    return None


def bep_argument(words, command_index):
    """Last explicit JSON output wins; never interpret a bazel run program's args."""
    found = None
    index = command_index + 1
    while index < len(words) and words[index] != "--":
        word = words[index]
        if word == "--build_event_json_file":
            index += 1
            if index == len(words):
                raise ValueError("missing --build_event_json_file path")
            found = words[index]
        elif word.startswith("--build_event_json_file="):
            found = word.split("=", 1)[1]
        index += 1
    return found


def discover(roots):
    result = {}
    for root in roots:
        if not root.is_dir():
            continue
        for directory, dirs, files in os.walk(root, followlinks=False):
            folder = Path(directory)
            dirs[:] = [
                d
                for d in dirs
                if d not in (".git", SNAPSHOT, ".ptk-cmake", "CMakeFiles", ".cmake")
                and not (folder / d).is_symlink()
            ]
            for name in files:
                if name.endswith(SUFFIXES):
                    path = folder / name
                    if current := stamp(path):
                        result[path] = (root, current)
    return result


class BazelReportingRunner:
    def __init__(self, runner, os_name):
        self.runner, self.os_name = runner, os_name

    def run(self, command, on_output, cancel=None, *, mask, on_problem, execute=None):
        execute = execute or self.runner.run
        reports = Path(command.env["PTK_STEP_REPORTS_DIR"]).resolve()
        target = reports / SNAPSHOT
        roots = [Path(command.env["PTK_BUILD_DIR"]).resolve(), reports]
        step = command.env["PTK_STEP"]
        problems, records, before = [], [], {}
        direct, bep, temporary, executable = None, None, False, ""
        effective = command
        try:
            before = discover(roots)
            direct = invocation(command, self.os_name)
            if direct:
                words, index = direct
                explicit = bep_argument(words, index)
                if explicit == "":
                    # An explicit empty destination disables BEP capture.
                    pass
                elif explicit is not None:
                    destination = Path(command.cwd) / explicit
                    # Canonicalize the parent to match discovery (including ../
                    # and directory aliases), retaining final-symlink checks.
                    bep = destination.parent.resolve() / destination.name
                else:
                    target.mkdir(parents=True, exist_ok=True)
                    bep = target / (uuid.uuid4().hex + ".raw-bep")
                    temporary = True
                    # After startup flags and before targets / a run separator.
                    words.insert(index + 1, "--build_event_json_file=" + str(bep))
                if bep is not None:
                    before[bep] = (bep.parent, stamp(bep))
                path = next(
                    (v for k, v in command.env.items() if k.upper() == "PATH"), ""
                )
                program = (
                    str((Path(command.cwd) / words[0]).resolve())
                    if "/" in words[0] or "\\" in words[0]
                    else words[0]
                )
                executable = self.runner.which(program, path=path) or program
                # Keep Bazelisk and its environment intact: BEP records the selected
                # Bazel version without a separate probe or another server startup.
                effective = replace(command, argv=words, shell=None)
        except READ_ERRORS as exc:
            problems.append(f"{step}: cannot prepare Bazel reporting: {exc}")
        lines, captured = [], 0

        def output(line):
            nonlocal captured
            on_output(line)
            if direct:
                captured += len(line.encode("utf-8")) + 1
                if captured <= MAX_BYTES:
                    lines.append(line)

        started = time.monotonic()
        try:
            outcome = execute(effective, output, cancel)
            duration = time.monotonic() - started
            collecting = time.monotonic()
            state = (
                "cancelled"
                if outcome.cancelled
                else "passed"
                if outcome.exit_code == 0
                else "failed"
            )
            candidates = {}
            captured_direct = False
            try:
                for path, (root, current) in discover(roots).items():
                    if before.get(path, (None, None))[1] != current:
                        candidates[path] = root
                if bep is not None and stamp(bep) != before.get(bep, (None, None))[1]:
                    candidates[bep] = bep.parent
                for path, root in candidates.items():
                    try:
                        replay = {}
                        record = parse(
                            path,
                            root,
                            step,
                            problems,
                            console=lines if direct and path == bep else (),
                            executable=executable if direct and path == bep else "",
                            outcome=state,
                            duration=duration,
                            replay=replay if direct and path == bep else None,
                            graph_sidecar=False,
                        )
                        records.append(record)
                        captured_direct |= direct is not None and path == bep
                        if (
                            direct
                            and path == bep
                            and not outcome.cancelled
                            and not outcome.timed_out
                        ):
                            collect(
                                record,
                                replay,
                                command,
                                direct,
                                self.runner,
                                cancel,
                                target,
                                on_output,
                            )
                    except READ_ERRORS as exc:
                        problems.append(
                            f"{step}: cannot import Bazel evidence {path}: {exc}"
                        )
                if direct and not captured_direct:
                    report = BazelReport(
                        step,
                        "Captured console",
                        executable=executable,
                        command=direct[0][direct[1]],
                        status=state,
                        duration=duration,
                    )
                    Findings(report).console(lines, "Bazel console", line_numbers=True)
                    report.availability["BEP"] = (
                        "Disabled by explicit empty output path"
                        if bep is None
                        else "No current BEP file was produced"
                    )
                    report.availability["version"] = (
                        "Unavailable; current PATH is not queried"
                    )
                    records.append(report)
                    if bep is not None:
                        problems.append(
                            f"{step}: Bazel did not produce current BEP evidence"
                        )
                if records and captured > MAX_BYTES:
                    problems.append(
                        f"{step}: Bazel console capture exceeds 100 MiB; diagnostics may be incomplete"
                    )
            except READ_ERRORS as exc:
                problems.append(f"{step}: cannot collect Bazel reporting: {exc}")
            if records or problems:
                try:
                    target.mkdir(parents=True, exist_ok=True)
                    data = {
                        "bazel": [asdict(record) for record in records],
                        "problems": problems,
                        # Avoid re-importing explicit/copied raw streams when a
                        # normalized capture of those exact bytes already exists.
                        "captured_files": [
                            str(path.relative_to(reports))
                            for path in dict.fromkeys([*before, *candidates])
                            if path.is_relative_to(reports)
                            and path.name.endswith(SUFFIXES)
                        ],
                    }
                    text = (
                        json.dumps(mask_data(data, mask), ensure_ascii=False, indent=2)
                        + "\n"
                    )
                    if len(text.encode("utf-8")) > MAX_BYTES:
                        raise ValueError("normalized Bazel evidence exceeds 100 MiB")
                    (target / f"{time.time_ns()}-{uuid.uuid4().hex}.json").write_text(
                        text, encoding="utf-8"
                    )
                except READ_ERRORS as exc:
                    on_problem(f"cannot save Bazel evidence: {exc}")
            return replace(
                outcome,
                reporting_duration=outcome.reporting_duration
                + time.monotonic()
                - collecting,
            )
        finally:
            if temporary and bep is not None:
                try:
                    bep.unlink(missing_ok=True)
                except OSError as exc:
                    on_problem(f"cannot remove temporary Bazel evidence: {exc}")


def read(reports, step):
    result, captured = Contribution(step), set()
    for path in sorted((reports / SNAPSHOT).glob("*.json")):
        try:
            data = json.loads(bounded_text(path, reports))
            result.problems.extend(data["problems"])
            captured.update(data["captured_files"])
            for item in data["bazel"]:
                item["diagnostics"] = [
                    LogFinding(**finding) for finding in item["diagnostics"]
                ]
                result.bazel.append(BazelReport(**item))
        except READ_ERRORS as exc:
            result.problems.append(f"{step}: cannot read Bazel snapshot: {exc}")
    # report.import can copy a BEP file here without running Bazel in PTK.
    for path in sorted(reports.glob("*")):
        if path.name.endswith(SUFFIXES) and path.name not in captured:
            try:
                result.bazel.append(parse(path, reports, step, result.problems))
            except READ_ERRORS as exc:
                result.problems.append(
                    f"{step}: cannot read Bazel report {path.name}: {exc}"
                )
    return result
