"""Configured, target-level dependencies and non-invasive graph collection."""

import json
from dataclasses import replace
from pathlib import Path

import pytest
from tests.reporting.test_bazel import (
    FakeRunner,
    command,
    produce,
    stream,
    target_id,
    write_stream,
)

from ptk.adapters.reporting import bazel, bazel_graph, bazel_html
from ptk.application.ports import ProcessOutcome
from ptk.domain.reporting.model import BazelReport, Report


def rule(name, deps=(), config=1, kind="cc_library"):
    return {
        "configurationId": config,
        "target": {
            "rule": {
                "name": name,
                "ruleClass": kind,
                "ruleInput": [dep[0] for dep in deps],
                "configuredRuleInput": [
                    {"label": dep, "configurationId": cfg} for dep, cfg in deps
                ],
            }
        },
    }


def evidence():
    return {
        "configurations": [
            {"id": 1, "checksum": "cfg"},
            {"id": 2, "checksum": "other"},
        ],
        "results": [
            rule(
                "//:app",
                [
                    ("//:left", 1),
                    ("//:common", 1),
                    ("//:input.cc", 0),
                    ("//:generated.cc", 1),
                    ("//:choice", 1),
                    ("@ext//:lib", 1),
                ],
            ),
            rule("//:left", [("//:common", 1)]),
            rule("//:common"),
            rule("//:generator", kind="genrule"),
            {
                "configurationId": 1,
                "target": {
                    "generatedFile": {
                        "name": "//:generated.cc",
                        "generatingRule": "//:generator",
                    }
                },
            },
            rule("//:choice", kind="config_setting"),
            rule("//:inactive"),
            rule("//:app", config=2),
            rule("@ext//:lib", [("@ext//:internal", 1)]),
            rule("@ext//:internal"),
        ],
    }


def report():
    return BazelReport(
        "compile",
        "run.bep.json",
        version="9.1.0",
        complete=True,
        targets=[{"label": "//:app", "configuration": "cfg", "status": "passed"}],
    )


def canonical(*options):
    return {
        "id": {"structuredCommandLine": {"commandLineLabel": "canonical"}},
        "structuredCommandLine": {
            "commandLineLabel": "canonical",
            "sections": [
                {
                    "sectionLabel": "command options",
                    "optionList": {
                        "option": [
                            {"optionName": name, "combinedForm": value}
                            for name, value in options
                        ]
                    },
                }
            ],
        },
    }


def events():
    return stream(
        canonical(
            ("define", "--define=choice=yes"),
            ("config", "--config=chosen"),
            ("build_event_json_file", "--build_event_json_file=original.json"),
            ("profile", "--profile=original.profile"),
            ("bes_backend", "--bes_backend=remote"),
        ),
        {
            "id": {"targetCompleted": target_id("//:app")},
            "completed": {"success": True},
        },
    )


def test_overview_keeps_shared_targets_generated_producers_and_external_boundary():
    data = evidence()
    data["results"][0]["target"]["rule"]["ruleInput"].append("//:inactive")
    graph = bazel_graph.build_graph(data, report(), "cquery")
    nodes = {n["id"]: n for n in graph["nodes"]}
    assert set(nodes) == {
        "//:app",
        "//:left",
        "//:common",
        "//:generator",
        "@ext//:lib",
    }
    assert set(nodes["//:app"]["needs"]) == {
        "//:left",
        "//:common",
        "//:generator",
        "@ext//:lib",
    }
    assert nodes["//:left"]["needs"] == ["//:common"]
    assert nodes["@ext//:lib"]["needs"] == []
    assert nodes["//:app"]["status"] == "passed"
    assert all(n["status"] == "configured" for k, n in nodes.items() if k != "//:app")
    assert "not an execution timeline" in graph["caption"]


def test_configurations_remain_distinct_and_must_match_original_build():
    data, invocation = evidence(), report()
    data["results"][0]["target"]["rule"]["configuredRuleInput"].append(
        {"label": "//:common", "configurationId": 2}
    )
    data["results"].append(rule("//:common", config=2))
    graph = bazel_graph.build_graph(data, invocation, "cquery")
    assert {n["id"] for n in graph["nodes"] if n["id"].startswith("//:common")} == {
        "//:common [cfg]",
        "//:common [other]",
    }
    invocation.targets[0]["configuration"] = "not-this-build"
    with pytest.raises(ValueError, match="do not match"):
        bazel_graph.build_graph(data, invocation, "cquery")


@pytest.mark.parametrize(
    "mutation, message",
    [
        (
            lambda d: d["results"][0]["target"]["rule"].pop("configuredRuleInput"),
            "configured dependencies missing",
        ),
        (
            lambda d: d["results"].append(rule("//:app", kind="different")),
            "conflicting",
        ),
        (
            lambda d: d["results"][2]["target"]["rule"].update(
                configuredRuleInput=[{"label": "//:app", "configurationId": 1}]
            ),
            "cycle",
        ),
    ],
)
def test_malformed_or_ambiguous_graph_is_not_rendered(mutation, message):
    data = evidence()
    mutation(data)
    with pytest.raises(ValueError, match=message):
        bazel_graph.build_graph(data, report(), "cquery")


def test_large_graph_has_an_explicit_limit(monkeypatch):
    monkeypatch.setattr(bazel_graph, "MAX_TARGETS", 3)
    with pytest.raises(ValueError, match="exceeds 3"):
        bazel_graph.build_graph(evidence(), report(), "cquery")


def test_tool_configuration_is_omitted_from_imported_graph():
    data = evidence()
    data["configurations"][1]["isTool"] = True
    data["results"][0]["target"]["rule"]["configuredRuleInput"].append(
        {"label": "//:tool", "configurationId": 2}
    )
    data["results"].append(rule("//:tool", config=2))
    graph = bazel_graph.build_graph(data, report(), "cquery")
    assert "//:tool" not in {n["id"] for n in graph["nodes"]}


def test_automatic_query_reuses_context_preserves_outputs_and_masks_snapshot(tmp_path):
    secret = "private-label"
    data = evidence()
    data["results"][2]["target"]["rule"]["ruleClass"] = secret

    def body(cmd, output):
        if "cquery" not in cmd.argv:
            produce(events())(cmd, output)
        else:
            dest = next(
                a.split("=", 1)[1] for a in cmd.argv if a.startswith("--output_file=")
            )
            Path(dest).write_text(json.dumps(data))

    runner = FakeRunner(body)
    cmd = command(
        tmp_path,
        ["bazelisk", "--output_base=cache", "run", "//:app", "--", "--forwarded"],
    )
    original = list(cmd.argv)
    outcome = bazel.BazelReportingRunner(runner, "linux").run(
        cmd,
        lambda l: None,
        mask=lambda s: s.replace(secret, "***"),
        on_problem=pytest.fail,
    )
    assert outcome.exit_code == 0 and outcome.reporting_duration > 0
    assert cmd.argv == original and len(runner.calls) == 2
    query = runner.calls[1]
    assert query.argv[:5] == [
        "bazelisk",
        "--output_base=cache",
        "--ignore_all_rc_files",
        "--nowrite_command_log",
        "cquery",
    ]
    assert (
        query.env == cmd.env
        and query.cwd == cmd.cwd
        and query.timeout == bazel_graph.QUERY_TIMEOUT
    )
    assert "--define=choice=yes" in query.argv
    assert not any(
        "original." in a or a.startswith("--config=") or a == "--forwarded"
        for a in query.argv
    )
    assert "--bes_backend=" in query.argv and "--noimplicit_deps" in query.argv
    result = bazel.read(tmp_path / "reports", "compile")
    assert not result.problems and len(result.bazel) == 1
    assert len(result.bazel[0].graph["nodes"]) == 5
    assert secret not in json.dumps(result.bazel[0].graph)
    assert not list((tmp_path / "reports" / ".ptk-bazel").glob("*.raw-*"))
    assert (
        "command options"
        not in next((tmp_path / "reports" / ".ptk-bazel").glob("*.json")).read_text()
    )


@pytest.mark.parametrize(
    "query_outcome",
    [
        ProcessOutcome(2),
        ProcessOutcome(1, timed_out=True),
        ProcessOutcome(1, cancelled=True),
    ],
)
def test_query_failure_preserves_build_result_without_duplicate_diagnostics(
    tmp_path, query_outcome
):
    class Runner(FakeRunner):
        def run(self, cmd, output, cancel=None):
            if "cquery" in cmd.argv:
                return query_outcome
            return super().run(cmd, output, cancel)

    runner = Runner(produce(events()))
    outcome = bazel.BazelReportingRunner(runner, "linux").run(
        command(tmp_path), lambda l: None, mask=lambda s: s, on_problem=pytest.fail
    )
    assert outcome.exit_code == 0 and not outcome.timed_out and not outcome.cancelled
    [invocation] = bazel.read(tmp_path / "reports", "compile").bazel
    assert not invocation.graph and not invocation.diagnostics
    assert "Unavailable" in invocation.availability["target graph"]


def test_raw_import_pairs_graph_without_invoking_bazel_and_rejects_symlinks(tmp_path):
    write_stream(tmp_path / "run.bep.json", events())
    path = tmp_path / "run.cquery.json"
    path.write_text(json.dumps(evidence()))
    result = bazel.read(tmp_path, "compile")
    assert not result.problems and result.bazel[0].graph
    path.unlink()
    outside = tmp_path.parent / "outside.json"
    outside.write_text(json.dumps(evidence()))
    path.symlink_to(outside)
    result = bazel.read(tmp_path, "compile")
    assert result.problems and not result.bazel[0].graph


def test_full_report_graph_is_collapsed_escaped_and_describes_dependencies(tmp_path):
    invocation = report()
    invocation.graph = bazel_graph.build_graph(evidence(), invocation, "native cquery")
    invocation.graph["nodes"][0]["message"] = "</script><script>bad()</script>"
    parent = Report(
        project="p",
        job="j",
        variant="v",
        run_id="r",
        status="passed",
        started_at="",
        duration=0,
        params={},
        param_sources={},
        steps=[],
        bazel=[invocation],
    )
    markup = bazel_html.section([parent], tmp_path)
    assert '<details class="ptk-graph">' in markup
    assert "Target dependencies: prerequisites" in markup
    assert "Execution flows" not in markup and "bad()</script>" not in markup
    assert 'aria-label="Zoom in"' in markup and "Drag to pan" in markup


def test_cancelled_build_does_not_start_a_query(tmp_path):
    class Runner(FakeRunner):
        def run(self, *args, **kwargs):
            return replace(super().run(*args, **kwargs), cancelled=True)

    runner = Runner(produce(events()))
    bazel.BazelReportingRunner(runner, "linux").run(
        command(tmp_path), lambda l: None, mask=lambda s: s, on_problem=pytest.fail
    )
    assert len(runner.calls) == 1
