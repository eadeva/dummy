"""Deterministic diagnostic recognition and suppression; no filesystem access."""

import re
from fnmatch import fnmatchcase

ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
# Deliberately anchored: command echoes and summaries such as '0 errors' are not diagnostics.
PATTERNS = [
    re.compile(
        r"^(?P<file>.+?):(?P<line>\d+)(?::\d+)?:\s*(?:fatal )?(?P<level>error|warning):\s*(?P<message>.+)$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?P<file>.+?)\((?P<line>\d+)(?:,\d+)?\)\s*:\s*(?:fatal )?(?P<level>error|warning)\s*(?P<code>[A-Z]+\d+)?\s*:\s*(?P<message>.+)$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?:CMake |[\w.+/-]+:\s*)?(?:fatal )?(?P<level>Error|Warning)(?:\s+\([^)]*\))?(?:\s+at\s+(?P<file>.+?):(?P<line>\d+)(?:\s+\([^)]*\))?)?:\s*(?P<message>.*)$",
        re.IGNORECASE,
    ),
    re.compile(r"^\[(?P<level>ERROR|WARNING|WARN)\]\s*(?P<message>.+)$", re.IGNORECASE),
    re.compile(r"^(?P<code>\w*(?:Error|Exception)):\s*(?P<message>.+)$"),
]


def diagnostic(line):
    text = ANSI.sub("", line).strip()
    if re.match(r"^\d\d:\d\d:\d\d(?:\.\d+)? ptk:", text):
        return None
    for pattern in PATTERNS:
        match = pattern.match(text)
        if match:
            value = match.groupdict()
            return {
                "level": "warning"
                if value.get("level", "error").lower() in {"warning", "warn"}
                else "error",
                "message": value.get("message") or text,
                "file": value.get("file") or "",
                "line": int(value["line"]) if value.get("line") else None,
                "rule": value.get("code") or "",
            }
    return None


def disposition(finding, rules):
    for rule, pattern in rules:
        match = rule.match
        if (
            fnmatchcase(finding.step, match.step)
            and (match.severity is None or match.severity == finding.level)
            and pattern.search(finding.message)
        ):
            finding.disposition = "ignored" if rule.action == "ignore" else "justified"
            finding.suppression_rule = rule.id
            finding.reason = rule.reason
            return
