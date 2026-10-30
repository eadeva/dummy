"""All child jobs inherit the workflow invocation's captured date."""

import json
from datetime import datetime

from tests.workflows.test_cli import invoke, repository

from ptk.bootstrap import create_app
from ptk.drivers.cli import state


def test_parallel_workflow_jobs_share_the_invocation_date(tmp_path, monkeypatch):
    instant = datetime.fromisoformat("2026-10-26T15:07:00+01:00")
    monkeypatch.setattr(state, "create_app", lambda: create_app(started_at=instant))
    job = {
        "steps": {"stamp": {"uses": "echo", "with": {"message": "${date.timestamp}"}}}
    }
    root = repository(
        tmp_path,
        jobs={"one": job, "two": job},
        workflows={
            "verify": {
                "open_report": None,
                "jobs": {"a": {"job": "one"}, "b": {"job": "two"}},
            }
        },
    )
    result = invoke(root, "verify")
    assert result.exit_code == 0, result.output
    reports = list(root.glob("_reports/workflows/verify/*/jobs/*/report.json"))
    assert len(reports) == 2
    for report in reports:
        date = json.loads(report.read_text())["context"]["date"]
        assert date["timestamp"] == "2026_10_26_1507"
        assert date["utc"]["timestamp"] == "2026_10_26_1407"
