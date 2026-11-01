"""Scaffolding must work before a project exists and must never overwrite files."""

import json

import pytest

from ptk.application.use_cases.init import InitProject
from ptk.domain.errors import PtkError
from ptk.drivers.cli.main import cli
from tests.cli_runner import CliRunner


class MemoryScaffold:
    def create(self, target, files, *, dry_run):
        self.files = files.copy()
        self.dry_run = dry_run
        return False


def test_use_case_renders_valid_configuration(tmp_path):
    import yaml

    files = MemoryScaffold()
    result = InitProject(files).execute(
        tmp_path, 'My "project": #1', config_path="ptk", dry_run=True
    )
    entry = yaml.safe_load(result.files[".main.ptk.yml"])
    assert set(entry) == {"repository"}
    config = yaml.safe_load(result.files["ptk/project.ptk.yml"])
    assert config["name"] == 'My "project": #1'
    assert config["default_job"] == "hello"
    assert files.dry_run


@pytest.mark.parametrize("name", ["", "   ", "line\nbreak"])
def test_invalid_name_has_no_side_effects(tmp_path, name):
    scaffold = MemoryScaffold()
    with pytest.raises(PtkError, match="project name"):
        InitProject(scaffold).execute(tmp_path, name, config_path="ptk")
    assert not hasattr(scaffold, "files")


def test_new_project_runs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner(env={"PTK_CX": "0"})
    target = tmp_path / "new project"
    result = runner.invoke(
        cli,
        ["init", str(target), "--config-dir", "ptk"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output
    assert ".ptk/" in (target / ".gitignore").read_text()
    from ptk.adapters.host import SystemHost
    from ptk.bootstrap import create_app

    app = create_app()
    initialized = app.load_project.execute(config_file=target / ".main.ptk.yml")
    assert initialized.maintainers.maintainers == [SystemHost().user_id()]
    assert app.role(initialized) == "maintainer"
    base = []
    assert runner.invoke(cli, [*base, "validate"], cwd=target).exit_code == 0
    ran = runner.invoke(
        cli, [*base, "hello", "--message", "custom message"], cwd=target
    )
    assert ran.exit_code == 0, ran.output
    assert (target / "_reports/debug/hello/report.html").is_file()
    assert not (target / "_reports/debug/hello/report.json").exists()
    report = json.loads((target / "_logs/debug/hello/run.json").read_text())
    assert report["status"] == "passed"
    assert report["params"]["message"] == "custom message"


def test_dry_run_does_not_create_directory(tmp_path):
    target = tmp_path / "preview"
    result = CliRunner(env={"PTK_CX": "0"}).invoke(
        cli, ["init", str(target), "--config-dir", "ptk", "--dry-run"]
    )
    assert result.exit_code == 0, result.output
    assert "component.variants.ptk.yml" in result.output
    assert not target.exists()


def test_existing_config_is_preserved(tmp_path):
    main = tmp_path / ".main.ptk.yml"
    main.write_text("unchanged")
    for args in ([], ["--dry-run"]):
        result = CliRunner(env={"PTK_CX": "0"}).invoke(
            cli, ["init", str(tmp_path), "--config-dir", "ptk", *args]
        )
        assert result.exit_code == 2
        assert "refusing to overwrite" in result.output
        assert main.read_text() == "unchanged"
        assert not (tmp_path / ".gitignore").exists()


def test_existing_gitignore_is_preserved_and_alias_works(tmp_path):
    ignore = tmp_path / ".gitignore"
    ignore.write_text("my-own-rule\n")
    result = CliRunner(env={"PTK_CX": "0"}).invoke(
        cli, ["init", str(tmp_path), "--config-dir", "ptk"]
    )
    assert result.exit_code == 0, result.output
    assert "Kept existing .gitignore" in result.output
    assert ignore.read_text().startswith("my-own-rule\n")
    assert ".gen.version.ptk.yml" in ignore.read_text()


def test_init_does_not_use_parent_project(tmp_path, monkeypatch):
    (tmp_path / ".main.ptk.yml").write_text("invalid: parent")
    child = tmp_path / "child"
    child.mkdir()
    monkeypatch.chdir(child)
    result = CliRunner(env={"PTK_CX": "0"}).invoke(
        cli, ["init", "--config-dir", "ptk"], catch_exceptions=False
    )
    assert result.exit_code == 0, result.output
    assert (child / ".main.ptk.yml").is_file()


def test_conflicting_global_options_rejected(tmp_path):
    result = CliRunner(env={"PTK_CX": "0"}).invoke(
        cli, ["--set", "project.name=other", "init", str(tmp_path)]
    )
    assert result.exit_code == 2
    assert not (tmp_path / ".main.ptk.yml").exists()


def test_custom_config_directory_and_outputs(tmp_path):
    runner = CliRunner(env={"PTK_CX": "0"})
    result = runner.invoke(
        cli,
        ["init", str(tmp_path), "--config-dir", "config/ptk files", "--yes"],
    )
    assert result.exit_code == 0, result.output
    folder = tmp_path / "config/ptk files"
    for name in (
        "project.ptk.yml",
        "jobs/hello.ptk.yml",
        "jobs/build.ptk.yml",
        "project.variants.ptk.yml",
        "variants/debug.ptk.yml",
        "variants/release.ptk.yml",
        "tools.ptk.yml",
        "versioning.ptk.yml",
        "credentials.ptk.yml",
        "configs.ptk.yml",
        "maintainers.ptk.yml",
    ):
        assert (folder / name).is_file()
        assert "#" in (folder / name).read_text()
    assert sorted(p.name for p in (folder / "jobs").iterdir()) == [
        "build.ptk.yml",
        "hello.ptk.yml",
    ]
    base = []
    for variant in ("debug", "release"):
        result = runner.invoke(
            cli, [*base, "--variant", variant, "hello"], cwd=tmp_path
        )
        assert result.exit_code == 0, result.output
        result = runner.invoke(
            cli, [*base, "--variant", variant, "build"], cwd=tmp_path
        )
        assert result.exit_code == 0, result.output
        assert (tmp_path / f"_bin/{variant}/build/generated/version.h").is_file()
    assert len(list(tmp_path.rglob(".gen.version.ptk.yml"))) == 4


def test_init_prompts_for_directory(tmp_path, monkeypatch):
    import sys

    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    # CliRunner replaces stdin; patch the driver's predicate through its wrapper.
    from unittest.mock import patch

    with patch("click.testing._NamedTextIOWrapper.isatty", return_value=True):
        result = CliRunner(env={"PTK_CX": "0"}).invoke(
            cli, ["init", str(tmp_path)], input="config/toolkit\n"
        )
    assert result.exit_code == 0, result.output
    assert (tmp_path / "config/toolkit/versioning.ptk.yml").exists()


@pytest.mark.parametrize("directory", ["../outside", ".git/config", ".ptk/config"])
def test_init_rejects_invalid_directory(tmp_path, directory):
    result = CliRunner(env={"PTK_CX": "0"}).invoke(
        cli, ["init", str(tmp_path), "--config-dir", directory]
    )
    assert result.exit_code == 2
    assert not (tmp_path / ".main.ptk.yml").exists()


def test_init_preflights_all_files(tmp_path):
    folder = tmp_path / "ptk"
    folder.mkdir(parents=True)
    (folder / "tools.ptk.yml").write_text("keep me")
    result = CliRunner(env={"PTK_CX": "0"}).invoke(
        cli, ["init", str(tmp_path), "--config-dir", "ptk"]
    )
    assert result.exit_code == 2
    assert not (tmp_path / ".main.ptk.yml").exists()
    assert (folder / "tools.ptk.yml").read_text() == "keep me"


def test_scaffold_discovered_fragments_variants_and_cx(tmp_path):
    from ptk.application.use_cases.variants import VariantService
    from ptk.bootstrap import create_app

    result = CliRunner(env={"PTK_CX": "0"}).invoke(
        cli, ["init", str(tmp_path), "--config-dir", "ptk", "--yes"]
    )
    assert result.exit_code == 0, result.output
    for cx in (False, True):
        project = create_app().load_project.execute(
            config_file=tmp_path / ".main.ptk.yml", cx=cx
        )
        assert set(project.config.jobs) == {"hello", "build"}
        assert project.config.versioning.project.version == "0.1.0"
        assert project.cx is cx
        variants = VariantService(project)
        assert variants.resolve("debug").values["core.DEBUG"] is True
        assert variants.resolve("release").values["core.DEBUG"] is False
        assert project.config.tools == {}
        assert project.config.credentials == {}
    # New jobs are discovered without editing any existing configuration file.
    (tmp_path / "ptk/jobs/check.ptk.yml").write_text(
        """\
steps:
  check:
    uses: echo
    with:
      message: discovered
"""
    )
    result = CliRunner(env={"PTK_CX": "0"}).invoke(cli, ["check"], cwd=tmp_path)
    assert result.exit_code == 0, result.output
    assert "discovered" in result.output


@pytest.mark.parametrize("config_dir", ["ptk", "config/toolkit", "."])
def test_init_readme_links_and_bundle_are_ready_for_sync(tmp_path, config_dir):
    import re

    from ptk.bootstrap import create_app

    app = create_app(environ={"PTK_CX": "0"})
    app.init_project.execute(tmp_path, config_path=config_dir)
    readme = tmp_path / config_dir / "README.md"
    for link in re.findall(r"\]\(([^)]+)\)", readme.read_text()):
        assert (readme.parent / link).exists(), link
    assert (tmp_path / ".github/agents/ptk-expert.agent.md").is_file()
    assert len(list((tmp_path / ".github/skills").glob("ptk-*/SKILL.md"))) == 16
    assert (
        app.setup_authoring.execute(tmp_path, check=True, config_path=config_dir).paths
        == []
    )


def test_init_readme_is_protected_and_dry_run_writes_nothing(tmp_path):
    from ptk.bootstrap import create_app

    app = create_app(environ={})
    app.init_project.execute(tmp_path, config_path="config/ptk", dry_run=True)
    assert not list(tmp_path.iterdir())
    folder = tmp_path / "config/ptk"
    folder.mkdir(parents=True)
    readme = folder / "README.md"
    readme.write_text("custom readme")
    with pytest.raises(PtkError, match="refusing to overwrite"):
        app.init_project.execute(tmp_path, config_path="config/ptk")
    assert readme.read_text() == "custom readme"
    assert not (tmp_path / ".github").exists()


def test_init_bundle_conflict_prevents_partial_initialization(tmp_path):
    from ptk.bootstrap import create_app

    path = tmp_path / ".github/agents/ptk-expert.agent.md"
    path.parent.mkdir(parents=True)
    path.write_text("custom agent")
    with pytest.raises(PtkError, match="refusing to overwrite"):
        create_app(environ={}).init_project.execute(tmp_path, config_path="config")
    assert path.read_text() == "custom agent"
    assert not (tmp_path / ".main.ptk.yml").exists()
    assert not (tmp_path / "config/README.md").exists()


def test_init_rejects_config_readme_collision_with_managed_bundle(tmp_path):
    from ptk.bootstrap import create_app

    with pytest.raises(PtkError, match="conflicts with the managed assistant bundle"):
        create_app(environ={}).init_project.execute(tmp_path, config_path=".github/ptk")
    assert not (tmp_path / ".main.ptk.yml").exists()
