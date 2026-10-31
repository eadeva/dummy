"""Bounded readers for CMake evidence. Never execute a generated CMake file."""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

from ....domain.reporting.log_analysis import ANSI
from ....domain.reporting.model import LogFinding

MAX_BYTES = 100 * 1024 * 1024
READ_ERRORS = (
    OSError,
    ValueError,
    TypeError,
    KeyError,
    IndexError,
    AttributeError,
    RecursionError,
    yaml.YAMLError,
)


def stamp(path):
    try:
        stat = path.stat()
        return (stat.st_mtime_ns, stat.st_size, stat.st_ino)
    except FileNotFoundError:
        return None


def text_file(path, root, *, offset=0):
    path, root = Path(path), Path(root).resolve()
    if path.is_symlink() or not path.resolve().is_relative_to(root):
        raise ValueError("CMake evidence must stay inside its build directory")
    if path.stat().st_size - offset > MAX_BYTES:
        raise ValueError("CMake artifact exceeds 100 MiB")
    with path.open("rb") as stream:
        stream.seek(offset)
        data = stream.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError("CMake artifact exceeds 100 MiB")
    return data.decode("utf-8-sig", errors="replace")


def json_file(path, root):
    data = json.loads(text_file(path, root))
    if not isinstance(data, dict):
        raise TypeError("expected a JSON object")
    return data


def cache_values(text):
    result = {}
    for line in text.splitlines():
        if match := re.match(r'^(?:"([^"]+)"|([^/#][^:]*)):([^=]+)=(.*)$', line):
            result[match[1] or match[2]] = match[4]
    return result


def cache_version(values):
    parts = [
        values.get(f"CMAKE_CACHE_{p}_VERSION", "") for p in ("MAJOR", "MINOR", "PATCH")
    ]
    return ".".join(parts) if all(p.isdigit() for p in parts) else ""


def version_tuple(version):
    match = re.match(r"^(\d+)\.(\d+)(?:\.(\d+))?", version)
    if not match:
        raise ValueError(f"unrecognized CMake version: {version!r}")
    return tuple(int(part or 0) for part in match.groups())


HEADER = re.compile(
    r"^CMake (?P<kind>Deprecation Warning|Warning|Error)(?:\s+\((?P<category>[^)]+)\))?"
    r"(?:\s+at\s+(?P<file>.+):(?P<line>\d+)(?:\s+\([^)]*\))?"
    r"|\s+in\s+(?P<infile>.+?)(?:\s+\([^)]*\))?)?:[ \t]*(?P<message>.*)$"
)


def console_diagnostics(lines, step):
    """CMake headers only: compiler probe output must not become diagnostics."""
    result = []
    clean = [ANSI.sub("", line) for line in lines]
    for index, line in enumerate(clean):
        match = HEADER.match(line)
        if not match:
            continue
        message = [match["message"]] if match["message"] else []
        for following in clean[index + 1 :]:
            if not following.strip():
                if message:
                    break
                continue
            if not following[:1].isspace():
                break
            message.append(following.strip())
        result.append(
            LogFinding(
                tool="CMake",
                step=step,
                rule="CMake." + (match["category"] or match["kind"]).replace(" ", ""),
                level="error" if match["kind"] == "Error" else "warning",
                message="\n".join(message) or line,
                file=match["file"] or match["infile"] or "",
                line=int(match["line"]) if match["line"] else None,
                log_line=index + 1,
            )
        )
    return result


def sarif_diagnostics(data, step):
    result = []
    for run in data.get("runs", []):
        driver = run.get("tool", {}).get("driver", {})
        rules = {r.get("id"): r for r in driver.get("rules", [])}
        for item in run.get("results", []):
            level = item.get("level", "warning")
            if level not in ("error", "warning", "note", "none"):
                raise ValueError(f"unknown SARIF diagnostic level: {level}")
            message = item.get("message", {})
            text = message.get("text") or message.get("markdown")
            if not text:
                templates = {
                    **driver.get("globalMessageStrings", {}),
                    **rules.get(item.get("ruleId"), {}).get("messageStrings", {}),
                }
                text = templates.get(message.get("id"), {}).get("text", "")
                for i, arg in enumerate(message.get("arguments", [])):
                    text = text.replace("{" + str(i) + "}", str(arg))
            if not text:
                raise ValueError("SARIF diagnostic has no resolvable message")
            location = (item.get("locations") or [{}])[0].get("physicalLocation", {})
            result.append(
                LogFinding(
                    tool="CMake",
                    rule=item.get("ruleId", ""),
                    level="note" if level == "none" else level,
                    message=text.strip(),
                    file=location.get("artifactLocation", {}).get("uri", ""),
                    line=location.get("region", {}).get("startLine"),
                    step=step,
                )
            )
    return result


def attempt(report, problems, label, operation):
    try:
        operation()
    except READ_ERRORS as exc:
        report.availability[label] = "Unreadable"
        problems.append(f"{report.step}: cannot import CMake {label}: {exc}")


def read_cache(report, build):
    values = cache_values(text_file(build / "CMakeCache.txt", build))
    keys = (
        "CMAKE_HOME_DIRECTORY",
        "CMAKE_PROJECT_NAME",
        "CMAKE_BUILD_TYPE",
        "CMAKE_CONFIGURATION_TYPES",
        "CMAKE_GENERATOR",
        "CMAKE_TOOLCHAIN_FILE",
        "CMAKE_SYSTEM_NAME",
        "CMAKE_SYSTEM_PROCESSOR",
        "CMAKE_C_COMPILER",
        "CMAKE_CXX_COMPILER",
        "CMAKE_MAKE_PROGRAM",
    )
    report.configuration = {key: values[key] for key in keys if key in values}
    report.availability["configuration"] = "Imported"


def current_index(build, before):
    directory = build / ".cmake/api/v1/reply"
    indexes = list(directory.glob("index-*.json")) + list(
        directory.glob("error-*.json")
    )
    indexes = [p for p in indexes if before.get(str(p)) != stamp(p)]
    return max(indexes, key=lambda p: p.name.split("-", 1)[1]) if indexes else None


def read_api(report, build, before, problems):
    index = current_index(build, before)
    if index is None:
        report.availability["targets"] = "No current File API reply"
        return None
    data = json_file(index, build)
    report.configuration["CMAKE_GENERATOR"] = (
        data.get("cmake", {}).get("generator", {}).get("name", "")
    )
    # Only consume this client's versioned requests, not another client's replies.
    replies = data.get("reply", {}).get("client-ptk", {})
    log = None
    for reply in replies.values():
        if "error" in reply:
            continue
        kind = reply.get("kind")
        if kind == "configureLog":
            log = json_file(index.parent / reply["jsonFile"], build)
        elif kind == "toolchains":

            def read_toolchains(reply=reply):
                report.toolchains = json_file(index.parent / reply["jsonFile"], build)[
                    "toolchains"
                ]
                report.availability["toolchains"] = "Imported"

            attempt(report, problems, "toolchains", read_toolchains)
        elif kind == "codemodel":

            def read_targets(reply=reply):
                model = json_file(index.parent / reply["jsonFile"], build)
                targets = []
                for config in model["configurations"]:
                    for target in config.get("targets", []):
                        detail = json_file(index.parent / target["jsonFile"], build)
                        targets.append(
                            {
                                "id": detail["id"],
                                "name": detail["name"],
                                "type": detail["type"],
                                "configuration": config["name"],
                                "needs": [
                                    d["id"] for d in detail.get("dependencies", [])
                                ],
                                "artifacts": [
                                    a["path"] for a in detail.get("artifacts", [])
                                ],
                                "sources": [
                                    s["path"] for s in detail.get("sources", [])
                                ],
                            }
                        )
                report.targets = targets
                report.availability["targets"] = "Imported"

            attempt(report, problems, "targets", read_targets)
    return log


def decode_block(value):
    # Configure-log block scalars have their own encoding on top of YAML.
    return re.sub(
        r"\\(?:\\|x[0-9a-fA-F]{2})",
        lambda m: "\\" if m[0] == "\\\\" else chr(int(m[0][2:], 16)),  # noqa: FURB166
        str(value),
    )


def read_events(report, build, before, log=None, *, packages=False):
    path = Path(log["path"]) if log else build / "CMakeFiles/CMakeConfigureLog.yaml"
    if not path.is_absolute():
        path = build / path
    old = before.get(str(path))
    if not path.exists() or old == stamp(path):
        report.availability["checks"] = "No new configure events"
        return
    offset = (
        old[1]
        if old and path.stat().st_size > old[1] and path.stat().st_ino == old[2]
        else 0
    )
    allowed = (
        set(log["eventKindNames"])
        if log
        else {"message-v1", "try_compile-v1", "try_run-v1"}
    )
    text = text_file(path, build, offset=offset)
    for document in yaml.safe_load_all(text):
        if document is None:
            continue
        if not isinstance(document, dict) or not isinstance(
            document.get("events", []), list
        ):
            raise TypeError("invalid configure-log document")
        for event in document.get("events", []):
            kind = event["kind"]
            if kind not in allowed:
                continue
            if kind in ("try_compile-v1", "try_run-v1"):
                compiled = event.get("buildResult", {})
                executed = event.get("runResult", {})
                code = executed.get("exitCode", compiled.get("exitCode"))
                report.checks.append(
                    {
                        "name": event.get("description")
                        or " / ".join(event.get("checks", []))
                        or kind,
                        "kind": kind,
                        "result": "supported"
                        if code == 0
                        else "not-supported"
                        if code is not None
                        else "unknown",
                        "exit_code": code,
                        "backtrace": event.get("backtrace", []),
                        "output": decode_block(compiled.get("stdout", ""))
                        + decode_block(executed.get("stdout", ""))
                        + decode_block(executed.get("stderr", "")),
                    }
                )
            elif packages and kind in ("find_package-v1", "find-v1"):
                report.packages.append(
                    {
                        "name": event.get("name") or event.get("variable", ""),
                        "kind": kind,
                        "found": event.get("found"),
                        "requested": event.get("version_request", {}),
                        "required": event.get("settings", {}).get(
                            "required", "unspecified"
                        ),
                        "components": event.get("components", []),
                        "candidates": event.get(
                            "candidates", event.get("searched_directories", [])
                        ),
                        "backtrace": event.get("backtrace", []),
                    }
                )
    report.availability["checks"] = "Imported current events"
    if packages:
        report.availability["packages"] = "Imported current events"


def read_legacy_checks(report, build, before):
    for name in ("CMakeOutput.log", "CMakeError.log"):
        path = build / "CMakeFiles" / name
        old = before.get(str(path))
        if not path.is_file() or old == stamp(path):
            continue
        offset = (
            old[1]
            if old and path.stat().st_size > old[1] and path.stat().st_ino == old[2]
            else 0
        )
        text = text_file(path, build, offset=offset)
        if text.strip():
            report.checks.append(
                {
                    "name": name,
                    "kind": "probe-log",
                    "result": "unclassified",
                    "output": text,
                }
            )
    report.availability["checks"] = (
        "Probe logs retained; individual outcomes are not inferred"
    )
