"""Install and run repository hooks without changing project configuration."""

from collections.abc import Callable
from pathlib import Path

from ...domain.errors import PtkError
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

    @staticmethod
    def command_config(project: Project) -> Path:
        """Explicit commands also work when automatic installation is disabled."""
        spec = project.config.configs.get("pre-commit")
        return project.root / (
            spec.output if spec and spec.output else ".pre-commit-config.yaml"
        )

    def inspect(self, project: Project) -> HookStatus:
        return self._hooks.status(project.root, self.command_config(project))

    def install(self, project: Project, out: Callable[[str], None]) -> None:
        self._hooks.ensure(project.root, self.command_config(project), out)

    def uninstall(self, project: Project, out: Callable[[str], None]) -> None:
        self._hooks.uninstall(project.root, self.command_config(project), out)

    def _command(
        self, project: Project, args: list[str], out: Callable[[str], None]
    ) -> int:
        result = self._hooks.run(project.root, self.command_config(project), args, out)
        if result.error or result.timed_out:
            raise PtkError(result.error or "pre-commit timed out")
        return result.exit_code

    def validate(self, project: Project, out: Callable[[str], None]) -> int:
        return self._command(project, ["validate-config"], out)

    def run(
        self,
        project: Project,
        out: Callable[[str], None],
        *,
        hook: str | None = None,
        all_files: bool = False,
        files: tuple[str, ...] = (),
        from_ref: str | None = None,
        to_ref: str | None = None,
        hook_stage: str | None = None,
        show_diff_on_failure: bool = False,
        verbose: bool = False,
    ) -> int:
        if bool(from_ref) != bool(to_ref):
            raise PtkError("--from-ref and --to-ref must be supplied together")
        if sum((all_files, bool(files), bool(from_ref))) > 1:
            raise PtkError(
                "Choose only one of --all-files, --file or --from-ref/--to-ref"
            )
        args = ["run"]
        if all_files:
            args.append("--all-files")
        if from_ref:
            args.extend([f"--from-ref={from_ref}", f"--to-ref={to_ref}"])
        if hook_stage:
            args.append(f"--hook-stage={hook_stage}")
        if show_diff_on_failure:
            args.append("--show-diff-on-failure")
        if verbose:
            args.append("--verbose")
        if files:
            paths = []
            for file in files:
                path = (project.root / file).resolve()
                if not path.is_relative_to(project.root.resolve()):
                    raise PtkError(
                        f"pre-commit file must be inside the repository: {file}"
                    )
                relative = path.relative_to(project.root.resolve()).as_posix()
                paths.append("./" + relative if relative.startswith("-") else relative)
            args.extend(["--files", *paths])
        if hook:
            args.extend(["--", hook])
        return self._command(project, args, out)
