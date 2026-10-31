"""GN source-root locations and conservative console/log evidence merging."""

import posixpath
import re

from .log_analysis import ANSI, diagnostic


def message(lines, index, header):
    """Retain GN's explanation below its quoted source line and caret."""
    if not re.match(r"^(ERROR|WARNING) at .+?:\d+", ANSI.sub("", lines[index]).strip()):
        return header
    details = []
    for offset in range(index + 1, min(len(lines), index + 25)):
        line = ANSI.sub("", lines[offset]).strip()
        if (
            diagnostic(line)
            or line.startswith(("Done.", "Generating ", "See "))
            or re.match(r"^\d\d:\d\d:\d\d(?:\.\d+)? ptk:", line)
        ):
            break
        following = (
            ANSI.sub("", lines[offset + 1]).strip() if offset + 1 < len(lines) else ""
        )
        if (
            not line
            or re.fullmatch(r"[\^~\- ]+", line)
            or re.fullmatch(r"[\^~\- ]+", following)
        ):
            continue
        details.append(line[:500])
    return header + ("\n" + "\n".join(details) if details else "")


def identity(finding, root):
    path = finding.file.replace("\\", "/")
    if path.startswith("//"):
        path = root.rstrip("/") + "/" + path[2:]
    return (
        finding.step,
        finding.level,
        posixpath.normpath(path) if path else "",
        finding.line,
        " ".join(finding.message.split()),
    )


def merge_log_evidence(report):
    indexes = {}
    for gn in report.gn:
        index = indexes.setdefault(gn.root, {})
        for finding in gn.diagnostics:
            index.setdefault(identity(finding, gn.root), []).append(finding)
    retained = []
    for finding in report.log_findings:
        matches = [
            item
            for root, index in indexes.items()
            for item in index.get(identity(finding, root), [])
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
