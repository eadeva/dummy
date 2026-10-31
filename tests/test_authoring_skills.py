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


def test_installed_workflow_skill_supports_a_consumer_pipeline(tmp_path, monkeypatch):
    """Exercise the documented flow without PTK's own jobs or source layout."""
    import json

    from ptk.adapters.authoring import AuthoringFiles
    from ptk.application.use_cases.authoring import SetupAuthoring
    from ptk.drivers.cli.main import cli
    from tests.cli_runner import CliRunner
    from tests.conftest import grant_maintainer
    from tests.project_files import write_project
    from tests.test_git_metadata import repo

    repo(tmp_path)
    write_project(
        tmp_path / ".main.ptk.yml",
        {
            "repository": {"alias": "device", "config_path": "automation"},
            "project": {"name": "Device"},
            "jobs": {
                "compile": {
                    "steps": {"build": {"run": ["echo", "compile"]}},
                    "outputs": [
                        {"path": "dist/device.bin", "artifact_type": "firmware"}
                    ],
                },
                "inspect": {"steps": {"inspect": {"run": ["echo", "inspect"]}}},
            },
            "workflows": {
                "quality": {
                    "jobs": {
                        "producer": {"job": "compile"},
                        "consumer": {"job": "inspect", "needs": ["producer"]},
                    }
                }
            },
            "artifactory": {
                "url": "https://artifacts.example.invalid/artifactory",
                "repository": "ci",
                "events": {"push": {"path": "checks"}},
            },
        },
    )
    grant_maintainer(tmp_path)
    SetupAuthoring(AuthoringFiles(), "test").execute(tmp_path)
    installed = tmp_path / ".github/skills/ptk-github-workflows/SKILL.md"
    assert installed.is_file()
    assert "../../ptk/docs/guides/github-actions.rst" in installed.read_text()
    assert "additional_properties" in installed.read_text()
    monkeypatch.chdir(tmp_path)
    runner = CliRunner(env={"PTK_CI": "1", "GITHUB_EVENT_NAME": "push", "PTK_ROLE": ""})
    for args in (["validate"], ["maintainer", "gen-workflows", "quality"]):
        result = runner.invoke(cli, args)
        assert result.exit_code == 0, result.output
    path = tmp_path / ".github/workflows/ptk-quality.yml"
    generated = yaml.safe_load(path.read_text())
    assert generated["jobs"]["consumer"]["needs"] == ["setup", "producer"]
    assert "workflow_call" in generated["on"]
    result = runner.invoke(cli, ["maintainer", "matrix", "--workflow", "quality"])
    assert result.exit_code == 0, result.output
    row = json.loads(result.output)["jobs"]["consumer"]["include"][0]
    assert row["variant"] is None
    assert row["producers"][0]["job"] == "compile"
    assert not (
        tmp_path / "dist/device.bin"
    ).exists()  # Generation never executes jobs.
    before = path.read_bytes()
    result = runner.invoke(cli, ["maintainer", "gen-workflows", "quality"])
    assert "Warning:" in result.output and path.read_bytes() == before
    assert (
        SetupAuthoring(AuthoringFiles(), "test").execute(tmp_path, check=True).paths
        == []
    )
