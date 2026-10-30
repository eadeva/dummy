"""Preflight and schedule job calls while preserving repository boundaries."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from ...domain.errors import PtkError
from ...domain.execution.model import Status
from ...domain.workflows import WorkflowJob, WorkflowSpec
from ..scheduling import schedule
from .run import Cancelled, PreparedRun


@dataclass
class PlannedCall:
    id: str
    spec: WorkflowJob
    repo: str
    prepared: PreparedRun

    @property
    def resources(self):
        p = self.prepared
        resources = {
            (
                "job",
                str(p.project.root.resolve()),
                p.plan.variant or "default",
                p.plan.job,
            )
        }
        for step in p.plan.walk():
            python = step.spec.python
            if python is not None and python.project is not None:
                project = (p.project.root / python.project).resolve()
                environment = {**p.plan.base_env, **step.env}
                venv = Path(environment.get("UV_PROJECT_ENVIRONMENT") or ".venv")
                # Explicit absolute paths also support projects in uv workspaces.
                # Resolve ordinary relative paths from the selected project.
                if not venv.is_absolute():
                    venv = project / venv
                resources.add(
                    (
                        "uv project environment",
                        str(venv.resolve()),
                    )
                )
        return resources


@dataclass
class WorkflowPlan:
    name: str
    spec: WorkflowSpec
    jobs: list[PlannedCall]


class PrepareWorkflow:
    def execute(self, name: str, spec: WorkflowSpec, prepare: Callable) -> WorkflowPlan:
        jobs = []
        for invocation, job in spec.jobs.items():
            try:
                repo, prepared = prepare(job, invocation)
            except PtkError as exc:
                raise PtkError(f"workflow {name}, {invocation}: {exc}") from None
            jobs.append(PlannedCall(invocation, job, repo, prepared))
        validate_resources(jobs, spec.ancestors())
        return WorkflowPlan(name, spec, jobs)


def validate_resources(jobs: list[PlannedCall], ancestors: dict[str, set[str]]) -> None:
    resources = {job.id: job.resources for job in jobs}
    for index, job in enumerate(jobs):
        for other in jobs[:index]:
            if other.id in ancestors[job.id] or job.id in ancestors[other.id]:
                continue
            overlap = resources[job.id] & resources[other.id]
            if overlap:
                raise PtkError(
                    f"workflow jobs {other.id!r} and {job.id!r} can run concurrently and share "
                    + "/".join(min(overlap))
                    + "; add a needs dependency or isolate their outputs and environments"
                )


@dataclass
class CallOutcome:
    status: Status
    reports: list[str] = field(default_factory=list)
    run_id: str = ""
    report_errors: bool = False


@dataclass
class WorkflowJobResult:
    id: str
    status: Status
    repo: str = ""
    job: str = ""
    variant: str | None = None
    start: float = 0
    duration: float = 0
    allowed_failure: bool = False
    message: str = ""
    reports: list[str] = field(default_factory=list)
    run_id: str = ""
    report_errors: bool = False
    needs: list[str] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return self.status == Status.FAILED or self.report_errors

    @property
    def failed(self):
        return (
            self.status in (Status.FAILED, Status.CANCELLED)
            and not self.allowed_failure
        )


@dataclass
class WorkflowResult:
    name: str
    status: Status
    duration: float
    jobs: list[WorkflowJobResult]

    @property
    def has_errors(self) -> bool:
        return self.status == Status.FAILED or any(job.has_errors for job in self.jobs)


def combine(results):
    if any(r.status == Status.CANCELLED and not r.allowed_failure for r in results):
        return Status.CANCELLED
    if any(r.failed for r in results):
        return Status.FAILED
    if results and all(r.status == Status.SKIPPED for r in results):
        return Status.SKIPPED
    return Status.PASSED


class RunWorkflow:
    def execute(
        self, plan: WorkflowPlan, run: Callable, cancel: Cancelled
    ) -> WorkflowResult:
        started = time.monotonic()

        def record(node, status, message=""):
            prepared = node.prepared
            return WorkflowJobResult(
                id=node.id,
                status=status,
                repo=node.repo,
                job=prepared.plan.job,
                variant=prepared.plan.variant,
                start=time.monotonic() - started,
                message=message,
                needs=list(node.spec.needs),
            )

        def visit(node):
            if cancel.is_set():
                return record(node, Status.CANCELLED, "workflow cancelled")
            result = record(node, Status.PENDING)
            try:
                outcome = run(node, cancel)
                result.status, result.reports, result.run_id = (
                    outcome.status,
                    outcome.reports,
                    outcome.run_id,
                )
                result.report_errors = outcome.report_errors
            except (PtkError, OSError, ValueError) as exc:
                result.status, result.message = Status.FAILED, str(exc)
            result.duration = time.monotonic() - started - result.start
            result.allowed_failure = (
                node.spec.continue_on_error and result.status == Status.FAILED
            )
            return result

        results = schedule(
            {job.id: job for job in plan.jobs},
            {job.id: job.spec.needs for job in plan.jobs},
            visit,
            record,
            cancel,
            plan.spec.max_workers,
        )
        status = Status.CANCELLED if cancel.is_set() else combine(results)
        return WorkflowResult(plan.name, status, time.monotonic() - started, results)
