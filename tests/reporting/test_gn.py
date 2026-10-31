"""Native GN generation, configured targets, warnings and shared report policy."""

import json
import os
import shutil
from dataclasses import asdict
from pathlib import Path

import pytest

from ptk.adapters.process import SubprocessRunner
from ptk.adapters.reporting import exporters, gn, html
from ptk.adapters.reporting.runner import ReportingRunner
from ptk.adapters.reporting.store import FileReportStore
from ptk.application.ports import ProcessOutcome
from ptk.application.use_cases.report import ReportService
from ptk.domain.execution.model import CommandSpec


def project(root):
    return {
        "build_settings": {
            "root_path": str(root),
            "build_dir": "//build/",
            "default_toolchain": "//:tc",
            "gen_input_files": ["//BUILD.gn"],
        },
        "targets": {
            "//:app": {
                "type": "executable",
                "toolchain": "//:tc",
                "deps": ["//:left", "//:core", "//:core(//:host)"],
                "sources": ["main.cc"],
                "defines": ["SECRET=hidden"],
            },
            "//:left": {"type": "group", "toolchain": "//:tc", "deps": ["//:core"]},
            "//:core": {"type": "static_library", "toolchain": "//:tc", "deps": []},
            "//:core(//:host)": {
                "type": "source_set",
                "toolchain": "//:host",
                "testonly": True,
                "deps": [],
            },
        },
        "toolchains": {"//:tc": {"cc": {"command": "secret compiler command"}}},
    }


def command(root, args=None, shell=None):
    (root / ".gn").touch()
    return CommandSpec(
        argv=None if shell else (args or ["gn", "gen", "build"]),
        shell=shell,
        cwd=str(root),
        timeout=2,
        env={
            **os.environ,
            "PATH": "/selected/bin",
            "PTK_BUILD_DIR": str(root / "build"),
            "PTK_STEP_REPORTS_DIR": str(root / "reports"),
            "PTK_STEP": "configure",
        },
    )


class FakeGN:
    def __init__(
        self, *, code=0, supported=True, lines=(), write=True, transform=lambda d: d
    ):
        self.code, self.supported, self.lines, self.write, self.transform = (
            code,
            supported,
            lines,
            write,
            transform,
        )
        self.calls, self.lookups = [], []

    def which(self, program, path=None):
        self.lookups.append((program, path))
        return "/selected/bin/gn"

    def run(self, cmd, output, cancel=None):
        self.calls.append(cmd)
        if cmd.argv[-1:] == ["--version"]:
            output("2614 (test-version)")
            return ProcessOutcome(0)
        if cmd.argv[-2:] == ["help", "gen"]:
            output('--json-file-name=<name> "json"' if self.supported else "Old GN")
            return ProcessOutcome(0)
        if self.code == 0 and self.write and cmd.argv and "--ide=json" in cmd.argv:
            _, values, _, build = gn.invocation(cmd, "linux")
            name = values.get("--json-file-name", ["project.json"])[-1]
            path = build / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(self.transform(project(Path(cmd.cwd)))))
        for line in self.lines:
            output(line)
        return ProcessOutcome(self.code)


def capture(root, runner, **kwargs):
    cmd = command(root, **kwargs)
    original = asdict(cmd)
    output, problems = [], []
    outcome = gn.GNReportingRunner(runner, "linux").run(
        cmd,
        output.append,
        mask=lambda s: s.replace("private-token", "***"),
        on_problem=problems.append,
    )
    assert asdict(cmd) == original
    assert not problems
    return outcome, gn.read(root / "reports", "configure"), output


def test_direct_uses_native_json_stable_regeneration_path_and_actual_child_path(
    tmp_path,
):
    runner = FakeGN(
        lines=[
            "WARNING at //BUILD.gn:7:2: useful warning",
            "source context",
            "Done. Made 4 targets",
        ]
    )
    outcome, result, _ = capture(tmp_path, runner)
    assert not result.problems and outcome.exit_code == 0
    assert outcome.reporting_duration >= 0
    assert runner.lookups == [("gn", "/selected/bin")]
    assert len(runner.calls) == 3
    assert runner.calls[-1].argv == [
        "gn",
        "gen",
        "build",
        "--ide=json",
        "--json-file-name=" + gn.GENERATED,
    ]
    [record] = result.gn
    assert record.version == "2614 (test-version)" and record.status == "passed"
    assert len(record.targets) == len(record.graph["nodes"]) == 4
    assert next(n for n in record.graph["nodes"] if n["id"] == "//:left")["needs"] == [
        "//:core"
    ]
    assert all(n["status"] == "configured" for n in record.graph["nodes"])
    assert "main.cc" not in json.dumps(
        record.graph
    ) and "secret compiler" not in json.dumps(asdict(record))
    assert (
        record.diagnostics[0].file == "//BUILD.gn" and record.diagnostics[0].line == 7
    )
    assert record.diagnostics[0].context[-1] == "source context"
    assert (tmp_path / "build" / gn.GENERATED).is_file()
    shutil.rmtree(tmp_path / "build")
    assert asdict(gn.read(tmp_path / "reports", "configure")) == asdict(result)


@pytest.mark.parametrize(
    "options",
    [
        ["--ide=vs2022"],
        ["--json-ide-script=hook.py"],
        ["--json-file-name=custom.json"],
        ["--json-ide-script-args=foo"],
    ],
)
def test_existing_ide_or_dormant_json_script_options_are_not_activated(
    tmp_path, options
):
    args = ["gn", "gen", "build", *options]
    runner = FakeGN()
    _, result, _ = capture(tmp_path, runner, args=args)
    assert len(runner.calls) == 2 and runner.calls[-1].argv == args
    assert (
        not result.gn[0].graph
        and "preserved" in result.gn[0].availability["target graph"]
    )


def test_explicit_json_path_and_identical_native_output_are_reused_without_duplication(
    tmp_path,
):
    args = [
        "gn",
        "gen",
        "reports",
        "--ide=json",
        "--json-file-name=custom.gn-project.json",
    ]
    runner = FakeGN()
    _, first, _ = capture(tmp_path, runner, args=args)
    assert not first.problems and len(first.gn) == 1
    path = tmp_path / "reports/custom.gn-project.json"
    before = path.read_bytes(), path.stat().st_mtime_ns
    runner = FakeGN(write=False)
    _, second, _ = capture(tmp_path, runner, args=args)
    assert len(second.gn) == 2 and all(r.targets for r in second.gn)
    assert (path.read_bytes(), path.stat().st_mtime_ns) == before
    assert runner.calls[-1].argv == args


def test_failed_generation_keeps_diagnostics_and_rejects_previous_graph(tmp_path):
    capture(tmp_path, FakeGN())
    outcome, result, _ = capture(
        tmp_path,
        FakeGN(
            code=7,
            lines=[
                "ERROR at //BUILD.gn:9:1: invalid graph",
                "bad statement",
                "See //BUILDCONFIG.gn:2:1: from here",
            ],
        ),
    )
    assert outcome.exit_code == 7 and len(result.gn) == 2
    failed = next(r for r in result.gn if r.status == "failed")
    assert not failed.targets and not failed.graph
    assert failed.diagnostics[0].message.startswith("invalid graph\nbad statement")
    assert "previous JSON is not reused" in failed.availability["target graph"]


def test_capability_failure_keeps_original_command_and_console(tmp_path):
    runner = FakeGN(supported=False, lines=["WARNING Old capability"])
    _, result, _ = capture(tmp_path, runner)
    assert runner.calls[-1].argv == ["gn", "gen", "build"]
    assert result.gn[0].diagnostics[0].message == "Old capability"
    assert not result.gn[0].graph


def test_json_masking_and_snapshot_limits(tmp_path, monkeypatch):
    def change(data):
        data["targets"]["//:core"]["type"] = "private-token"
        return data

    _, result, _ = capture(
        tmp_path, FakeGN(transform=change, lines=["WARNING private-token"])
    )
    raw = next((tmp_path / "reports" / gn.SNAPSHOT).glob("*.json")).read_text()
    assert "private-token" not in raw and "***" in raw
    assert not result.problems
    monkeypatch.setattr(gn, "MAX_BYTES", 3)
    assert gn.read(tmp_path / "reports", "configure").problems


def test_manual_project_log_policy_dedup_and_full_dedicated_exports(tmp_path):
    folder = tmp_path / "reports/configure"
    folder.mkdir(parents=True)
    (folder / "capture.gn-project.json").write_text(json.dumps(project(tmp_path)))
    lines = "WARNING at //BUILD.gn:2:1: accepted warning\nERROR at //BUILD.gn:3:1: justified defect\n"
    (folder / "capture.gn.log").write_text(lines)
    log = tmp_path / "configure.log"
    log.write_text(lines)
    summary = {
        "job": "gen",
        "status": "passed",
        "reports_dir": str(folder.parent),
        "log_dir": str(tmp_path),
        "steps": [
            {
                "step": "configure",
                "kind": "run",
                "needs": [],
                "status": "passed",
                "log_file": str(log),
            }
        ],
        "log_analysis": {
            "enabled": True,
            "rules": [
                {
                    "id": "known",
                    "match": {"message_regex": "accepted warning"},
                    "action": "ignore",
                    "reason": "upstream",
                },
                {
                    "id": "reviewed",
                    "match": {"severity": "error", "message_regex": "justified defect"},
                    "action": "justify",
                    "reason": "reviewed exception",
                },
            ],
        },
    }
    service = ReportService(FileReportStore({}), "test")
    record = service.build(None, summary)
    assert len(record.gn) == 1 and not record.problems and not record.log_findings
    assert not record.has_errors and not record.test_totals()
    assert {f.disposition for f in record.gn[0].diagnostics} == {"ignored", "justified"}
    assert all(
        "Source: PTK log analysis" in f.context for f in record.gn[0].diagnostics
    )
    files = service.export(
        record, ["html", "json", "markdown", "junit"], tmp_path / "out"
    )
    assert {p.name for p in files} == {
        "report.html",
        "report.json",
        "report.md",
        "report.xml",
        "diagnostics.html",
    }
    dedicated = (tmp_path / "out/diagnostics.html").read_text()
    assert (
        dedicated.count('data-source="gn"') == 2 and "reviewed exception" in dedicated
    )
    assert '<section id="gn">' in html.render(record)
    assert json.loads(exporters.to_json(record))["totals"]["gn"]["targets"] == 4
    assert "GN" in exporters.to_markdown(record)
    summary["log_analysis"]["enabled"] = False
    assert not service.build(None, summary).has_errors


def test_raw_log_only_warning_error_context_and_repetition(tmp_path):
    (tmp_path / "failed.gn.log").write_text(
        "ERROR at //BUILD.gn:4:2 (//:host): cannot load\ncontext\nERROR at //BUILD.gn:4:2 (//:host): cannot load\ncontext\nWARNING warning without location\n"
    )
    [record] = gn.read(tmp_path, "gen").gn
    assert len(record.diagnostics) == 2
    assert (
        record.diagnostics[0].occurrences == 2
        and record.diagnostics[0].file == "//BUILD.gn"
    )
    assert not record.version and not record.graph


def test_same_header_with_different_explanations_stays_distinct(tmp_path):
    (tmp_path / "args.gn.log").write_text(
        'WARNING at command-line:1:3: Build argument has no effect.\na=true\n  ^---\nThe variable "a" was set.\nWARNING at command-line:1:10: Build argument has no effect.\nb=true\n  ^---\nThe variable "b" was set.\n'
    )
    [record] = gn.read(tmp_path, "gen").gn
    assert len(record.diagnostics) == 2
    assert 'variable "a"' in record.diagnostics[0].message
    assert 'variable "b"' in record.diagnostics[1].message


def test_bounded_file_accepts_exact_limit_and_rejects_overflow(tmp_path, monkeypatch):
    monkeypatch.setattr(gn, "MAX_BYTES", 16)
    path = tmp_path / "input"
    path.write_bytes(b"a" * 16)
    assert len(gn.bounded_text(path, tmp_path)) == 16
    path.write_bytes(b"a" * 17)
    with pytest.raises(ValueError, match="exceeds"):
        gn.bounded_text(path, tmp_path)


def test_default_project_name_pairs_log_and_keeps_graph_if_log_is_unsafe(tmp_path):
    (tmp_path / "project.json").write_text(json.dumps(project(tmp_path)))
    path = tmp_path / "project.gn.log"
    path.write_text("WARNING useful diagnostic\n")
    result = gn.read(tmp_path, "generate")
    assert (
        len(result.gn) == 1
        and result.gn[0].diagnostics[0].message == "useful diagnostic"
    )
    path.unlink()
    outside = tmp_path.parent / "outside.gn.log"
    outside.write_text("ERROR unsafe\n")
    path.symlink_to(outside)
    result = gn.read(tmp_path, "generate")
    assert len(result.gn) == 1 and result.gn[0].graph and len(result.problems) == 1
    assert not result.gn[0].diagnostics


@pytest.mark.skipif(
    not os.environ.get("PTK_TEST_GN"),
    reason="set PTK_TEST_GN for native workflow integration",
)
@pytest.mark.parametrize("cx", [False, True])
def test_native_workflow_policy_dedicated_opening_and_retained_graph(
    tmp_path, monkeypatch, cx
):
    from tests.workflows.test_cli import invoke, repository

    from ptk.adapters import help_html

    opened = []
    monkeypatch.setattr(
        help_html, "open_in_browser", lambda path: opened.append(path) or True
    )
    root = repository(
        tmp_path,
        jobs={
            "generate": {
                "open_report": None,
                "steps": {
                    "gen": {
                        "run": [os.environ["PTK_TEST_GN"], "gen", "${run.build_dir}"]
                    }
                },
            }
        },
        workflows={
            "verify": {"open_report": None, "jobs": {"generate": {"job": "generate"}}}
        },
        extra={
            "report_formats": ["html", "json"],
            "log_analysis": {
                "enabled": True,
                "rules": [
                    {
                        "id": "known",
                        "match": {"message_regex": "ignored warning"},
                        "action": "ignore",
                        "reason": "upstream",
                    },
                    {
                        "id": "accepted",
                        "match": {"message_regex": "justified warning"},
                        "action": "justify",
                        "reason": "reviewed",
                    },
                ],
            },
        },
    )
    (root / ".gn").write_text('buildconfig = "//BUILDCONFIG.gn"\n')
    (root / "BUILDCONFIG.gn").write_text('set_default_toolchain("//:tc")\n')
    (root / "BUILD.gn").write_text(
        'toolchain("tc") { tool("stamp") { command = "touch {{output}}" } }\ngroup("app") {}\nprint("ERROR active defect")\nprint("WARNING ignored warning")\nprint("WARNING justified warning")\n'
    )
    if cx:
        result = invoke(root, "generate", env={"PTK_CI": "1"})
        assert result.exit_code == 0, result.output
        report = json.loads(
            (root / "_reports/default/generate/report.json").read_text()
        )
        assert len(report["gn"]) == 1 and not report["log_findings"]
        assert (
            root / "_reports/default/generate/diagnostics.html"
        ).is_file() and not opened
    else:
        result = invoke(root, "workflow", "run", "verify")
        assert result.exit_code == 0, result.output
        path = next(root.glob("_reports/workflows/verify/*/workflow.json"))
        child = json.loads(path.read_text())["children"]["generate"]
        assert len(child["gn"]) == 1 and not child["log_findings"]
        assert {f["disposition"] for f in child["gn"][0]["diagnostics"]} == {
            "active",
            "ignored",
            "justified",
        }
        assert opened == [path.with_name("diagnostics.html")]
        assert (
            path.with_name("diagnostics.html").read_text().count('data-source="gn"')
            == 3
        )
        assert 'id="gn"' in path.with_name("workflow.html").read_text()
        next(root.glob("_builds/default/generate/gen/" + gn.GENERATED)).write_text(
            "changed"
        )
        assert json.loads(path.read_text())["children"]["generate"]["gn"] == child["gn"]
    opened.clear()
    with (root / "BUILD.gn").open("a") as handle:
        handle.write('assert(false, "actual generation defect")\n')
    failed = invoke(root, "generate", env={"PTK_CI": "1" if cx else "0"})
    assert failed.exit_code != 0
    report = json.loads((root / "_reports/default/generate/report.json").read_text())
    assert not report["log_findings"] and not report["gn"][0]["graph"]
    assert any(
        "actual generation defect" in f["message"]
        for f in report["gn"][0]["diagnostics"]
    )
    assert opened == (
        [] if cx else [root / "_reports/default/generate/diagnostics.html"]
    )


@pytest.mark.skipif(
    not os.environ.get("PTK_TEST_GN"),
    reason="set PTK_TEST_GN for native visibility integration",
)
def test_native_hidden_step_and_dry_run_do_not_instrument(tmp_path):
    from tests.workflows.test_cli import invoke, repository

    root = repository(
        tmp_path,
        jobs={
            "generate": {
                "steps": {
                    "gen": {
                        "report": False,
                        "run": [os.environ["PTK_TEST_GN"], "gen", "${run.build_dir}"],
                    }
                }
            }
        },
        extra={"report_formats": ["json"]},
    )
    (root / ".gn").write_text('buildconfig = "//BUILDCONFIG.gn"\n')
    (root / "BUILDCONFIG.gn").write_text('set_default_toolchain("//:tc")\n')
    (root / "BUILD.gn").write_text(
        'toolchain("tc") { tool("stamp") { command = "touch {{output}}" } }\ngroup("app") {}\n'
    )
    assert invoke(root, "generate", "--dry-run").exit_code == 0
    assert not list(root.rglob("build.ninja"))
    result = invoke(root, "generate")
    assert result.exit_code == 0, result.output
    assert not list(root.rglob(gn.GENERATED)) and not list(root.rglob(gn.SNAPSHOT))
    assert (
        json.loads((root / "_reports/default/generate/report.json").read_text())["gn"]
        == []
    )


@pytest.mark.parametrize(
    "mutation",
    [
        lambda d: d.update(targets=[]),
        lambda d: d["targets"]["//:app"].update(deps="bad"),
        lambda d: d["targets"]["//:core"].update(deps=["//:app"]),
    ],
)
def test_malformed_and_cyclic_native_data_has_collection_diagnostics(
    tmp_path, mutation
):
    data = project(tmp_path)
    mutation(data)
    (tmp_path / "bad.gn-project.json").write_text(json.dumps(data))
    assert gn.read(tmp_path, "gen").problems


def test_filtered_dependencies_are_explicit_and_large_graphs_bounded(
    tmp_path, monkeypatch
):
    data = project(tmp_path)
    data["targets"].pop("//:core")
    path = tmp_path / "filtered.gn-project.json"
    path.write_text(json.dumps(data))
    [record] = gn.read(tmp_path, "gen").gn
    assert (
        next(n for n in record.graph["nodes"] if n["id"] == "//:core")["status"]
        == "unavailable"
    )
    monkeypatch.setattr(gn, "MAX_GRAPH_TARGETS", 3)
    [record] = gn.read(tmp_path, "gen").gn
    assert (
        not record.graph
        and len(record.targets) == 3
        and "exceeds 3" in record.availability["target graph"]
    )


def test_symlinks_and_unknown_commands_are_not_instrumented(tmp_path):
    outside = tmp_path.parent / "gn-outside.json"
    outside.write_text(json.dumps(project(tmp_path)))
    (tmp_path / "bad.gn-project.json").symlink_to(outside)
    assert gn.read(tmp_path, "gen").problems
    for args in (
        ["gn", "check", "build"],
        ["gn", "desc", "build", "*"],
        ["gn", "gen", "build", "--help"],
        ["gn", "--version"],
    ):
        assert gn.invocation(command(tmp_path, args=args), "linux") is None
    assert (
        gn.invocation(command(tmp_path, shell="gn gen build && ninja"), "linux") is None
    )


def test_wrapper_only_captures_changed_gn_named_outputs(tmp_path):
    build = tmp_path / "build"
    build.mkdir()
    stale = build / "old.gn-project.json"
    stale.write_text(json.dumps(project(tmp_path)))

    class Wrapper(FakeGN):
        def run(self, cmd, output, cancel=None):
            self.calls.append(cmd)
            (build / "new.gn-project.json").write_text(json.dumps(project(tmp_path)))
            (build / "project.json").write_text('{"unrelated":"tool"}')
            return ProcessOutcome(0)

    runner = Wrapper()
    _, result, _ = capture(tmp_path, runner, args=["wrapper"])
    assert len(runner.calls) == 1 and len(result.gn) == 1 and not result.problems
    assert (
        result.gn[0].source.endswith("new.gn-project.json") and not result.gn[0].version
    )


@pytest.mark.skipif(
    not os.environ.get("PTK_TEST_GN"),
    reason="set PTK_TEST_GN for native GN integration",
)
def test_native_generation_shared_targets_warnings_and_failed_regeneration(tmp_path):
    (tmp_path / ".gn").write_text('buildconfig = "//BUILDCONFIG.gn"\n')
    (tmp_path / "BUILDCONFIG.gn").write_text('set_default_toolchain("//:tc")\n')
    (
        tmp_path / "BUILD.gn"
    ).write_text("""toolchain("tc") { tool("stamp") { command = "touch {{output}}" } }
group("core") {}
group("left") { public_deps = [ ":core" ] }
group("data") {}
group("app") { deps = [ ":left", ":core" ] data_deps = [ ":data" ] }
""")
    cmd = command(
        tmp_path, [os.environ["PTK_TEST_GN"], "gen", "build", "--args=unknown_arg=true"]
    )
    cmd.env["PATH"] = os.environ["PATH"]
    runner = ReportingRunner(SubprocessRunner(), "linux")
    for failed in (False, True):
        if failed:
            with (tmp_path / "BUILD.gn").open("a") as handle:
                handle.write('assert(false, "deliberate GN failure")\n')
        outcome = runner.run(
            cmd, lambda line: None, mask=lambda s: s, on_problem=pytest.fail
        )
        record = gn.read(tmp_path / "reports", "configure").gn[-1]
        assert bool(outcome.exit_code) == failed
        assert record.version and record.status == ("failed" if failed else "passed")
        if failed:
            assert not record.graph and any(
                "deliberate GN failure" in f.message for f in record.diagnostics
            )
        else:
            assert any(f.level == "warning" for f in record.diagnostics)
            nodes = {n["id"]: n for n in record.graph["nodes"]}
            assert len(nodes) == 4 and nodes["//:app"]["needs"] == [
                "//:core",
                "//:data",
                "//:left",
            ]
            assert nodes["//:left"]["needs"] == ["//:core"]
            ninja = (tmp_path / "build/build.ninja").read_text()
            assert (
                "--ide=json" in ninja
                and gn.GENERATED in ninja
                and "reports" not in ninja
            )
