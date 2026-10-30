"""Persistent registration survives fresh shells, old PATH and inactive venvs."""

import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

from ptk.drivers.cli import shell_setup
from ptk.drivers.cli.completion_profiles import START
from ptk.drivers.cli.main import cli

ROOT = Path(__file__).resolve().parents[1]
POWERSHELL = shutil.which("pwsh") or shutil.which("powershell")


@pytest.fixture
def installation(tmp_path, monkeypatch):
    home = tmp_path / "user home"
    home.mkdir()
    tool_bin = tmp_path / "工具's shared tools"
    tool_bin.mkdir()
    launcher = tool_bin / ("ptk.exe" if sys.platform == "win32" else "ptk")
    launcher.write_text(
        f'#!/bin/sh\nprintf "called\\n" >> {shlex.quote(str(tool_bin / "invocations.log"))}\nexec {shlex.quote(sys.executable)} -m ptk "$@"\n',
        encoding="utf-8",
    )
    launcher.chmod(0o755)
    ps = [home / "WindowsPowerShell/profile.ps1", home / "PowerShell/profile.ps1"]
    monkeypatch.setattr(shell_setup, "bash_home", lambda: home)
    monkeypatch.setattr(shell_setup, "powershell_profiles", lambda: ps)
    monkeypatch.chdir(tmp_path)
    sources = {
        shell: CliRunner()
        .invoke(
            cli,
            [
                "self-service",
                "completion",
                shell,
                *(["--double-tab"] if shell == "powershell" else []),
            ],
        )
        .output
        for shell in ("bash", "powershell")
    }
    return home, launcher, ps, sources


def test_cli_installs_all_profiles_and_is_idempotent(installation):
    home, launcher, ps, _ = installation
    original = "# Existing login settings\nexport KEPT_SETTING=yes\n"
    (home / ".profile").write_text(original)
    result = CliRunner().invoke(
        cli, ["self-service", "completion", "install", "--executable", str(launcher)]
    )
    assert result.exit_code == 0, result.output
    assert all(path.is_file() for path in ps)
    assert (home / ".profile").read_text(encoding="utf-8-sig").startswith(original)
    assert not (home / ".bash_profile").exists()
    files = [
        home / ".profile",
        home / ".bashrc",
        home / ".local/share/ptk/completion.bash",
        *ps,
    ]
    before = {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in files}
    again = CliRunner().invoke(
        cli, ["self-service", "completion", "install", "--executable", str(launcher)]
    )
    assert again.exit_code == 0, again.output
    assert before == {
        path: (path.read_bytes(), path.stat().st_mtime_ns) for path in files
    }
    assert all(path.read_text(encoding="utf-8-sig").count(START) == 1 for path in files)


def test_malformed_profile_preflight_leaves_every_file_unchanged(installation):
    home, launcher, ps, sources = installation
    ps[-1].parent.mkdir()
    ps[-1].write_text(START)
    with pytest.raises(ValueError, match="markers"):
        shell_setup.install_all(sources, launcher)
    assert list(home.rglob("*")) == [ps[-1].parent, ps[-1]]


@pytest.mark.parametrize("shell", ["bash", "powershell"])
@pytest.mark.parametrize("profile_index", [0, 1])
@pytest.mark.skipif(
    sys.platform == "win32",
    reason="POSIX test launcher; native Windows runs other installer tests",
)
def test_fresh_shell_without_venv_or_shared_tool_on_path(
    installation, shell, profile_index
):
    home, launcher, ps, sources = installation
    if shell == "powershell" and not POWERSHELL:
        pytest.skip("requires PowerShell")
    shell_setup.install_all(sources, launcher)
    env = {
        k: v for k, v in os.environ.items() if k not in {"VIRTUAL_ENV", "PYTHONHOME"}
    }
    env.update(
        PATH=os.defpath,
        PYTHONPATH=str(ROOT / "src"),
        TEST_CALL_LOG=str(launcher.parent / "invocations.log"),
    )
    if shell == "bash":
        profile = home / (".bashrc" if profile_index == 0 else ".bash_profile")
        command = """if [ -e "$TEST_CALL_LOG" ]; then exit 41; fi
command -v ptk
COMP_WORDS=(ptk self-service "")
COMP_CWORD=2
_ptk_completion ptk
printf '%s\\n' "${COMPREPLY[@]}"
"""
        argv = ["bash", "--noprofile", "--rcfile", str(profile), "-ic", command]
    else:
        env["TEST_PROFILE"] = str(ps[profile_index])
        command = """$ptkToolDirectory = 'keep my setting'
. $env:TEST_PROFILE
if ($ptkToolDirectory -ne 'keep my setting') { throw 'profile changed my variable' }
if (Test-Path -LiteralPath $env:TEST_CALL_LOG) { throw 'PTK ran during profile loading' }
$found = (Get-Command ptk).Source
$matches = @((TabExpansion2 'ptk self-service ' 17).CompletionMatches.CompletionText)
@{ executable = $found; matches = $matches } | ConvertTo-Json -Compress
"""
        argv = [
            POWERSHELL,
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            command,
        ]
    result = subprocess.run(
        argv, cwd=home, env=env, capture_output=True, text=True, check=False, timeout=30
    )
    assert result.returncode == 0, result.stdout + result.stderr
    if shell == "bash":
        lines = result.stdout.splitlines()
        assert lines[0] == str(launcher)
        assert {"completion", "extension", "tools"} <= set(lines[1:])
    else:
        data = json.loads(result.stdout)
        assert data["executable"] == str(launcher)
        assert {"completion", "extension", "tools"} <= set(data["matches"])


@pytest.mark.skipif(sys.platform == "win32", reason="requires POSIX sh")
def test_profile_loader_is_safe_in_posix_sh(installation):
    home, launcher, _, sources = installation
    (home / ".profile").write_text("KEPT_SETTING=yes\n")
    shell_setup.install_all(sources, launcher)
    result = subprocess.run(
        [
            "sh",
            "-c",
            '. "$1"; printf "%s" "$KEPT_SETTING"',
            "sh",
            str(home / ".profile"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0 and result.stdout == "yes"


def test_each_powershell_edition_supplies_its_own_profile(tmp_path, monkeypatch):
    executables = {name: tmp_path / name for name in ("powershell", "pwsh")}
    for path in executables.values():
        path.touch()
    monkeypatch.setattr(
        shell_setup.shutil, "which", lambda name: str(executables[name])
    )
    calls = []

    def query(args):
        calls.append(args)
        return str(tmp_path / Path(args[0]).name / "profile.ps1")

    monkeypatch.setattr(shell_setup, "_capture", query)
    monkeypatch.setattr(shell_setup, "WINDOWS", False)
    profiles = shell_setup.powershell_profiles()
    assert len(profiles) == len(calls) == 2
    assert all(
        "-NoProfile" in args and args[-1] == shell_setup.PROFILE_QUERY for args in calls
    )
    assert profiles[0] != profiles[1]


@pytest.mark.parametrize(
    "native,expected",
    [
        (r"C:\Users\A B\tools", "/c/Users/A B/tools"),
        (r"\\server\share\tools", "//server/share/tools"),
    ],
)
def test_git_bash_path_conversion(monkeypatch, native, expected):
    monkeypatch.setattr(shell_setup, "WINDOWS", True)
    assert shell_setup.bash_path(native) == expected


def test_default_tool_location_uses_uv_not_active_venv(tmp_path, monkeypatch):
    launcher = tmp_path / "ptk"
    launcher.touch()
    monkeypatch.setattr(shell_setup, "WINDOWS", False)
    monkeypatch.setattr(
        shell_setup.shutil,
        "which",
        lambda name: "/tools/uv" if name == "uv" else "/project/.venv/bin/ptk",
    )
    monkeypatch.setattr(shell_setup, "_capture", lambda args: str(tmp_path))
    assert shell_setup.tool_executable() == launcher


@pytest.mark.skipif(
    sys.platform == "win32" or not POWERSHELL,
    reason="tests real PowerShell startup with Linux XDG isolation",
)
def test_powershell_automatically_loads_profile_in_a_new_terminal(
    installation, monkeypatch
):
    home, launcher, _, sources = installation
    config = home / "xdg-config"
    profile = config / "powershell/profile.ps1"
    monkeypatch.setattr(shell_setup, "powershell_profiles", lambda: [profile])
    shell_setup.install_all(sources, launcher)
    env = {
        k: v for k, v in os.environ.items() if k not in {"VIRTUAL_ENV", "PYTHONHOME"}
    }
    env.update(
        XDG_CONFIG_HOME=str(config), PATH=os.defpath, PYTHONPATH=str(ROOT / "src")
    )
    result = subprocess.run(
        [
            POWERSHELL,
            "-NoLogo",
            "-NonInteractive",
            "-Command",
            "@((TabExpansion2 'ptk self-service ' 17).CompletionMatches.CompletionText) | ConvertTo-Json -Compress",
        ],
        cwd=home,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert {"completion", "extension", "tools"} <= set(json.loads(result.stdout))


def test_git_bash_home_is_queried_without_loading_profiles(tmp_path, monkeypatch):
    git = tmp_path / "Git/cmd/git.exe"
    bash = tmp_path / "Git/bin/bash.exe"
    bash.parent.mkdir(parents=True)
    bash.touch()
    custom_home = tmp_path / "redirected home"
    monkeypatch.setattr(shell_setup, "WINDOWS", True)
    monkeypatch.setattr(
        shell_setup.shutil, "which", lambda name: str(git) if name == "git" else None
    )

    def query(args):
        assert args == [str(bash), "--noprofile", "--norc", "-c", 'cygpath -w "$HOME"']
        return str(custom_home)

    monkeypatch.setattr(shell_setup, "_capture", query)
    assert shell_setup.bash_home() == custom_home


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX symlink fixture")
def test_tool_location_preserves_global_launcher_symlink(tmp_path):
    target = tmp_path / "internal-env/ptk"
    target.parent.mkdir()
    target.touch()
    link = tmp_path / "ptk"
    link.symlink_to(target)
    assert shell_setup.tool_executable(link) == link


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX isolated uv launcher")
@pytest.mark.parametrize("mode", ["install", "opt-out", "malformed"])
def test_bash_installer_configures_real_completion_without_a_venv(tmp_path, mode):
    from tests.test_completion_profiles import _executable

    binary = tmp_path / "tool bin"
    _executable(binary)
    uv = binary / "uv"
    uv.write_text('#!/bin/sh\nif [ "$2" = dir ]; then printf "%s\\n" "$TEST_BIN"; fi\n')
    uv.chmod(0o755)
    profile = tmp_path / "PowerShell/profile.ps1"
    if mode == "malformed":
        profile.parent.mkdir()
        profile.write_text(START)
    env = {
        k: v
        for k, v in os.environ.items()
        if k not in {"VIRTUAL_ENV", "PYTHONHOME", "PTK_SOURCE", "PTK_EXTRAS"}
    }
    env.update(
        TEST_BIN=str(binary),
        TEST_ROOT=str(tmp_path),
        TEST_PROFILE=str(profile),
        PATH=str(binary) + os.pathsep + os.defpath,
        PYTHONPATH=str(ROOT / "src") + os.pathsep + str(binary),
    )
    argv = ["sh", str(ROOT / "install/install.sh"), "--no-extension"]
    if mode == "opt-out":
        argv.append("--no-completion")
    result = subprocess.run(
        argv,
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    if mode == "malformed":
        assert result.returncode != 0 and "completion setup failed" in result.stdout
        assert "done -" not in result.stdout
        assert profile.read_text(encoding="utf-8-sig") == START
        assert not (tmp_path / "bash home").exists()
    else:
        assert result.returncode == 0, result.stdout + result.stderr
        assert (tmp_path / "bash home/.bashrc").exists() == (mode == "install")
        assert profile.exists() == (mode == "install")
