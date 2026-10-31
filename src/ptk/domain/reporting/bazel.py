"""Exact Bazel evidence identities; ambiguous findings retain separate sources."""

import posixpath
import re
from urllib.parse import unquote


def identity(finding, workspace=""):
    path = unquote(finding.file.removeprefix("file://")).replace("\\", "/")
    if (
        path
        and workspace
        and not (path.startswith("/") or re.match(r"^[A-Za-z]:/", path))
    ):
        path = workspace.replace("\\", "/") + "/" + path
    return (
        finding.step,
        finding.level,
        posixpath.normpath(path) if path else "",
        finding.line,
        " ".join(finding.message.split()),
    )


def merge_log_evidence(report):
    indexes = {}
    for bazel in report.bazel:
        index = indexes.setdefault(bazel.workspace, {})
        for item in bazel.diagnostics:
            index.setdefault(identity(item, bazel.workspace), []).append(item)
    retained = []
    for finding in report.log_findings:
        matches = [
            item
            for workspace, index in indexes.items()
            for item in index.get(identity(finding, workspace), [])
        ]
        if len(matches) != 1:
            retained.append(finding)
            continue
        target = matches[0]
        target.context.append("Source: PTK log analysis")
        target.source_log = finding.source_log
        target.log_line = finding.log_line
        target.log_lines = finding.log_lines
        target.occurrences = max(target.occurrences, finding.occurrences)
    report.log_findings = retained
