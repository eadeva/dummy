"""Resolve a destination without selecting files, requesting secrets or uploading."""

from ...domain.artifacts import destination
from ...domain.config.dates import date_values
from ...domain.config.substitution import LazyNamespace, Scope
from ...domain.errors import PtkError
from .role import visible
from .variants import VariantService


class ResolveDestination:
    def __init__(self, versions, github_context, instant, environment, git=None):
        self.versions, self.github_context, self.instant = (
            versions,
            github_context,
            instant,
        )
        self.environment = environment
        self.git = git

    def execute(self, project, *, job, variant=None, event=None, role="user", at=None):
        config = project.config
        if config.artifactory is None:
            raise PtkError("no artifactory_paths.ptk.yml configuration found")
        selected = config.jobs.get(job)
        if selected is None:
            raise PtkError(f"unknown job {job!r}")
        if not visible(selected.audience, role):
            raise PtkError(f"{job!r} is a maintainer-only job")
        if config.variants:
            chosen = VariantService(project).resolve(variant)
            if chosen.errors:
                raise PtkError("; ".join(map(str, chosen.errors)))
            variant = chosen.name
        elif variant:
            raise PtkError("this project has no variants")
        github = self.github_context()
        event = event or github.get("event_name")
        if not event:
            raise PtkError("destination resolution needs GITHUB_EVENT_NAME or --event")
        github["event_name"] = event
        alias = config.repository.alias if config.repository else config.project.name
        versions = self.versions.resolve(project, variant, job)

        def read_git():
            if self.git is None:
                raise PtkError(
                    "Git metadata is not available in this execution context."
                )
            return self.git.discover(project.root)

        scope = Scope(
            env=self.environment,
            vars=config.vars,
            namespaces={
                "project": {
                    "alias": alias,
                    "name": config.project.name,
                    "root": str(project.root),
                    "description": config.project.description,
                },
                "version": {
                    **versions,
                    "current": versions.get("projects", {}).get(alias, {}),
                },
                "date": date_values(at or self.instant),
                "run": {"job": job, "variant": variant or "default"},
                "github": github,
                "git": LazyNamespace(read_git),
            },
        )
        try:
            return destination(
                config.artifactory,
                scope,
                event=event,
                ref_type=github.get("ref_type"),
                job=job,
            )
        except (ValueError, TypeError) as exc:
            raise PtkError(str(exc)) from None
