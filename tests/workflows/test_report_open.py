"""Workflow report policies include child failures and keep execution exit codes."""

import sys

import pytest
import yaml
from click.testing import CliRunner
from pydantic import ValidationError

from ptk.adapters import help_html
from ptk.application.use_cases.workflow import RunWorkflow, WorkflowResult
from ptk.domain.execution.model import Status
from ptk.domain.workflows import WorkflowSpec
from ptk.drivers.cli import workflows
from ptk.drivers.cli.main import cli


@pytest.fixture
def invoke(write):
    def run(
        policy="default",
        *,
        outcome="passed",
        mode="run",
        ci=False,
        invalid=False,
        child_policy=None,
    ):
        code = (
            "raise SystemExit(1)"
            if outcome in {"failed", "tolerated"}
            else "print('ok')"
        )
        if outcome == "imported":
            code = (
                "import os; from pathlib import Path; "
                "Path(os.environ['PTK_STEP_REPORTS_DIR'], 'tests.xml').write_text("
                "'<testsuite><testcase name=\"bad\"><failure/></testcase></testsuite>')"
            )
        call = {"job": "missing" if invalid else "check"}
        workflow = {
            "steps": [
                {
                    "group": {
                        "steps": [{"check": call}],
                        "continue_on_error": outcome == "tolerated",
                    }
                }
            ]
        }
        if policy != "default":
            workflow["open_report"] = policy
        root = write(
            {
                ".main.ptk.yml": yaml.safe_dump(
                    {
                        "project": {"name": "report-open"},
                        "jobs": {
                            "check": {
                                "open_report": child_policy,
                                "steps": [
                                    {"run": {"run": [sys.executable, "-c", code]}}
                                ],
                            }
                        },
                    }
                ),
                "workflow.ptk.yml": yaml.safe_dump({"workflows": {"verify": workflow}}),
            }
        )
        env = {
            "PTK_ROLE": "user",
            "PTK_CI": "" if ci == "auto" else "0",
            "GITHUB_ACTIONS": "true" if ci == "auto" else "false",
        }
        result = CliRunner(env=env).invoke(
            cli,
            [
                "-c",
                str(root / ".main.ptk.yml"),
                *(["--ci"] if ci is True else []),
                "workflow",
                mode,
                "verify",
            ],
            catch_exceptions=False,
        )
        return result, root

    return run


@pytest.mark.parametrize(
    "policy,outcome,expected",
    [
        ("default", "passed", True),
        ("always", "passed", True),
        ("always", "failed", True),
        ("on-errors", "passed", False),
        ("on-errors", "failed", True),
        ("on-errors", "tolerated", True),
        ("on-errors", "imported", True),
        (None, "failed", False),
    ],
)
def test_workflow_opens_its_aggregate_report(
    invoke, opened_reports, policy, outcome, expected
):
    result, _ = invoke(policy, outcome=outcome)
    assert result.exit_code == (1 if outcome == "failed" else 0), result.output
    assert len(opened_reports) == int(expected)
    assert all(path.name == "workflow.html" for path in opened_reports)


@pytest.mark.parametrize("ci", [False, True, "auto"])
def test_preview_and_cx_never_open_reports(invoke, opened_reports, ci):
    preview, root = invoke(mode="dry-run", ci=ci)
    assert preview.exit_code == 0, preview.output
    assert not list(root.rglob("workflow.html"))
    if ci:
        result, _ = invoke(ci=ci)
        assert result.exit_code == 2 and "locally only" in result.output
    assert opened_reports == []


def test_preflight_failure_has_no_report_to_open(invoke, opened_reports):
    result, _ = invoke(invalid=True)
    assert result.exit_code == 2
    assert opened_reports == []


@pytest.mark.parametrize("raises", [False, True])
def test_browser_unavailable_preserves_failure_exit_code(invoke, monkeypatch, raises):
    def unavailable(path):
        if raises:
            raise OSError("no desktop")
        return False

    monkeypatch.setattr(help_html, "open_in_browser", unavailable)
    result, _ = invoke(outcome="failed")
    assert result.exit_code == 1
    assert "no browser available" in result.output


def test_failed_aggregate_report_write_does_not_open_a_file(
    invoke, monkeypatch, opened_reports
):
    def fail_write(*args):
        raise OSError("cannot write report")

    monkeypatch.setattr(workflows, "write_workflow_report", fail_write)
    result, _ = invoke()
    assert result.exit_code == 0
    assert "workflow report not written" in result.output
    assert opened_reports == []


@pytest.mark.parametrize("policy,expected", [("always", True), ("on-errors", False)])
def test_cancellation_alone_is_not_an_error(
    invoke, monkeypatch, opened_reports, policy, expected
):
    monkeypatch.setattr(
        RunWorkflow,
        "execute",
        lambda *args: WorkflowResult("verify", Status.CANCELLED, 0, []),
    )
    result, _ = invoke(policy)
    assert result.exit_code == 130
    assert bool(opened_reports) is expected


def test_invalid_workflow_report_policy_is_rejected():
    with pytest.raises(ValidationError):
        WorkflowSpec(open_report="sometimes", steps=[{"check": "check"}])


@pytest.mark.parametrize(
    "policy,outcome,expected",
    [
        ("always", "passed", "workflow.html"),
        ("on-errors", "failed", "workflow.html"),
        ("on-errors", "passed", "report.html"),
        (None, "passed", "report.html"),
    ],
)
def test_workflow_opening_suppresses_child_openings(
    invoke, opened_reports, policy, outcome, expected
):
    result, _ = invoke(policy, outcome=outcome, child_policy="always")
    assert result.exit_code == (1 if outcome == "failed" else 0), result.output
    assert len(opened_reports) == 1
    assert opened_reports[0].name == expected
    if expected == "report.html":
        assert "jobs" in opened_reports[0].parts
