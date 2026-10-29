"""Persist completion for the user's supported shells, independent of a venv."""

import base64
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path, PureWindowsPath

from .completion_profiles import update_profile

WINDOWS = sys.platform == "win32"
PROFILE_QUERY = (
    "[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false); "
    "[Console]::Write($PROFILE.CurrentUserAllHosts)"
)


def _capture(args):
    result = subprocess.run(
        args,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=15,
    )
    if result.returncode:
        raise ValueError(
            f"Cannot query {args[0]}: {(result.stderr or result.stdout).strip()}"
        )
    return result.stdout.strip()


def tool_executable(explicit=None):
    if explicit is not None:
        path = (
            explicit.expanduser().absolute()
        )  # retain the stable uv launcher, not its symlink target
    else:
        uv = shutil.which("uv")
        if uv is None:
            raise ValueError(
                "Cannot locate uv. Use --executable PATH to select the installed PTK launcher."
            )
        directory = _capture([uv, "tool", "dir", "--bin"])
        if not directory:
            raise ValueError("uv returned an empty tool executable directory")
        path = Path(directory) / ("ptk.exe" if WINDOWS else "ptk")
    if not path.is_absolute() or not path.is_file():
        raise ValueError(
            f"Shared PTK executable not found: {path}. Install PTK with the installer first."
        )
    return path


def powershell_profiles():
    candidates = [shutil.which(name) for name in ("powershell", "pwsh")]
    if WINDOWS:
        # Either edition may be installed but absent from this process's old PATH.
        for variable, suffix in (
            ("SYSTEMROOT", "System32/WindowsPowerShell/v1.0/powershell.exe"),
            ("PROGRAMFILES", "PowerShell/7/pwsh.exe"),
        ):
            if os.environ.get(variable):
                candidates.append(str(Path(os.environ[variable]) / suffix))
    profiles = []
    visited = set()
    for candidate in candidates:
        if not candidate or not Path(candidate).is_file():
            continue
        key = os.path.normcase(os.path.realpath(candidate))
        if key in visited:
            continue
        visited.add(key)
        value = _capture(
            [
                candidate,
                "-NoLogo",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                PROFILE_QUERY,
            ]
        )
        path = Path(value)
        if not value or not path.is_absolute():
            raise ValueError(
                f"{candidate} did not return an absolute current-user profile path"
            )
        profiles.append(path)
    return profiles


def bash_home():
    if WINDOWS:
        # Query Git Bash without reading user startup scripts; do not launch WSL's bash.exe.
        git = shutil.which("git")
        candidates = []
        if git:
            candidates.extend(
                Path(git).parents[i] / "bin/bash.exe"
                for i in range(min(3, len(Path(git).parents)))
            )
        if os.environ.get("PROGRAMFILES"):
            candidates.append(Path(os.environ["PROGRAMFILES"]) / "Git/bin/bash.exe")
        for candidate in candidates:
            if candidate.is_file():
                value = _capture(
                    [
                        str(candidate),
                        "--noprofile",
                        "--norc",
                        "-c",
                        'cygpath -w "$HOME"',
                    ]
                )
                if value and Path(value).is_absolute():
                    return Path(value)
                raise ValueError("Git Bash did not return an absolute home directory")
    return Path.home()


def bash_path(path):
    value = str(path)
    if not WINDOWS:
        return value
    windows = PureWindowsPath(value)
    if len(windows.drive) == 2 and windows.drive[1] == ":":
        return f"/{windows.drive[0].lower()}/" + "/".join(windows.parts[1:])
    return windows.as_posix()  # UNC paths retain //server/share


def powershell_source(source, executable):
    # ASCII source also works in Windows PowerShell 5.1's BOM-less ANSI profiles.
    directory = base64.b64encode(str(executable.parent).encode("utf-8")).decode("ascii")
    prefix = f"""# Make the shared tool available even in terminals with an inherited old PATH.
& {{
    $ptkToolDirectory = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('{directory}'))
    if ((Test-Path -LiteralPath $ptkToolDirectory -PathType Container) -and
        ($env:PATH -split [regex]::Escape([IO.Path]::PathSeparator)) -notcontains $ptkToolDirectory) {{
        $env:PATH = (@($env:PATH, $ptkToolDirectory) | Where-Object {{ $_ }}) -join [IO.Path]::PathSeparator
    }}
}}
"""
    return prefix + source.replace("-CommandName ptk ", "-CommandName ptk, ptk.exe ")


def install_all(sources, executable, extra_profiles=()):
    """Preflight all managed blocks, then update each file atomically."""
    executable = tool_executable(executable)
    home = bash_home()
    script = home / ".local/share/ptk/completion.bash"
    directory = shlex.quote(bash_path(executable.parent))
    bash = f"""# Keep an explicitly activated development environment ahead of the shared tool.
_ptk_tool_directory={directory}
case ":$PATH:" in
    *":$_ptk_tool_directory:"*) ;;
    *) export PATH="${{PATH:+$PATH:}}$_ptk_tool_directory" ;;
esac
unset _ptk_tool_directory
""" + sources["bash"]
    location = shlex.quote(bash_path(script))
    loader = f"""# POSIX syntax: .profile may also be read by shells other than Bash.
if [ -n "${{BASH_VERSION:-}}" ] && [ -r {location} ]; then
    . {location}
fi
"""
    login = next(
        (
            home / name
            for name in (".bash_profile", ".bash_login", ".profile")
            if (home / name).exists()
        ),
        home / ".bash_profile",
    )
    plan = {script: bash, home / ".bashrc": loader, login: loader}
    powershell = powershell_source(sources["powershell"], executable)
    for path in [*powershell_profiles(), *extra_profiles]:
        plan[path] = powershell
    # Canonical paths also deduplicate redirected/symlinked profile names.
    plan = {path.expanduser().resolve(): source for path, source in plan.items()}
    for path, source in plan.items():
        update_profile(path, source, dry_run=True)
    return [(path, update_profile(path, source)) for path, source in plan.items()]
