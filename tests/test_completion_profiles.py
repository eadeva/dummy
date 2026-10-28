"""Persistent completion preserves profiles and works in actual PowerShell."""

import codecs
import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

from ptk.drivers.cli.completion_profiles import END, START, update_profile
from ptk.drivers.cli.main import cli

ROOT = Path(__file__).resolve().parents[1]
POWERSHELL = shutil.which("pwsh") or shutil.which("powershell")


@pytest.mark.parametrize(
    "encoding,bom",
    [
        ("utf-8", b""),
        ("utf-8", codecs.BOM_UTF8),
        ("utf-16-le", codecs.BOM_UTF16_LE),
        ("utf-16-be", codecs.BOM_UTF16_BE),
        ("cp1252", b""),
    ],
)
@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_install_update_remove_preserves_profile(tmp_path, encoding, bom, newline):
    profile = tmp_path / "profile.ps1"
    original = bom + ("# Benutzer café" + newline + "$custom = 42" + newline).encode(
        encoding
    )
    profile.write_bytes(original)
    assert update_profile(profile, "# first registration\n")
    first = profile.read_bytes()
    modified = profile.stat().st_mtime_ns
    assert first.startswith(original)
    assert profile.with_name("profile.ps1.ptk.bak").read_bytes() == original
    assert not update_profile(profile, "# first registration\n")
    assert profile.stat().st_mtime_ns == modified
    assert update_profile(profile, "# updated registration\n")
    assert profile.read_bytes().startswith(original)
    assert profile.read_bytes().decode(encoding).count(START) == 1
    assert profile.with_name("profile.ps1.ptk.bak").read_bytes() == original
    assert update_profile(profile, None)
    assert profile.read_bytes() == original
    assert not update_profile(profile, None)


def test_missing_profile_and_surrounding_settings(tmp_path):
    profile = tmp_path / "PowerShell directory/profile.ps1"
    assert not update_profile(profile, None)
    assert not profile.parent.exists()
    assert update_profile(profile, "# registration")
    assert not profile.with_name(profile.name + ".ptk.bak").exists()
    profile.write_text("# before\n" + profile.read_text() + "# after\n")
    assert update_profile(profile, "# replacement")
    assert profile.read_text().startswith("# before\n")
    assert profile.read_text().endswith("# after\n")
    assert update_profile(profile, None)
    assert profile.read_text() == "# before\n# after\n"


def test_failed_replace_preserves_existing_profile(tmp_path, monkeypatch):
    profile = tmp_path / "profile.ps1"
    original = b"# existing settings\n"
    profile.write_bytes(original)

    def fail(*args):
        raise PermissionError("file in use")

    monkeypatch.setattr("ptk.drivers.cli.completion_profiles.os.replace", fail)
    with pytest.raises(PermissionError, match="file in use"):
        update_profile(profile, "# registration")
    assert profile.read_bytes() == original
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        "profile.ps1",
        "profile.ps1.ptk.bak",
    ]


@pytest.mark.parametrize(
    "content", [START, END, END + "\n" + START, START + "\n" + START + "\n" + END]
)
def test_malformed_blocks_are_not_overwritten(tmp_path, content):
    profile = tmp_path / "profile.ps1"
    profile.write_text(content)
    original = profile.read_bytes()
    with pytest.raises(ValueError, match="markers"):
        update_profile(profile, "# new")
    assert profile.read_bytes() == original
    assert not profile.with_name(profile.name + ".ptk.bak").exists()


def test_profile_command_and_invalid_combinations(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    profile = tmp_path / "profile with spaces.ps1"
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "setup",
            "completion",
            "powershell",
            "--double-tab",
            "--install",
            str(profile),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "Register-ArgumentCompleter" in profile.read_text()
    assert "Set-PSReadLineKeyHandler" in profile.read_text()
    before = profile.read_bytes()
    for args in (
        ["bash", "--install", str(profile)],
        ["powershell", "--install", str(profile), "--output", str(profile)],
        ["powershell", "--install", str(profile), "--uninstall", str(profile)],
        ["powershell", "--uninstall", str(profile), "--double-tab"],
    ):
        failed = runner.invoke(cli, ["setup", "completion", *args])
        assert failed.exit_code == 2, failed.output
        assert profile.read_bytes() == before
    removed = runner.invoke(
        cli, ["setup", "completion", "powershell", "--uninstall", str(profile)]
    )
    assert removed.exit_code == 0, removed.output
    assert profile.read_text() == ""


def _executable(folder):
    folder.mkdir()
    target = folder / "ptk.exe"
    if sys.platform == "win32":
        launcher = Path(sys.executable).parent / "ptk.exe"
        if not launcher.exists():
            pytest.skip("requires PTK's installed Windows launcher")
        shutil.copyfile(launcher, target)
    else:
        target.write_text(
            f'#!/bin/sh\nexec {shlex.quote(sys.executable)} -m ptk "$@"\n'
        )
        target.chmod(0o755)
        shutil.copyfile(target, folder / "ptk")
        (folder / "ptk").chmod(0o755)
    return target


def _powershell(script, tmp_path, **extra):
    env = {**os.environ, **extra}
    env["PYTHONPATH"] = str(ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(
        [POWERSHELL, "-NoLogo", "-NoProfile", "-NonInteractive", "-File", str(script)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=40,
    )


@pytest.mark.skipif(not POWERSHELL, reason="requires PowerShell")
@pytest.mark.parametrize("mode", ["default", "opt-out", "failure", "profile-error"])
def test_windows_installer_registers_and_persists_completion(tmp_path, mode):
    binary = tmp_path / "tool bin"
    _executable(binary)
    profile = tmp_path / "redirected documents/PowerShell/profile.ps1"
    profile.parent.mkdir(parents=True)
    original = '# My settings: café\n$global:KeptSetting = "kept"\n'.encode("utf-8-sig")
    if mode == "profile-error":
        original += START.encode()
    profile.write_bytes(original)
    script = tmp_path / "install-test.ps1"
    script.write_text("""$ErrorActionPreference = 'Stop'
$PROFILE = Join-Path $env:TEST_ROOT 'host.ps1'
$PROFILE | Add-Member -NotePropertyName CurrentUserAllHosts -NotePropertyValue $env:TEST_PROFILE
function uv {
    $global:LASTEXITCODE = 0
    if ($args[0] -eq 'tool' -and $args[1] -eq 'dir') { $env:TEST_BIN }
    if ($env:TEST_MODE -eq 'failure' -and $args[1] -eq 'install') { $global:LASTEXITCODE = 9 }
}
$options = @{ NoExtension = $true }
if ($env:TEST_MODE -eq 'opt-out') { $options.NoCompletion = $true }
& $env:TEST_INSTALL @options
if ($env:TEST_MODE -eq 'default') {
    & $env:TEST_INSTALL @options
    $matches = @((TabExpansion2 'ptk setup ' 10).CompletionMatches.CompletionText)
    if ('completion' -notin $matches -or 'init' -notin $matches) { throw "completion missing: $matches" }
    if ((Get-PSReadLineKeyHandler -Chord Tab).Function -ne 'Complete') { throw 'Tab binding missing' }
}
""")
    result = _powershell(
        script,
        tmp_path,
        TEST_ROOT=str(tmp_path),
        TEST_PROFILE=str(profile),
        TEST_BIN=str(binary),
        TEST_MODE=mode,
        TEST_INSTALL=str(ROOT / "install/install.ps1"),
    )
    if mode == "failure":
        assert result.returncode != 0
        assert "done -" not in result.stdout
    else:
        assert result.returncode == 0, result.stdout + result.stderr
    if mode != "default":
        assert profile.read_bytes() == original
        if mode == "profile-error":
            assert "completion setup failed" in result.stdout + result.stderr
            assert "Tab completion enabled now" not in result.stdout
        return
    assert "completion setup failed" not in result.stdout + result.stderr
    assert profile.read_bytes().startswith(original)
    assert profile.read_text(encoding="utf-8-sig").count(START) == 1
    assert profile.with_name(profile.name + ".ptk.bak").read_bytes() == original
    # A fresh PowerShell process loads the persisted profile without the installer.
    script.write_text(""". $env:TEST_PROFILE
$matches = @((TabExpansion2 'ptk setup ' 10).CompletionMatches.CompletionText)
@{ matches = $matches; kept = $global:KeptSetting; tab = (Get-PSReadLineKeyHandler -Chord Tab).Function } | ConvertTo-Json -Compress
""")
    fresh = _powershell(
        script,
        tmp_path,
        TEST_PROFILE=str(profile),
        PATH=str(binary) + os.pathsep + os.environ["PATH"],
    )
    assert fresh.returncode == 0, fresh.stdout + fresh.stderr
    data = json.loads(fresh.stdout)
    assert {"init", "completion"} <= set(data["matches"])
    assert data["kept"] == "kept" and data["tab"] == "Complete"
