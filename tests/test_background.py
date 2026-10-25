"""Background jobs overlap, join, report failures and respect cancellation."""

import os
import sys
import threading

import pytest
import yaml
from pydantic import ValidationError

from ptk.application.use_cases.run import Cancelled, RunRequest
from ptk.bootstrap import create_app
from ptk.domain.config.model import StepSpec
from ptk.domain.execution.model import Status


def execute(tmp_path, steps, cancel=None):
    (tmp_path / "main.ptk.yml").write_text(
        yaml.safe_dump(
            {"project": {"name": "background"}, "actions": {"go": {"steps": steps}}}
        )
    )
    app = create_app(environ=dict(os.environ))
    project = app.load_project.execute(tmp_path)
    prepared = app.prepare_run(project).execute(project, RunRequest(action="go"))
    return app.run_action(project).execute(prepared, cancel=cancel)


def command(code, **kwargs):
    return {"run": [sys.executable, "-c", code], "timeout": 10, **kwargs}


def test_background_overlaps_and_joins(tmp_path):
    result = execute(
        tmp_path,
        [
            {
                "worker": command(
                    "from pathlib import Path; import time; p=Path('ready'); "
                    "exec('while not p.exists(): time.sleep(0.02)'); "
                    "Path('done').write_text('yes')",
                    background=True,
                )
            },
            {"release": command("from pathlib import Path; Path('ready').touch()")},
        ],
    )
    assert result.status is Status.PASSED
    assert (tmp_path / "done").read_text() == "yes"
    assert [s.name for s in result.steps] == ["worker", "release"]
    assert all(s.status is Status.PASSED for s in result.steps)


@pytest.mark.parametrize("allowed", [False, True])
def test_background_failure_is_reported(tmp_path, allowed):
    result = execute(
        tmp_path,
        [
            {
                "worker": command(
                    "import sys; sys.exit(7)",
                    background=True,
                    continue_on_error=allowed,
                )
            },
            {"later": command("pass")},
        ],
    )
    assert result.steps[0].exit_code == 7
    assert result.status is (Status.PASSED if allowed else Status.FAILED)


def test_background_cancel(tmp_path):
    cancel = Cancelled()
    timer = threading.Timer(0.5, cancel.set)
    timer.start()
    try:
        result = execute(
            tmp_path,
            [
                {"worker": command("import time; time.sleep(30)", background=True)},
                {"foreground": command("import time; time.sleep(30)")},
            ],
            cancel,
        )
    finally:
        timer.cancel()
    assert result.status is Status.CANCELLED
    assert all(s.status is Status.CANCELLED for s in result.steps)


def test_background_requires_process():
    with pytest.raises(ValidationError, match="only allowed for run"):
        StepSpec(name="wait", uses="wait", background=True)


def test_background_joins_at_nested_boundary(tmp_path):
    result = execute(
        tmp_path,
        [
            {
                "group": {
                    "steps": [
                        {
                            "worker": command(
                                "from pathlib import Path; import time; time.sleep(0.1); Path('nested').touch()",
                                background=True,
                            )
                        },
                    ]
                }
            },
            {
                "verify": command(
                    "from pathlib import Path; assert Path('nested').exists()"
                )
            },
        ],
    )
    assert result.status is Status.PASSED
    assert result.steps[0].children[0].status is Status.PASSED


def test_background_timeout(tmp_path):
    result = execute(
        tmp_path,
        [
            {
                "worker": command(
                    "import time; time.sleep(30)", background=True, timeout=0.2
                )
            },
        ],
    )
    assert result.status is Status.FAILED
    assert "timed out" in result.steps[0].message
