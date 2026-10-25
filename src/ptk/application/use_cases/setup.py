"""``ptk setup doctor`` (diagnose) and ``ptk setup self`` (get a machine ready)."""

from __future__ import annotations

import platform
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from ...domain.errors import PtkError
from ...domain.execution.model import CommandSpec
from ..ports import HostEnvironment, ProcessRunner
from .configs import SharedConfigs
from .credentials import CredentialService
from .project import Project
from .role import Role
from .tools import ToolService

OK, WARN, FAIL = "ok", "warning", "problem"


@dataclass
class Check:
    area: str
    status: str  # ok | warning | problem
    detail: str
    fix: str = ""


class Environment:
    """Facts about programs on this machine (via the process runner)."""

    def __init__(self, host: HostEnvironment, runner: ProcessRunner, uv: str):
        self._host = host
        self._runner = runner
        self.uv = uv

    def output(self, argv: list[str], cwd: str = ".") -> str | None:
        lines: list[str] = []
        outcome = self._runner.run(
            CommandSpec(argv=argv, cwd=cwd, env=dict(self._host.variables), timeout=30),
            lines.append,
        )
        return "\n".join(lines).strip() if outcome.exit_code == 0 else None


class Doctor:
    def __init__(
        self, env: Environment, tools: ToolService, configs: SharedConfigs, version: str
    ):
        self._env = env
        self._tools = tools
        self._configs = configs
        self._version = version

    def run(
        self,
        project: Project | None,
        project_error: str | None,
        credentials: CredentialService | None,
        role: Role,
        *,
        include_machine: bool = True,
    ) -> list[Check]:
        checks = []
        if include_machine:
            checks = [
                Check(
                    "ptk", OK, f"{self._version} on Python {platform.python_version()}"
                ),
            ]
            uv = self._env.output([self._env.uv, "--version"])
            checks.append(
                Check("uv", OK, uv)
                if uv
                else Check(
                    "uv", FAIL, "not found", "install uv: https://docs.astral.sh/uv/"
                )
            )
            git = self._env.output(["git", "--version"])
            if git is None:
                checks.append(Check("git", FAIL, "not found", "install git"))
            else:
                email = self._env.output(
                    ["git", "config", "user.email"],
                    cwd=str(project.root) if project else ".",
                )
                checks.append(
                    Check("git", OK, f"{git}, user.email {email}")
                    if email
                    else Check(
                        "git",
                        WARN,
                        f"{git}, no user.email",
                        'git config --global user.email "..."',
                    )
                )
        if project is None:
            checks.append(
                Check("configuration", FAIL, project_error or "no project found")
            )
            return checks
        checks.append(
            Check(
                "configuration",
                WARN if project.warnings else OK,
                f"{project.main_file} ({len(project.files)} files, {len(project.warnings)} warnings)",
            )
        )
        checks.append(Check("role", OK, role))
        for status in self._tools.status(project):
            checks.append(
                Check(f"tool {status.name}", OK, status.version or "found")
                if status.ok
                else Check(
                    f"tool {status.name}",
                    FAIL,
                    status.problem,
                    f"ptk setup (or install {status.name} yourself)",
                )
            )
        if credentials is not None:
            for row in credentials.status():
                checks.append(
                    Check(f"credential {row.key.ref}", OK, f"from {row.provider}")
                    if row.provider
                    else Check(
                        f"credential {row.key.ref}",
                        WARN,
                        "not available",
                        f"ptk setup creds set {row.key.credential} {row.key.field}",
                    )
                )
        try:
            for item in self._configs.plan(project):
                state = OK if item.status == "up to date" else WARN
                checks.append(
                    Check(
                        f"config {item.path.name}",
                        state,
                        item.status,
                        "" if state == OK else "ptk setup configs sync",
                    )
                )
        except PtkError as exc:
            checks.append(Check("configs", FAIL, str(exc)))
        if "pre-commit" in project.config.configs and (project.root / ".git").is_dir():
            hook = project.root / ".git" / "hooks" / "pre-commit"
            checks.append(
                Check("pre-commit hook", OK, "installed")
                if hook.is_file()
                else Check("pre-commit hook", WARN, "not installed", "ptk setup self")
            )
        return checks


class SelfSetup:
    def __init__(self, env: Environment, tools: ToolService, configs: SharedConfigs):
        self._env = env
        self._tools = tools
        self._configs = configs

    def run(
        self,
        project: Project,
        credentials: CredentialService,
        *,
        install_tools: bool,
        allow_system: bool,
        out: Callable[[str], None],
    ) -> list[Check]:
        checks: list[Check] = []
        for name, argv in (
            ("uv", [self._env.uv, "--version"]),
            ("git", ["git", "--version"]),
        ):
            found = self._env.output(argv)
            checks.append(
                Check(name, OK, found)
                if found
                else Check(name, FAIL, "not found", f"install {name}")
            )
        if project.config.configs:
            items = self._configs.sync(project)
            changed = [i.path.name for i in items if i.status != "up to date"]
            checks.append(
                Check(
                    "shared configs",
                    OK,
                    f"updated {', '.join(changed)}" if changed else "up to date",
                )
            )
        if "pre-commit" in project.config.configs:
            checks.append(self._pre_commit(project.root, out))
        if install_tools and project.config.tools:
            for result in self._tools.setup(
                project, list(project.config.tools), allow_system=allow_system, out=out
            ):
                checks.append(
                    Check(
                        f"tool {result.name}", OK if result.ok else FAIL, result.outcome
                    )
                )
        for row in credentials.status():
            if row.provider is None:
                checks.append(
                    Check(
                        f"credential {row.key.ref}",
                        WARN,
                        "not available",
                        f"ptk setup creds set {row.key.credential} {row.key.field}",
                    )
                )
        return checks

    def _pre_commit(self, root: Path, out: Callable[[str], None]) -> Check:
        if not (root / ".git").is_dir():
            return Check("pre-commit hook", WARN, "not a git repository - skipped")
        installed = self._env.output(
            [self._env.uv, "tool", "run", "pre-commit", "install"], cwd=str(root)
        )
        if installed is None:
            return Check(
                "pre-commit hook",
                FAIL,
                "installation failed",
                "uv tool run pre-commit install",
            )
        out(installed)
        return Check("pre-commit hook", OK, "installed")
