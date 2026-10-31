"""Minimal execution and artifact metadata for a GitHub workflow setup job."""

from ...domain.errors import PtkError
from ...domain.execution.planning import variant_restriction
from ...domain.suggest import did_you_mean
from .role import visible
from .variants import VariantService


class ExportMatrix:
    def __init__(self, destinations):
        self.destinations = destinations

    def execute(self, project, *, role, variant=None, jobs=(), event=None, at=None):
        config = project.config
        for name in jobs:
            if name not in config.jobs:
                raise PtkError(f"unknown job {name!r}{did_you_mean(name, config.jobs)}")
        service = VariantService(project)
        if not service.has_variants:
            if variant is not None:
                raise PtkError("this project has no variants; omit --variant")
            variants = [(None, [])]
        else:
            selected = (
                variant.split(",") if variant is not None else service.line.buildable()
            )
            variants, seen = [], set()
            for selection in selected:
                name = service.name_of(selection.strip())
                if name in seen:
                    continue
                seen.add(name)
                resolved = service.resolve(name)
                if resolved.abstract:
                    raise PtkError(
                        f"variant {name!r} is abstract; select a concrete variant"
                    )
                if resolved.errors:
                    raise PtkError(
                        f"invalid variant {name!r}: "
                        + "; ".join(map(str, resolved.errors))
                    )
                variants.append((name, resolved.aliases))
        rows, bases = [], []
        alias = config.repository.alias
        for name, aliases in variants:
            for job_name, spec in config.jobs.items():
                if jobs and job_name not in jobs:
                    continue
                if not visible(spec.audience, role):
                    continue
                if spec.only_cx and not project.ci:
                    continue
                if variant_restriction(spec, name):
                    continue
                upload = None
                if config.artifactory is not None:
                    destination = self.destinations.execute(
                        project,
                        job=job_name,
                        variant=name,
                        event=event,
                        role=role,
                        at=at,
                        include_base=True,
                        include_identity=True,
                    )
                    base = destination.pop("base")
                    identity = destination.pop("identity")
                    bases.append(base)
                    upload = {
                        **destination,
                        "base_path": base["path"],
                        "base_url": base["url"],
                    }
                else:
                    identity = self.destinations.identity(
                        project, job=job_name, variant=name
                    )
                command = [
                    "ptk",
                    *(["-V", name] if name is not None else []),
                    *(["maintainer"] if spec.audience == "maintainer" else []),
                    "run",
                    job_name,
                ]
                rows.append(
                    {
                        "repository": alias,
                        "variant": name,
                        "aliases": list(aliases),
                        "job": job_name,
                        "command": command,
                        **identity,
                        "upload": upload,
                    }
                )
        shared = bases[0] if bases and all(base == bases[0] for base in bases) else None
        return {"schema_version": 1, "matrix": {"include": rows}, "upload_base": shared}
