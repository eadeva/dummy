"""Import diagnostics from bounded, captured step logs, including archived runs."""

import re
from pathlib import Path

from ...domain.config.model import LogAnalysisSpec
from ...domain.reporting.gn import message as gn_message
from ...domain.reporting.log_analysis import ANSI, diagnostic, disposition
from ...domain.reporting.model import Contribution, LogFinding

MAX_BYTES = 50 * 1024 * 1024


def analyze(summary):
    result = Contribution(step="")
    policy = LogAnalysisSpec.model_validate(summary["log_analysis"])
    if not policy.enabled:
        return result
    rules = [(rule, re.compile(rule.match.message_regex)) for rule in policy.rules]
    root = Path(summary.get("log_dir") or ".").resolve()
    seen = set()
    for step in summary.get("steps", []):
        if not step.get("report", True) or not step.get("log_file"):
            continue
        path = Path(step["log_file"])
        if str(path) in seen:
            continue
        seen.add(str(path))
        try:
            if (
                not summary.get("log_dir")
                or not path.resolve().is_relative_to(root)
                or any(p.is_symlink() for p in (path, *path.parents))
            ):
                raise ValueError(
                    "log is outside the recorded run directory or uses a symlink"
                )
            if path.stat().st_size > MAX_BYTES:
                raise ValueError("log exceeds the 50 MiB analysis limit")
            # Bounded read keeps source line numbers and surrounding context exact.
            with path.open("rb") as stream:
                data = stream.read(MAX_BYTES + 1)
            if len(data) > MAX_BYTES:
                raise ValueError("log exceeds the 50 MiB analysis limit")
            lines = data.decode("utf-8", errors="replace").splitlines()
            groups = {}
            for index, line in enumerate(lines):
                parsed = diagnostic(line)
                if parsed is None:
                    continue
                parsed["message"] = gn_message(lines, index, parsed["message"])
                # CMake and other diagnostic headers may put the message on following lines.
                if not parsed["message"] or parsed["message"].endswith(":"):
                    continuation = []
                    for following in lines[index + 1 : index + 21]:
                        if not following.strip() or not following[:1].isspace():
                            break
                        continuation.append(ANSI.sub("", following).strip())
                    if continuation:
                        parsed["message"] += "\n" + "\n".join(continuation)
                finding = LogFinding(
                    tool="log-analyzer",
                    step=step["step"],
                    source_log=str(path),
                    log_line=index + 1,
                    **parsed,
                )
                disposition(finding, rules)
                key = (
                    finding.level,
                    finding.message,
                    finding.file,
                    finding.line,
                    finding.rule,
                    finding.disposition,
                    finding.suppression_rule,
                )
                if key in groups:
                    existing = groups[key]
                    existing.occurrences += 1
                    if len(existing.log_lines) < 50:
                        existing.log_lines.append(index + 1)
                    continue
                finding.log_lines = [index + 1]
                finding.context = [
                    f"{i + 1}: {ANSI.sub('', lines[i])}"
                    for i in range(max(0, index - 2), min(len(lines), index + 3))
                ]
                groups[key] = finding
            result.log_findings.extend(groups.values())
        except (OSError, ValueError) as exc:
            result.problems.append(f"{step['step']}: cannot analyze {path.name}: {exc}")
    return result
