"""Real captured logs, policy snapshots, independent dispositions and safe exports."""

import json
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError
from tests.cli_runner import CliRunner
from tests.project_files import read_project, write_project

from ptk.adapters.logging.files import rotate
from ptk.adapters.reporting import exporters, html
from ptk.adapters.reporting.log_analysis import analyze
from ptk.adapters.workflow_files import snapshot_logs
from ptk.bootstrap import create_app
from ptk.domain.config.model import LogAnalysisSpec, PtkConfig
from ptk.domain.reporting.log_analysis import diagnostic
from ptk.domain.reporting.model import from_summary
from ptk.drivers.cli.main import cli


@pytest.mark.parametrize(
    "line,level,file,number",
    [
        ("src/main.cpp:42:3: error: undefined reference", "error", "src/main.cpp", 42),
        (
            r"C:\src\main.cpp(19,2): warning C4996: old SDK",
            "warning",
            r"C:\src\main.cpp",
            19,
        ),
        (
            "CMake Warning at CMakeLists.txt:8 (message): deprecated SDK",
            "warning",
            "CMakeLists.txt",
            8,
        ),
        ("\x1b[31mERROR: bad input\x1b[0m", "error", "", None),
        ("[WARN] no cache", "warning", "", None),
        ("ValueError: invalid number", "error", "", None),
        (
            "FAILED tests/test_api.py::test_request[default]",
            "error",
            "tests/test_api.py",
            None,
        ),
        (
            r"ERROR tests\test_api.py::test_request - ValueError: missing",
            "error",
            r"tests\test_api.py",
            None,
        ),
        (
            "ERROR tests/test_api.py - ImportError: missing dependency",
            "error",
            "tests/test_api.py",
            None,
        ),
    ],
)
def test_diagnostic_formats(line, level, file, number):
    item = diagnostic(line)
    assert (item["level"], item["file"], item["line"]) == (level, file, number)


@pytest.mark.parametrize(
    "line",
    [
        "0 errors, 0 warnings",
        "error_count=0",
        "echo ERROR: test",
        '12:00:01 ptk: $ echo "ERROR: test"',
        "This documentation explains error handling",
        "E           AssertionError: expected 3",
        "FAILED is a possible test status",
        "======= 7 failed, 788 passed, 62 skipped =======",
    ],
)
def test_non_diagnostics_are_not_findings(line):
    assert diagnostic(line) is None


def make_summary(tmp_path):
    log = tmp_path / "compile.log"
    log.write_text(
        "12:00:00 ptk: $ compiler\nhello\nsrc/a.cpp:9: warning: SDK function foo is deprecated\nsrc/a.cpp:9: warning: SDK function foo is deprecated\nERROR: <script>alert(1)</script>\nERROR: expected invalid input\n0 errors\n"
    )
    return {
        "project": "demo",
        "job": "build",
        "variant": "debug",
        "status": "passed",
        "log_dir": str(tmp_path),
        "log_analysis": {
            "enabled": True,
            "rules": [
                {
                    "id": "sdk",
                    "match": {
                        "step": "compile",
                        "severity": "warning",
                        "message_regex": "^SDK function",
                    },
                    "action": "justify",
                    "reason": "Waiting for SDK <upgrade>",
                },
                {
                    "id": "negative",
                    "match": {
                        "severity": "error",
                        "message_regex": "^expected invalid input$",
                    },
                    "action": "ignore",
                    "reason": "Negative test",
                },
            ],
        },
        "steps": [
            {
                "step": "compile",
                "status": "passed",
                "log_file": str(log),
                "kind": "run",
                "needs": [],
            }
        ],
    }


def test_rules_grouping_context_and_escaped_exports(tmp_path):
    summary = make_summary(tmp_path)
    result = analyze(summary)
    assert result.problems == []
    assert [(f.disposition, f.occurrences) for f in result.log_findings] == [
        ("justified", 2),
        ("active", 1),
        ("ignored", 1),
    ]
    justified = result.log_findings[0]
    assert (
        justified.log_lines == [3, 4]
        and justified.reason == "Waiting for SDK <upgrade>"
    )
    assert justified.context[0] == "1: 12:00:00 ptk: $ compiler"
    report = from_summary(summary, [result])
    report.log_analysis_enabled = True
    assert report.has_errors and report.ok
    page = html.render(report, link_root=tmp_path / "reports")
    assert "<script>alert(1)</script>" not in page
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page
    assert 'data-disposition="ignored"' in page and 'value="active" selected' in page
    assert "../compile.log" in page and "Log analysis" in page
    assert "Waiting for SDK &lt;upgrade&gt;" in page
    assert json.loads(exporters.to_json(report))["log_findings"][0]["occurrences"] == 2
    assert "| warning | justified | compile |" in exporters.to_markdown(report)
    assert "Negative test" in exporters.to_markdown(report)


def test_suppression_does_not_change_execution_or_test_failure(tmp_path):
    summary = make_summary(tmp_path)
    summary["log_analysis"]["rules"] = [
        {
            "id": "all",
            "match": {"message_regex": "."},
            "action": "justify",
            "reason": "Explicit test policy",
        }
    ]
    report = from_summary(summary, [analyze(summary)])
    assert not report.has_errors and report.ok
    summary["status"] = "failed"
    report = from_summary(summary, [analyze(summary)])
    assert report.has_errors and not report.ok


def test_hidden_steps_external_symlinks_and_size_limit(tmp_path, monkeypatch):
    from ptk.adapters.reporting import log_analysis

    summary = make_summary(tmp_path)
    summary["steps"][0]["report"] = False
    assert not analyze(summary).log_findings
    summary["steps"][0]["report"] = True
    monkeypatch.setattr(log_analysis, "MAX_BYTES", 10)
    assert "limit" in analyze(summary).problems[0]
    monkeypatch.setattr(log_analysis, "MAX_BYTES", 100000)
    summary["log_dir"] = str(tmp_path / "other")
    assert "outside" in analyze(summary).problems[0]
    summary["log_dir"] = str(tmp_path)
    alias = tmp_path / "alias.log"
    try:
        alias.symlink_to(tmp_path / "compile.log")
    except OSError:
        return
    summary["steps"][0]["log_file"] = str(alias)
    assert "symlink" in analyze(summary).problems[0]


def test_history_and_workflow_snapshots_keep_logs_and_policy(tmp_path):
    folder = tmp_path / "logs"
    folder.mkdir()
    summary = make_summary(folder)
    summary["run_id"] = "old-run"
    (folder / "run.json").write_text(json.dumps(summary))
    rotate(folder, 3)
    archived = json.loads((folder / "_history/old-run/run.json").read_text())
    assert analyze(archived).log_findings[0].occurrences == 2
    assert Path(analyze(archived).log_findings[0].source_log).parent == (
        folder / "_history/old-run"
    )
    copied = snapshot_logs(archived, tmp_path / "workflow")
    assert not analyze(copied).problems
    assert analyze(copied).log_findings[0].reason == "Waiting for SDK <upgrade>"


@pytest.mark.parametrize(
    "policy",
    [
        {
            "rules": [
                {
                    "id": "a",
                    "match": {"message_regex": "["},
                    "action": "ignore",
                    "reason": "test",
                }
            ]
        },
        {
            "rules": [
                {
                    "id": "a",
                    "match": {"message_regex": "."},
                    "action": "ignore",
                    "reason": " ",
                }
            ]
        },
        {
            "rules": [
                {
                    "id": "a",
                    "match": {"message_regex": "."},
                    "action": "ignore",
                    "reason": "test",
                }
            ]
            * 2
        },
    ],
)
def test_bad_policies_rejected(policy):
    with pytest.raises(ValidationError):
        LogAnalysisSpec.model_validate(policy)


def test_defaults_removed_fields_and_real_job_history(tmp_path):
    entry = tmp_path / ".main.ptk.yml"
    write_project(
        entry,
        {
            "project": {"name": "demo"},
            "jobs": {
                "build": {
                    "steps": {
                        "compile": {
                            "run": [
                                sys.executable,
                                "-c",
                                "print('WARNING: SDK is deprecated')",
                            ]
                        }
                    }
                }
            },
            "log_analysis": {
                "rules": [
                    {
                        "id": "sdk",
                        "match": {"message_regex": "^SDK"},
                        "action": "justify",
                        "reason": "Upgrade pending",
                    }
                ]
            },
        },
    )
    runner = CliRunner(env={"PTK_CI": "0", "PTK_ROLE": "user"})
    result = runner.invoke(cli, ["build"], cwd=tmp_path)
    assert result.exit_code == 0, result.output
    report_dir = tmp_path / "_reports/default/build"
    assert (report_dir / "report.html").is_file() and not (
        report_dir / "report.json"
    ).exists()
    app = create_app(environ={"PTK_ROLE": "user"})
    project = app.load_project.execute(tmp_path)
    assert project.config.logging_history_backups == 3
    summary = app.reports.latest(project, "build", None)
    project.config.log_analysis.rules = []
    report = app.reports.build(project, summary)
    assert report.log_findings[0].disposition == "justified"
    result = runner.invoke(
        cli, ["report", "export", "build", "-f", "json"], cwd=tmp_path
    )
    assert result.exit_code == 0, result.output
    assert (
        json.loads((report_dir / "report.json").read_text())["log_findings"][0][
            "reason"
        ]
        == "Upgrade pending"
    )
    for key in ("logging", "reporting"):
        model = read_project(entry)
        model[key] = {}
        with pytest.raises(ValidationError):
            PtkConfig.model_validate(model)


def test_rule_order_step_scope_and_multiline_headers(tmp_path):
    summary = make_summary(tmp_path)
    Path(summary["steps"][0]["log_file"]).write_text(
        "CMake Warning at CMakeLists.txt:8 (message):\n  SDK function old_api is deprecated\n\nWARNING: other warning\n"
    )
    summary["log_analysis"]["rules"].insert(
        0,
        {
            "id": "first",
            "match": {"step": "comp*", "message_regex": "SDK function"},
            "action": "ignore",
            "reason": "First rule wins",
        },
    )
    result = analyze(summary)
    assert result.log_findings[0].suppression_rule == "first"
    assert "SDK function" in result.log_findings[0].message
    assert result.log_findings[1].disposition == "active"
    summary["steps"][0]["step"] = "other-step"
    assert all(f.disposition == "active" for f in analyze(summary).log_findings)
    summary["log_analysis"]["enabled"] = False
    assert analyze(summary).log_findings == []


@pytest.mark.parametrize("enabled", [True, False])
def test_test_failures_and_log_diagnostics_share_section_without_changing_counts(
    tmp_path, enabled
):
    entry = tmp_path / ".main.ptk.yml"
    write_project(entry, {"project": {"name": "tests"}})
    app = create_app(environ={"PTK_ROLE": "user"})
    project = app.load_project.execute(tmp_path)
    summary = make_summary(tmp_path)
    summary["log_analysis"] = {"enabled": enabled, "rules": []}
    summary["status"] = summary["steps"][0]["status"] = "failed"
    summary["steps"][0]["message"] = "exit code 1"
    summary["reports_dir"] = str(tmp_path / "results")
    folder = tmp_path / "results/compile"
    folder.mkdir(parents=True)
    (folder / "tests.xml").write_text(
        '<testsuite name="unit"><testcase classname="tests.test_api" name="test_request">'
        "<failure>AssertionError: &lt;expected&gt;</failure>"
        "</testcase></testsuite>"
    )
    Path(summary["steps"][0]["log_file"]).write_text(
        "E           AssertionError: &lt;expected&gt;\n"
        "================ short test summary info ================\n"
        "FAILED tests/test_api.py::test_request - AssertionError: <expected>\n"
        "================ 1 failed in 0.12s ================\n"
    )
    report = app.reports.build(project, summary)
    assert report.test_totals() == {"failed": 1}
    assert len(report.log_findings) == int(enabled)
    if enabled:
        finding = report.log_findings[0]
        assert finding.rule == "pytest.failed"
        assert (
            finding.message
            == "tests/test_api.py::test_request: AssertionError: <expected>"
        )
        assert finding.log_line == 3 and finding.occurrences == 1
    page = html.render(report)
    assert page.count("<h2>What failed</h2>") == 1
    section = page.split("<h2>What failed</h2>", 1)[1].split("</section>", 1)[0]
    assert "tests.test_api.test_request" in section
    assert "AssertionError: &lt;expected&gt;" in section
    assert ("<summary>Log analysis</summary>" in section) == enabled
    assert 'class="log-analysis" open' not in section
    assert "No active errors or warnings" not in page
    assert json.loads(exporters.to_json(report))["totals"]["tests"] == {"failed": 1}


def test_failed_run_with_unrecognized_output_does_not_claim_no_errors(tmp_path):
    summary = make_summary(tmp_path)
    summary["status"] = summary["steps"][0]["status"] = "failed"
    Path(summary["steps"][0]["log_file"]).write_text("Something went wrong\n")
    report = from_summary(summary, [analyze(summary)])
    report.log_analysis_enabled = True
    page = html.render(report)
    assert "<h2>What failed</h2>" in page
    assert "No recognized active log diagnostics" in page
    assert "No active errors or warnings" not in page
    assert not report.log_findings and report.has_errors
