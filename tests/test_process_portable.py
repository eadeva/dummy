"""Real subprocess coverage without POSIX shell assumptions."""

import os
import shutil
import sys
import threading
from types import SimpleNamespace

import pytest

from ptk.adapters.process import SubprocessRunner
from ptk.domain.config.model import StepSpec
from ptk.domain.execution.commands import build_command
from ptk.domain.execution.model import CommandSpec, PlannedStep
from tests.project_files import write_project


def test_captured_windows_launch_hides_console_and_keeps_process_group(
    tmp_path, monkeypatch
):
    import io
    import subprocess

    from ptk.adapters import process_options

    monkeypatch.setattr(process_options, "WINDOWS", True)
    for name, value in {
        "CREATE_NO_WINDOW": 0x08000000,
        "CREATE_NEW_PROCESS_GROUP": 0x200,
        "STARTF_USESHOWWINDOW": 1,
        "SW_HIDE": 0,
    }.items():
        monkeypatch.setattr(subprocess, name, value, raising=False)
    monkeypatch.setattr(
        subprocess,
        "STARTUPINFO",
        lambda: SimpleNamespace(dwFlags=0, wShowWindow=1),
        raising=False,
    )
    launches = []

    def popen(args, **kwargs):
        launches.append(kwargs)
        return SimpleNamespace(
            stdout=io.BytesIO(b"captured\n"), poll=lambda: 0, wait=lambda: 0
        )

    monkeypatch.setattr(subprocess, "Popen", popen)
    lines = []
    result = SubprocessRunner().run(
        CommandSpec(
            argv=[sys.executable, "-c", "pass"], cwd=str(tmp_path), env=dict(os.environ)
        ),
        lines.append,
    )
    assert result.exit_code == 0 and lines == ["captured"]
    assert launches[0]["creationflags"] == 0x08000200
    assert launches[0]["startupinfo"].dwFlags & 1
    assert launches[0]["startupinfo"].wShowWindow == 0


@pytest.mark.skipif(sys.platform != "win32", reason="native Windows console APIs")
@pytest.mark.parametrize("shell", [False, True])
def test_windows_captured_process_has_no_console_window(tmp_path, shell):
    import subprocess

    argv = [
        sys.executable,
        "-c",
        (
            "import ctypes; from ctypes import wintypes; "
            "get_window = ctypes.windll.kernel32.GetConsoleWindow; "
            "get_window.restype = wintypes.HWND; print(bool(get_window()))"
        ),
    ]
    command = CommandSpec(
        shell=subprocess.list2cmdline(argv) if shell else None,
        argv=None if shell else argv,
        cwd=str(tmp_path),
        env=dict(os.environ),
    )
    lines = []
    result = SubprocessRunner().run(command, lines.append)
    assert result.exit_code == 0, (result, lines)
    # CREATE_NO_WINDOW suppresses the window; a console code page may still exist.
    assert lines == ["False"]


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
    spec = StepSpec(run=[str(script)])
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
    write_project(
        config,
        """\
repository:
  alias: demo
  config_path: .
project:
  name: demo
jobs:
  hello:
    steps:
      greet:
        uses: echo
        with:
          message: "caf\\xE9 \\U0001F9EA"
""",
    )
    result = subprocess.run(
        [sys.executable, "-m", "ptk.drivers.cli.main", "hello"],
        cwd=config.parent,
        env={**os.environ, "PYTHONIOENCODING": "cp1252:strict"},
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr.decode("cp1252")
    output = result.stdout.decode("cp1252")
    assert "caf\u00e9" in output and "\\U0001f9ea" in output
    assert "passed" in output
