"""Workflow boundaries and the shared live transcript of its child jobs."""

from ... import __version__
from ...adapters.logging.transcript import RunTranscript, TranscriptFile
from ...domain import run_output as display
from ...domain.logging import Level
from .console import header


class WorkflowOutput:
    def __init__(self, console, plan, target, run_id, root, owner, variant):
        self.console, self.plan = console, plan
        self.path = target / "workflow.log"
        self.file = TranscriptFile(self.path)
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
        header(self.console, "WORKFLOW", self.plan.name, "START", self.rows)
        self.file.write(
            "\n".join(
                [display.boundary("WORKFLOW", self.plan.name, "START"), *self.rows]
            )
        )

    def job_label(self, node):
        job = node.prepared.plan.job
        return f"{node.repo}:{job}" if self.qualify else job

    def observer(self, node, *, verbose=0):
        return RunTranscript(
            self.file.write,
            level=Level.TRACE if verbose >= 2 else Level.DEBUG,
            job_label=self.job_label(node),
        )

    def finish(self, result):
        state = f"{str(result.status).upper()} | {result.duration:.1f}s"
        rows = [display.counts("Jobs", result.jobs)]
        for job in result.jobs:
            rows.append(
                f"{job.id}: {display.prefix(job.repo + ':' + job.job, job.variant)} {display.outcome(job)}"
                + (f" | {display.one_line(job.message)}" if job.message else "")
            )
        rows.append(f"Log: {self.path}")
        header(
            self.console, "WORKFLOW", self.plan.name, state, rows, status=result.status
        )
        self.file.write(
            "\n".join([display.boundary("WORKFLOW", self.plan.name, state), *rows])
        )

    def close(self):
        self.file.close()
