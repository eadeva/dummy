"""Real subprocess coverage without POSIX shell assumptions."""

import os
import shutil
import sys
import threading

import pytest

from ptk.adapters.process import SubprocessRunner
from ptk.domain.config.model import StepSpec
from ptk.domain.execution.commands import build_command
from ptk.domain.execution.model import CommandSpec, PlannedStep


def test_process_environment_and_exit(tmp_path):
    lines = []
    outcome = SubprocessRunner().run(
        CommandSpec(
            argv=[
                sys.executable,
                "-c",
                "import os,sys; print(os.environ['PTK_TEST_VALUE']); sys.exit(7)",
            ],
            cwd=str(tmp_path),
            env={**os.environ, "PTK_TEST_VALUE": "a value"},
        ),
        lines.append,
    )
    assert outcome.exit_code == 7
    assert lines == ["a value"]


def test_process_timeout(tmp_path):
    outcome = SubprocessRunner().run(
        CommandSpec(
            argv=[sys.executable, "-c", "import time; time.sleep(30)"],
            cwd=str(tmp_path),
            env=dict(os.environ),
            timeout=0.2,
        ),
        lambda _: None,
    )
    assert outcome.timed_out and outcome.exit_code != 0


def test_process_cancellation(tmp_path):
    cancel = threading.Event()
    lines = []

    def output(line):
        lines.append(line)
        cancel.set()

    outcome = SubprocessRunner().run(
        CommandSpec(
            argv=[
                sys.executable,
                "-u",
                "-c",
                "import time; print('ready'); time.sleep(30)",
            ],
            cwd=str(tmp_path),
            env=dict(os.environ),
            timeout=10,
        ),
        output,
        cancel,
    )
    assert lines == ["ready"]
    assert outcome.cancelled and not outcome.timed_out and outcome.exit_code != 0


@pytest.mark.skipif(sys.platform != "win32", reason="native Windows scripts")
@pytest.mark.parametrize("suffix", [".cmd", ".ps1"])
def test_windows_script(tmp_path, suffix):
    script = tmp_path / ("script with spaces" + suffix)
    script.write_text(
        "@echo off\necho native-script-ok\n"
        if suffix == ".cmd"
        else "Write-Output 'native-script-ok'\n",
        encoding="utf-8",
    )
    powershell = shutil.which("pwsh") or shutil.which("powershell")
    assert suffix != ".ps1" or powershell, "Windows CI needs PowerShell"
    spec = StepSpec(name="native", run=[str(script)])
    step = PlannedStep(path=("native",), spec=spec, run=spec.run)
    command = build_command(
        step,
        env=dict(os.environ),
        cwd=str(tmp_path),
        os_name="windows",
        python=None,
        powershell=powershell or "powershell",
    )
    lines = []
    outcome = SubprocessRunner().run(command, lines.append)
    assert outcome.exit_code == 0, (outcome, lines)
    assert "native-script-ok" in lines


def test_cli_redirected_legacy_encoding_does_not_abort_job(tmp_path):
    """Exercise the real entry point, not Click's UTF-8 in-memory test streams."""
    import subprocess

    config = tmp_path / ".main.ptk.yml"
    config.write_text(
        "repository: {alias: demo, config_path: .}\n"
        "project: {name: demo}\n"
        "jobs:\n  hello:\n    steps:\n"
        "      - greet: {uses: echo, with: {message: 'caf\u00e9 \U0001f9ea'}}\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, "-m", "ptk.drivers.cli.main", "-c", str(config), "hello"],
        env={**os.environ, "PYTHONIOENCODING": "cp1252:strict"},
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr.decode("cp1252")
    output = result.stdout.decode("cp1252")
    assert "caf\u00e9" in output and "\\U0001f9ea" in output
    assert "passed" in output
