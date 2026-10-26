"""Reports: importers, exporters, report.import, reports after runs, ptk report."""

from __future__ import annotations

import json
import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from click.testing import CliRunner

from ptk.adapters import help_html
from ptk.adapters.reporting import exporters, html, importers
from ptk.domain.reporting.model import from_summary
from ptk.drivers.cli.main import cli

pytestmark = pytest.mark.skipif(sys.platform.startswith("win"), reason="POSIX shell")
HOST = {
    "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
    "HOME": "/tmp",
    "PTK_ROLE": "user",
}

JUNIT = """<testsuites><testsuite name="unit">
<testcase classname="parser" name="ok" time="0.5"/>
<testcase classname="parser" name="bad"><failure message="boom &lt;x&gt;">trace</failure></testcase>
<testcase classname="io" name="skip"><skipped/></testcase>
<testcase classname="io" name="err"><error message="crash"/></testcase>
</testsuite></testsuites>"""
SARIF = {
    "runs": [
        {
            "tool": {"driver": {"name": "clang-tidy"}},
            "results": [
                {
                    "ruleId": "bugprone-x",
                    "level": "error",
                    "message": {"text": "bad thing"},
                    "locations": [
                        {
                            "physicalLocation": {
                                "artifactLocation": {"uri": "a.c"},
                                "region": {"startLine": 3},
                            }
                        }
                    ],
                },
                {"ruleId": "style-y", "message": {"text": "meh"}},
            ],
        }
    ]
}


def test_importers_scan_step_folders(tmp_path):
    step = tmp_path / "checks" / "unit"
    step.mkdir(parents=True)
    (step / "results.xml").write_text(JUNIT)
    (step / "tidy.sarif").write_text(json.dumps(SARIF))
    (step / "coverage.xml").write_text('<coverage line-rate="0.75"/>')
    (step / "broken.xml").write_text("<testsuite")
    (step / "notes.txt").write_text("ignored")
    (tmp_path / "report.xml").write_text(JUNIT)  # ptk's own output: ignored
    (tmp_path / "unknown").mkdir()
    (tmp_path / "unknown" / "x.xml").write_text(JUNIT)  # not a step folder
    [contribution] = importers.scan(
        tmp_path, importers.step_folders(["checks", "checks/unit"])
    )
    assert contribution.step == "checks/unit"
    [suite] = contribution.suites
    assert [c.status for c in suite.cases] == ["passed", "failed", "skipped", "error"]
    assert suite.cases[1].message == "boom <x>"
    assert [(f.rule, f.level, f.file, f.line) for f in contribution.findings] == [
        ("bugprone-x", "error", "a.c", 3),
        ("style-y", "warning", "", None),
    ]
    assert round(contribution.coverage[0].percent) == 75
    assert len(contribution.problems) == 1 and "broken.xml" in contribution.problems[0]


SUMMARY = {
    "project": "p",
    "job": "ci",
    "variant": "v1",
    "run_id": "r1",
    "status": "failed",
    "started_at": "2026-10-24T10:00:00+02:00",
    "duration": 10.0,
    "params": {"jobs": 4},
    "param_sources": {"jobs": "command line"},
    "steps": [
        {"step": "build", "kind": "run", "status": "passed", "start": 0, "duration": 4},
        {
            "step": "checks",
            "kind": "set",
            "status": "failed",
            "start": 4,
            "duration": 6,
        },
        {
            "step": "checks/lint",
            "kind": "run",
            "status": "failed",
            "start": 4,
            "duration": 2,
            "allowed_failure": True,
            "message": "exit code 1",
        },
        {
            "step": "checks/test",
            "kind": "run",
            "status": "failed",
            "start": 4,
            "duration": 6,
            "message": "exit code 2",
            "command": "pytest <&>",
            "log_file": "/w/_logs/v1/ci/checks/test.log",
        },
        {
            "step": "docs",
            "kind": "run",
            "status": "skipped",
            "message": "condition is false",
        },
    ],
}


def report():
    step = importers.parse_junit(ET.fromstring(JUNIT), "checks/test", "results.xml")
    from ptk.domain.reporting.model import Contribution

    return from_summary(SUMMARY, [Contribution("checks/test", suites=step)], "0.1")


def test_junit_export():
    root = ET.fromstring(exporters.to_junit(report()).split("\n", 1)[1])
    own, imported = root.findall("testsuite")
    assert (
        own.get("tests") == "4"
        and own.get("failures") == "1"
        and own.get("skipped") == "1"
    )
    lint = next(c for c in own if c.get("name") == "lint")
    assert lint.find("failure") is None and "allowed" in lint.find("system-out").text
    assert (
        imported.get("name") == "checks/test: unit" and imported.get("failures") == "1"
    )


def test_markdown_and_json_export():
    md = exporters.to_markdown(report())
    assert md.startswith("## Job - ci ❌ — failed")
    assert "| jobs | `4` | command line |" in md and "failed (allowed)" in md
    assert "**Tests:** 1 passed, 1 failed, 1 error, 1 skipped" in md
    data = json.loads(exporters.to_json(report()))
    assert data["totals"]["tests"] == {
        "passed": 1,
        "failed": 1,
        "skipped": 1,
        "error": 1,
    }


def test_html_export(tmp_path):
    page = html.render(report(), link_root=Path("/w/_reports/v1/ci"))
    assert "<h1>Job - ci</h1>" in page
    assert "<title>Job - ci failed - p</title>" in page
    assert "pytest &lt;&amp;&gt;" in page and "<&>" not in page
    assert 'href="../../../_logs/v1/ci/checks/test.log"' in page
    assert "What failed" in page and "parser.bad" in page
    assert 'class="bar allowed"' in page and "https://" not in page
    assert "1 (1 allowed)" not in page  # lint allowed, test blocking -> "2 (1 allowed)"
    assert "2 (1 allowed)" in page


# --------------------------------------------------------------------------- end to end

PROJECT = """
project: {name: rep, default_job: ci}
environment: {keep: [JUNIT]}
reporting: {formats: [json, junit, html, markdown, github]}
jobs:
  ci:
    steps:
      - unit: 'printf "%s" "$JUNIT" > "$PTK_STEP_REPORTS_DIR/results.xml"'
      - grab: {uses: report.import, with: {files: ["tools/*.sarif", "tools/*.sarif"]}}
      - none: {uses: report.import, with: {files: [nothing/*.xml], optional: true}}
"""


@pytest.fixture
def project(write, tmp_path):
    root = write({".main.ptk.yml": PROJECT, "tools/tidy.sarif": json.dumps(SARIF)})
    summary = tmp_path / "gh-summary.md"
    env = {**HOST, "JUNIT": JUNIT, "GITHUB_STEP_SUMMARY": str(summary)}

    def invoke(*args):
        base = ["--config", str(root / ".main.ptk.yml"), "--no-ci"]
        return CliRunner(env=env).invoke(cli, [*base, *args], catch_exceptions=False)

    invoke.root = root
    invoke.summary = summary
    return invoke


def test_reports_after_run(project):
    result = project()
    assert result.exit_code == 0, result.output
    out = project.root / "_reports/default/ci"
    assert {p.name for p in out.iterdir() if p.is_file()} == {
        "report.json",
        "report.xml",
        "report.html",
        "report.md",
    }
    data = json.loads((out / "report.json").read_text())
    assert data["totals"]["tests"]["failed"] == 1
    assert (
        len(data["findings"]) == 4
    )  # the same file imported twice -> tidy.sarif, tidy-2.sarif
    assert sorted(p.name for p in (out / "grab").iterdir()) == [
        "tidy-2.sarif",
        "tidy.sarif",
    ]
    assert project.summary.read_text().startswith("## Job - ci ✅")
    assert "report: " in result.output


def test_report_import_without_match_fails(write):
    root = write(
        {
            ".main.ptk.yml": """
        project: {name: x}
        jobs: {go: {steps: [{grab: {uses: report.import, with: {files: [no/*.xml]}}}]}}
        """
        }
    )
    result = CliRunner(env=HOST).invoke(
        cli, ["--config", str(root / ".main.ptk.yml"), "go"], catch_exceptions=False
    )
    assert result.exit_code == 1 and "no files matched" in result.output


def test_report_export_and_history(project, monkeypatch):
    project()
    first = json.loads((project.root / "_logs/default/ci/run.json").read_text())[
        "run_id"
    ]
    import time

    time.sleep(1.05)
    project()
    exported = project(
        "report", "export", "-f", "markdown", "-o", str(project.root / "out")
    )
    assert exported.exit_code == 0 and (project.root / "out/report.md").is_file()
    opened: list[Path] = []
    monkeypatch.setattr(
        help_html, "open_in_browser", lambda path: opened.append(path) or True
    )
    old = project("report", "open", "--run", first)
    assert old.exit_code == 0 and opened and first in str(opened[0])
    missing = project("report", "export", "--run", "19990101-000000")
    assert missing.exit_code == 2 and "kept runs" in missing.output


def test_reporting_disabled(write):
    root = write(
        {
            ".main.ptk.yml": """
        project: {name: x}
        reporting: {formats: []}
        jobs: {go: {steps: [{a: "echo hi"}]}}
        """
        }
    )
    result = CliRunner(env=HOST).invoke(
        cli, ["--config", str(root / ".main.ptk.yml"), "go"], catch_exceptions=False
    )
    assert (
        result.exit_code == 0
        and not (root / "_reports/default/go/report.html").exists()
    )
