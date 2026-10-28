"""Workspace init fills missing PTK configurations without changing existing ones."""

import os
from unittest.mock import patch

import pytest
import yaml
from click.testing import CliRunner

from ptk.drivers.cli.main import cli

from .test_workspace import repository


def checkout(root, *names):
    (root / ".repo").mkdir()
    (root / ".repo/project.list").write_text("\n".join(names))
    for name in names:
        directory = root / name
        directory.mkdir(parents=True)
        target = root / ".repo/projects" / f"{name}.git"
        target.mkdir(parents=True)
        (directory / ".git").write_text(
            f"gitdir: {os.path.relpath(target, directory)}\n"
        )


def snapshot(root):
    return {
        path.relative_to(root): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def test_init_initializes_all_unconfigured_git_repo_members(tmp_path, monkeypatch):
    checkout(tmp_path, "nested/engine", "frontend")
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        cli, ["setup", "init", "--config-dir", "config/ptk", "--yes"]
    )
    assert result.exit_code == 0, result.output
    assert "Initialized 2 repositories; skipped 0" in result.output
    assert not (tmp_path / ".main.ptk.yml").exists()
    assert not (tmp_path / ".gitignore").exists()
    for name, alias in (("nested/engine", "engine"), ("frontend", "frontend")):
        entry = yaml.safe_load((tmp_path / name / ".main.ptk.yml").read_text())
        assert entry["repository"] == {"alias": alias, "config_path": "config/ptk"}
        assert (tmp_path / name / "config/ptk/jobs/hello.ptk.yml").is_file()
        for args in ([alias, "setup", "config", "validate"], [alias, "hello"]):
            result = runner.invoke(cli, args)
            assert result.exit_code == 0, result.output
    before = snapshot(tmp_path)
    result = runner.invoke(cli, ["setup", "init", "--yes"])
    assert result.exit_code == 0, result.output
    assert "Initialized 0 repositories; skipped 2" in result.output
    assert snapshot(tmp_path) == before


def test_init_skips_existing_config_without_loading_its_includes(tmp_path, monkeypatch):
    checkout(tmp_path, "existing", "new", "broken")
    main = repository(tmp_path / "existing", "existing", config_path="custom")
    (main.parent / "custom/jobs/build.ptk.yml").unlink()
    # Existing config is protected even when it cannot be parsed.
    (tmp_path / "broken/.main.ptk.yml").write_text("invalid: [")
    before = {name: snapshot(tmp_path / name) for name in ("existing", "broken")}
    monkeypatch.chdir(tmp_path)
    result = CliRunner(env={"PTK_ROLE": "user"}).invoke(
        cli, ["setup", "init", "--config-dir", "ptk", "--yes"]
    )
    assert result.exit_code == 0, result.output
    assert "Initialized 1 repositories; skipped 2" in result.output
    for name, files in before.items():
        assert snapshot(tmp_path / name) == files
    assert (tmp_path / "new/.main.ptk.yml").is_file()


def test_init_dry_run_previews_all_members_without_writes(tmp_path, monkeypatch):
    checkout(tmp_path, "a", "nested/b")
    (tmp_path / "a/.gitignore").write_text("keep-this-rule\n")
    before = snapshot(tmp_path)
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(
        cli, ["setup", "init", "--config-dir", "ptk", "--dry-run", "--yes"]
    )
    assert result.exit_code == 0, result.output
    assert "Would initialize 2 repositories" in result.output
    assert "would create" in result.output
    assert snapshot(tmp_path) == before
    assert not (tmp_path / "a/ptk").exists()


@pytest.mark.parametrize("configured", [False, True])
def test_init_from_git_repo_member_subdirectory_initializes_workspace(
    tmp_path, monkeypatch, configured
):
    checkout(tmp_path, "a", "nested/b")
    if configured:
        repository(tmp_path / "a", "a")
    subdir = tmp_path / "a/src/deep"
    subdir.mkdir(parents=True)
    monkeypatch.chdir(subdir)
    result = CliRunner().invoke(cli, ["setup", "init", "--config-dir", "ptk", "--yes"])
    assert result.exit_code == 0, result.output
    for name in ("a", "nested/b"):
        assert (tmp_path / name / ".main.ptk.yml").is_file()
    assert not (subdir / ".main.ptk.yml").exists()


def test_explicit_directory_still_initializes_one_project(tmp_path, monkeypatch):
    checkout(tmp_path, "a", "b")
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(
        cli, ["setup", "init", "a", "--name", "Only A", "--config-dir", "ptk", "--yes"]
    )
    assert result.exit_code == 0, result.output
    assert (tmp_path / "a/.main.ptk.yml").is_file()
    assert not (tmp_path / "b/.main.ptk.yml").exists()


def test_workspace_init_prompts_once_for_config_directory(tmp_path, monkeypatch):
    checkout(tmp_path, "a", "b")
    monkeypatch.chdir(tmp_path)
    with patch("click.testing._NamedTextIOWrapper.isatty", return_value=True):
        result = CliRunner().invoke(cli, ["setup", "init"], input="config/toolkit\n")
    assert result.exit_code == 0, result.output
    assert result.output.count("PTK configuration directory") == 1
    for name in ("a", "b"):
        assert (tmp_path / name / "config/toolkit/project.ptk.yml").is_file()
    with patch("click.testing._NamedTextIOWrapper.isatty", return_value=True):
        result = CliRunner().invoke(cli, ["setup", "init"])
    assert result.exit_code == 0, result.output
    assert "PTK configuration directory" not in result.output


def test_workspace_init_preflights_all_repositories_before_writing(
    tmp_path, monkeypatch
):
    checkout(tmp_path, "a", "b")
    fragment = tmp_path / "b/ptk/tools.ptk.yml"
    fragment.parent.mkdir(parents=True)
    fragment.write_text("preserve existing fragment")
    before = snapshot(tmp_path)
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(cli, ["setup", "init", "--config-dir", "ptk", "--yes"])
    assert result.exit_code != 0
    assert "refusing to overwrite" in result.output
    assert snapshot(tmp_path) == before
    assert not (tmp_path / "a/ptk").exists()


def test_workspace_init_chooses_unique_nonreserved_aliases(tmp_path, monkeypatch):
    checkout(tmp_path, "existing", "first/lib", "second/lib", "setup", "init")
    repository(tmp_path / "existing", "lib")
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, ["setup", "init", "--config-dir", "ptk", "--yes"])
    assert result.exit_code == 0, result.output
    aliases = []
    for name in ("existing", "first/lib", "second/lib", "setup", "init"):
        entry = yaml.safe_load((tmp_path / name / ".main.ptk.yml").read_text())
        aliases.append(entry["repository"]["alias"])
    assert len(set(aliases)) == 5
    assert not set(aliases).intersection({"setup", "init", "help", "repos"})
    for alias in aliases[1:]:
        result = runner.invoke(cli, [alias, "hello"])
        assert result.exit_code == 0, result.output


@pytest.mark.parametrize("explicit", [False, True])
def test_manual_workspace_init_preserves_marker_and_uses_bounded_members(
    tmp_path, monkeypatch, explicit
):
    marker = {"virtual_monorepo": True}
    if explicit:
        marker["members"] = ["nested/a", "b"]
        (tmp_path / "nested/a").mkdir(parents=True)
    else:
        (tmp_path / "a/.git").mkdir(parents=True)
    (tmp_path / "b/.git").mkdir(parents=True)
    (tmp_path / "build-output").mkdir()
    main = tmp_path / ".main.ptk.yml"
    main.write_text(yaml.safe_dump(marker))
    before = main.read_bytes()
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(cli, ["setup", "init", "--config-dir", "ptk", "--yes"])
    assert result.exit_code == 0, result.output
    assert "Initialized 2 repositories" in result.output
    assert main.read_bytes() == before
    assert not (tmp_path / "build-output/.main.ptk.yml").exists()
    assert not (tmp_path / "ptk").exists()
    result = CliRunner().invoke(cli, ["setup", "--help"])
    assert result.exit_code == 0 and "init" in result.output


def test_unchecked_out_members_are_reported_without_creating_directories(
    tmp_path, monkeypatch
):
    checkout(tmp_path, "a")
    (tmp_path / ".repo/project.list").write_text("a\nmissing/path\n")
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(cli, ["setup", "init", "--config-dir", "ptk", "--yes"])
    assert result.exit_code == 0, result.output
    assert "not checked out" in result.output
    assert not (tmp_path / "missing").exists()


def test_bulk_init_rejects_name_and_missing_index(tmp_path, monkeypatch):
    checkout(tmp_path, "a", "b")
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(cli, ["setup", "init", "--name", "same", "--yes"])
    assert result.exit_code != 0 and "explicit DIRECTORY" in result.output
    assert not (tmp_path / "a/.main.ptk.yml").exists()
    (tmp_path / ".repo/project.list").unlink()
    result = CliRunner().invoke(cli, ["setup", "init", "--yes"])
    assert result.exit_code != 0 and "repo sync" in result.output
    assert not (tmp_path / ".main.ptk.yml").exists()


@pytest.mark.parametrize("config_dir", ["", "../outside", ".git/config"])
def test_bulk_init_rejects_invalid_config_directory(tmp_path, monkeypatch, config_dir):
    checkout(tmp_path, "a", "b")
    before = snapshot(tmp_path)
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(
        cli, ["setup", "init", "--config-dir", config_dir, "--yes"]
    )
    assert result.exit_code != 0
    assert "configuration directory" in result.output
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize("vmr", [False, True])
@pytest.mark.parametrize("options", [[], ["--yes"], ["--dry-run"]])
def test_init_requires_a_config_folder_in_scripts(tmp_path, monkeypatch, vmr, options):
    if vmr:
        checkout(tmp_path, "a", "b")
    monkeypatch.chdir(tmp_path)
    before = snapshot(tmp_path)
    result = CliRunner().invoke(cli, ["setup", "init", *options])
    assert result.exit_code == 2, result.output
    assert "Supply --config-dir PATH" in result.output
    assert snapshot(tmp_path) == before
    assert not (tmp_path / "ptk").exists()


def test_interactive_empty_folder_does_not_select_a_default(tmp_path, monkeypatch):
    checkout(tmp_path, "a", "b")
    monkeypatch.chdir(tmp_path)
    before = snapshot(tmp_path)
    with patch("click.testing._NamedTextIOWrapper.isatty", return_value=True):
        result = CliRunner().invoke(cli, ["setup", "init"], input="\n")
    assert result.exit_code != 0
    assert snapshot(tmp_path) == before
    assert not (tmp_path / "a/ptk").exists()
