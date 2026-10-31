"""All importer findings share dispositions and a local-only diagnostics view."""

import json
import sys

import pytest
from tests.project_files import read_project, write_project
from tests.reporting.test_sphinx import write_exports
from tests.workflows.test_cli import repository

from ptk.adapters import help_html
from ptk.adapters.reporting import exporters
from ptk.adapters.reporting.store import FileReportStore
from ptk.application.use_cases.report import ReportService


def evidence(root):
    folder = root / "reports/check"
    folder.mkdir(parents=True)
    (folder / "test.xml").write_text(
        '<testsuite name="tests"><testcase name="test_accept"><failure message="accepted test defect"/></testcase></testsuite>'
    )
    (folder / "lint.sarif").write_text(
        json.dumps(
            {
                "runs": [
                    {
                        "tool": {"driver": {"name": "lint"}},
                        "results": [
                            {
                                "ruleId": "R1",
                                "level": "error",
                                "message": {"text": "accepted lint defect"},
                            },
                            {
                                "level": "warning",
                                "message": {"text": "review this warning"},
                            },
                        ],
                    }
                ]
            }
        )
    )
    from ptk.adapters.reporting import sphinx

    write_exports(root / "build")
    sphinx.capture(root / "build", folder, "check", "passed")
    return folder.parent


def test_all_importers_share_retained_rules_and_dedicated_output(tmp_path):
    reports = evidence(tmp_path)
    summary = {
        "job": "build",
        "status": "passed",
        "reports_dir": str(reports),
        "steps": [{"step": "check", "needs": [], "kind": "run", "status": "passed"}],
        "log_analysis": {
            "enabled": False,
            "rules": [
                {
                    "id": "accepted",
                    "match": {
                        "severity": "error",
                        "message_regex": "accepted|Status violates",
                    },
                    "action": "justify",
                    "reason": "Reviewed for this delivery",
                }
            ],
        },
    }
    service = ReportService(FileReportStore({}), "test")
    report = service.build(None, summary)
    assert not report.has_errors
    assert report.suites[0].cases[0].disposition == "justified"
    assert report.findings[0].disposition == "justified"
    assert report.sphinx[0].violations[0].disposition == "justified"
    assert report.test_totals()["failed"] == 1  # Actual test outcomes are unchanged.
    files = service.export(report, ["html", "json"], tmp_path / "out")
    assert {p.name for p in files} == {"report.html", "report.json", "diagnostics.html"}
    page = (tmp_path / "out/diagnostics.html").read_text()
    for source in ("test", "static", "sphinx"):
        assert f'data-source="{source}"' in page
    assert page.count('data-disposition="justified"') == 3
    assert "Reviewed for this delivery" in page and "Open full report" in page
    assert 'href="#r-step' not in page  # no broken execution links in dedicated view
    data = json.loads(exporters.to_json(report))
    assert data["suites"][0]["cases"][0]["status"] == "failed"
    # No dependence on today's project configuration when exporting saved evidence.
    (tmp_path / "out/report.html").unlink()
    service.export(report, [], tmp_path / "only")
    assert (tmp_path / "only/diagnostics.html").is_file()
    assert "Open full report" not in (tmp_path / "only/diagnostics.html").read_text()


@pytest.mark.parametrize(
    "ci,suppressed,level,expected",
    [
        (False, False, "error", True),
        (True, False, "error", False),
        (False, True, "error", False),
        (False, False, "warning", False),
    ],
)
def test_diagnostics_open_on_active_errors_even_without_full_formats(
    tmp_path, monkeypatch, ci, suppressed, level, expected
):
    opened = []
    monkeypatch.setattr(
        help_html, "open_in_browser", lambda path: opened.append(path) or True
    )
    data = {
        "runs": [
            {
                "tool": {"driver": {"name": "lint"}},
                "results": [
                    {"level": level, "message": {"text": "Known imported issue"}}
                ],
            }
        ]
    }
    code = (
        "import os;from pathlib import Path;Path(os.environ['PTK_STEP_REPORTS_DIR'],'lint.sarif').write_text("
        + repr(json.dumps(data))
        + ")"
    )
    root = repository(
        tmp_path,
        jobs={"build": {"steps": {"check": {"run": [sys.executable, "-c", code]}}}},
        extra={"report_formats": []},
    )
    if suppressed:
        config = read_project(root / ".main.ptk.yml")
        config["log_analysis"] = {
            "rules": [
                {
                    "id": "known",
                    "match": {"message_regex": "Known imported issue"},
                    "action": "ignore",
                    "reason": "Tracked separately",
                }
            ]
        }
        write_project(root / ".main.ptk.yml", config)
    from tests.cli_runner import CliRunner

    from ptk.drivers.cli.main import cli

    result = CliRunner(env={"PTK_CI": "1" if ci else "0"}).invoke(
        cli, ["build"], catch_exceptions=False, cwd=root
    )
    assert result.exit_code == 0, result.output
    assert bool(opened) == expected
    path = root / "_reports/default/build/diagnostics.html"
    assert path.is_file()
    if expected:
        assert opened == [path]
    assert not (path.parent / "report.html").exists()
