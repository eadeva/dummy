"""Observable failures found in the full-project review."""

import json
import os
import signal
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from ptk.adapters.credentials.vault import Vault
from ptk.adapters.process import SubprocessRunner
from ptk.application.use_cases.project import ExportSchema
from ptk.bootstrap import create_app
from ptk.domain.errors import ConfigError
from ptk.domain.execution.model import CommandSpec
from ptk.drivers.cli.main import cli
from tests.cli_runner import CliRunner
from tests.project_files import project_files, write_project


def test_vault_updates_from_two_clients_preserve_both(tmp_path):
    path = tmp_path / "vault.json"
    one = Vault(path, lambda _: "test-password")
    one.set("initial", "value")
    two = Vault(path, lambda _: "test-password")
    two.entries()
    one.set("one", "first")
    two.set("two", "second")
    assert Vault(path, lambda _: "test-password").entries() == {
        "initial": "value",
        "one": "first",
        "two": "second",
    }
    one.remove("initial")
    assert Vault(path, lambda _: "test-password").entries() == {
        "one": "first",
        "two": "second",
    }


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX process groups")
def test_term_resistant_descendant_is_killed(tmp_path, monkeypatch):
    from ptk.adapters import process

    monkeypatch.setattr(process, "GRACE_SECONDS", 0.2)
    pidfile = tmp_path / "pid"
    heartbeat = tmp_path / "heartbeat"
    child = f"import os,signal,time; from pathlib import Path; signal.signal(signal.SIGTERM,signal.SIG_IGN); Path({str(pidfile)!r}).write_text(str(os.getpid()))\nwhile True:\n Path({str(heartbeat)!r}).write_text(str(time.monotonic()))\n time.sleep(0.02)"
    parent = f"import subprocess,sys,time; subprocess.Popen([sys.executable,'-c',{child!r}],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); time.sleep(30)"
    result = SubprocessRunner().run(
        CommandSpec(
            argv=[sys.executable, "-c", parent],
            cwd=str(tmp_path),
            env=dict(os.environ),
            timeout=1,
        ),
        lambda _: None,
    )
    assert result.timed_out
    pid = int(pidfile.read_text())
    # Use progress rather than /proc status: an orphan can remain a zombie.
    import contextlib
    import time

    time.sleep(0.1)
    before = heartbeat.read_text()
    time.sleep(0.2)
    if heartbeat.read_text() != before:
        with contextlib.suppress(ProcessLookupError):
            os.kill(pid, signal.SIGKILL)
        pytest.fail("descendant continued working after timeout")


def test_report_inputs_are_fresh_and_history_is_immutable(tmp_path):
    script = tmp_path / "emit.py"
    script.write_text(
        'import os,sys\nfrom pathlib import Path\nif sys.argv[1] != "none":\n Path(os.environ["PTK_STEP_REPORTS_DIR"],"test.xml").write_text("<testsuite><testcase name=\\""+sys.argv[1]+"\\"/></testsuite>")'
    )
    main = tmp_path / ".main.ptk.yml"
    write_project(
        main,
        yaml.safe_dump(
            {
                "repository": {"alias": "demo", "config_path": "."},
                "project": {"name": "demo"},
                "report_formats": ["json"],
                "jobs": {
                    "go": {
                        "params": {"name": {"default": "first-test"}},
                        "steps": {
                            "test": {
                                "run": [sys.executable, str(script), "${params.name}"]
                            }
                        },
                    }
                },
            }
        ),
    )
    runner = CliRunner()
    base = []
    assert runner.invoke(cli, [*base, "go"], cwd=Path(main).parent).exit_code == 0
    first_id = json.loads((tmp_path / "_logs/default/go/run.json").read_text())[
        "run_id"
    ]
    assert (
        runner.invoke(
            cli, [*base, "go", "--name", "none"], cwd=Path(main).parent
        ).exit_code
        == 0
    )
    report = tmp_path / "_reports/default/go/report.json"
    assert "first-test" not in report.read_text()
    assert (
        runner.invoke(
            cli, [*base, "go", "--name", "second-test"], cwd=Path(main).parent
        ).exit_code
        == 0
    )
    result = runner.invoke(
        cli,
        [*base, "report", "export", "go", "--run", first_id, "-f", "json"],
        cwd=Path(main).parent,
    )
    assert result.exit_code == 0, result.output
    assert "second-test" not in report.read_text()
    assert "first-test" in report.read_text()


def test_requirement_redefinition_is_a_conflict(write, load):
    root = write(
        project_files(
            """\
project:
  name: demo
tools:
  ninja:
    version: '>=1'
jobs:
  go:
    requires_tools:
      ninja:
        version: '>=2'
    steps:
      ok:
        uses: echo
""",
            {"local.ptk.yml": "jobs: {go: {requires_tools: [ninja]}}"},
        )
    )
    with pytest.raises(ConfigError, match="unexpected configuration filename"):
        load(root)


def test_schema_describes_authored_files():
    schema = ExportSchema().execute()
    assert "include" not in schema["properties"]
    assert "required" not in schema["allOf"][0]["else"]
    assert schema["allOf"][0]["if"]["required"] == ["virtual_monorepo"]
    assert schema["allOf"][0]["then"]["properties"]["repository"] is False
    assert "default" not in schema["properties"]["virtual_monorepo"]
    assert {"type": "string"} not in schema["properties"]["variants"]["anyOf"]
    assert any(
        s.get("type") == "array"
        for s in schema["$defs"]["JobSpec"]["properties"]["requires_tools"]["anyOf"]
    )


def test_login_identity_does_not_query_git(tmp_path, monkeypatch):
    from ptk.adapters.host import SystemHost

    monkeypatch.setattr("getpass.getuser", lambda: "local-login")

    def forbidden(*args, **kwargs):
        raise AssertionError("identity lookup must not run Git")

    monkeypatch.setattr(subprocess, "run", forbidden)
    assert SystemHost({}).user_id() == "local-login"
    assert (
        SystemHost(
            {
                "GITHUB_ACTIONS": "true",
                "GITHUB_ACTOR": "alice",
                "GITHUB_TRIGGERING_ACTOR": "bob",
            }
        ).user_id()
        == "bob"
    )
    assert (
        SystemHost({"GITHUB_ACTIONS": "true", "GITHUB_ACTOR": "alice"}).user_id()
        == "alice"
    )
    assert SystemHost({"GITHUB_ACTIONS": "true"}).user_id() is None
    assert SystemHost({"GITHUB_ACTOR": "alice"}).user_id() == "local-login"


def test_isolated_job_environment_does_not_inherit_secrets(write, load, monkeypatch):
    monkeypatch.setenv("UNRELATED_TOKEN", "must-not-inherit")
    root = write(
        project_files(
            """\
project:
  name: demo
environment:
  keep:
  - KEPT
jobs:
  go:
    steps:
      ok:
        uses: echo
"""
        )
    )
    from ptk.application.use_cases.run import RunRequest

    app = create_app(
        environ={
            "UNRELATED_TOKEN": "must-not-inherit",
            "KEPT": "yes",
            "PATH": "/other-repo/bin",
        }
    )
    prepared = app.prepare_run(load(root)).execute(load(root), RunRequest(job="go"))
    assert "UNRELATED_TOKEN" not in prepared.plan.base_env
    assert prepared.plan.base_env["KEPT"] == "yes"
    assert "/other-repo/bin" not in prepared.plan.base_env["PATH"]


def test_requirement_merge_does_not_change_arbitrary_variable_maps():
    from ptk.domain.config.tree import from_plain, merge, to_plain

    before = from_plain({"vars": {"requires_tools": {"x": {"setting": 1}}}})
    after = from_plain({"vars": {"requires_tools": {"x": True}}})
    assert to_plain(merge(before, after))["vars"]["requires_tools"]["x"] is True
