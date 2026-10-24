"""End-to-end runs with real processes (Linux/macOS shell commands, Python via uv)."""

from __future__ import annotations

import os
import shutil
import sys
import threading
import time
from pathlib import Path

import pytest

from ptk.application.use_cases.run import Cancelled, RunRequest
from ptk.bootstrap import create_app
from ptk.domain.errors import PtkError
from ptk.domain.execution.model import Status

pytestmark = pytest.mark.skipif(
    sys.platform.startswith("win"), reason="uses POSIX shell commands"
)

HOST = {
    "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
    "HOME": os.environ.get("HOME", "/tmp"),
}
UV = shutil.which("uv") or (
    str(Path.home() / ".local/bin/uv")
    if (Path.home() / ".local/bin/uv").exists()
    else None
)
if UV:
    HOST["PTK_UV"] = UV
    HOST["PATH"] = str(Path(UV).parent) + os.pathsep + HOST["PATH"]

PROJECT = """
project: {name: e2e}
vars: {greeting: "hello ${project.name}"}
credentials:
  repo: {fields: [token], env: {token: REPO_TOKEN}}
actions:
  go:
    params:
      who: {default: world}
      fail: {type: bool, default: false}
    env: {ACTION_LEVEL: "a"}
    steps:
      - hello: ["${sys}", "-c", "import os; print(os.environ['GREETING'], os.environ['PTK_PARAM_WHO'])"]
      - prepare:
          run: echo "${vars.greeting}" > marker.txt; pwd
          cwd: ${run.build_dir}
          env: {GREETING: unused}
      - checks:
          parallel: true
          steps:
            - a: {run: "sleep 0.3; echo A-done"}
            - b: {run: "sleep 0.3; echo B-done"}
            - flaky: {run: "exit 3", continue_on_error: true}
            - never: {run: "echo never", when: "params.fail and os == 'windows'"}
      - script:
          run: tools/show.py --flag
          python: {interpreter: cli}
          passthrough: true
      - secret:
          run: ["${sys}", "-c", "import os; print('token is', os.environ['TOKEN'])"]
          secrets: {TOKEN: repo.token}
      - broken: {run: "exit 7", when: "params.fail"}
      - after: "echo after"
"""

SHOW = """
import os, sys
print("args", sys.argv[1:])
print("step", os.environ["PTK_STEP"], "variant", os.environ["PTK_VARIANT"])
"""


@pytest.fixture
def project(write):
    root = write(
        {
            "main.ptk.yml": PROJECT.replace("${sys}", sys.executable).replace(
                "print(os.environ['GREETING']", "print(os.environ.get('GREETING', '-')"
            ),
            "tools/show.py": SHOW,
        }
    )
    return root


def run(root: Path, environ: dict[str, str] | None = None, **request):
    env = {**HOST, "REPO_TOKEN": "s3cr3t-value", **(environ or {})}
    app = create_app(environ=env)
    project = app.load_project.execute(root)
    prepared = app.prepare_run(project).execute(
        project, RunRequest(action="go", **request)
    )
    lines: list[tuple[str, str]] = []

    class Collect:
        def run_started(self, plan):
            pass

        def step_started(self, step, command):
            pass

        def output(self, step, line):
            lines.append((step.label, line))

        def step_finished(self, step, result):
            pass

        def run_finished(self, result):
            pass

    result = app.run_action(project).execute(
        prepared, [Collect(), *app.log_observers(prepared)]
    )
    return result, lines, prepared


def by_label(result):
    return {r.label: r for r in result.walk()}


def test_full_run(project):
    result, lines, _prepared = run(project, passthrough=["--extra", "x y"])
    steps = by_label(result)
    assert result.status is Status.PASSED, [
        (r.label, r.status, r.message) for r in result.walk()
    ]
    out = {}
    for label, line in lines:
        out.setdefault(label, []).append(line)
    assert out["hello"] == ["- world"]
    build_dir = project / "_builds/default/go/prepare"
    assert (build_dir / "marker.txt").read_text().strip() == "hello e2e"
    assert out["prepare"] == [str(build_dir)]
    assert {"A-done", "B-done"} <= {line for _, line in lines}
    assert (
        steps["checks/flaky"].status is Status.FAILED
        and steps["checks/flaky"].allowed_failure
    )
    assert steps["checks"].status is Status.PASSED
    assert steps["checks/never"].status is Status.SKIPPED
    assert out["script"] == [
        "args ['--flag', '--extra', 'x y']",
        "step script variant default",
    ]
    assert out["secret"] == ["token is ********"]
    assert steps["broken"].status is Status.SKIPPED
    assert steps["after"].status is Status.PASSED
    # logs follow the layout and never contain the secret
    run_log = project / "_logs/default/go/run.log"
    assert run_log.is_file() and (project / "_logs/default/go/checks/a.log").is_file()
    text = run_log.read_text()
    assert "s3cr3t" not in text and "token is ********" in text
    assert "s3cr3t" not in steps["secret"].command
    assert (project / "_reports/default/go/checks/a").is_dir() and (
        project / "_bin/default"
    ).is_dir()


def test_parallel_steps_overlap(project):
    result, _, _ = run(project, start="checks", end="checks")
    checks = by_label(result)["checks"]
    assert checks.duration < 0.55  # two 0.3 s sleeps in parallel
    assert by_label(result)["hello"].message == "outside --from/--to range"


def test_failure_stops_following_steps(project):
    result, _, _ = run(project, params={"fail": "true"})
    steps = by_label(result)
    assert result.status is Status.FAILED
    assert steps["broken"].status is Status.FAILED and steps["broken"].exit_code == 7
    assert (
        steps["after"].status is Status.SKIPPED
        and "earlier step failed" in steps["after"].message
    )


def test_missing_secret_stops_before_anything_runs(project):
    with pytest.raises(PtkError, match="REPO_TOKEN is not set") as info:
        run(project, environ={"REPO_TOKEN": ""})
    assert "ptk creds set repo" in str(info.value)
    assert not (project / "_logs").exists()  # nothing was started


def test_secret_of_skipped_step_is_not_needed(project):
    result, _lines, _ = run(project, environ={"REPO_TOKEN": ""}, end="script")
    assert by_label(result)["secret"].status is Status.SKIPPED


def test_timeout_and_retries(write):
    root = write(
        {
            "main.ptk.yml": """
        project: {name: t}
        actions:
          go:
            steps:
              - slow: {run: "sleep 5", timeout: 0.3}
        """
        }
    )
    result, _, _ = run(root)
    slow = by_label(result)["slow"]
    assert (
        slow.status is Status.FAILED
        and "timed out" in slow.message
        and slow.duration < 3
    )

    root = write(
        {
            "main.ptk.yml": """
        project: {name: t}
        actions:
          go:
            steps:
              - flaky: {run: "test -f once || (touch once; exit 1)", retries: 2}
        """
        }
    )
    result, _lines, _ = run(root)
    flaky = by_label(result)["flaky"]
    assert flaky.status is Status.PASSED and flaky.attempts == 2


def test_cancel_kills_process_tree(write):
    root = write(
        {
            "main.ptk.yml": """
        project: {name: t}
        actions:
          go:
            steps:
              - long: {run: "sleep 30 & sleep 30; wait"}
              - next: "echo next"
        """
        }
    )
    app = create_app(environ=HOST)
    project = app.load_project.execute(root)
    prepared = app.prepare_run(project).execute(project, RunRequest(action="go"))
    cancel = Cancelled()
    threading.Timer(0.5, cancel.set).start()
    start = time.monotonic()
    result = app.run_action(project).execute(prepared, [], cancel)
    assert time.monotonic() - start < 8
    assert result.status is Status.CANCELLED
    assert by_label(result)["next"].status is Status.CANCELLED


def test_program_not_found(write):
    root = write(
        {
            "main.ptk.yml": """
        project: {name: t}
        actions:
          go:
            steps:
              - missing: [definitely-not-a-program-xyz]
        """
        }
    )
    result, _, _ = run(root)
    assert "program not found" in by_label(result)["missing"].message


def test_builtin_steps(write):
    root = write(
        {
            "main.ptk.yml": """
        project: {name: t}
        actions:
          go:
            params: {msg: {default: hi}}
            steps:
              - say: {uses: echo, with: {message: "${params.msg} there"}}
              - nope: {uses: files.cpoy}
        """
        }
    )
    result, lines, _ = run(root)
    assert ("say", "hi there") in lines
    assert "not available" in by_label(result)["nope"].message


@pytest.mark.skipif(UV is None, reason="uv not installed")
def test_python_venv_and_plain_script(write):
    root = write(
        {
            "main.ptk.yml": """
            project: {name: t}
            actions:
              go:
                steps:
                  - plain: tools/where.py
                  - in-venv:
                      run: tools/where.py
                      python: {venv: {requirements: tools/req.txt}}
                  - venv-cmd:
                      run: ["python", "-c", "import sys; print(sys.prefix)"]
                      python: {venv: {requirements: tools/req.txt}}
            """,
            "tools/where.py": "import sys, os\nprint(os.environ.get('VIRTUAL_ENV', 'none'))\n",
            "tools/req.txt": "# no packages - creating the venv must work offline\n",
        }
    )
    result, lines, _ = run(root)
    assert result.status is Status.PASSED, [(r.label, r.message) for r in result.walk()]
    venvs = list((root / ".ptk/venvs").iterdir())
    assert len(venvs) == 1  # same requirements -> same cached venv
    out = {label: line for label, line in lines if not line.startswith("ptk:")}
    assert out["in-venv"] == str(venvs[0])
    assert out["venv-cmd"] == str(venvs[0])
    # changing the requirements creates a new environment
    (root / "tools/req.txt").write_text("# changed\n")
    run(root)
    assert len(list((root / ".ptk/venvs").iterdir())) == 2


def test_dry_run_masks_secrets_and_does_not_execute(project):
    app = create_app(environ={**HOST, "REPO_TOKEN": "s3cr3t-value"})
    proj = app.load_project.execute(project)
    prepared = app.prepare_run(proj).execute(
        proj, RunRequest(action="go", dry_run=True)
    )
    runner = app.run_action(proj)
    secret_step = next(s for s in prepared.plan.walk() if s.name == "secret")
    command, _ = runner.describe(prepared, secret_step)
    assert "s3cr3t" not in command
    assert not (project / "_builds").exists() and not (project / "_logs").exists()
