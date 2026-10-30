"""Keep the published skill catalog complete and its source links usable."""

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_skills_are_shipped_and_documented():
    paths = list((ROOT / ".claude/skills").glob("*/SKILL.md"))
    catalog = (ROOT / "docs/guides/skills.rst").read_text(encoding="utf-8")
    documented = set(
        re.findall(r"literalinclude:: ../../\.claude/skills/([^/]+)/SKILL.md", catalog)
    )
    assert {p.parent.name for p in paths} == documented
    for path in paths:
        _, frontmatter, body = path.read_text(encoding="utf-8").split("---", 2)
        metadata = yaml.safe_load(frontmatter)
        assert metadata["name"] == path.parent.name
        assert metadata["description"]
        interface = yaml.safe_load(
            (path.parent / "agents/openai.yaml").read_text(encoding="utf-8")
        )["interface"]
        assert f"${path.parent.name}" in interface["default_prompt"]
        assert 25 <= len(interface["short_description"]) <= 64
        assert path.parent.name in catalog
        for reference in re.findall(r"`((?:src/|docs/|tests/)[^`]+)`", body):
            assert (ROOT / reference).exists(), (path, reference)
        for reference in re.findall(r"\]\(([^)]+)\)", body):
            assert (path.parent / reference).exists(), (path, reference)


def test_authoring_starter_runs_from_its_configuration_directory(tmp_path, monkeypatch):
    import shutil

    from ptk.drivers.cli.main import cli
    from tests.cli_runner import CliRunner

    source = ROOT / "examples/authoring"
    destination = tmp_path / "authoring"
    shutil.copytree(source, destination)
    monkeypatch.chdir(destination / "config")
    runner = CliRunner()
    for args in (
        ["validate"],
        ["-V", "debug", "build", "--dry-run"],
        ["build", "--all-variants"],
    ):
        result = runner.invoke(cli, args)
        assert result.exit_code == 0, result.output
    for variant, size in [("debug", 4), ("release", 8)]:
        text = (
            destination / "_builds" / variant / "build" / "generate" / "variant.h"
        ).read_text(encoding="utf-8")
        assert f"#define VARIANT_DEVICE_SIZE {size}" in text
