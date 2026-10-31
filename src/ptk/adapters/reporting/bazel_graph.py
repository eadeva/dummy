"""Bazel's configured target graph, reduced to useful rule-level dependencies."""

import json
import re
import time
import uuid
from collections import Counter
from dataclasses import replace
from graphlib import TopologicalSorter

from .bazel_bep import READ_ERRORS, bounded_text

MAX_TARGETS = 2000
QUERY_TIMEOUT = 60
PLUMBING = {
    "config_setting",
    "constraint_setting",
    "constraint_value",
    "platform",
    "toolchain",
    "toolchain_type",
}
OUTPUT_OPTIONS = {
    "config",
    "profile",
    "memory_profile",
    "starlark_cpu_profile",
    "explain",
    "script_path",
    "run",
    "tool_tag",
    "invocation_id",
    "symlink_prefix",
    "experimental_workspace_rules_log_file",
    "experimental_execution_graph_log",
    "experimental_execution_graph_log_path",
    "experimental_ui_debug_all_events",
}


def main_repo(label):
    return label.startswith(("//", "@//", "@@//"))


def label(value):
    # cquery and BEP may spell the main repository differently.
    return value.lstrip("@") if main_repo(value) else value


def build_graph(data, report, source):
    configurations = {
        str(c["id"]): c["checksum"] for c in data.get("configurations", [])
    }
    tools = {c["checksum"] for c in data.get("configurations", []) if c.get("isTool")}

    def configuration(value):
        if checksum := value.get("configurationChecksum"):
            return checksum
        cid = str(value.get("configurationId", 0))
        if cid != "0":
            return configurations[cid]
        return value.get("configuration", {}).get("checksum", "")

    rules, generated = {}, {}
    for item in data["results"]:
        target, config = item["target"], configuration(item)
        if "rule" in target:
            rule = target["rule"]
            key = (label(rule["name"]), config)
            if key in rules and rules[key] != rule:
                raise ValueError("conflicting configured target")
            rules[key] = rule
        elif "generatedFile" in target:
            value = target["generatedFile"]
            generated[label(value["name"]), config] = (
                label(value["generatingRule"]),
                config,
            )

    roots = {
        (label(t["label"]), t["configuration"]): t
        for t in report.targets
        if not t.get("aspect")
    }
    if not roots or any(key not in rules for key in roots):
        raise ValueError("cquery targets/configurations do not match this build")
    needs, pending = {}, sorted(roots)
    while pending:
        key = pending.pop()
        if key in needs:
            continue
        rule = rules[key]
        deps = set()
        # External rules are useful boundary nodes, not another tree to expand.
        if main_repo(key[0]) or key in roots:
            if rule.get("ruleInput") and not rule.get("configuredRuleInput"):
                raise ValueError(
                    "configured dependencies missing; export with --transitions=lite"
                )
            for value in rule.get("configuredRuleInput", []):
                dep = (label(value["label"]), configuration(value))
                dep = generated.get(dep, dep)
                if (
                    dep in rules
                    and dep[1] not in tools
                    and rules[dep]["ruleClass"] not in PLUMBING
                ):
                    deps.add(dep)
        needs[key] = sorted(deps)
        pending.extend(deps)
        if len(needs) > MAX_TARGETS:
            raise ValueError(f"target overview exceeds {MAX_TARGETS} nodes")
    # Reject corrupt cyclic input before handing it to the layout engine.
    tuple(TopologicalSorter(needs).static_order())
    counts = Counter(name for name, _ in needs)
    ids = {
        key: key[0] if counts[key[0]] == 1 else f"{key[0]} [{key[1]}]" for key in needs
    }
    nodes = []
    for key, deps in sorted(needs.items()):
        external = not main_repo(key[0]) and key not in roots
        nodes.append(
            {
                "id": ids[key],
                "needs": [ids[dep] for dep in deps],
                "label": rules[key]["ruleClass"],
                "kind": "bazel-target",
                "configuration": key[1],
                "status": roots[key]["status"] if key in roots else "configured",
                "message": (
                    "External dependency; transitive details omitted. "
                    if external
                    else ""
                )
                + (
                    "Build result recorded by BEP."
                    if key in roots
                    else "Dependency analysis only; individual build result not reported."
                ),
            }
        )
    return {
        "nodes": nodes,
        "source": source,
        "caption": "Target dependencies: prerequisites → dependents. Shared targets appear once. This is not an execution timeline.",
        "notice": "Bazel cquery configured targets, matched to the build's configuration. Source/output files, toolchains and configuration helper rules are omitted; external dependencies stop at the boundary. Only BEP target results supply passed/failed states.",
    }


def sidecar(report, path, root, problems):
    report.availability["target graph"] = "Unavailable: no matching cquery evidence"
    for suffix in (".bep.jsonl", ".bep.json"):
        if path.name.endswith(suffix):
            candidate = path.with_name(path.name[: -len(suffix)] + ".cquery.json")
            if candidate.exists() or candidate.is_symlink():
                try:
                    report.graph = build_graph(
                        json.loads(bounded_text(candidate, root)),
                        report,
                        str(candidate),
                    )
                    report.availability["target graph"] = (
                        "Imported Bazel cquery JSON; target configurations verified"
                    )
                except READ_ERRORS as exc:
                    problems.append(
                        f"{report.step}: cannot import Bazel target graph: {exc}"
                    )
            break


def query_options(replay):
    options = []
    for option in replay["command options"]:
        name = option["optionName"]
        if (
            "HIDDEN" in option.get("metadataTags", [])
            or name in OUTPUT_OPTIONS
            or name.startswith(
                (
                    "build_event_",
                    "bes_",
                    "execution_log_",
                    "experimental_execution_log_",
                )
            )
        ):
            continue
        options.append(option["combinedForm"])
    return options


def collect(report, replay, command, direct, runner, cancel, folder, on_output):
    """One bounded native query; collection failures never replace the build exit."""
    if report.graph:
        return
    if not report.complete or not report.targets:
        report.availability["target graph"] = (
            "Unavailable: build did not record a complete set of target results"
        )
        return
    if "command options" not in replay or not re.match(
        r"(?:[6-9]|[1-9]\d+)\.", report.version
    ):
        report.availability["target graph"] = (
            "Unavailable: requires Bazel 6+ and canonical build options"
        )
        return
    if cancel is not None and cancel.is_set():
        report.availability["target graph"] = "Not collected: cancelled"
        return
    path = folder / (uuid.uuid4().hex + ".raw-cquery")
    started = time.monotonic()
    try:
        roots = sorted({t["label"] for t in report.targets if not t.get("aspect")})
        if not roots or any("," in target for target in roots):
            raise ValueError(
                "cannot express the recorded top-level targets as a query universe"
            )
        words, index = direct
        # Canonical build options already contain rc/config expansion. Preserve
        # the selected launcher, startup options, environment and working folder.
        argv = [
            *words[:index],
            "--ignore_all_rc_files",
            "--nowrite_command_log",
            "cquery",
        ]
        argv += query_options(replay)
        argv += [
            'kind("rule|generated file", deps(set('
            + " ".join(json.dumps(t) for t in roots)
            + ")))",
            "--universe_scope=" + ",".join(roots),
            "--noimplicit_deps",
            "--notool_deps",
            "--noinclude_aspects",
            "--output=jsonproto",
            "--transitions=lite",
            "--proto:include_configurations",
            "--proto:output_rule_attrs=",
            "--output_file=" + str(path),
            "--bes_backend=",
            "--symlink_prefix=/",
            "--tool_tag=ptk-target-graph",
        ]
        folder.mkdir(parents=True, exist_ok=True)
        on_output("ptk: collecting Bazel target dependencies (cquery; 60s timeout)")
        # Keep query output separate from build diagnostics and never retain its
        # command line, which can contain secrets or expanded environment values.
        result = runner.run(
            replace(command, argv=argv, shell=None, timeout=QUERY_TIMEOUT),
            lambda line: None,
            cancel,
        )
        if result.timed_out or result.cancelled or result.exit_code:
            reason = (
                "cancelled"
                if result.cancelled
                else "timed out"
                if result.timed_out
                else f"exit {result.exit_code}"
            )
            raise ValueError(f"native cquery {reason}; target graph unavailable")
        report.graph = build_graph(
            json.loads(bounded_text(path, folder)),
            report,
            "Bazel cquery --output=jsonproto --transitions=lite",
        )
        report.availability["target graph"] = (
            "Native cquery after this build; target configurations verified"
        )
    except READ_ERRORS as exc:
        report.availability["target graph"] = f"Unavailable: {exc}"
    finally:
        report.availability["graph collection duration"] = (
            f"{time.monotonic() - started:.2f}s (outside command timeout)"
        )
        path.unlink(missing_ok=True)
