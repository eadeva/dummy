"""Scaffolding must work before a project exists and must never overwrite files."""

import json

import pytest
from click.testing import CliRunner

from ptk.application.use_cases.init import InitProject
from ptk.domain.errors import PtkError
from ptk.drivers.cli.main import cli


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
    assert set(entry) == {"repository", "include"}
    config = yaml.safe_load(result.files["ptk/project.ptk.yml"])
    assert config["project"]["name"] == 'My "project": #1'
    assert config["project"]["default_job"] == "hello"
    assert files.dry_run


@pytest.mark.parametrize("name", ["", "   ", "line\nbreak"])
def test_invalid_name_has_no_side_effects(tmp_path, name):
    scaffold = MemoryScaffold()
    with pytest.raises(PtkError, match="project name"):
        InitProject(scaffold).execute(tmp_path, name, config_path="ptk")
    assert not hasattr(scaffold, "files")


def test_new_project_runs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    target = tmp_path / "new project"
    result = runner.invoke(
        cli,
        ["setup", "init", str(target), "--config-dir", "ptk"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output
    assert "local.ptk.yml" in (target / ".gitignore").read_text()
    from ptk.adapters.host import SystemHost
    from ptk.bootstrap import create_app

    app = create_app()
    initialized = app.load_project.execute(config_file=target / ".main.ptk.yml")
    assert initialized.maintainers.maintainers == [SystemHost().user_id()]
    assert app.role(initialized) == "maintainer"
    base = ["-c", str(target / ".main.ptk.yml"), "--no-ci"]
    assert runner.invoke(cli, [*base, "setup", "config", "validate"]).exit_code == 0
    ran = runner.invoke(cli, [*base, "hello", "--message", "custom message"])
    assert ran.exit_code == 0, ran.output
    report = json.loads((target / "_reports/debug/hello/report.json").read_text())
    assert report["status"] == "passed"
    assert report["params"]["message"] == "custom message"


def test_dry_run_does_not_create_directory(tmp_path):
    target = tmp_path / "preview"
    result = CliRunner().invoke(
        cli, ["setup", "init", str(target), "--config-dir", "ptk", "--dry-run"]
    )
    assert result.exit_code == 0, result.output
    assert "schema_version: 1" in result.output
    assert not target.exists()


def test_existing_config_is_preserved(tmp_path):
    main = tmp_path / ".main.ptk.yml"
    main.write_text("unchanged")
    for args in ([], ["--dry-run"]):
        result = CliRunner().invoke(
            cli, ["setup", "init", str(tmp_path), "--config-dir", "ptk", *args]
        )
        assert result.exit_code == 2
        assert "refusing to overwrite" in result.output
        assert main.read_text() == "unchanged"
        assert not (tmp_path / ".gitignore").exists()


def test_existing_gitignore_is_preserved_and_alias_works(tmp_path):
    ignore = tmp_path / ".gitignore"
    ignore.write_text("my-own-rule\n")
    result = CliRunner().invoke(cli, ["init", str(tmp_path), "--config-dir", "ptk"])
    assert result.exit_code == 0, result.output
    assert "Kept existing .gitignore" in result.output
    assert ignore.read_text().startswith("my-own-rule\n")
    assert ".gen.version.ptk.yml" in ignore.read_text()


def test_init_does_not_use_parent_project(tmp_path, monkeypatch):
    (tmp_path / ".main.ptk.yml").write_text("invalid: parent")
    child = tmp_path / "child"
    child.mkdir()
    monkeypatch.chdir(child)
    result = CliRunner().invoke(
        cli, ["setup", "init", "--config-dir", "ptk"], catch_exceptions=False
    )
    assert result.exit_code == 0, result.output
    assert (child / ".main.ptk.yml").is_file()


def test_conflicting_global_options_rejected(tmp_path):
    result = CliRunner().invoke(
        cli, ["--set", "project.name=other", "setup", "init", str(tmp_path)]
    )
    assert result.exit_code == 2
    assert not (tmp_path / ".main.ptk.yml").exists()


def test_custom_config_directory_and_outputs(tmp_path):
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["setup", "init", str(tmp_path), "--config-dir", "config/ptk files", "--yes"],
    )
    assert result.exit_code == 0, result.output
    folder = tmp_path / "config/ptk files"
    for name in (
        "project.ptk.yml",
        "jobs/hello.ptk.yml",
        "jobs/build.ptk.yml",
        "variants/variants.ptk.yml",
        "variants/debug.ptk.yml",
        "variants/release.ptk.yml",
        "tools/tools.ptk.yml",
        "versioning/versioning.ptk.yml",
        "environment/environment.ptk.yml",
        "credentials/credentials.ptk.yml",
        "configs/configs.ptk.yml",
        "cx.ptk.yml",
        "maintainers.ptk.yml",
    ):
        assert (folder / name).is_file()
        assert "#" in (folder / name).read_text()
    assert sorted(p.name for p in (folder / "jobs").iterdir()) == [
        "build.ptk.yml",
        "hello.ptk.yml",
    ]
    base = ["-c", str(tmp_path / ".main.ptk.yml")]
    for variant in ("debug", "release"):
        result = runner.invoke(cli, [*base, "hello", "--variant", variant])
        assert result.exit_code == 0, result.output
        result = runner.invoke(cli, [*base, "build", "--variant", variant])
        assert result.exit_code == 0, result.output
        assert (tmp_path / f"_bin/{variant}/generated/version.h").is_file()
    assert len(list(tmp_path.rglob(".gen.version.ptk.yml"))) == 4


def test_init_prompts_for_directory(tmp_path, monkeypatch):
    import sys

    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    # CliRunner replaces stdin; patch the driver's predicate through its wrapper.
    from unittest.mock import patch

    with patch("click.testing._NamedTextIOWrapper.isatty", return_value=True):
        result = CliRunner().invoke(
            cli, ["setup", "init", str(tmp_path)], input="config/toolkit\n"
        )
    assert result.exit_code == 0, result.output
    assert (tmp_path / "config/toolkit/versioning/versioning.ptk.yml").exists()


@pytest.mark.parametrize("directory", ["../outside", ".git/config", ".ptk/config"])
def test_init_rejects_invalid_directory(tmp_path, directory):
    result = CliRunner().invoke(
        cli, ["setup", "init", str(tmp_path), "--config-dir", directory]
    )
    assert result.exit_code == 2
    assert not (tmp_path / ".main.ptk.yml").exists()


def test_init_preflights_all_files(tmp_path):
    folder = tmp_path / "ptk/tools"
    folder.mkdir(parents=True)
    (folder / "tools.ptk.yml").write_text("keep me")
    result = CliRunner().invoke(
        cli, ["setup", "init", str(tmp_path), "--config-dir", "ptk"]
    )
    assert result.exit_code == 2
    assert not (tmp_path / ".main.ptk.yml").exists()
    assert (folder / "tools.ptk.yml").read_text() == "keep me"


def test_scaffold_nested_includes_variants_and_ci(tmp_path):
    from ptk.application.use_cases.variants import VariantService
    from ptk.bootstrap import create_app

    result = CliRunner().invoke(
        cli, ["setup", "init", str(tmp_path), "--config-dir", "ptk", "--yes"]
    )
    assert result.exit_code == 0, result.output
    for ci in (False, True):
        project = create_app().load_project.execute(
            config_file=tmp_path / ".main.ptk.yml", ci=ci
        )
        assert set(project.config.jobs) == {"hello", "build"}
        assert project.config.versioning.project.version == "0.1.0"
        assert project.config.environment.set.get("PTK_CI") == ("true" if ci else None)
        variants = VariantService(project)
        assert variants.resolve("debug").values["DEBUG"] is True
        assert variants.resolve("release").values["DEBUG"] is False
        assert project.config.tools == {}
        assert project.config.credentials == {}
    # New jobs are discovered through the jobs glob without editing the index.
    (tmp_path / "ptk/jobs/check.ptk.yml").write_text(
        "jobs:\n  check:\n    steps:\n      - check: {uses: echo, with: {message: discovered}}\n"
    )
    result = CliRunner().invoke(cli, ["-c", str(tmp_path / ".main.ptk.yml"), "check"])
    assert result.exit_code == 0, result.output
    assert "discovered" in result.output
