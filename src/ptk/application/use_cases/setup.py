"""Diagnose the local development environment with ``ptk self-service doctor``."""

from __future__ import annotations

import platform
from dataclasses import dataclass

from ...domain.errors import PtkError
from ...domain.execution.model import CommandSpec
from ..ports import HostEnvironment, ProcessRunner
from .configs import SharedConfigs
from .credentials import CredentialService
from .hooks import EnsureHooks
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

    def user_id(self) -> str | None:
        return self._host.user_id()


class Doctor:
    def __init__(
        self,
        env: Environment,
        tools: ToolService,
        configs: SharedConfigs,
        version: str,
        hooks: EnsureHooks,
    ):
        self._env = env
        self._tools = tools
        self._configs = configs
        self._version = version
        self._hooks = hooks

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
        checks.append(
            Check(
                "role",
                OK,
                f"{role}; user ID: {self._env.user_id() or 'unknown'}; list: {project.config_root / 'maintainers.ptk.yml'}",
            )
        )
        for status in self._tools.status(project):
            checks.append(
                Check(f"tool {status.name}", OK, status.version or "found")
                if status.ok
                else Check(
                    f"tool {status.name}",
                    FAIL,
                    status.problem,
                    f"ptk self-service tools (or install {status.name} yourself)",
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
                        f"ptk self-service creds set {row.key.credential} {row.key.field}",
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
                        "" if state == OK else "ptk maintainer sync configs",
                    )
                )
        except PtkError as exc:
            checks.append(Check("configs", FAIL, str(exc)))
        try:
            hooks = self._hooks.status(project)
            if hooks is not None:
                checks.append(
                    Check(
                        "pre-commit hook",
                        OK if hooks.installed else WARN,
                        hooks.detail,
                        ""
                        if hooks.installed
                        else "run a local PTK job to install the configured hooks",
                    )
                )
        except PtkError as exc:
            checks.append(Check("pre-commit hook", FAIL, str(exc)))
        return checks
