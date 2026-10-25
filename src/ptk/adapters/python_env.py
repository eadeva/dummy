"""PythonEnvManager adapter: uv is the Python manager.

| python:                 | scripts (x.py)                              | commands                    |
|-------------------------|---------------------------------------------|-----------------------------|
| (none)                  | ``uv run --no-project x.py`` (PEP 723 ok)   | as is                       |
| ``uvx: pkg``            | ``uv run --no-project --with pkg python x.py`` | ``uv tool run --from pkg``  |
| ``venv: {...}``         | ``<venv>/bin/python x.py``                  | venv first on PATH          |
| ``project: dir``        | ``uv run --project dir python x.py``        | ``uv run --project dir``    |
| ``interpreter: cli``    | ptk's own interpreter                       | its folder first on PATH    |

Venvs are cached in ``.ptk/venvs/<hash>``; the hash covers the Python request,
the content of the requirement files and the package list, so changing a
requirement file creates a fresh environment. Nothing is "activated" and ptk's
own process is never touched.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
from collections.abc import Callable
from pathlib import Path

from ..application.ports import ProcessRunner
from ..domain.config.model import PythonSpec, VenvSpec
from ..domain.errors import PtkError
from ..domain.execution.commands import PythonRuntime
from ..domain.execution.model import CommandSpec

WINDOWS = sys.platform.startswith("win")
MARKER = ".ptk-complete"


def find_uv(environ: dict[str, str] | None = None) -> str:
    environ = environ if environ is not None else dict(os.environ)
    if environ.get("PTK_UV"):
        return environ["PTK_UV"]
    found = shutil.which("uv")
    if found:
        return found
    for candidate in (
        Path.home() / ".local" / "bin" / ("uv.exe" if WINDOWS else "uv"),
        Path.home() / ".cargo" / "bin" / ("uv.exe" if WINDOWS else "uv"),
    ):
        if candidate.is_file():
            return str(candidate)
    return "uv"


def venv_python(venv: Path) -> Path:
    return venv / ("Scripts/python.exe" if WINDOWS else "bin/python")


def venv_bin(venv: Path) -> Path:
    return venv / ("Scripts" if WINDOWS else "bin")


class UvPythonEnvManager:
    def __init__(
        self,
        runner: ProcessRunner,
        *,
        uv: str | None = None,
        cache_dir: str = ".ptk/venvs",
        environ: dict[str, str] | None = None,
    ):
        self._runner = runner
        self._uv = uv or find_uv(environ)
        self._cache_dir = cache_dir
        self._environ = dict(os.environ if environ is None else environ)

    def runtime(
        self,
        spec: PythonSpec | None,
        root: Path,
        *,
        create: bool,
        on_output: Callable[[str], None] | None = None,
    ) -> PythonRuntime | None:
        uv = self._uv
        if spec is None:
            return PythonRuntime(
                "uv run (script dependencies from PEP 723 header)",
                script_prefix=[uv, "run", "--no-project"],
            )
        if spec.uvx is not None:
            withs = [a for pkg in spec.with_ for a in ("--with", pkg)]
            return PythonRuntime(
                f"uvx {spec.uvx}"
                + (f" + {', '.join(spec.with_)}" if spec.with_ else ""),
                script_prefix=[
                    uv,
                    "run",
                    "--no-project",
                    "--with",
                    spec.uvx,
                    *withs,
                    "python",
                ],
                command_prefix=[uv, "tool", "run", "--from", spec.uvx, *withs],
            )
        if spec.project is not None:
            project = str((root / spec.project).resolve())
            groups = [arg for name in spec.groups for arg in ("--group", name)]
            prefix = [uv, "run", "--project", project, *groups]
            return PythonRuntime(
                f"uv project {spec.project}"
                + (f" (groups: {', '.join(spec.groups)})" if spec.groups else ""),
                script_prefix=[*prefix, "python"],
                command_prefix=prefix,
            )
        if spec.interpreter == "cli":
            return PythonRuntime(
                "ptk's own interpreter",
                script_prefix=[sys.executable],
                path_prepend=str(Path(sys.executable).parent),
            )
        assert spec.venv is not None
        venv = self.venv_path(spec.venv, root)
        if create:
            self._ensure_venv(spec.venv, venv, root, on_output or (lambda _l: None))
        state = "cached" if (venv / MARKER).is_file() else "to be created"
        return PythonRuntime(
            f"venv {venv.name} ({state})",
            script_prefix=[str(venv_python(venv))],
            path_prepend=str(venv_bin(venv)),
            env={"VIRTUAL_ENV": str(venv)},
        )

    # -- venvs -------------------------------------------------------------------------

    def venv_path(self, spec: VenvSpec, root: Path) -> Path:
        digest = hashlib.sha256()
        payload = {
            "python": spec.python,
            "packages": sorted(spec.packages),
            "requirements": [],
        }
        for req in spec.requirements:
            file = root / req
            if not file.is_file():
                raise PtkError(f"requirements file not found: {req}")
            payload["requirements"].append(
                [req, hashlib.sha256(file.read_bytes()).hexdigest()]
            )
        digest.update(json.dumps(payload, sort_keys=True).encode())
        return root / self._cache_dir / digest.hexdigest()[:16]

    def _ensure_venv(
        self, spec: VenvSpec, venv: Path, root: Path, out: Callable[[str], None]
    ) -> None:
        if (venv / MARKER).is_file():
            return
        if venv.exists():
            shutil.rmtree(venv)  # incomplete leftover of an interrupted run
        venv.parent.mkdir(parents=True, exist_ok=True)
        out(f"ptk: creating Python environment {venv}")
        create = [self._uv, "venv", str(venv), "--quiet"]
        if spec.python:
            create += ["--python", spec.python]
        self._uv_call(create, root, out)
        if spec.requirements or spec.packages:
            install = [self._uv, "pip", "install", "--python", str(venv_python(venv))]
            for req in spec.requirements:
                install += ["-r", str(root / req)]
            install += list(spec.packages)
            self._uv_call(install, root, out)
        (venv / MARKER).write_text(
            json.dumps(
                {
                    "python": spec.python,
                    "requirements": spec.requirements,
                    "packages": spec.packages,
                }
            )
        )

    def _uv_call(self, argv: list[str], root: Path, out: Callable[[str], None]) -> None:
        outcome = self._runner.run(
            CommandSpec(argv=argv, cwd=str(root), env=self._environ), out
        )
        if outcome.exit_code != 0:
            raise PtkError(
                f"uv failed ({outcome.error or f'exit code {outcome.exit_code}'}): {' '.join(argv)}"
            )
