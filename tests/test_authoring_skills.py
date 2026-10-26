"""Keep the published skill catalog complete and its source links usable."""

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_plan_skills_are_shipped_and_documented():
    planned = set(re.findall(r"`(ptk-[a-z-]+)`", (ROOT / "docs/PLAN.md").read_text()))
    paths = list((ROOT / ".claude/skills").glob("*/SKILL.md"))
    assert {p.parent.name for p in paths} == planned
    catalog = (ROOT / "docs/skills.rst").read_text()
    for path in paths:
        _, frontmatter, body = path.read_text().split("---", 2)
        metadata = yaml.safe_load(frontmatter)
        assert metadata["name"] == path.parent.name
        assert metadata["description"]
        assert path.parent.name in catalog
        for reference in re.findall(r"`((?:src/|docs/|tests/)[^`]+)`", body):
            assert (ROOT / reference).exists(), (path, reference)
        for reference in re.findall(r"\]\(([^)]+)\)", body):
            assert (path.parent / reference).exists(), (path, reference)


def test_authoring_starter_runs_from_its_configuration_directory(tmp_path, monkeypatch):
    import shutil

    from click.testing import CliRunner

    from ptk.drivers.cli.main import cli

    source = ROOT / "examples/authoring"
    destination = tmp_path / "authoring"
    shutil.copytree(source, destination)
    monkeypatch.chdir(destination / "config")
    runner = CliRunner()
    for args in (
        ["setup", "config", "validate"],
        ["-V", "debug", "dry-run", "build"],
        ["build", "--all-variants"],
    ):
        result = runner.invoke(cli, args)
        assert result.exit_code == 0, result.output
    for variant, size in [("debug", 4), ("release", 8)]:
        text = (destination / "_bin" / variant / "variant.h").read_text()
        assert f"#define VH_SIZE {size}" in text


def test_plugin_starter_installed_entry_point_runs(tmp_path, monkeypatch):
    import configparser
    import tomllib

    from click.testing import CliRunner

    from ptk.drivers.cli.main import cli

    source = ROOT / "examples/plugin"
    project = tomllib.loads((source / "pyproject.toml").read_text())["project"]
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
    config.write_text(
        yaml.safe_dump(
            {
                "repository": {"alias": "plugin", "config_path": "."},
                "project": {"name": "plugin"},
                "plugins": [project["name"]],
                "jobs": {"check": {"steps": [{"example": {"uses": "example.check"}}]}},
            }
        )
    )
    result = CliRunner().invoke(cli, ["-c", str(config), "check"])
    assert result.exit_code == 0 and "Example check passed" in result.output, (
        result.output
    )
