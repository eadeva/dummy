"""Keep the published skill catalog complete and its source links usable."""

import re
from pathlib import Path

import yaml

from tests.project_files import write_project

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


def test_plugin_starter_installed_entry_point_runs(tmp_path, monkeypatch):
    import configparser
    import tomllib

    from ptk.drivers.cli.main import cli
    from tests.cli_runner import CliRunner

    source = ROOT / "examples/plugin"
    project = tomllib.loads((source / "pyproject.toml").read_text(encoding="utf-8"))[
        "project"
    ]
    dist = tmp_path / "ptk_example_extension-0.1.0.dist-info"
    dist.mkdir()
    (dist / "METADATA").write_text(
        f"Metadata-Version: 2.1\nName: {project['name']}\nVersion: {project['version']}\n"
    )
    entrypoints = configparser.ConfigParser()
    entrypoints.read_dict(project["entry-points"])
    with (dist / "entry_points.txt").open("w") as handle:
        entrypoints.write(handle)
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.syspath_prepend(str(source))
    config = tmp_path / ".main.ptk.yml"
    write_project(
        config,
        yaml.safe_dump(
            {
                "repository": {"alias": "plugin", "config_path": "."},
                "project": {"name": "plugin"},
                "plugins": [project["name"]],
                "jobs": {"check": {"steps": {"example": {"uses": "example.check"}}}},
            }
        ),
    )
    result = CliRunner().invoke(cli, ["check"], cwd=Path(config).parent)
    assert result.exit_code == 0 and "Example check passed" in result.output, (
        result.output
    )
