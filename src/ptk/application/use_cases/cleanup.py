"""Compute and preflight all cleanup targets before performing any deletion."""

from dataclasses import dataclass
from pathlib import Path

from ...domain.layout import safe


@dataclass(frozen=True)
class CleanupTarget:
    path: Path
    project: object


def targets(project, selections=None):
    from .run import layout_of

    layout = layout_of(project)
    roots = [Path(p) for p in layout.all_roots()]
    if selections is None:
        return [CleanupTarget(p, project) for p in dict.fromkeys(roots)]
    return [
        CleanupTarget(root / safe(variant or "default") / safe(job), project)
        for root in dict.fromkeys(roots)
        for variant, job in dict.fromkeys(selections)
    ]


class CleanOutputs:
    def __init__(self, validate, delete):
        self.validate = validate
        self.delete = delete

    def preflight(self, selected):
        for target in selected:
            self.validate(target.path, target.project.root, target.project.files)

    def execute(self, selected, out):
        self.preflight(selected)
        for target in selected:
            self.delete(target.path)
            out(f"cleaned {target.path}")


def prepare_cleanup(project, job_name, variant, role):
    """Resolve scope without tools, credentials, parameters or version commands."""
    from types import SimpleNamespace

    from ...domain.errors import PtkError
    from ...domain.execution.planning import variant_restriction
    from .role import visible
    from .run import layout_of
    from .variants import VariantService

    job_name = job_name or project.config.project.default_job
    job = project.config.jobs.get(job_name)
    if job is None:
        raise PtkError(f"unknown job {job_name!r}")
    if not visible(job.audience, role):
        raise PtkError(f"{job_name!r} is a maintainer-only job")
    if job.only_cx and not project.ci:
        raise PtkError(f"job {job_name!r} is only available in CX/CI")
    service = VariantService(project)
    if service.has_variants:
        resolved = service.resolve(variant)
        if resolved.abstract:
            raise PtkError(
                f"variant {resolved.name!r} is abstract; select a concrete variant"
            )
        if resolved.errors:
            raise PtkError("invalid variant: " + "; ".join(map(str, resolved.errors)))
        variant = resolved.name
    elif variant:
        raise PtkError("this project has no variants")
    reason = variant_restriction(job, variant)
    if reason:
        raise PtkError(f"job {job_name!r}: {reason}")
    plan = SimpleNamespace(job=job_name, variant=variant, base_env={}, walk=list)
    return SimpleNamespace(project=project, plan=plan, layout=layout_of(project))
