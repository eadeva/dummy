"""Exercise both installers against isolated uv/PTK launchers."""

import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
POWERSHELL = shutil.which("pwsh")


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="uses POSIX fake executables; PowerShell runs on Linux here",
)
@pytest.mark.parametrize("shell", ["sh", "powershell"])
@pytest.mark.parametrize("mode", ["checkout", "package", "opt-out", "failure"])
def test_installer_uses_selected_tool_for_extension(tmp_path, shell, mode):
    if shell == "powershell" and not POWERSHELL:
        pytest.skip("requires PowerShell")
    binary = tmp_path / "uv tool bin"
    binary.mkdir()
    calls = tmp_path / "extension-calls.jsonl"
    source = tmp_path / "checkout with spaces"
    (source / "src/ptk").mkdir(parents=True)
    (source / "pyproject.toml").write_text('[project]\nname="ptk"\n')
    install = source / "install"
    install.mkdir()
    suffix = "ps1" if shell == "powershell" else "sh"
    script = install / f"install.{suffix}"
    shutil.copyfile(ROOT / "install" / script.name, script)
    # A decoy ptk on PATH must not be used instead of uv's selected executable.
    decoy = tmp_path / "decoy"
    decoy.mkdir()
    (decoy / "ptk").write_text("#!/bin/sh\nexit 97\n")
    (decoy / "ptk").chmod(0o755)
    program = tmp_path / "fake_ptk.py"
    program.write_text("""import json, os, sys
with open(os.environ['TEST_CALLS'], 'a') as stream:
    stream.write(json.dumps(sys.argv[1:]) + '\\n')
sys.exit(8 if os.environ['TEST_MODE'] == 'failure' else 0)
""")
    launcher = binary / ("ptk.exe" if shell == "powershell" else "ptk")
    launcher.write_text(
        f'#!/bin/sh\nexec {shlex.quote(sys.executable)} {shlex.quote(str(program))} "$@"\n'
    )
    launcher.chmod(0o755)
    env = {k: v for k, v in os.environ.items() if k not in {"PTK_SOURCE", "PTK_EXTRAS"}}
    env.update(
        TEST_BIN=str(binary),
        TEST_CALLS=str(calls),
        TEST_MODE=mode,
        TEST_INSTALL=str(script),
        PATH=str(decoy) + os.pathsep + env["PATH"],
    )
    if mode == "package":
        env["PTK_SOURCE"] = "ptk==1.2.3"
    if shell == "powershell":
        wrapper = tmp_path / "wrapper.ps1"
        wrapper.write_text("""function uv {
    $global:LASTEXITCODE = 0
    if ($args[1] -eq 'dir') { $env:TEST_BIN }
}
$options = @{ NoCompletion = $true }
if ($env:TEST_MODE -eq 'opt-out') { $options.NoExtension = $true }
& $env:TEST_INSTALL @options
""")
        argv = [POWERSHELL, "-NoProfile", "-NonInteractive", "-File", str(wrapper)]
    else:
        uv = decoy / "uv"
        uv.write_text(
            '#!/bin/sh\nif [ "$2" = dir ]; then printf "%s\\n" "$TEST_BIN"; fi\n'
        )
        uv.chmod(0o755)
        argv = ["sh", str(script), "--no-completion"] + (
            ["--no-extension"] if mode == "opt-out" else []
        )
    result = subprocess.run(
        argv,
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
    )
    if mode == "opt-out":
        assert result.returncode == 0, result.stdout + result.stderr
        assert not calls.exists()
        return
    recorded = [json.loads(line) for line in calls.read_text().splitlines()]
    assert len(recorded) == 1
    assert recorded[0][:3] == ["self-service", "extension", "--if-available"]
    assert ("--force" in recorded[0]) == (mode != "package")
    if mode == "failure":
        assert result.returncode != 0 and "done -" not in result.stdout
    else:
        assert result.returncode == 0, result.stdout + result.stderr
