"""Preflight and schedule action calls while preserving repository boundaries."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from ...domain.errors import PtkError
from ...domain.execution.model import Status
from ...domain.workflows import WorkflowNode, WorkflowSpec
from .run import Cancelled, PreparedRun


@dataclass
class PlannedCall:
    path: tuple[str, ...]
    spec: WorkflowNode
    repo: str = ""
    prepared: PreparedRun | None = None
    children: list[PlannedCall] = field(default_factory=list)

    def walk(self):
        yield self
        for child in self.children:
            yield from child.walk()

    @property
    def resources(self):
        assert self.prepared is not None
        p = self.prepared
        resources = {
            (
                "action",
                str(p.project.root.resolve()),
                p.plan.variant or "default",
                p.plan.action,
            )
        }
        for step in p.plan.walk():
            python = step.spec.python
            if python is not None and python.project is not None:
                resources.add(
                    (
                        "uv project environment",
                        str((p.project.root / python.project).resolve()),
                    )
                )
        return resources


@dataclass
class WorkflowPlan:
    name: str
    spec: WorkflowSpec
    steps: list[PlannedCall]

    def walk(self):
        for step in self.steps:
            yield from step.walk()


class PrepareWorkflow:
    def execute(self, name: str, spec: WorkflowSpec, prepare: Callable) -> WorkflowPlan:
        def visit(node, parent=()):
            path = (*parent, node.name)
            planned = PlannedCall(path, node)
            if node.steps is not None:
                planned.children = [visit(child, path) for child in node.steps]
                validate_parallel(planned.children, node.parallel)
            else:
                try:
                    planned.repo, planned.prepared = prepare(node, path)
                except PtkError as exc:
                    raise PtkError(
                        f"workflow {name}, {'/'.join(path)}: {exc}"
                    ) from None
            return planned

        steps = [visit(node) for node in spec.steps]
        validate_parallel(steps, spec.parallel)
        return WorkflowPlan(name, spec, steps)


def validate_parallel(nodes: list[PlannedCall], parallel: bool) -> None:
    if not parallel:
        return
    seen = set()
    for node in nodes:
        keys = set().union(
            *(call.resources for call in node.walk() if call.prepared is not None)
        )
        overlap = seen & keys
        if overlap:
            resource = next(iter(overlap))
            raise PtkError(
                "parallel workflow branches share "
                + "/".join(resource)
                + "; sequence these calls to protect their outputs and environments"
            )
        seen.update(keys)


@dataclass
class CallOutcome:
    status: Status
    reports: list[str] = field(default_factory=list)
    run_id: str = ""


@dataclass
class WorkflowStepResult:
    path: str
    status: Status
    repo: str = ""
    action: str = ""
    variant: str | None = None
    start: float = 0
    duration: float = 0
    allowed_failure: bool = False
    message: str = ""
    reports: list[str] = field(default_factory=list)
    run_id: str = ""
    children: list[WorkflowStepResult] = field(default_factory=list)

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
    steps: list[WorkflowStepResult]


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
        slots = threading.Semaphore(plan.spec.max_workers)

        def record(node, status, message=""):
            prepared = node.prepared
            return WorkflowStepResult(
                path="/".join(node.path),
                status=status,
                repo=node.repo,
                action=prepared.plan.action if prepared else "",
                variant=prepared.plan.variant if prepared else None,
                start=time.monotonic() - started,
                message=message,
            )

        def skip(node, status, message):
            result = record(node, status, message)
            result.children = [skip(child, status, message) for child in node.children]
            return result

        def sequence(nodes, parallel):
            if parallel:
                with ThreadPoolExecutor(
                    max_workers=min(len(nodes), plan.spec.max_workers)
                ) as pool:
                    futures = [pool.submit(visit, node) for node in nodes]
                    return [future.result() for future in futures]
            results = []
            blocked = False
            for node in nodes:
                if cancel.is_set():
                    results.append(skip(node, Status.CANCELLED, "workflow cancelled"))
                elif blocked:
                    results.append(
                        skip(node, Status.SKIPPED, "previous workflow step failed")
                    )
                else:
                    result = visit(node)
                    results.append(result)
                    blocked = result.failed
            return results

        def visit(node):
            if cancel.is_set():
                return skip(node, Status.CANCELLED, "workflow cancelled")
            result = record(node, Status.PENDING)
            if node.children:
                result.children = sequence(node.children, node.spec.parallel)
                result.status = combine(result.children)
            else:
                while not slots.acquire(timeout=0.1):
                    if cancel.is_set():
                        return skip(node, Status.CANCELLED, "workflow cancelled")
                try:
                    if cancel.is_set():
                        return skip(node, Status.CANCELLED, "workflow cancelled")
                    result.start = time.monotonic() - started
                    outcome = run(node, cancel)
                    result.status, result.reports, result.run_id = (
                        outcome.status,
                        outcome.reports,
                        outcome.run_id,
                    )
                except (PtkError, OSError, ValueError) as exc:
                    result.status, result.message = Status.FAILED, str(exc)
                finally:
                    slots.release()
            result.duration = time.monotonic() - started - result.start
            result.allowed_failure = (
                node.spec.continue_on_error and result.status == Status.FAILED
            )
            return result

        results = sequence(plan.steps, plan.spec.parallel)
        status = Status.CANCELLED if cancel.is_set() else combine(results)
        return WorkflowResult(plan.name, status, time.monotonic() - started, results)
