"""Bounded discovery of the conventional PTK configuration directory."""

from pathlib import Path

from ...domain.config.layout import ENTITY_DIRECTORIES, SECTION_FILES
from ...domain.errors import ConfigError, Location, Problem


def checked_path(root: Path, relative: str) -> Path:
    path = root / relative
    if (
        Path(relative).is_absolute()
        or ".." in Path(relative).parts
        or not path.resolve().is_relative_to(root)
    ):
        raise ConfigError(
            [Problem(f"configuration path must stay within the repository: {relative}")]
        )
    current = root
    for part in Path(relative).parts:
        current = current / part
        if current != path and current.exists() and not current.is_dir():
            raise ConfigError(
                [Problem(f"configuration parent must be a directory: {current}")]
            )
        if current.is_symlink():
            raise ConfigError(
                [
                    Problem(
                        f"configuration paths cannot contain symbolic links: {relative}"
                    )
                ]
            )
    return path


def discover_files(
    main: Path, config_path: str, components: tuple[Path, ...] = ()
) -> list[Path]:
    root = main.resolve().parent
    folder = checked_path(root, config_path)
    known = {
        "project.ptk.yml",
        "project.variants.ptk.yml",
        "maintainers.ptk.yml",
        *SECTION_FILES,
    }
    files = [main]
    problems = []
    for file in sorted(folder.iterdir()):
        if file.name in ENTITY_DIRECTORIES:
            checked_path(root, str(file.relative_to(root)))
            if not file.is_dir():
                problems.append(
                    Problem(
                        "expected a configuration directory",
                        location=Location(str(file)),
                    )
                )
                continue
            for entity in sorted(file.iterdir()):
                if entity.is_dir() or not entity.name.endswith(".ptk.yml"):
                    problems.append(
                        Problem(
                            "expected <name>.ptk.yml directly in this directory",
                            location=Location(str(entity)),
                        )
                    )
                    continue
                checked_path(root, str(entity.relative_to(root)))
                files.append(entity)
        elif file.name.endswith((".ptk.yml", ".ptk.yaml")):
            if (
                file == main
                or file in components
                or file.name == ".gen.version.ptk.yml"
            ):
                continue
            if file.name not in known:
                problems.append(
                    Problem(
                        "unexpected configuration filename; expected one of: "
                        + ", ".join(sorted(known))
                        + "; named jobs, workflows and variants belong in their directories",
                        location=Location(str(file)),
                    )
                )
            elif file.name != "maintainers.ptk.yml":
                checked_path(root, str(file.relative_to(root)))
                files.append(file)
    if problems:
        raise ConfigError(problems)
    return files
