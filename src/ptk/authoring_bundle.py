"""Allowlisted authoring assets shared by wheel builds and editable installs.

Keep this module stdlib-only: Hatch loads it before runtime dependencies exist.
"""

from pathlib import Path

SKILLS = (
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
    "ptk-versioning",
    "ptk-package-preparation",
)
DOCS = (
    "guides/agent-guide",
    "reference/cli",
    "guides/configuration",
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
)

EXAMPLES = ("authoring", "python-tool", "quickstart", "workflows", "artifacts")


def source_files(root: Path) -> dict[str, Path]:
    files = {f"docs/{name}.rst": root / "docs" / f"{name}.rst" for name in DOCS}
    resource = "docs/resources/bazel/ptk_variants.bzl"
    files[resource] = root / resource
    for name in SKILLS:
        files[f"skills/{name}/SKILL.md"] = root / ".claude/skills" / name / "SKILL.md"
        metadata = root / ".claude/skills" / name / "agents/openai.yaml"
        if metadata.is_file():
            files[f"skills/{name}/agents/openai.yaml"] = metadata
    files["agents/ptk-expert.agent.md"] = root / ".claude/agents/ptk-expert.md"
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
