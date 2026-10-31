"""BEP evidence, actual invocation capture, report policy and source identity."""

import json
import os
import sys
from pathlib import Path

import pytest

from ptk.adapters.process import SubprocessRunner
from ptk.adapters.reporting import bazel, bazel_bep, diagnostics, exporters, html
from ptk.adapters.reporting.runner import ReportingRunner
from ptk.adapters.reporting.store import FileReportStore
from ptk.application.ports import ProcessOutcome
from ptk.application.use_cases.report import ReportService
from ptk.domain.execution.model import CommandSpec
from ptk.domain.reporting.model import from_summary


def stream(*events, version="9.1.0", exit_code=0, workspace="/src", invocation="run-1"):
    finished = {
        "id": {"buildFinished": {}},
        "finished": {
            "exitCode": {
                "name": "SUCCESS" if exit_code == 0 else "BUILD_FAILURE",
                "code": exit_code,
            }
        },
    }
    events = [*events, finished]
    started = {
        "id": {"started": {}},
        "children": [event["id"] for event in events],
        "started": {
            "buildToolVersion": version,
            "uuid": invocation,
            "command": "test",
            "workspaceDirectory": workspace,
        },
    }
    events[-1]["lastMessage"] = True
    return [started, *events]


def write_stream(path, events):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(event) + "\n" for event in events), encoding="utf-8"
    )
    return path


def read_stream(tmp_path, events, **kwargs):
    path = write_stream(tmp_path / "run.bep.json", events)
    problems = []
    report = bazel_bep.parse(path, tmp_path, "compile", problems, **kwargs)
    return report, problems


def target_id(label="//:unit", config="cfg"):
    return {"label": label, "configuration": {"id": config}}


def test_structured_results_progress_chunks_warnings_and_flaky_attempts(tmp_path):
    report, problems = read_stream(
        tmp_path,
        stream(
            {
                "id": {"progress": {"opaqueCount": 0}},
                "progress": {"stderr": "WARNING: /src/lib.cc:8:2: known "},
            },
            {
                "id": {"progress": {"opaqueCount": 1}},
                "progress": {"stderr": "warning\n"},
            },
            {
                "id": {"targetConfigured": {"label": "//:unit"}},
                "configured": {"targetKind": "custom_test rule"},
            },
            {"id": {"targetCompleted": target_id()}, "completed": {"success": True}},
            {
                "id": {
                    "testResult": {**target_id(), "run": 1, "shard": 0, "attempt": 1}
                },
                "testResult": {
                    "status": "FAILED",
                    "testAttemptDuration": "1.25s",
                    "testActionOutput": [
                        {"name": "test.log", "uri": "bytestream://cache/blobs/hash/123"}
                    ],
                },
            },
            {
                "id": {
                    "testResult": {**target_id(), "run": 1, "shard": 0, "attempt": 2}
                },
                "testResult": {
                    "status": "PASSED",
                    "cachedLocally": True,
                    "executionInfo": {"cachedRemotely": False},
                    "warning": ["Test took too long"],
                },
            },
            {
                "id": {"testSummary": target_id()},
                "testSummary": {
                    "overallStatus": "FLAKY",
                    "totalRunCount": 2,
                    "runCount": 1,
                    "attemptCount": 2,
                    "shardCount": 1,
                    "totalRunDuration": "2.5s",
                },
            },
            {
                "id": {"buildMetrics": {}},
                "buildMetrics": {
                    "actionSummary": {"actionsExecuted": "7"},
                    "timingMetrics": {"wallTimeInMs": "2345"},
                },
            },
        ),
        console=["WARNING: /src/lib.cc:8:2: known warning"],
    )
    assert not problems and report.complete and report.version == "9.1.0"
    assert report.targets[0]["kind"] == "custom_test rule"
    assert report.test_attempts[0]["duration"] == 1.25
    assert report.test_attempts[1]["cached_locally"]
    assert report.tests[0]["duration"] == 2.5
    assert len(report.diagnostics) == 3
    assert {f.level for f in report.diagnostics} == {"warning"}
    warning = next(f for f in report.diagnostics if f.message == "known warning")
    assert warning.file == "/src/lib.cc" and warning.line == 8
    assert warning.occurrences == 1
    assert warning.context == [
        "Source: Bazel BEP progress stderr",
        "Source: Bazel console",
    ]
    assert report.artifacts[0]["uri"].startswith("bytestream://")


def test_exact_action_target_console_duplicates_merge_without_generic_failure(tmp_path):
    message = "/src/lib.cc:9:3: bad include"
    detail = {"message": message}
    report, problems = read_stream(
        tmp_path,
        stream(
            {
                "id": {
                    "actionCompleted": {**target_id("//:lib"), "primaryOutput": "lib.o"}
                },
                "action": {
                    "type": "CppCompile",
                    "failureDetail": detail,
                    "exitCode": 1,
                },
            },
            {
                "id": {"targetCompleted": target_id("//:lib")},
                "completed": {"failureDetail": detail},
            },
            exit_code=1,
        ),
        console=["ERROR: " + message],
    )
    assert not problems
    assert len(report.diagnostics) == 1
    finding = report.diagnostics[0]
    assert finding.message == "bad include"
    assert finding.file == "/src/lib.cc" and finding.line == 9
    assert {s for s in finding.context if s.startswith("Source:")} == {
        "Source: Bazel BEP action",
        "Source: Bazel BEP target completion",
        "Source: Bazel console",
    }
    assert report.actions[0]["configuration"] == "cfg"


@pytest.mark.parametrize(
    "version", ["7.6.0", "8.4.0", "9.1.0", "10.0.0-pre.20260101", "development version"]
)
def test_producing_version_and_optional_fields_are_preserved(tmp_path, version):
    report, problems = read_stream(
        tmp_path,
        stream(
            {"id": {"futureEvent": {"id": "x"}}, "futurePayload": {"unknown": True}},
            {"id": {"testSummary": target_id()}, "testSummary": {"overallStatus": 1}},
            version=version,
        ),
    )
    assert not problems and report.version == version and report.complete
    assert report.tests[0]["status"] == "PASSED"
    assert report.tests[0]["duration"] is None


def test_target_configurations_attempts_and_artifacts_are_distinct(tmp_path):
    events = []
    for config in ("host", "target"):
        events.append(
            {
                "id": {"testSummary": target_id(config=config)},
                "testSummary": {"overallStatus": "FAILED"},
            }
        )
        events.append(
            {
                "id": {"targetCompleted": target_id(config=config)},
                "completed": {
                    "success": True,
                    "outputGroup": [
                        {
                            "name": "default",
                            "fileSets": [{"id": "shared"}],
                            "inlineFiles": [{"name": "inline", "contents": "c2VjcmV0"}],
                        }
                    ],
                },
            }
        )
    events.append(
        {
            "id": {"namedSet": {"id": "shared"}},
            "namedSetOfFiles": {
                "files": [{"name": "output", "uri": "file:///do/not/read"}],
                "fileSets": [],
            },
        }
    )
    report, problems = read_stream(tmp_path, stream(*events, exit_code=1))
    assert not problems and len(report.tests) == 2 and len(report.diagnostics) == 2
    assert (
        "host" in report.diagnostics[0].message
        and "target" in report.diagnostics[1].message
    )
    assert len(report.artifacts) == 1
    assert "contents" not in report.targets[0]["output_groups"][0]["files"][0]


def test_unrelated_failure_does_not_hide_action_or_target_outcomes(tmp_path):
    report, problems = read_stream(
        tmp_path,
        stream(
            {
                "id": {"progress": {}},
                "progress": {"stderr": "ERROR: unrelated error\n"},
            },
            {
                "id": {
                    "actionCompleted": {
                        **target_id("//:first"),
                        "primaryOutput": "first.o",
                    }
                },
                "action": {"exitCode": 1},
            },
            {"id": {"targetCompleted": target_id("//:first")}, "completed": {}},
            {"id": {"targetCompleted": target_id("//:second")}, "completed": {}},
            exit_code=1,
        ),
    )
    assert not problems
    assert len(report.diagnostics) == 3
    assert any("first.o" in f.message for f in report.diagnostics)
    assert any("Target failed: //:second" in f.message for f in report.diagnostics)


def test_duplicate_events_count_once_and_incomplete_stream_retains_evidence(tmp_path):
    event = {"id": {"progress": {}}, "progress": {"stderr": "WARNING: retained\n"}}
    events = stream(event)
    events.insert(2, event)
    report, problems = read_stream(tmp_path, events)
    assert (
        not problems
        and len(report.diagnostics) == 1
        and report.diagnostics[0].occurrences == 1
    )
    path = write_stream(tmp_path / "cut.bep.json", events[:-1])
    with path.open("a") as handle:
        handle.write('{"id":')
    problems = []
    cut = bazel_bep.parse(path, tmp_path, "compile", problems)
    assert cut.version == "9.1.0" and not cut.complete
    assert cut.diagnostics[0].message == "retained"
    assert any("cannot import BEP event" in p for p in problems)
    assert any("incomplete" in p for p in problems)


def test_conflicting_events_and_missing_announcements_are_explicit(tmp_path):
    first = {"id": {"progress": {}}, "progress": {"stderr": "WARNING: first\n"}}
    second = {"id": {"progress": {}}, "progress": {"stderr": "WARNING: second\n"}}
    events = stream(first, second)
    events[0]["children"].append({"futureEvent": {"id": "absent"}})
    report, problems = read_stream(tmp_path, events)
    assert not report.complete
    assert any("conflicting duplicate" in p for p in problems)
    assert any("missing events=1" in p for p in problems)
    assert [f.message for f in report.diagnostics] == ["first"]


def test_terminal_aborted_event_is_complete_but_not_a_success(tmp_path):
    events = stream()
    events[-1].pop("finished")
    events[-1]["aborted"] = {
        "reason": "INTERNAL",
        "description": "Registry unavailable",
    }
    report, problems = read_stream(tmp_path, events)
    assert not problems and report.complete
    assert report.exit_code is None and report.status == "unknown"
    assert report.diagnostics[0].level == "error"


def test_optional_metric_groups_and_invalid_metrics_remain_reportable(tmp_path):
    report, problems = read_stream(
        tmp_path,
        stream(
            {
                "id": {"buildMetrics": {}},
                "buildMetrics": {
                    "futureCounter": 5,
                    "workerMetrics": [{"workerId": 3}],
                    "timingMetrics": {"wallTimeInMs": "123"},
                },
            }
        ),
    )
    assert not problems and "futureCounter" not in report.metrics
    assert report.metrics["workerMetrics"] == [{"workerId": 3}]
    report, problems = read_stream(
        tmp_path,
        stream({"id": {"buildMetrics": {}}, "buildMetrics": {"timingMetrics": None}}),
    )
    assert problems and not report.complete and report.metrics == {}
    root = from_summary({"job": "build"}, [])
    root.bazel = [report]
    assert "Bazel" in html.render(root)


def test_artifact_links_only_use_existing_local_file_uris(tmp_path):
    from ptk.adapters.reporting.bazel_html import artifact_link

    path = tmp_path / "test output.log"
    path.write_text("test log")
    assert 'href="test%20output.log"' in artifact_link({"uri": path.as_uri()}, tmp_path)
    for uri in (
        "bytestream://cache/blob",
        "https://example.invalid/log",
        "file://server/share",
        "javascript:alert(1)",
        (tmp_path / "absent").as_uri(),
    ):
        assert artifact_link({"uri": uri}, tmp_path) == ""


def test_size_boundary_unsafe_paths_and_malformed_events(tmp_path, monkeypatch):
    path = write_stream(tmp_path / "event.bep.json", stream())
    monkeypatch.setattr(bazel_bep, "MAX_BYTES", path.stat().st_size)
    assert bazel_bep.parse(path, tmp_path, "compile", []).complete
    with path.open("a") as handle:
        handle.write(" ")
    with pytest.raises(ValueError, match="100 MiB"):
        bazel_bep.parse(path, tmp_path, "compile", [])
    with pytest.raises(ValueError, match="recorded directory"):
        bazel_bep.parse(path, tmp_path / "elsewhere", "compile", [])
    link = tmp_path / "link.bep.json"
    try:
        link.symlink_to(path)
    except OSError:
        pytest.skip("symlinks unavailable")
    with pytest.raises(ValueError, match="recorded directory"):
        bazel_bep.parse(link, tmp_path, "compile", [])


def command(tmp_path, args=None, shell=None):
    return CommandSpec(
        argv=args
        if args is not None
        else None
        if shell
        else ["bazel", "build", "//:lib"],
        shell=shell,
        cwd=str(tmp_path),
        timeout=3,
        env={
            **os.environ,
            "PATH": "/selected/tool/bin",
            "PTK_BUILD_DIR": str(tmp_path / "build"),
            "PTK_STEP_REPORTS_DIR": str(tmp_path / "reports"),
            "PTK_STEP": "compile",
        },
    )


class FakeRunner:
    def __init__(self, body, exit_code=0):
        self.body, self.exit_code = body, exit_code
        self.calls, self.lookups = [], []

    def which(self, program, path=None):
        self.lookups.append((program, path))
        return "/selected/tool/bin/" + program

    def run(self, cmd, output, cancel=None):
        self.calls.append(cmd)
        self.body(cmd, output)
        return ProcessOutcome(self.exit_code)


def produce(events, console=()):
    def body(cmd, output):
        words, index = bazel.invocation(cmd, "linux")
        path = Path(cmd.cwd) / bazel.bep_argument(words, index)
        write_stream(path, events)
        for line in console:
            output(line)

    return body


def test_bazelisk_startup_options_run_separator_path_and_snapshot_masking(tmp_path):
    secret = 'private"with\\escapes'
    line = "WARNING: " + secret
    events = stream({"id": {"progress": {}}, "progress": {"stderr": line + "\n"}})
    runner = FakeRunner(produce(events, [line]))
    original = [
        "bazelisk",
        "--output_base",
        "build",
        "--host_jvm_args=-Xmx1g",
        "run",
        "//:app",
        "--",
        "--build_event_json_file=program-arg",
    ]
    cmd = command(tmp_path, original)
    mask = lambda text: text.replace(secret, "********")
    outcome = bazel.BazelReportingRunner(runner, "linux").run(
        cmd, lambda _: None, mask=mask, on_problem=pytest.fail
    )
    assert outcome.exit_code == 0 and cmd.argv == original
    assert len(runner.calls) == 1  # no separate --version invocation
    assert runner.lookups == [("bazelisk", "/selected/tool/bin")]
    used = runner.calls[0].argv
    assert used[:5] == original[:5] and used[-3:] == original[-3:]
    assert used[5].startswith("--build_event_json_file=")
    report = bazel.read(tmp_path / "reports", "compile")
    assert not report.problems and len(report.bazel) == 1
    assert report.bazel[0].version == "9.1.0"
    assert len(report.bazel[0].diagnostics) == 1
    assert report.bazel[0].diagnostics[0].message == "********"
    assert not list((tmp_path / "reports/.ptk-bazel").glob("*.raw-bep"))
    text = next((tmp_path / "reports/.ptk-bazel").glob("*.json")).read_text()
    assert secret not in text and json.dumps(secret)[1:-1] not in text


@pytest.mark.parametrize(
    "args",
    [
        ["bazel", "query", "//..."],
        ["bazel", "clean"],
        ["bazel", "version"],
        ["python", "bazel.py", "build"],
        ["bazel", "--unknown", "some-value", "build"],
        ["bazel", "--unknown", "build", "query", "//..."],
    ],
)
def test_unrelated_commands_are_not_instrumented(tmp_path, args):
    runner = FakeRunner(lambda cmd, output: None)
    cmd = command(tmp_path, args)
    bazel.BazelReportingRunner(runner, "linux").run(
        cmd, lambda _: None, mask=lambda s: s, on_problem=pytest.fail
    )
    assert runner.calls == [cmd] and not runner.lookups
    assert not bazel.read(tmp_path / "reports", "compile").bazel


def test_simple_shell_and_windows_command_parsing(tmp_path):
    cmd = command(tmp_path, shell='"bazel" --output_base "path with spaces" test //...')
    words, index = bazel.invocation(cmd, "linux")
    assert words[index] == "test" and words[2] == "path with spaces"
    assert (
        bazel.invocation(
            command(tmp_path, shell="bazel build //... && echo done"), "linux"
        )
        is None
    )
    cmd = command(tmp_path, [r"C:\tools\bazel.exe", "coverage", "//..."])
    assert bazel.invocation(cmd, "windows")[1] == 1


def test_explicit_bep_path_reused_once_and_historical_capture_is_immutable(tmp_path):
    path = tmp_path / "reports/custom.bep.json"
    cmd = command(
        tmp_path, ["bazel", "test", "--build_event_json_file", str(path), "//:unit"]
    )
    runner = FakeRunner(produce(stream()))
    collector = bazel.BazelReportingRunner(runner, "linux")
    collector.run(cmd, lambda _: None, mask=lambda s: s, on_problem=pytest.fail)
    assert runner.calls[0].argv == cmd.argv and path.is_file()
    assert len(bazel.read(path.parent, "compile").bazel) == 1
    path.write_text("replaced later")
    assert len(bazel.read(path.parent, "compile").bazel) == 1
    assert not bazel.read(path.parent, "compile").problems
    runner.body = produce(stream(version="8.4.0", invocation="retry-2"))
    collector.run(cmd, lambda _: None, mask=lambda s: s, on_problem=pytest.fail)
    assert [r.version for r in bazel.read(path.parent, "compile").bazel] == [
        "9.1.0",
        "8.4.0",
    ]


def test_explicit_output_parent_alias_does_not_duplicate_discovered_stream(tmp_path):
    (tmp_path / "build").mkdir()
    path = tmp_path / "build/../reports/alias.bep.json"
    cmd = command(
        tmp_path, ["bazel", "build", "--build_event_json_file=" + str(path), "//:lib"]
    )
    runner = FakeRunner(produce(stream()))
    bazel.BazelReportingRunner(runner, "linux").run(
        cmd, lambda _: None, mask=lambda s: s, on_problem=pytest.fail
    )
    result = bazel.read(tmp_path / "reports", "compile")
    assert not result.problems and len(result.bazel) == 1


def test_wrapper_changed_build_stream_and_stale_stream_are_not_confused(tmp_path):
    stale = write_stream(tmp_path / "build/stale.bep.json", stream(version="7.0.0"))
    fresh = tmp_path / "build/new.bep.jsonl"
    runner = FakeRunner(
        lambda cmd, output: write_stream(fresh, stream(version="8.4.0"))
    )
    cmd = command(tmp_path, ["build-wrapper", "test"])
    bazel.BazelReportingRunner(runner, "linux").run(
        cmd, lambda _: None, mask=lambda s: s, on_problem=pytest.fail
    )
    records = bazel.read(tmp_path / "reports", "compile")
    assert [r.version for r in records.bazel] == ["8.4.0"]
    assert stale.exists() and runner.calls == [cmd]


def test_missing_or_malformed_bep_preserves_process_outcome_and_console(tmp_path):
    def malformed(cmd, output):
        words, index = bazel.invocation(cmd, "linux")
        Path(bazel.bep_argument(words, index)).write_bytes(b"\xff")
        output("ERROR: still useful")

    runner = FakeRunner(malformed, exit_code=17)
    outcome = bazel.BazelReportingRunner(runner, "linux").run(
        command(tmp_path), lambda _: None, mask=lambda s: s, on_problem=pytest.fail
    )
    result = bazel.read(tmp_path / "reports", "compile")
    assert outcome.exit_code == 17 and result.problems
    assert result.bazel[0].diagnostics[0].message == "still useful"


def test_raw_bep_import_policy_deduplication_and_all_export_formats(tmp_path):
    reports = tmp_path / "reports"
    write_stream(
        reports / "compile/manual.bep.json",
        stream(
            {
                "id": {"progress": {}},
                "progress": {
                    "stderr": "WARNING: accepted warning\nERROR: justified defect\n"
                },
            },
            exit_code=1,
        ),
    )
    log = tmp_path / "logs/compile.log"
    log.parent.mkdir()
    log.write_text("WARNING: accepted warning\nERROR: justified defect\n")
    summary = {
        "job": "build",
        "status": "passed",
        "reports_dir": str(reports),
        "log_dir": str(log.parent),
        "steps": [
            {
                "step": "compile",
                "needs": [],
                "kind": "run",
                "status": "passed",
                "log_file": str(log),
            }
        ],
        "log_analysis": {
            "enabled": True,
            "rules": [
                {
                    "id": "ignore",
                    "match": {"message_regex": "accepted warning"},
                    "action": "ignore",
                    "reason": "Upstream issue",
                },
                {
                    "id": "justify",
                    "match": {
                        "severity": "error",
                        "step": "compile",
                        "message_regex": "justified defect",
                    },
                    "action": "justify",
                    "reason": "Reviewed exception",
                },
            ],
        },
    }
    service = ReportService(FileReportStore({}), "test")
    report = service.build(None, summary)
    assert (
        not report.has_errors and not report.log_findings and not report.test_totals()
    )
    assert len(report.bazel[0].diagnostics) == 2
    assert all(
        "Source: PTK log analysis" in f.context for f in report.bazel[0].diagnostics
    )
    assert {f.disposition for f in report.bazel[0].diagnostics} == {
        "ignored",
        "justified",
    }
    files = service.export(
        report, ["html", "json", "markdown", "junit"], tmp_path / "out"
    )
    assert {f.name for f in files} == {
        "report.html",
        "report.json",
        "report.md",
        "report.xml",
        "diagnostics.html",
    }
    page = (tmp_path / "out/diagnostics.html").read_text()
    assert page.count('class="diagnostic"') == 2
    assert 'data-source="bazel"' in page and "Reviewed exception" in page
    assert 'href="#bazel"' in (tmp_path / "out/report.html").read_text()
    data = json.loads(exporters.to_json(report))
    assert data["totals"]["bazel"]["invocations"] == 1
    assert data["totals"]["tests"] == {}
    summary["log_analysis"]["enabled"] = False
    assert not service.build(None, summary).has_errors


def test_report_markup_escapes_untrusted_bazel_strings(tmp_path):
    report, problems = read_stream(
        tmp_path,
        stream(
            {
                "id": {"progress": {}},
                "progress": {"stderr": "WARNING: <img src=x onerror=alert(1)>\n"},
            },
            version="<script>bad</script>",
        ),
    )
    assert not problems
    root = from_summary({"job": "build"}, [])
    root.bazel = [report]
    page = html.render(root)
    dedicated = diagnostics.page(
        diagnostics.collect(root, "owner"),
        name="build",
        identity="owner",
        status="passed",
        root=tmp_path,
    )
    assert "<script>bad</script>" not in page and "&lt;script&gt;bad" in page
    assert "<img src=x" not in dedicated and "&lt;img" in dedicated


@pytest.mark.parametrize("cx", [False, True])
def test_workflow_bazel_diagnostics_open_locally_and_retain_saved_policy(
    tmp_path, monkeypatch, cx
):
    from tests.workflows.test_cli import invoke, repository

    from ptk.adapters import help_html

    opened = []
    monkeypatch.setattr(
        help_html, "open_in_browser", lambda path: opened.append(path) or True
    )
    events = stream(
        {
            "id": {"progress": {}},
            "progress": {
                "stderr": "ERROR: actual defect\nWARNING: ignored warning\nWARNING: justified warning\n"
            },
        },
        {
            "id": {"testSummary": target_id()},
            "testSummary": {"overallStatus": "PASSED"},
        },
    )
    text = "".join(json.dumps(event) + "\n" for event in events)
    code = (
        "import os;from pathlib import Path;"
        "Path(os.environ['PTK_BUILD_DIR'],'current.bep.json').write_text("
        + repr(text)
        + ");"
        "Path(os.environ['PTK_STEP_REPORTS_DIR'],'tests.xml').write_text('<testsuite><testcase name=\"one\"/></testsuite>');"
        "print('ERROR: actual defect\\nWARNING: ignored warning\\nWARNING: justified warning')"
    )
    root = repository(
        tmp_path,
        jobs={
            "build": {
                "open_report": None,
                "steps": {"compile": {"run": [sys.executable, "-c", code]}},
            }
        },
        workflows={
            "verify": {"open_report": None, "jobs": {"build": {"job": "build"}}}
        },
        extra={
            "report_formats": ["html", "json"],
            "log_analysis": {
                "enabled": True,
                "rules": [
                    {
                        "id": "ignored",
                        "match": {"message_regex": "ignored warning"},
                        "action": "ignore",
                        "reason": "Tracked upstream",
                    },
                    {
                        "id": "justified",
                        "match": {"message_regex": "justified warning"},
                        "action": "justify",
                        "reason": "Reviewed behavior",
                    },
                ],
            },
        },
    )
    if cx:
        result = invoke(root, "build", env={"PTK_CI": "1"})
        assert result.exit_code == 0, result.output
        report = json.loads((root / "_reports/default/build/report.json").read_text())
        assert report["bazel"] and not opened
        assert (root / "_reports/default/build/diagnostics.html").is_file()
        return  # Workflows are local-only; CX executes their individual jobs.
    result = invoke(root, "workflow", "run", "verify")
    assert result.exit_code == 0, result.output
    summary = next(root.glob("_reports/workflows/verify/*/workflow.json"))
    workflow = json.loads(summary.read_text())
    child = workflow["children"]["build"]
    assert len(child["bazel"]) == 1 and not child["log_findings"]
    assert len(child["suites"][0]["cases"]) == 1
    assert {f["disposition"] for f in child["bazel"][0]["diagnostics"]} == {
        "active",
        "ignored",
        "justified",
    }
    page = summary.with_name("diagnostics.html").read_text()
    assert page.count('class="diagnostic"') == 3 and "Reviewed behavior" in page
    assert opened == ([] if cx else [summary.with_name("diagnostics.html")])
    assert 'id="bazel"' in summary.with_name("workflow.html").read_text()
    # Later changes to the producing build tree cannot alter the workflow snapshot.
    next(root.glob("_builds/default/build/compile/*.bep.json")).write_text("replaced")
    assert (
        json.loads(summary.read_text())["children"]["build"]["bazel"] == child["bazel"]
    )


def test_stale_explicit_output_is_not_imported_and_empty_path_is_respected(tmp_path):
    path = write_stream(tmp_path / "reports/stale.bep.json", stream(version="7.0.0"))
    runner = FakeRunner(
        lambda cmd, output: output("ERROR: startup failed"), exit_code=2
    )
    cmd = command(
        tmp_path, ["bazel", "build", "--build_event_json_file=" + str(path), "//:lib"]
    )
    bazel.BazelReportingRunner(runner, "linux").run(
        cmd, lambda _: None, mask=lambda s: s, on_problem=pytest.fail
    )
    result = bazel.read(path.parent, "compile")
    assert len(result.bazel) == 1 and result.bazel[0].version == ""
    assert any("current BEP" in p for p in result.problems)
    cmd = command(tmp_path, ["bazel", "test", "--build_event_json_file=", "//:unit"])
    cmd.env["PTK_STEP_REPORTS_DIR"] = str(tmp_path / "disabled")
    bazel.BazelReportingRunner(runner, "linux").run(
        cmd, lambda _: None, mask=lambda s: s, on_problem=pytest.fail
    )
    result = bazel.read(tmp_path / "disabled", "compile")
    assert not result.problems and "Disabled" in result.bazel[0].availability["BEP"]
    assert runner.calls[-1].argv == cmd.argv


def test_hidden_step_and_dry_run_do_not_capture_bazel(tmp_path):
    from tests.workflows.test_cli import invoke, repository

    text = "".join(json.dumps(event) + "\n" for event in stream())
    code = (
        "import os;from pathlib import Path;Path(os.environ['PTK_BUILD_DIR'],'hidden.bep.json').write_text("
        + repr(text)
        + ")"
    )
    root = repository(
        tmp_path,
        jobs={
            "build": {
                "steps": {
                    "hidden": {"report": False, "run": [sys.executable, "-c", code]}
                }
            }
        },
        extra={"report_formats": ["json"]},
    )
    preview = invoke(root, "build", "--dry-run")
    assert preview.exit_code == 0 and not list(root.rglob("*.bep.json"))
    result = invoke(root, "build", env={"PTK_CI": "1"})
    assert result.exit_code == 0, result.output
    report = json.loads((root / "_reports/default/build/report.json").read_text())
    assert not report["bazel"] and not report["steps"]


@pytest.mark.skipif(
    not os.environ.get("PTK_TEST_BAZEL"),
    reason="set PTK_TEST_BAZEL for native BEP integration",
)
def test_native_bazel_success_and_analysis_failure(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    (root / "MODULE.bazel").write_text('module(name="ptk_report_probe")\n')
    (root / "probe.bzl").write_text(
        'def _probe(ctx):\n    if ctx.attr.bad:\n        fail("Deliberate analysis failure")\n    out = ctx.actions.declare_file(ctx.label.name + ".txt")\n    ctx.actions.write(out, "ok")\n    return [DefaultInfo(files=depset([out]))]\nprobe=rule(implementation=_probe, attrs={"bad":attr.bool()})\n'
    )
    (root / "BUILD.bazel").write_text(
        'load(":probe.bzl", "probe")\nprobe(name="ok")\nprobe(name="bad", bad=True)\n'
    )
    startup = [
        os.environ["PTK_TEST_BAZEL"],
        "--batch",
        "--output_user_root=" + str(tmp_path / "cache"),
    ]
    if trust := os.environ.get("PTK_TEST_BAZEL_TRUSTSTORE"):
        startup.append("--host_jvm_args=-Djavax.net.ssl.trustStore=" + trust)
    reports = []
    for label, failed in (("ok", False), ("bad", True)):
        cmd = command(
            root,
            startup
            + [
                "build",
                "--incompatible_autoload_externally=",
                "--lockfile_mode=off",
                "//:" + label,
            ],
        )
        cmd.env["PATH"] = os.environ["PATH"]
        cmd.env["PTK_STEP_REPORTS_DIR"] = str(root / label)
        cmd.timeout = 180
        lines, problems = [], []
        outcome = ReportingRunner(SubprocessRunner(), "linux").run(
            cmd, lines.append, mask=lambda s: s, on_problem=problems.append
        )
        assert bool(outcome.exit_code) == failed, "\n".join(lines)
        result = bazel.read(root / label, "compile")
        assert not problems and not result.problems
        [report] = result.bazel
        assert report.version and report.complete
        assert bool(report.exit_code) == failed
        if failed:
            assert any(
                "Deliberate analysis failure" in f.message for f in report.diagnostics
            )
        else:
            assert (
                report.targets[0]["label"] == "//:ok"
                and report.targets[0]["status"] == "passed"
            )
        reports.append(report)
    assert reports[0].invocation_id != reports[1].invocation_id
