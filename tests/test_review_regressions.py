"""Observable failures found in the full-project review."""

import json
import os
import signal
import subprocess
import sys

import pytest
import yaml
from click.testing import CliRunner

from ptk.adapters.credentials.vault import Vault
from ptk.adapters.process import SubprocessRunner
from ptk.application.use_cases.project import ExportSchema
from ptk.application.use_cases.tools import tools_for_actions
from ptk.bootstrap import create_app
from ptk.domain.execution.model import CommandSpec
from ptk.drivers.cli.main import cli


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
    main.write_text(
        yaml.safe_dump(
            {
                "repository": {"alias": "demo", "config_path": "."},
                "project": {"name": "demo"},
                "reporting": {"formats": ["json"]},
                "actions": {
                    "go": {
                        "params": {"name": {"default": "first-test"}},
                        "steps": [
                            {
                                "test": {
                                    "run": [
                                        sys.executable,
                                        str(script),
                                        "${params.name}",
                                    ]
                                }
                            }
                        ],
                    }
                },
            }
        )
    )
    runner = CliRunner()
    base = ["-c", str(main)]
    assert runner.invoke(cli, [*base, "go"]).exit_code == 0
    first_id = json.loads((tmp_path / "_logs/default/go/run.json").read_text())[
        "run_id"
    ]
    assert runner.invoke(cli, [*base, "go", "--name", "none"]).exit_code == 0
    report = tmp_path / "_reports/default/go/report.json"
    assert "first-test" not in report.read_text()
    assert runner.invoke(cli, [*base, "go", "--name", "second-test"]).exit_code == 0
    result = runner.invoke(
        cli, [*base, "report", "export", "go", "--run", first_id, "-f", "json"]
    )
    assert result.exit_code == 0, result.output
    assert "second-test" not in report.read_text()
    assert "first-test" in report.read_text()


def test_requirement_true_preserves_earlier_action_settings(write, load):
    root = write(
        {
            ".main.ptk.yml": "project: {name: demo}\ntools: {ninja: {version: '>=1'}}\nactions: {go: {requires_tools: {ninja: {version: '>=2'}}, steps: [{ok: {uses: echo}}]}}",
            "local.ptk.yml": "actions: {go: {requires_tools: [ninja]}}",
        }
    )
    assert tools_for_actions(load(root), ["go"]).config.tools["ninja"].version == ">=2"


def test_schema_describes_authored_files():
    schema = ExportSchema().execute()
    assert "include" in schema["properties"]
    assert schema["required"] == ["repository"]
    assert {"type": "string"} in schema["properties"]["variants"]["anyOf"]
    assert any(
        s.get("type") == "array"
        for s in schema["$defs"]["ActionSpec"]["properties"]["requires_tools"]["anyOf"]
    )


def test_repository_identity_ignores_callers_git_configuration(tmp_path, monkeypatch):
    from ptk.adapters.host import SystemHost

    for name in ["a", "b"]:
        repo = tmp_path / name
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        subprocess.run(
            ["git", "-C", str(repo), "config", "user.email", name + "@example.invalid"],
            check=True,
        )
    monkeypatch.chdir(tmp_path / "a")
    assert SystemHost().user_identity(tmp_path / "b")[0] == "b@example.invalid"


def test_isolated_action_environment_does_not_inherit_secrets(write, load, monkeypatch):
    monkeypatch.setenv("UNRELATED_TOKEN", "must-not-inherit")
    root = write(
        {
            ".main.ptk.yml": "project: {name: demo}\nenvironment: {keep: [KEPT]}\nactions: {go: {steps: [{ok: {uses: echo}}]}}"
        }
    )
    from ptk.application.use_cases.run import RunRequest

    app = create_app(
        environ={
            "UNRELATED_TOKEN": "must-not-inherit",
            "KEPT": "yes",
            "PATH": "/other-repo/bin",
        }
    )
    prepared = app.prepare_run(load(root)).execute(load(root), RunRequest(action="go"))
    assert "UNRELATED_TOKEN" not in prepared.plan.base_env
    assert prepared.plan.base_env["KEPT"] == "yes"
    assert "/other-repo/bin" not in prepared.plan.base_env["PATH"]
