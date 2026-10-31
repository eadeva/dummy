"""Conservative identity matching between structured and captured CMake findings."""

import posixpath
import re
from urllib.parse import unquote


def normalized_message(message):
    message = re.sub(
        r"^CMake (?:Deprecation Warning|Warning|Error)(?:\s+\([^)]*\))?(?:\s+(?:at|in)\s+[^\n]+)?:[ \t]*\n?",
        "",
        message,
    )
    return " ".join(message.split())


def same_diagnostic(left, right, source_root=""):
    def path(value):
        value = unquote(value.removeprefix("file://")).replace("\\", "/")
        if (
            value
            and source_root
            and not (value.startswith("/") or re.match(r"^[A-Za-z]:/", value))
        ):
            value = source_root.replace("\\", "/") + "/" + value
        return posixpath.normpath(value) if value else ""

    return (
        left.step == right.step
        and left.level == right.level
        and left.line == right.line
        and path(left.file) == path(right.file)
        and normalized_message(left.message) == normalized_message(right.message)
    )


def merge_log_evidence(report):
    """Merge exact evidence identities; ambiguous matches keep explicit sources."""
    retained = []
    for log in report.log_findings:
        matches = [
            finding
            for cmake in report.cmake
            for finding in cmake.diagnostics
            if same_diagnostic(
                finding, log, cmake.configuration.get("CMAKE_HOME_DIRECTORY", "")
            )
        ]
        if len(matches) != 1:
            retained.append(log)
            continue
        finding = matches[0]
        finding.context.append("Source: PTK log analysis")
        finding.source_log = log.source_log
        finding.log_line = log.log_line
        finding.log_lines = log.log_lines
        finding.occurrences = log.occurrences
    report.log_findings = retained


def merge_sarif_evidence(report):
    retained = []
    for finding in report.findings:
        matches = [
            item
            for cmake in report.cmake
            for item in cmake.diagnostics
            if finding.tool.casefold() == "cmake"
            and same_diagnostic(
                item, finding, cmake.configuration.get("CMAKE_HOME_DIRECTORY", "")
            )
        ]
        if len(matches) == 1:
            matches[0].context.append("Source: SARIF report importer")
        else:
            retained.append(finding)
    report.findings = retained
