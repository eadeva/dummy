"""Resolve PTK's own distribution version using its existing configuration engine."""

from email.parser import Parser
from pathlib import Path

from packaging.version import InvalidVersion, Version


def configured_version(root: Path) -> str:
    # Installation must work even when jobs or other project files need repair.
    # Read only version inputs, using PTK's normal reader, schemas and discovery.
    # Keep imports lazy: rebuilding an sdist only needs its frozen metadata.
    from ptk.adapters.config.discovery import checked_path
    from ptk.adapters.config.source import FileConfigSource
    from ptk.adapters.host import SystemHost
    from ptk.adapters.process import SubprocessRunner
    from ptk.adapters.versioning import VersionIO
    from ptk.application.use_cases.project import validation_problems
    from ptk.domain.config.layout import MainDocument, VariantSettingsDocument
    from ptk.domain.config.schema_walk import unknown_keys
    from ptk.domain.config.tree import to_plain
    from ptk.domain.errors import ConfigError, Location, Problem
    from ptk.domain.versioning import VersioningSpec

    root = root.absolute()
    files = FileConfigSource()

    def read_document(path, model):
        tree = files.read(path)
        problems = unknown_keys(model, tree)
        problems += validation_problems(model, tree, skip_unknown=bool(problems))
        if problems:
            raise ConfigError(problems)
        return model.model_validate(to_plain(tree))

    main = root / ".main.ptk.yml"
    marker = read_document(main, MainDocument)
    if marker.virtual_monorepo or marker.repository is None:
        raise ConfigError(
            [
                Problem(
                    "PTK package requires a repository marker",
                    location=Location(str(main)),
                )
            ]
        )
    folder = checked_path(root, marker.repository.config_path)
    version_file = folder / "versioning.ptk.yml"
    spec = read_document(version_file, VersioningSpec)
    if spec.project is None:
        raise ConfigError(
            [
                Problem(
                    "PTK package requires versioning.project configuration",
                    location=Location(str(version_file)),
                )
            ]
        )
    settings_file = folder / "project.variants.ptk.yml"
    variant = None
    if settings_file.exists() or settings_file.is_symlink():
        variant = read_document(settings_file, VariantSettingsDocument).default
    override = spec.variants.get(variant)
    source = override.project if override and override.project else spec.project
    return VersionIO(SubprocessRunner(), SystemHost()).discover(source, root)["value"]


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
