"""Workflow boundaries and the shared live transcript of its child jobs."""

import threading

from ... import __version__
from ...adapters.logging.transcript import RunTranscript, TranscriptFile
from ...domain import run_output as display
from ...domain.logging import Level
from .console import print_block


class WorkflowOutput:
    def __init__(self, console, plan, target, run_id, root, owner, variant):
        self.console, self.plan = console, plan
        self.path = target / "workflow.log"
        self.file = TranscriptFile(self.path)
        self.identity = display.prefix(
            plan.name, variant if owner is not None else "workspace"
        )
        self._failures = {}
        self._lock = threading.Lock()
        self.qualify = owner is None or any(
            node.prepared.project.root != owner.root for node in plan.jobs
        )
        rows = []
        if owner is not None:
            rows.append(
                f"Owner: {owner.config.project.name} ({owner.config.repository.alias})"
            )
            rows.append(f"Owner variant: {variant or 'default (no variant model)'}")
        else:
            rows.append(f"Workspace: {root}")
        rows.extend(
            [
                f"PTK: {__version__} | Run: {run_id}",
                f"Jobs: {len(plan.jobs)} | Max concurrent: {plan.spec.max_workers}",
            ]
        )
        seen = set()
        for node in plan.jobs:
            prepared = node.prepared
            p = prepared.plan
            version = display.project_version(p)
            key = (node.repo, p.variant, version)
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                prepared.mask(
                    f"Repository: {node.repo} | Project: {p.project} | Project version: {version} | Variant: {display.variant_label(p)}"
                )
            )
        self.rows = [display.one_line(row) for row in rows]

    def start(self):
        self.block(
            display.start_block(
                "WORKFLOW",
                self.identity,
                self.rows,
                width=self.console.width,
            )
        )

    def block(self, block):
        print_block(self.console, block)
        self.file.write(display.plain(block))

    def job_label(self, node):
        job = node.prepared.plan.job
        return f"{node.repo}:{job}" if self.qualify else job

    def observer(self, node, *, verbose=0):
        return RunTranscript(
            self.file.write,
            level=Level.TRACE if verbose >= 2 else Level.DEBUG,
            job_label=self.job_label(node),
        )

    def job_finished(self, node, result):
        failures = display.job_failures(
            result,
            self.job_label(node),
            allowed=node.spec.continue_on_error,
        )
        with self._lock:
            self._failures[node.id] = failures

    def finish(self, result):
        entries, failures = [], []
        for job in result.jobs:
            identity = display.prefix(
                job.repo + ":" + job.job if self.qualify else job.job,
                job.variant,
            )
            detail = f"invocation: {job.id}"
            if job.report_errors and job.status == "passed":
                detail += "; report findings (see report)"
            item = display.entry(identity, job, detail=detail, kind="JOB")
            entries.append(item)
            failed_steps = self._failures.get(job.id, [])
            failures.extend(failed_steps)
            if job.status == "failed" and not failed_steps:
                failures.append(item)
        self.block(
            display.summary_block(
                "WORKFLOW",
                self.identity,
                result,
                entries,
                failures=failures,
                log_file=self.path,
                width=self.console.width,
            )
        )

    def close(self):
        self.file.close()
