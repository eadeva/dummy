import json
import os
import sys
from pathlib import Path

import yaml

from ptk.application.use_cases.run import RunRequest
from ptk.bootstrap import create_app
from ptk.domain.execution.model import Status
from ptk.domain.reporting.summary import run_summary
from ptk.drivers.cli.main import cli
from tests.cli_runner import CliRunner
from tests.project_files import write_project


def project(tmp_path, steps, **job):
    file = tmp_path / ".main.ptk.yml"
    write_project(
        file,
        yaml.safe_dump(
            {
                "repository": {"alias": "demo", "config_path": "."},
                "project": {"name": "controls"},
                "jobs": {"go": {"steps": steps, **job}},
            }
        ),
    )
    app = create_app(environ=dict(os.environ))
    return file, app, app.load_project.execute(tmp_path)


def test_secret_prompt_and_path_param(tmp_path):
    file, _, _ = project(
        tmp_path,
        [
            {
                "print": {
                    "run": [
                        sys.executable,
                        "-c",
                        "import os; print(os.environ['TOKEN'])",
                    ],
                    "env": {"TOKEN": "${params.token}"},
                }
            }
        ],
        params={
            "token": {"type": "secret", "required": True},
            "output": {"type": "path", "default": "a path"},
        },
    )
    result = CliRunner().invoke(
        cli,
        ["go", "--token", "--output", "two words"],
        input="secret-value\n",
        cwd=Path(file).parent,
    )
    assert result.exit_code == 0, result.output
    assert "secret-value" not in result.output
    for path in (tmp_path / "_logs").rglob("*"):
        if path.is_file():
            assert "secret-value" not in path.read_text()
    summary = json.loads(next((tmp_path / "_logs").rglob("run.json")).read_text())
    assert summary["params"]["token"] == "********"
    assert summary["params"]["output"] == "two words"


def test_report_false_hides_descendants_but_retains_run_failure(tmp_path):
    _, app, p = project(
        tmp_path,
        [
            {
                "hidden": {
                    "report": False,
                    "steps": [
                        {"fail": {"run": [sys.executable, "-c", "raise SystemExit(1)"]}}
                    ],
                }
            }
        ],
    )
    prepared = app.prepare_run(p).execute(p, RunRequest(job="go"))
    result = app.run_job(p).execute(prepared)
    summary = run_summary(prepared.plan, result)
    assert len(summary["steps"]) == 2  # audit logs retain every step
    report = app.reports.build(p, summary)
    assert not report.steps and report.status == "failed"


def test_group_deadline_does_not_cancel_parent(tmp_path):
    _, app, p = project(
        tmp_path,
        [
            {
                "limited": {
                    "timeout": 0.1,
                    "continue_on_error": True,
                    "steps": [{"wait": {"uses": "wait", "with": {"seconds": 5}}}],
                }
            },
            {"after": {"uses": "echo"}},
        ],
    )
    prepared = app.prepare_run(p).execute(p, RunRequest(job="go"))
    result = app.run_job(p).execute(prepared)
    assert result.status is Status.PASSED
    assert result.steps[0].status is Status.FAILED
    assert result.steps[1].status is Status.PASSED
    assert result.duration < 2


def test_builtin_timeout_and_retries(tmp_path):
    _, app, p = project(
        tmp_path,
        [
            {
                "wait": {
                    "uses": "wait",
                    "timeout": 0.05,
                    "retries": 1,
                    "with": {"seconds": 5},
                }
            }
        ],
    )
    prepared = app.prepare_run(p).execute(p, RunRequest(job="go"))
    result = app.run_job(p).execute(prepared)
    assert result.steps[0].attempts == 2
    assert "timed out" in result.steps[0].message
    assert result.duration < 2


def test_group_retries_repeat_children_and_report_attempts(tmp_path):
    _, app, p = project(
        tmp_path,
        [
            {
                "retry": {
                    "retries": 1,
                    "steps": [
                        {
                            "flaky": {
                                "run": [
                                    sys.executable,
                                    "-c",
                                    "from pathlib import Path; p=Path('seen'); existed=p.exists(); p.touch(); raise SystemExit(0 if existed else 1)",
                                ]
                            }
                        }
                    ],
                }
            }
        ],
    )
    prepared = app.prepare_run(p).execute(p, RunRequest(job="go"))
    result = app.run_job(p).execute(prepared)
    assert result.status is Status.PASSED
    assert result.steps[0].attempts == 2
    assert result.steps[0].children[0].status is Status.PASSED
