"""Automatic report opening follows job policy without changing run outcomes."""

import sys

import pytest
import yaml
from pydantic import ValidationError

from ptk.adapters import help_html
from ptk.adapters.reporting.store import FileReportStore
from ptk.domain.config.model import JobSpec
from ptk.domain.reporting.model import Contribution, Finding, from_summary
from ptk.drivers.cli.main import cli
from tests.cli_runner import CliRunner
from tests.project_files import project_files


@pytest.fixture
def invoke(write, monkeypatch):
    opened = []

    def open_browser(path):
        assert path.is_file()
        assert "</html>" in path.read_text(encoding="utf-8")
        opened.append(path)
        return True

    monkeypatch.setattr(help_html, "open_in_browser", open_browser)

    def run(
        policy=None,
        *,
        fail=False,
        ci=False,
        dry=False,
        imported_failure=False,
        all_variants=False,
        formats=None,
    ):
        code = "import sys; sys.exit(1)" if fail else "print('ok')"
        if imported_failure:
            code = (
                "import os; from pathlib import Path; "
                "Path(os.environ['PTK_STEP_REPORTS_DIR'], 'tests.xml').write_text("
                "'<testsuite><testcase name=\"bad\"><failure/></testcase></testsuite>')"
            )
        job = {"steps": {"check": {"run": [sys.executable, "-c", code]}}}
        if policy is not None:
            job["open_report"] = policy
        config = {
            "project": {"name": "report-open"},
            "report_formats": ["json"] if formats is None else formats,
            "jobs": {"check": job},
        }
        if all_variants:
            config["variants"] = {"default": "one", "variants": {"one": {}, "two": {}}}
        root = write(project_files(yaml.safe_dump(config)))
        args = []
        args.append("check")
        if dry:
            args.append("--dry-run")
        if all_variants:
            args.append("--all-variants")
        env = {
            "PTK_CI": "" if ci == "auto" else "1" if ci else "0",
            "GITHUB_ACTIONS": "true" if ci == "auto" else "false",
        }
        result = CliRunner(env=env).invoke(cli, args, catch_exceptions=False, cwd=root)
        return result, opened, root

    return run


@pytest.mark.parametrize(
    "policy,fail,ci,dry,expected",
    [
        (None, False, False, False, False),
        (None, True, False, False, False),
        ("always", False, False, False, True),
        ("always", True, False, False, True),
        ("on_errors", False, False, False, False),
        ("on_errors", True, False, False, True),
        ("always", False, True, False, False),
        ("on_errors", True, True, False, False),
        ("always", False, "auto", False, False),
        ("always", False, False, True, False),
    ],
)
def test_open_policy(invoke, policy, fail, ci, dry, expected):
    result, opened, root = invoke(policy, fail=fail, ci=ci, dry=dry)
    assert result.exit_code == (1 if fail and not dry else 0), result.output
    assert bool(opened) == expected
    if ci or dry or policy is None:
        assert not list(root.rglob("report.html"))


def test_imported_test_failure_opens_even_when_command_passes(invoke):
    result, opened, _ = invoke("on_errors", imported_failure=True)
    assert result.exit_code == 0, result.output
    assert len(opened) == 1


def test_each_variant_and_html_with_empty_formats(invoke):
    result, opened, _ = invoke("always", all_variants=True, formats=[])
    assert result.exit_code == 0, result.output
    assert len(opened) == 2
    assert {p.parent.parent.name for p in opened} == {"one", "two"}


@pytest.mark.parametrize("raises", [False, True])
def test_browser_unavailable_does_not_change_result(invoke, monkeypatch, raises):
    def unavailable(path):
        if raises:
            raise OSError("no desktop")
        return False

    monkeypatch.setattr(help_html, "open_in_browser", unavailable)
    result, _, root = invoke("always", fail=True)
    assert result.exit_code == 1
    assert "no browser available" in result.output
    assert list(root.rglob("report.html"))


def test_report_generation_failure_does_not_open_stale_file(
    invoke, monkeypatch, tmp_path
):
    stale = tmp_path / "_reports" / "default" / "check" / "report.html"
    stale.parent.mkdir(parents=True)
    stale.write_text("stale", encoding="utf-8")

    def fail_write(*args, **kwargs):
        raise OSError("cannot write")

    monkeypatch.setattr(FileReportStore, "write", fail_write)
    result, opened, _ = invoke("always")
    assert result.exit_code == 0
    assert "report not written" in result.output
    assert opened == []


@pytest.mark.parametrize(
    "status,level,problem,step_status,expected",
    [
        ("passed", "warning", "", "passed", False),
        ("cancelled", "note", "", "cancelled", False),
        ("skipped", "note", "", "skipped", False),
        ("passed", "error", "", "passed", True),
        ("passed", "note", "unreadable junit", "passed", True),
        ("passed", "note", "", "failed", True),
    ],
)
def test_report_error_conditions(status, level, problem, step_status, expected):
    report = from_summary(
        {
            "status": status,
            "steps": [
                {
                    "step": "check",
                    "status": step_status,
                    "allowed_failure": True,
                    "kind": "run",
                    "needs": [],
                }
            ],
        },
        [
            Contribution(
                "check",
                findings=[Finding("lint", "R1", level, "finding")],
                problems=[problem] if problem else [],
            )
        ],
    )
    assert report.has_errors is expected


def test_invalid_open_report_is_rejected():
    with pytest.raises(ValidationError):
        JobSpec.model_validate(
            {"open_report": "sometimes", "steps": {"hello": {"run": "echo hello"}}}
        )


def test_explicit_job_report_handles_missing_runs_without_hiding_errors(
    write, monkeypatch
):
    root = write(
        project_files(
            """\
project:
  name: report-open
variants:
  default: small
  variants:
    small: {}
    large: {}
layout:
  reports: custom-reports
report_formats: []
jobs:
  build:
    steps:
      hello:
        uses: echo
        with:
          message: hello
"""
        )
    )
    opened = []
    monkeypatch.setattr(
        help_html, "open_in_browser", lambda path: opened.append(path) or True
    )
    runner = CliRunner(env={"PTK_CI": "0", "PTK_ROLE": "user"})
    base = []

    def invoke(*args):
        return runner.invoke(cli, [*base, *args], catch_exceptions=False, cwd=root)

    missing = invoke("-V", "small", "report", "open", "--if-exists", "build")
    assert missing.exit_code == 0 and "Info:" in missing.output
    assert "hasn't run yet" in missing.output
    assert opened == [] and not (root / "custom-reports").exists()
    assert invoke("report", "open", "build").exit_code != 0
    assert invoke("report", "open", "--if-exists", "unknown").exit_code != 0
    assert (
        invoke("-V", "unknown", "report", "open", "--if-exists", "build").exit_code != 0
    )
    assert invoke("-V", "small", "run", "build").exit_code == 0
    assert (
        invoke("-V", "large", "report", "open", "--if-exists", "build").exit_code == 0
    )
    assert opened == []
    assert (
        invoke("-V", "small", "report", "open", "--if-exists", "build").exit_code == 0
    )
    assert opened == [root / "custom-reports/small/build/report.html"]
    assert "</html>" in opened[0].read_text(encoding="utf-8")
    summary = root / "_logs/small/build/run.json"
    summary.write_text("not json", encoding="utf-8")
    malformed = runner.invoke(
        cli, [*base, "report", "open", "--if-exists", "build"], cwd=root
    )
    assert malformed.exit_code != 0 and "hasn't run yet" not in malformed.output
