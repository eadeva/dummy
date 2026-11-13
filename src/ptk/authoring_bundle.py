"""Allowlisted authoring assets shared by wheel builds and editable installs.

Keep this module stdlib-only: Hatch loads it before runtime dependencies exist.
"""

from pathlib import Path

SKILLS = (
    "ptk-devops",
    "ptk-job-authoring",
    "ptk-config-authoring",
    "ptk-credentials",
    "ptk-python-steps",
    "ptk-reporting",
    "ptk-log-analyzer",
    "ptk-shared-configs",
    "ptk-tools-setup",
    "ptk-troubleshooting",
    "ptk-variant-model",
    "ptk-vmr",
    "ptk-workflow-authoring",
    "ptk-github-workflows",
    "ptk-versioning",
    "ptk-package-preparation",
)
DOCS = (
    "guides/agent-guide",
    "guides/local-setup",
    "reference/cli",
    "guides/configuration",
    "guides/vmr",
    "guides/python-tools",
    "guides/variant-generation",
    "guides/editor",
    "reference/execution",
    "reference/builtins",
    "guides/getting-started",
    "reference/configuration-schema",
    "guides/versioning",
    "guides/workflows",
    "guides/packaging",
    "guides/artifacts",
    "guides/performance",
    "guides/log-analysis",
    "guides/reports",
    "guides/output-reuse",
    "guides/cx-matrix",
    "guides/github-actions",
    "guides/docker",
    "guides/shared-configs",
)

EXAMPLES = ("authoring", "python-tool", "quickstart", "workflows", "artifacts")


def source_files(root: Path) -> dict[str, Path]:
    files = {f"docs/{name}.rst": root / "docs" / f"{name}.rst" for name in DOCS}
    for name in ("install.sh", "install.ps1"):
        files[f"install/{name}"] = root / "install" / name
    resource = "docs/resources/bazel/ptk_variants.bzl"
    files[resource] = root / resource
    for name in SKILLS:
        files[f"skills/{name}/SKILL.md"] = root / ".github/skills" / name / "SKILL.md"
        metadata = root / ".github/skills" / name / "agents/openai.yaml"
        if metadata.is_file():
            files[f"skills/{name}/agents/openai.yaml"] = metadata
    files["agents/ptk-expert.agent.md"] = root / ".github/agents/ptk-expert.md"
    files["VMR_GUIDE.md"] = root / "VMR_GUIDE.md"
    for example in EXAMPLES:
        directory = root / "examples" / example
        for path in directory.rglob("*"):
            relative = path.relative_to(directory)
            if path.name == ".gen.version.ptk.yml":
                continue
            if any(part.startswith(("_", ".")) for part in relative.parts[:-1]):
                continue
            if path.is_file() and (
                path.name.endswith((".ptk.yml", ".ptk.yaml"))
                or path.suffix == ".py"
                or path.name == "pyproject.toml"
            ):
                files[f"examples/{example}/{relative.as_posix()}"] = path
    for name, path in files.items():
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"missing or symlinked authoring resource: {name}")
    return files


def manifest_content(
    files: dict[str, bytes], version: str, configuration_readme=None
) -> bytes:
    """Identical provenance for initial scaffolding and protected updates."""
    import hashlib
    import json

    return (
        json.dumps(
            {
                "schema_version": 1,
                "ptk_version": version,
                **(
                    {"configuration_readme": configuration_readme}
                    if configuration_readme
                    else {}
                ),
                "files": {
                    name: hashlib.sha256(value).hexdigest()
                    for name, value in sorted(files.items())
                },
            },
            indent=2,
        )
        + "\n"
    ).encode()
