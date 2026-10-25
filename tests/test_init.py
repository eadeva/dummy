"""Scaffolding must work before a project exists and must never overwrite files."""

import json

import pytest
from click.testing import CliRunner

from ptk.application.use_cases.init import InitProject
from ptk.domain.config.model import PtkConfig
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
    result = InitProject(files).execute(tmp_path, 'My "project": #1', dry_run=True)
    config = PtkConfig.model_validate(yaml.safe_load(result.files["main.ptk.yml"]))
    assert config.project.name == 'My "project": #1'
    assert config.project.default_action == "hello"
    assert files.dry_run


@pytest.mark.parametrize("name", ["", "   ", "line\nbreak"])
def test_invalid_name_has_no_side_effects(tmp_path, name):
    scaffold = MemoryScaffold()
    with pytest.raises(PtkError, match="project name"):
        InitProject(scaffold).execute(tmp_path, name)
    assert not hasattr(scaffold, "files")


def test_new_project_runs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    target = tmp_path / "new project"
    result = runner.invoke(cli, ["setup", "init", str(target)], catch_exceptions=False)
    assert result.exit_code == 0, result.output
    assert "local.ptk.yml" in (target / ".gitignore").read_text()
    base = ["-c", str(target / "main.ptk.yml"), "--no-ci"]
    assert runner.invoke(cli, [*base, "setup", "config", "validate"]).exit_code == 0
    ran = runner.invoke(cli, [*base, "hello", "--message", "custom message"])
    assert ran.exit_code == 0, ran.output
    report = json.loads((target / "_reports/default/hello/report.json").read_text())
    assert report["status"] == "passed"
    assert report["params"]["message"] == "custom message"


def test_dry_run_does_not_create_directory(tmp_path):
    target = tmp_path / "preview"
    result = CliRunner().invoke(cli, ["setup", "init", str(target), "--dry-run"])
    assert result.exit_code == 0, result.output
    assert "schema_version: 1" in result.output
    assert not target.exists()


def test_existing_config_is_preserved(tmp_path):
    main = tmp_path / "main.ptk.yml"
    main.write_text("unchanged")
    for args in ([], ["--dry-run"]):
        result = CliRunner().invoke(cli, ["setup", "init", str(tmp_path), *args])
        assert result.exit_code == 2
        assert "refusing to overwrite" in result.output
        assert main.read_text() == "unchanged"
        assert not (tmp_path / ".gitignore").exists()


def test_existing_gitignore_is_preserved_and_alias_works(tmp_path):
    ignore = tmp_path / ".gitignore"
    ignore.write_text("my-own-rule\n")
    result = CliRunner().invoke(cli, ["init", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert "Kept existing .gitignore" in result.output
    assert ignore.read_text() == "my-own-rule\n"


def test_init_does_not_use_parent_project(tmp_path, monkeypatch):
    (tmp_path / "main.ptk.yml").write_text("invalid: parent")
    child = tmp_path / "child"
    child.mkdir()
    monkeypatch.chdir(child)
    result = CliRunner().invoke(cli, ["setup", "init"], catch_exceptions=False)
    assert result.exit_code == 0, result.output
    assert (child / "main.ptk.yml").is_file()


def test_conflicting_global_options_rejected(tmp_path):
    result = CliRunner().invoke(
        cli, ["--set", "project.name=other", "setup", "init", str(tmp_path)]
    )
    assert result.exit_code == 2
    assert not (tmp_path / "main.ptk.yml").exists()
