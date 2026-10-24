"""Composition root: the only module that wires concrete adapters to use cases."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from . import __version__
from .adapters.config.source import FileConfigSource
from .adapters.host import SystemHost
from .application.ports import ConfigSource, HostEnvironment
from .application.use_cases.project import ExportSchema, LoadProject, Project, ShowConfig
from .application.use_cases.variants import VariantService


@dataclass
class App:
    host: HostEnvironment
    load_project: LoadProject
    show_config: ShowConfig
    export_schema: ExportSchema

    def variants(self, project: Project) -> VariantService:
        return VariantService(project)


def create_app(*, source: ConfigSource | None = None, host: HostEnvironment | None = None,
               environ: Mapping[str, str] | None = None, version: str = __version__) -> App:
    host = host or SystemHost(environ)
    return App(
        host=host,
        load_project=LoadProject(source or FileConfigSource(), host, version),
        show_config=ShowConfig(),
        export_schema=ExportSchema(),
    )


def load(start: Path | None = None, **kwargs) -> Project:
    """Convenience for scripts: ``ptk.bootstrap.load()`` -> validated project."""
    return create_app().load_project.execute(start, **kwargs)
