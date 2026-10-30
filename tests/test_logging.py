"""Unified logging: levels, run.log / step logs, events.jsonl, run.json, history."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import pytest

from ptk.adapters.logging.files import rotate
from ptk.application.use_cases.run import RunRequest
from ptk.bootstrap import create_app
from ptk.domain.logging import (
    Level,
    console_level,
    file_level,
    history_name,
    runs_to_prune,
)
from ptk.drivers.cli.main import cli
from tests.cli_runner import CliRunner
from tests.project_files import project_files

pytestmark = pytest.mark.skipif(sys.platform.startswith("win"), reason="POSIX shell")

HOST = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": "/tmp"}

PROJECT = """\
project:
  name: logs
  default_job: go
logging_history_backups: KEEP
credentials:
  repo:
    fields:
    - token
jobs:
  go:
    params:
      who:
        default: me
    steps:
      hello:
        run: echo hi $TOKEN
        secrets:
          TOKEN: repo.token
      a:
        run: echo A
        needs:
        - hello
      b:
        run: exit 3
        continue_on_error: true
        needs:
        - hello
      flaky:
        run: test -f .once || (touch .once; exit 2)
        retries: 1
        needs:
        - a
        - b
"""


def project(write, keep=3):
    text = PROJECT.replace("KEEP", str(keep))
    return write(project_files(text))


def run(root: Path, token: str = "t0ps3cret", verbose=0):
    (root / ".once").unlink(missing_ok=True)
    app = create_app(environ={**HOST, "PTK_CRED_REPO_TOKEN": token})
    proj = app.load_project.execute(root)
    prepared = app.prepare_run(proj).execute(proj, RunRequest())
    return app.run_job(proj).execute(
        prepared, app.log_observers(prepared, verbose=verbose)
    )


LOGS = Path("_logs/default/go")


# --------------------------------------------------------------------------- domain


def test_levels():
    assert console_level("info") is Level.INFO
    assert console_level("info", verbose=1) is Level.DEBUG
    assert console_level("warning", verbose=2) is Level.TRACE
    assert console_level("debug", quiet=True) is Level.WARNING
    assert file_level("info") is Level.DEBUG and file_level("trace") is Level.TRACE
    with pytest.raises(ValueError, match="use trace, debug"):
        console_level("loud")


def test_history_rules():
    assert runs_to_prune(["3", "1", "2"], keep=2) == ["1"]
    assert runs_to_prune(["1"], keep=0) == ["1"]
    assert history_name("r1", ["r1", "r1-2"]) == "r1-3"


def test_rotate_without_summary_cleans_leftovers(tmp_path):
    (tmp_path / "old.log").write_text("x")
    rotate(tmp_path, keep=5)
    assert list(tmp_path.iterdir()) == []


# --------------------------------------------------------------------------- files


def test_logs_events_and_summary(write):
    root = project(write)
    result = run(root)
    folder = root / LOGS
    assert result.ok
    names = {p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file()}
    assert names == {
        "run.log",
        "run.json",
        "events.jsonl",
        "hello.log",
        "a.log",
        "b.log",
        "flaky.log",
    }
    events = [
        json.loads(line) for line in (folder / "events.jsonl").read_text().splitlines()
    ]
    assert events[0]["event"] == "run_started" and events[-1]["event"] == "run_finished"
    assert events[0]["param_sources"] == {"who": "default"}
    finished = {e["step"]: e for e in events if e["event"] == "step_finished"}
    assert finished["b"]["allowed_failure"] is True and finished["b"]["exit_code"] == 3
    assert finished["flaky"]["attempts"] == 2
    warnings = [e["text"] for e in events if e.get("level") == "warning"]
    assert "exit code 2 - retry 1/1" in warnings
    summary = json.loads((folder / "run.json").read_text())
    assert summary["status"] == "passed" and summary["params"] == {"who": "me"}
    assert [s["step"] for s in summary["steps"]] == [
        "hello",
        "a",
        "b",
        "flaky",
    ]
    # debug details are in the files, trace (full environment) is not at level info
    run_log = (folder / "run.log").read_text()
    assert "debug: cwd" in run_log and "trace:" not in run_log
    assert "[a] A" in run_log
    # the secret is nowhere
    for file in folder.rglob("*"):
        if file.is_file():
            assert "t0ps3cret" not in file.read_text(), file


def test_trace_level_logs_masked_environment(write):
    root = project(write)
    run(root, verbose=2)
    text = (root / LOGS / "hello.log").read_text()
    assert "trace: env TOKEN=********" in text and "trace: env PTK_STEP=hello" in text


def test_history_is_kept_and_pruned(write):
    root = project(write, keep=2)
    ids = []
    for _ in range(4):
        ids.append(run(root).run_id)
        time.sleep(1.05)  # run ids have second resolution
    history = root / LOGS / "_history"
    assert sorted(p.name for p in history.iterdir()) == ids[1:3]
    assert json.loads((root / LOGS / "run.json").read_text())["run_id"] == ids[3]
    assert (history / ids[2] / "a.log").is_file()


def test_keep_history_zero_keeps_only_latest(write):
    root = project(write, keep=0)
    run(root)
    run(root)
    assert not (root / LOGS / "_history").exists()
    assert (root / LOGS / "run.log").is_file()


def test_short_secret_is_not_masked_but_warned(write):
    root = project(write)
    run(root, token="ab")
    events = (root / LOGS / "events.jsonl").read_text()
    assert "cannot be masked" in events


# --------------------------------------------------------------------------- console


def test_console_verbosity(write):
    root = project(write)
    args = []
    env = {**HOST, "PTK_CRED_REPO_TOKEN": "t0ps3cret"}
    normal = CliRunner(env={"PTK_CI": "0", **env}).invoke(
        cli, [*args, "run"], catch_exceptions=False, cwd=root
    )
    assert "debug:" not in normal.output and "warning: exit code 2" in normal.output
    assert "  A" in normal.output or "[a] A" in normal.output
    (root / ".once").unlink(missing_ok=True)
    verbose = CliRunner(env={"PTK_CI": "0", **env}).invoke(
        cli, ["-v", *args, "run"], catch_exceptions=False, cwd=root
    )
    assert "debug: cwd" in verbose.output and "t0ps3cret" not in verbose.output
    (root / ".once").unlink(missing_ok=True)
    quiet = CliRunner(env={"PTK_CI": "0", **env}).invoke(
        cli, [*args, "run", "-q"], catch_exceptions=False, cwd=root
    )
    assert "[a] A" not in quiet.output and "warning:" in quiet.output
