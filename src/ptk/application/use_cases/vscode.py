"""Create or update VS Code tasks for the configured jobs (use case)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from ...domain import vscode
from ...domain.variants import rules as vr
from ..ports import TasksFile
from .project import Project
from .role import Role, visible


@dataclass
class TasksResult:
    path: Path
    up_to_date: bool
    written: bool
    lost_comments: bool
    labels: list[str] = field(default_factory=list)


class VSCodeTasks:
    def __init__(self, open_file: Callable[[Path], TasksFile]):
        self._open = open_file

    def execute(
        self,
        project: Project,
        role: Role,
        *,
        command: str = "ptk",
        users_only: bool = False,
        check: bool = False,
        path: Path | None = None,
        cwd: Path | None = None,
        repository_alias: str | None = None,
    ) -> TasksResult:
        config = project.config
        audience: Role = "user" if users_only else role
        jobs = [
            vscode.TaskJob(
                name=name,
                help=spec.help,
                is_default=name == config.project.default_job,
                passthrough=any(s.passthrough for s in spec.walk_steps()),
            )
            for name, spec in config.jobs.items()
            if visible(spec.audience, audience)
        ]
        variants: list[str] = []
        default_variant = None
        if config.variants is not None:
            variants = list(config.variants.buildable())
            default_variant = vr.default_variant(config.variants)
        tasks, inputs = vscode.build_tasks(
            jobs,
            command=command,
            variants=variants,
            default_variant=default_variant,
            repository_alias=repository_alias,
        )
        tasks.extend(
            vscode.workflow_tasks(
                [
                    (name, spec.help)
                    for name, spec in config.workflows.items()
                    if visible(spec.audience, audience)
                    and visible(
                        config.command_audience.get("workflow", "all"), audience
                    )
                ],
                command=command,
                repository_alias=repository_alias,
            )
        )
        if cwd is not None:
            for task in tasks:
                task["options"] = {"cwd": str(cwd)}
        return self._save(
            tasks, inputs, path or project.root / ".vscode" / "tasks.json", check
        )

    def workflows(
        self, workflows, *, root: Path, command="ptk", path=None, check=False
    ):
        tasks = vscode.workflow_tasks(workflows, command=command)
        for task in tasks:
            task["options"] = {"cwd": str(root)}
        return self._save(tasks, [], path or root / ".vscode" / "tasks.json", check)

    def _save(self, tasks, inputs, path, check):
        file = self._open(path)
        current = file.read()
        merged = vscode.merge(current, tasks, inputs)
        up_to_date = current is not None and merged == current
        written = False
        if not check and not up_to_date:
            file.write(merged)
            written = True
        return TasksResult(
            path=file.path,
            up_to_date=up_to_date,
            written=written,
            lost_comments=written and file.had_comments,
            labels=[t["label"] for t in tasks],
        )
