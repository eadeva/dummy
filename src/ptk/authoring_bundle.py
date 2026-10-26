"""Allowlisted authoring assets shared by wheel builds and editable installs.

Keep this module stdlib-only: Hatch loads it before runtime dependencies exist.
"""

from pathlib import Path

SKILLS = (
    "ptk-action-authoring",
    "ptk-config-authoring",
    "ptk-credentials",
    "ptk-plugin-development",
    "ptk-python-steps",
    "ptk-reporting",
    "ptk-shared-configs",
    "ptk-tools-setup",
    "ptk-troubleshooting",
    "ptk-variant-model",
    "ptk-vmr",
    "ptk-workflow-authoring",
    "ptk-versioning",
    "ptk-package-preparation",
)
DOCS = (
    "cli",
    "configuration",
    "editor",
    "m11",
    "plugins",
    "quickstart",
    "reference",
    "versioning",
    "workflows",
    "packaging",
)
EXAMPLES = ("authoring", "plugin", "quickstart", "workflows")


def source_files(root: Path) -> dict[str, Path]:
    files = {f"docs/{name}.rst": root / "docs" / f"{name}.rst" for name in DOCS}
    for name in SKILLS:
        files[f"skills/{name}/SKILL.md"] = root / ".claude/skills" / name / "SKILL.md"
    for example in EXAMPLES:
        directory = root / "examples" / example
        for path in directory.rglob("*"):
            relative = path.relative_to(directory)
            if path.name in {"local.ptk.yml", ".gen.version.ptk.yml"}:
                continue
            if any(part.startswith(("_", ".")) for part in relative.parts[:-1]):
                continue
            if path.is_file() and (
                path.name.endswith(".ptk.yml")
                or path.suffix == ".py"
                or path.name == "pyproject.toml"
            ):
                files[f"examples/{example}/{relative.as_posix()}"] = path
    for name, path in files.items():
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"missing or symlinked authoring resource: {name}")
    return files
