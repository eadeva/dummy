"""Bounded, offline import of Bazel's newline-delimited JSON Build Event Protocol.

Only the producing stream supplies the Bazel version. File references are
retained as evidence, never fetched or executed. Unknown event kinds are ignored.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from ...domain.reporting.bazel import identity
from ...domain.reporting.log_analysis import diagnostic
from ...domain.reporting.model import BazelReport, LogFinding

MAX_BYTES = 100 * 1024 * 1024
READ_ERRORS = (
    OSError,
    ValueError,
    TypeError,
    KeyError,
    IndexError,
    AttributeError,
    RecursionError,
)
TEST_STATUSES = (
    "NO_STATUS",
    "PASSED",
    "FLAKY",
    "TIMEOUT",
    "FAILED",
    "INCOMPLETE",
    "REMOTE_FAILURE",
    "FAILED_TO_BUILD",
    "TOOL_HALTED_BEFORE_TESTING",
)


def stamp(path):
    try:
        stat = path.stat()
        return stat.st_mtime_ns, stat.st_size, stat.st_ino
    except FileNotFoundError:
        return None


def bounded_text(path, root):
    path, root = Path(path), Path(root).resolve()
    if path.is_symlink() or not path.resolve().is_relative_to(root):
        raise ValueError("Bazel evidence must stay inside its recorded directory")
    if path.stat().st_size > MAX_BYTES:
        raise ValueError("Bazel artifact exceeds 100 MiB")
    with path.open("rb") as stream:
        data = stream.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError("Bazel artifact exceeds 100 MiB")
    return data.decode("utf-8-sig")


def object_id(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def seconds(value):
    result = float(str(value or "0").removesuffix("s"))
    if not math.isfinite(result) or result < 0:
        raise ValueError("invalid Bazel duration")
    return result


def status(value):
    if isinstance(value, int):
        return TEST_STATUSES[value] if 0 <= value < len(TEST_STATUSES) else str(value)
    return str(value or "NO_STATUS")


def location(event_id):
    return {
        "label": event_id.get("label", ""),
        "configuration": event_id.get("configuration", {}).get("id", ""),
    }


def file_reference(value):
    # Inline base64 blobs can contain arbitrary binary data or secrets. Do not retain them.
    return {
        k: value[k]
        for k in ("name", "uri", "pathPrefix", "digest", "length")
        if k in value
    }


class Findings:
    def __init__(self, report):
        self.report = report
        self.groups = {}
        self.counts = {}

    def add(self, finding, source, detail=""):
        key = identity(finding, self.report.workspace)
        if key not in self.groups:
            self.groups[key] = finding
            self.counts[key] = {}
            self.report.diagnostics.append(finding)
        target = self.groups[key]
        sources = self.counts[key]
        sources[source] = sources.get(source, 0) + 1
        target.occurrences = max(sources.values())
        for text in ("Source: " + source, detail):
            if text and text not in target.context:
                target.context.append(text)
        if finding.log_line:
            target.log_line = finding.log_line
            if finding.log_line not in target.log_lines and len(target.log_lines) < 50:
                target.log_lines.append(finding.log_line)

    def message(self, message, level, rule, source, detail=""):
        parsed = diagnostic(message) or diagnostic(level.upper() + ": " + message)
        finding = LogFinding(
            tool="Bazel",
            step=self.report.step,
            level=level,
            rule=rule,
            message=parsed["message"] if parsed else message,
            file=parsed["file"] if parsed else "",
            line=parsed["line"] if parsed else None,
        )
        self.add(finding, source, detail)

    def console(self, lines, source, *, line_numbers=False):
        for number, line in enumerate(lines, 1):
            parsed = diagnostic(line)
            if parsed:
                finding = LogFinding(tool="Bazel", step=self.report.step, **parsed)
                if line_numbers:
                    finding.log_line = number
                self.add(finding, source)


class BepImporter:
    name = "bazel-bep-json"

    def __init__(self, report, problems):
        self.report, self.problems = report, problems
        self.findings = Findings(report)
        self.seen, self.announced = {}, set()
        self.started = self.finished = self.last = False
        self.valid = True
        self.progress = {"stdout": "", "stderr": ""}
        self.kinds = {}
        self.artifacts = {}
        self.failed_targets = []

    def problem(self, message):
        self.problems.append(f"{self.report.step}: {self.report.source}: {message}")

    def files(self, values, source):
        for value in values:
            item = file_reference(value)
            key = object_id(item)
            if key not in self.artifacts:
                self.artifacts[key] = {**item, "sources": []}
            if source not in self.artifacts[key]["sources"]:
                self.artifacts[key]["sources"].append(source)

    def event(self, event):
        if not isinstance(event, dict) or not isinstance(event.get("id"), dict):
            raise TypeError("expected a BEP event object with an id")
        key = object_id(event["id"])
        digest = hashlib.sha256(object_id(event).encode()).digest()
        if key in self.seen:
            if self.seen[key] != digest:
                raise ValueError("conflicting duplicate BEP event id")
            return
        if self.last:
            raise ValueError("event follows the BEP lastMessage marker")
        self.seen[key] = digest
        self.announced.update(object_id(child) for child in event.get("children", []))
        self.last = bool(event.get("lastMessage", False))
        ids, report = event["id"], self.report
        if "buildFinished" in ids and "aborted" in event:
            self.finished = True
        if "started" in event:
            value = event["started"]
            self.started = True
            report.version = str(value.get("buildToolVersion", ""))
            report.invocation_id = str(value.get("uuid", ""))
            report.command = str(value.get("command", ""))
            report.workspace = str(value.get("workspaceDirectory", ""))
        if "progress" in event:
            for channel in self.progress:
                text = self.progress[channel] + event["progress"].get(channel, "")
                lines = text.split("\n")
                self.progress[channel] = lines.pop()
                self.findings.console(lines, "Bazel BEP progress " + channel)
        if "configuration" in event:
            value = event["configuration"]
            report.configurations.append(
                {
                    "id": ids.get("configuration", {}).get("id", ""),
                    **{
                        k: value[k]
                        for k in ("mnemonic", "platformName", "cpu", "isTool")
                        if k in value
                    },
                }
            )
        if "configured" in event:
            self.kinds[ids.get("targetConfigured", {}).get("label", "")] = event[
                "configured"
            ].get("targetKind", "")
        if "namedSetOfFiles" in event:
            value = event["namedSetOfFiles"]
            self.files(
                value.get("files", []),
                "Bazel BEP named file set " + ids["namedSet"]["id"],
            )
        if "completed" in event:
            value, target = event["completed"], ids.get("targetCompleted", {})
            record = {
                **location(target),
                "aspect": target.get("aspect", ""),
                "status": "passed" if value.get("success", False) else "failed",
                "failure": value.get("failureDetail", {}).get("message", ""),
                "output_groups": [
                    {
                        "name": group.get("name", ""),
                        "file_sets": group.get("fileSets", []),
                        "incomplete": bool(group.get("incomplete", False)),
                        "files": [
                            file_reference(item)
                            for item in group.get("inlineFiles", [])
                        ],
                    }
                    for group in value.get("outputGroup", [])
                ],
            }
            report.targets.append(record)
            if record["status"] == "failed":
                self.failed_targets.append(record)
            self.failure(
                value, "Bazel.target", "Bazel BEP target completion", record["label"]
            )
        if "action" in event:
            value, action_id = event["action"], ids.get("actionCompleted", {})
            record = {
                "label": action_id.get("label", ""),
                "primary_output": action_id.get("primaryOutput", ""),
                "configuration": action_id.get("configuration", {}).get("id", ""),
                "type": value.get("type", ""),
                "status": "passed" if value.get("success", False) else "failed",
                "exit_code": value.get("exitCode"),
                "failure": value.get("failureDetail", {}).get("message", ""),
            }
            report.actions.append(record)
            for channel in ("stdout", "stderr"):
                if channel in value:
                    self.files(
                        [value[channel]], f"Bazel action {record['label']} {channel}"
                    )
            self.failure(
                value,
                "Bazel.action",
                "Bazel BEP action",
                record["label"] + " " + record["primary_output"],
            )
        if "aborted" in event:
            value = event["aborted"]
            reason = value.get("reason", "UNKNOWN")
            level = (
                "note"
                if reason in ("USER_INTERRUPTED", "NO_ANALYZE", "NO_BUILD", "SKIPPED")
                else "error"
            )
            self.findings.message(
                value.get("description") or "Bazel event aborted: " + str(reason),
                level,
                "Bazel.aborted." + str(reason),
                "Bazel BEP aborted",
                key,
            )
        if "testResult" in event:
            value, test_id = event["testResult"], ids.get("testResult", {})
            execution = value.get("executionInfo", {})
            record = {
                **location(test_id),
                **{k: test_id.get(k, 0) for k in ("run", "shard", "attempt")},
                "status": status(value.get("status")),
                "details": value.get("statusDetails", ""),
                "duration": seconds(value["testAttemptDuration"])
                if "testAttemptDuration" in value
                else None,
                "cached_locally": bool(value.get("cachedLocally", False)),
                "cached_remotely": bool(execution.get("cachedRemotely", False)),
                "strategy": execution.get("strategy", ""),
            }
            report.test_attempts.append(record)
            self.files(
                value.get("testActionOutput", []), "Bazel test " + object_id(test_id)
            )
            for warning in value.get("warning", []):
                self.findings.message(
                    warning,
                    "warning",
                    "Bazel.test.warning",
                    "Bazel BEP test warning",
                    object_id(test_id),
                )
        if "testSummary" in event:
            value, test_id = event["testSummary"], ids.get("testSummary", {})
            record = {
                **location(test_id),
                "status": status(value.get("overallStatus")),
                "duration": seconds(value["totalRunDuration"])
                if "totalRunDuration" in value
                else None,
                **{
                    k: value.get(k, 0)
                    for k in (
                        "totalRunCount",
                        "runCount",
                        "attemptCount",
                        "shardCount",
                        "totalNumCached",
                    )
                },
            }
            report.tests.append(record)
            for outcome in ("passed", "failed"):
                self.files(
                    value.get(outcome, []),
                    "Bazel test summary " + record["label"] + " " + outcome,
                )
            if record["status"] != "PASSED":
                level = (
                    "warning"
                    if record["status"] == "FLAKY"
                    else "error"
                    if record["status"] in TEST_STATUSES[3:]
                    else "note"
                )
                self.findings.message(
                    f"Test target {record['label']} [{record['configuration']}]: {record['status']}",
                    level,
                    "Bazel.test." + record["status"],
                    "Bazel BEP test summary",
                )
        if "buildMetrics" in event:
            metrics = {
                key: value
                for key, value in event["buildMetrics"].items()
                if key
                in (
                    "actionSummary",
                    "memoryMetrics",
                    "targetMetrics",
                    "packageMetrics",
                    "timingMetrics",
                    "artifactMetrics",
                    "buildGraphMetrics",
                    "networkMetrics",
                    "workerMetrics",
                    "dynamicExecutionMetrics",
                )
            }
            if any(
                not isinstance(value, list if key == "workerMetrics" else dict)
                for key, value in metrics.items()
            ):
                raise TypeError("invalid Bazel metric group")
            report.metrics = metrics
        if "buildToolLogs" in event:
            self.files(
                event["buildToolLogs"].get("log", []), "Bazel BEP build tool logs"
            )
        if "finished" in event:
            value = event["finished"]
            self.finished = True
            if "exitCode" in value:
                report.exit_code = int(value["exitCode"].get("code", 0))
                report.exit_name = value["exitCode"].get("name", "")
            self.failure(value, "Bazel.finished", "Bazel BEP build finished")

    def failure(self, value, rule, source, detail=""):
        message = value.get("failureDetail", {}).get("message", "")
        if message:
            self.findings.message(message, "error", rule, source, detail)

    def finish(self, console):
        report = self.report
        for channel, tail in self.progress.items():
            self.findings.console([tail], "Bazel BEP progress " + channel)
        self.findings.console(console, "Bazel console", line_numbers=True)
        for target in report.targets:
            target["kind"] = self.kinds.get(target["label"], "")
            # File sets form a DAG, not a target dependency graph. Keep their ids
            # and references without inventing build edges or duplicating files.
        report.artifacts = list(self.artifacts.values())
        missing = self.announced - self.seen.keys()
        report.complete = (
            self.valid and self.started and self.finished and self.last and not missing
        )
        if not report.complete:
            self.problem(
                f"incomplete BEP stream (started={self.started}, finished={self.finished}, lastMessage={self.last}, missing events={len(missing)})"
            )
        if not report.version:
            report.availability["version"] = (
                "Not recorded by this invocation; current PATH is not queried"
            )
        report.availability["events"] = (
            f"{len(self.seen)} unique events; unknown event fields ignored"
        )
        report.availability["actions"] = (
            "Only actions emitted by Bazel; by default these are failures, not all executed actions"
        )
        report.availability["tests"] = (
            "Test-target summaries and attempts; individual JUnit cases are imported separately"
        )
        report.availability["artifacts"] = (
            "References only; no local artifact contents or remote URIs are fetched"
        )
        failed_actions = [
            action for action in report.actions if action["status"] == "failed"
        ]
        for action in failed_actions:
            if not action["failure"]:
                self.findings.message(
                    f"{action['type'] or 'Action'} failed: {action['label']} {action['primary_output']}",
                    "error",
                    "Bazel.action",
                    "Bazel BEP action",
                )
        action_targets = {(a["label"], a["configuration"]) for a in failed_actions}
        for target in self.failed_targets:
            if (
                not target["failure"]
                and (target["label"], target["configuration"]) not in action_targets
            ):
                self.findings.message(
                    f"Target failed: {target['label']} [{target['configuration']}]",
                    "error",
                    "Bazel.target",
                    "Bazel BEP target completion",
                )
        # Never hide another action/target failure merely because an unrelated
        # error exists. Only the generic invocation summary is redundant here.
        if report.exit_code and not any(f.level == "error" for f in report.diagnostics):
            self.findings.message(
                f"Bazel finished: {report.exit_name or report.exit_code}",
                "note" if report.exit_code == 8 else "error",
                "Bazel.finished",
                "Bazel BEP build finished",
            )
        if not report.status:
            report.status = (
                "passed"
                if report.exit_code == 0
                else "failed"
                if report.exit_code is not None
                else "unknown"
            )


def parse(
    path, root, step, problems, *, console=(), executable="", outcome="", duration=0
):
    report = BazelReport(
        step, str(path), executable=executable, status=outcome, duration=duration
    )
    importer = BepImporter(report, problems)
    text = bounded_text(path, root)
    for number, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        try:
            importer.event(json.loads(line))
        except READ_ERRORS as exc:
            importer.valid = False
            importer.problem(f"cannot import BEP event on line {number}: {exc}")
    importer.finish(console)
    return report
