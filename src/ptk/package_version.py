"""Resolve PTK's own distribution version using its existing configuration engine."""

from email.parser import Parser
from pathlib import Path

from packaging.version import InvalidVersion, Version


def configured_version(root: Path) -> str:
    # Reuse normal includes, config overlays, variant overrides and Git discovery.
    # Keep imports lazy: rebuilding an sdist only needs its frozen metadata.
    from ptk.adapters.config.source import FileConfigSource
    from ptk.adapters.host import SystemHost
    from ptk.adapters.process import SubprocessRunner
    from ptk.adapters.versioning import VersionIO
    from ptk.application.use_cases.project import LoadProject

    host = SystemHost()
    project = LoadProject(FileConfigSource(), host, "0+unknown").execute(
        config_file=root / ".main.ptk.yml"
    )
    config = project.config
    spec = config.versioning
    if spec is None or spec.project is None:
        raise ValueError("PTK package requires versioning.project configuration")
    variant = config.variants.default if config.variants else None
    override = spec.variants.get(variant)
    source = override.project if override and override.project else spec.project
    return VersionIO(SubprocessRunner(), host).discover(source, root)["value"]


def package_version(root: Path, *, resolved_version: str | None = None) -> str:
    """Freeze an sdist's version; otherwise use the run snapshot or live config."""
    metadata_file = root / "PKG-INFO"
    if metadata_file.is_file():
        metadata = Parser().parsestr(metadata_file.read_text(encoding="utf-8"))
        if metadata["Name"] != "ptk" or not metadata["Version"]:
            raise ValueError("invalid PTK source distribution metadata")
        value = metadata["Version"]
    elif resolved_version is not None:
        value = resolved_version
    else:
        value = configured_version(root)
    try:
        return str(Version(value))
    except InvalidVersion:
        raise ValueError(
            f"PTK project version {value!r} is not a valid Python package version"
        ) from None
