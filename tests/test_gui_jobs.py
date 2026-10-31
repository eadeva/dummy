"""GUI launch receipts, preparation and real process independence."""

import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from ptk.adapters.process import SubprocessRunner
from ptk.application.use_cases.run import RunRequest
from ptk.bootstrap import create_app
from ptk.domain.config.model import JobSpec
from ptk.domain.execution.model import CommandSpec
from ptk.drivers.cli.main import cli
from tests.cli_runner import CliRunner
from tests.project_files import write_project


def configuration(tmp_path, launch=None, **job):
    entry = tmp_path / ".main.ptk.yml"
    write_project(
        entry,
        {
            "project": {"name": "gui-test"},
            "report_formats": ["html", "json"],
            "jobs": {
                "viewer": {
                    "gui": True,
                    "steps": {
                        "prepare": {
                            "run": [
                                sys.executable,
                                "-c",
                                "from pathlib import Path; Path('prepared').touch()",
                            ]
                        },
                        "open": {
                            "needs": "prepare",
                            **(
                                launch
                                or {
                                    "run": ["viewer.py", "literal argument"],
                                    "python": {"interpreter": "cli"},
                                }
                            ),
                        },
                    },
                    **job,
                }
            },
        },
    )
    return entry


def wait_for(path, timeout=5):
    deadline = time.monotonic() + timeout
    while not path.exists() and time.monotonic() < deadline:
        time.sleep(0.025)
    assert path.exists(), path


@pytest.mark.parametrize("shell", [False, True])
def test_cli_exits_and_gui_survives_with_preparation_and_python(tmp_path, shell):
    # The child stays alive until the *test*, after PTK exits, releases it.
    script = tmp_path / "viewer.py"
    script.write_text(
        """
import json, os, sys, time
from pathlib import Path
assert Path('prepared').exists()
receipt = {'pid': os.getpid(), 'args': sys.argv[1:], 'step': os.environ['PTK_STEP']}
Path('receipt.tmp').write_text(json.dumps(receipt))
Path('receipt.tmp').replace('receipt.json')
deadline = time.monotonic() + 20
while not Path('release').exists() and time.monotonic() < deadline:
    time.sleep(.025)
Path('closed').touch()
""",
        encoding="utf-8",
    )
    launch = None
    if shell:
        import shlex

        words = [sys.executable, str(script), "literal argument"]
        launch = {
            "run": subprocess.list2cmdline(words)
            if sys.platform == "win32"
            else shlex.join(words)
        }
    configuration(tmp_path, launch)
    env = {
        **os.environ,
        "PTK_CI": "0",
        "PTK_ROLE": "user",
        "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src"),
    }
    try:
        result = subprocess.run(
            [sys.executable, "-m", "ptk", "run", "viewer"],
            cwd=tmp_path,
            env=env,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert "GUI launched" in result.stdout
        wait_for(tmp_path / "receipt.json")
        assert not (tmp_path / "closed").exists()
        receipt = json.loads((tmp_path / "receipt.json").read_text())
        assert receipt["args"] == ["literal argument"]
        assert receipt["step"] == "open"
        report = json.loads(
            (tmp_path / "_reports/default/viewer/report.json").read_text()
        )
        step = next(item for item in report["steps"] if item["label"] == "open")
        assert step["launched_pid"] > 0
        assert "application exit is not monitored" in step["message"]
    finally:
        (tmp_path / "release").touch()
        if (tmp_path / "receipt.json").exists():
            wait_for(tmp_path / "closed")


def test_gui_dry_run_and_step_selection_do_not_launch(tmp_path):
    configuration(tmp_path)
    runner = CliRunner(env={"PTK_CI": "0"})
    result = runner.invoke(cli, ["run", "viewer", "--dry-run"], cwd=tmp_path)
    assert result.exit_code == 0, result.output
    assert "GUI launch: detached" in result.output
    assert not (tmp_path / "prepared").exists()
    result = runner.invoke(cli, ["run", "viewer", "--to", "prepare"], cwd=tmp_path)
    assert result.exit_code == 0, result.output
    assert (tmp_path / "prepared").exists()
    assert "GUI launched" not in result.output


def test_gui_start_failure_and_failed_preparation_are_errors(tmp_path, monkeypatch):
    monkeypatch.setattr("webbrowser.open", lambda *a, **k: True)
    configuration(tmp_path, {"run": ["ptk-nonexistent-gui-executable"]})
    result = CliRunner(env={"PTK_CI": "0"}).invoke(cli, ["run", "viewer"], cwd=tmp_path)
    assert result.exit_code != 0 and "program not found" in result.output
    configuration(
        tmp_path,
        steps={
            "prepare": {"run": [sys.executable, "-c", "raise SystemExit(7)"]},
            "open": {"needs": "prepare", "run": ["ptk-nonexistent-gui-executable"]},
        },
    )
    result = CliRunner(env={"PTK_CI": "0"}).invoke(cli, ["run", "viewer"], cwd=tmp_path)
    assert result.exit_code != 0 and "blocked by needs" in result.output
    assert "program not found" not in result.output


@pytest.mark.parametrize(
    "steps",
    [
        {"a": {"run": "one"}, "b": {"run": "two"}},
        {"a": {"uses": "echo"}},
        {"a": {"run": "one", "timeout": 1}},
        {"a": {"run": "one", "retries": 1}},
    ],
)
def test_gui_requires_unambiguous_final_command_without_lifetime_controls(steps):
    with pytest.raises(ValidationError, match="gui"):
        JobSpec(gui=True, steps=steps)
    assert JobSpec(steps=steps).gui is False


@pytest.mark.parametrize("gui", [False, True])
def test_gui_session_environment_respects_explicit_overrides(tmp_path, gui):
    configuration(
        tmp_path,
        gui=gui,
        environment={"unset": ["DISPLAY"], "set": {"WAYLAND_DISPLAY": "chosen"}},
    )
    app = create_app(
        environ={
            "DISPLAY": ":0",
            "WAYLAND_DISPLAY": "original",
            "XDG_RUNTIME_DIR": "/run/user/1000",
            "UNRELATED_SECRET": "private",
        }
    )
    project = app.load_project.execute(tmp_path)
    prepared = app.prepare_run(project).execute(
        project, RunRequest(job="viewer", dry_run=True)
    )
    assert "DISPLAY" not in prepared.plan.base_env
    assert prepared.plan.base_env["WAYLAND_DISPLAY"] == "chosen"
    assert ("XDG_RUNTIME_DIR" in prepared.plan.base_env) is gui
    assert "UNRELATED_SECRET" not in prepared.plan.base_env
    assert prepared.plan.gui_step == ("open" if gui else None)


def test_cancelled_gui_is_not_spawned(tmp_path, monkeypatch):
    cancel = threading.Event()
    cancel.set()
    monkeypatch.setattr(
        subprocess, "Popen", lambda *a, **kw: pytest.fail("spawned after cancellation")
    )
    outcome = SubprocessRunner().run(
        CommandSpec(argv=["anything"], cwd=str(tmp_path), detached=True),
        lambda _: None,
        cancel,
    )
    assert outcome.cancelled and outcome.launched_pid is None


def test_windows_gui_launch_detaches_without_hiding_window_or_using_pipes(
    tmp_path, monkeypatch
):
    from ptk.adapters import process_options

    monkeypatch.setattr(process_options, "WINDOWS", True)
    monkeypatch.setattr(subprocess, "DETACHED_PROCESS", 8, raising=False)
    monkeypatch.setattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 512, raising=False)
    launched = []
    monkeypatch.setattr(
        subprocess,
        "Popen",
        lambda args, **kw: (
            launched.append(kw) or SimpleNamespace(pid=1234, wait=lambda: 0)
        ),
    )
    outcome = SubprocessRunner().run(
        CommandSpec(argv=["viewer"], cwd=str(tmp_path), detached=True), lambda _: None
    )
    assert outcome.launched_pid == 1234 and outcome.exit_code == 0
    assert launched[0]["creationflags"] == 520
    assert "startupinfo" not in launched[0]
    assert launched[0]["close_fds"] is True
    assert all(
        launched[0][stream] == subprocess.DEVNULL
        for stream in ("stdin", "stdout", "stderr")
    )


def test_gui_inventory_keeps_job_commands_and_type(tmp_path):
    configuration(tmp_path)
    result = CliRunner(env={"PTK_CI": "0"}).invoke(
        cli, ["describe", "--json", "--configuration"], cwd=tmp_path
    )
    assert result.exit_code == 0, result.output
    doc = json.loads(result.output)
    assert doc["schema_version"] == 5
    job = doc["projects"][0]["jobs"][0]
    assert job["gui"] is True and job["command"] == ["run", "viewer"]
