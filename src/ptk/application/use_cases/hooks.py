"""Install the configured local hooks without changing project configuration."""

from collections.abc import Callable
from pathlib import Path

from ..ports import HookStatus, RepositoryHooks
from .project import Project


class EnsureHooks:
    def __init__(self, hooks: RepositoryHooks):
        self._hooks = hooks

    @staticmethod
    def config(project: Project) -> Path | None:
        spec = project.config.configs.get("pre-commit")
        if spec is None or not spec.enabled:
            return None
        return project.root / (spec.output or ".pre-commit-config.yaml")

    def status(self, project: Project) -> HookStatus | None:
        config = self.config(project)
        return self._hooks.status(project.root, config) if config else None

    def execute(self, project: Project, out: Callable[[str], None]) -> None:
        config = self.config(project)
        if config is not None and not project.ci:
            self._hooks.ensure(project.root, config, out)
