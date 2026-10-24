"""Turn a planned ``run:`` step into a concrete command (pure).

| run                         | executed as                                         |
|-----------------------------|-----------------------------------------------------|
| list ``[cmd, arg, ...]``    | directly, no shell                                  |
| string                      | platform shell (``/bin/sh -c`` / ``cmd.exe /c``)    |
| ``x.bat`` / ``x.cmd``       | ``cmd /c x.bat ...``                                |
| ``x.ps1``                   | ``pwsh -NoProfile -ExecutionPolicy Bypass -File``   |
| ``x.sh``                    | ``bash x.sh ...``                                   |
| ``x.py``                    | Python through uv (see :class:`PythonRuntime`)      |

A string whose first word is a script, or any run of a step with ``python:``,
is split into words and executed without a shell.
"""

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass, field

from .environment import prepend_path
from .model import CommandSpec, PlannedStep

SCRIPT_SUFFIXES = (".bat", ".cmd", ".ps1", ".sh", ".py")
SHELL_OPERATORS = re.compile(r"&&|\|\||[|;<>]")


@dataclass(frozen=True)
class PythonRuntime:
    """How to run Python scripts and commands for one ``python:`` setting."""

    description: str
    script_prefix: list[str]  # + script.py args
    command_prefix: list[str] = field(
        default_factory=list
    )  # + cmd args (empty: run as is)
    path_prepend: str | None = None  # directory put first on PATH
    env: dict[str, str] = field(default_factory=dict)


def split_words(text: str, os_name: str) -> list[str]:
    if os_name == "windows":  # keep backslashes of Windows paths
        text = text.replace("\\", "\\\\")
    return shlex.split(text)


def script_suffix(word: str) -> str | None:
    lower = word.lower()
    return next((s for s in SCRIPT_SUFFIXES if lower.endswith(s)), None)


def build_command(
    step: PlannedStep,
    *,
    env: dict[str, str],
    cwd: str,
    os_name: str,
    python: PythonRuntime | None,
    powershell: str = "pwsh",
    plain_python: PythonRuntime | None = None,
) -> CommandSpec:
    """``python`` is the runtime of the step's ``python:`` setting; ``plain_python``
    runs ``*.py`` scripts of steps without one (default: ``uv run --no-project``)."""
    run = step.run
    if run is None:
        raise ValueError(f"step '{step.label}' has nothing to run")
    timeout = step.spec.timeout
    if isinstance(run, str):
        words = split_words(run, os_name)
        if not words:
            raise ValueError(f"step '{step.label}': empty command")
        if python is None and (
            script_suffix(words[0]) is None or SHELL_OPERATORS.search(run)
        ):
            return CommandSpec(shell=run, cwd=cwd, env=env, timeout=timeout)
        argv = words
    else:
        argv = list(run)
        if not argv:
            raise ValueError(f"step '{step.label}': empty command")

    suffix = script_suffix(argv[0])
    if python is not None:
        env = {**env, **python.env}
        if python.path_prepend:
            env = prepend_path(env, python.path_prepend, os_name=os_name)
        argv = (
            [*python.script_prefix, *argv]
            if suffix == ".py"
            else [*python.command_prefix, *argv]
        )
    elif suffix == ".py":
        prefix = (
            plain_python.script_prefix
            if plain_python
            else ["uv", "run", "--no-project"]
        )
        argv = [*prefix, *argv]
    elif suffix in (".bat", ".cmd"):
        argv = ["cmd", "/c", *argv]
    elif suffix == ".ps1":
        argv = [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", *argv]
    elif suffix == ".sh":
        argv = ["bash", *argv]
    return CommandSpec(argv=argv, cwd=cwd, env=env, timeout=timeout)
