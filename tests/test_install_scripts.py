"""Run installers against a fake uv, without modifying the developer's tools."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WINDOWS = sys.platform == "win32"


def invoke(tmp_path, *, checkout=True, source=None, fail=False):
    repo = tmp_path / "checkout with spaces"
    install = repo / "install"
    install.mkdir(parents=True)
    extension = "ps1" if WINDOWS else "sh"
    script = install / f"install.{extension}"
    shutil.copyfile(ROOT / "install" / script.name, script)
    if checkout:
        (repo / "src/ptk").mkdir(parents=True)
        (repo / "pyproject.toml").write_text('[project]\nname="ptk"\n')
    capture = tmp_path / "calls.jsonl"
    env = {k: v for k, v in os.environ.items() if k not in {"PTK_SOURCE", "PTK_EXTRAS"}}
    env.update(CAPTURE=str(capture), FAIL_INSTALL="1" if fail else "0")
    if source:
        env["PTK_SOURCE"] = source
    if WINDOWS:
        wrapper = tmp_path / "wrapper.ps1"
        wrapper.write_text("""function uv {
    ConvertTo-Json -Compress -InputObject @($args) | Add-Content $env:CAPTURE
    $global:LASTEXITCODE = 0
    if ($env:FAIL_INSTALL -eq "1" -and $args[1] -eq "install") { $global:LASTEXITCODE = 9 }
}
& $env:INSTALL_SCRIPT -NoExtension -NoCompletion
""")
        env["INSTALL_SCRIPT"] = str(script)
        argv = [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(wrapper),
        ]
    else:
        binary = tmp_path / "bin"
        binary.mkdir()
        uv = binary / "uv"
        uv.write_text(
            f"#!{sys.executable}\n"
            + """import json, os, sys
with open(os.environ["CAPTURE"], "a") as f:
    f.write(json.dumps(sys.argv[1:]) + "\\n")
sys.exit(9 if os.environ["FAIL_INSTALL"] == "1" and sys.argv[1:3] == ["tool", "install"] else 0)
"""
        )
        uv.chmod(0o755)
        env["PATH"] = str(binary) + os.pathsep + env["PATH"]
        argv = ["sh", str(script), "--no-extension", "--no-completion"]
    result = subprocess.run(
        argv, cwd=tmp_path, env=env, capture_output=True, text=True, check=False
    )
    calls = [
        json.loads(line)
        for line in capture.read_text(encoding="utf-8-sig").splitlines()
    ]
    return repo, result, calls


@pytest.mark.parametrize("mode", ["checkout", "standalone", "override"])
def test_installer_refreshes_selected_source(tmp_path, mode):
    explicit = "git+https://example.invalid/ptk@main" if mode == "override" else None
    repo, result, calls = invoke(
        tmp_path, checkout=mode != "standalone", source=explicit
    )
    assert result.returncode == 0, result.stdout + result.stderr
    install = calls[0]
    assert install[:2] == ["tool", "install"]
    assert {"--force", "--reinstall", "--upgrade"}.issubset(install)
    assert install[-1] == (explicit or ("ptk" if mode == "standalone" else str(repo)))
    assert calls[1] == ["tool", "update-shell"]


def test_installer_does_not_claim_success_after_failure(tmp_path):
    _, result, calls = invoke(tmp_path, fail=True)
    assert result.returncode != 0
    assert len(calls) == 1
    assert "done -" not in result.stdout
