"""Skills installed in consumer repositories must be usable without a PTK checkout."""

import json
import re
from pathlib import Path

import pytest
from click.testing import CliRunner

from ptk.adapters.authoring import AuthoringFiles
from ptk.application.use_cases.authoring import SetupAuthoring
from ptk.authoring_bundle import SKILLS, source_files
from ptk.domain.errors import PtkError
from ptk.drivers.cli.main import cli
from tests.conftest import grant_maintainer

from .test_workspace import repository, workspace


def test_vscode_setup_installs_tasks_skills_and_working_offline_links(
    tmp_path, monkeypatch
):
    repository(tmp_path, "consumer")
    grant_maintainer(tmp_path)
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    assert runner.invoke(cli, ["maintainer", "sync", "agent", "--check"]).exit_code == 1
    assert not (tmp_path / ".github").exists()
    assert runner.invoke(cli, ["maintainer", "sync", "tasks"]).exit_code == 0
    result = runner.invoke(cli, ["maintainer", "sync", "agent"])
    assert result.exit_code == 0, result.output
    assert (tmp_path / ".vscode/tasks.json").is_file()
    skills = list((tmp_path / ".github/skills").glob("*/SKILL.md"))
    assert {path.parent.name for path in skills} == set(SKILLS)
    for path in skills:
        text = path.read_text(encoding="utf-8")
        assert "src/ptk/" not in text and "tests/test_" not in text
        assert "../../ptk/docs/guides/agent-guide.rst" in text
        for target in re.findall(r"\]\(([^)]+)\)", text):
            resolved = (path.parent / target).resolve()
            assert resolved.is_relative_to(tmp_path / ".github"), (path, target)
            assert resolved.exists(), (path, target)
    agent = tmp_path / ".github/agents/ptk-expert.agent.md"
    assert agent.is_file()
    for target in re.findall(r"\]\(([^)]+)\)", agent.read_text()):
        assert (agent.parent / target).resolve().is_file(), target
    assert set(
        re.findall(r"../skills/(ptk-[a-z-]+)/SKILL.md", agent.read_text())
    ) == set(SKILLS)
    assert (tmp_path / ".github/ptk/docs/guides/agent-guide.rst").is_file()
    metadata = tmp_path / ".github/skills/ptk-log-analyzer/agents/openai.yaml"
    import yaml

    assert (
        yaml.safe_load(metadata.read_text())["interface"]["display_name"]
        == "PTK Log Analyzer"
    )
    schema = json.loads((tmp_path / ".github/ptk/config-schema.json").read_text())
    assert "StepSpec" in schema["$defs"]
    assert (
        tmp_path / ".github/ptk/examples/artifacts/config/artifactory_paths.ptk.yml"
    ).is_file()
    assert (tmp_path / ".github/ptk/docs/guides/artifacts.rst").is_file()
    before = {
        path: path.stat().st_mtime_ns
        for path in (tmp_path / ".github").rglob("*")
        if path.is_file()
    }
    assert runner.invoke(cli, ["maintainer", "sync", "agent", "--check"]).exit_code == 0
    assert runner.invoke(cli, ["maintainer", "sync", "agent"]).exit_code == 0
    assert before == {path: path.stat().st_mtime_ns for path in before}


def test_user_edits_and_unrelated_github_files_are_preserved(tmp_path):
    github = tmp_path / ".github"
    custom = github / "skills/custom/SKILL.md"
    custom.parent.mkdir(parents=True)
    custom.write_text("my own skill")
    service = SetupAuthoring(AuthoringFiles(), "1.0")
    service.execute(tmp_path)
    edited = github / "ptk/docs/reference/cli.rst"
    edited.write_text("local customization")
    before = {path: path.read_bytes() for path in github.rglob("*") if path.is_file()}
    for check in (True, False):
        with pytest.raises(PtkError, match="preserving locally changed"):
            SetupAuthoring(AuthoringFiles(), "2.0").execute(tmp_path, check=check)
        assert before == {path: path.read_bytes() for path in before}
    assert custom.read_text() == "my own skill"


def test_resource_updates_remove_only_unmodified_managed_files(tmp_path):
    adapter = AuthoringFiles()
    adapter.sync(
        tmp_path,
        {"ptk/docs/a.rst": b"old", "ptk/docs/obsolete.rst": b"old"},
        version="1",
        check=False,
    )
    custom = tmp_path / ".github/ptk/docs/custom.rst"
    custom.write_text("custom")
    changed = adapter.sync(
        tmp_path, {"ptk/docs/a.rst": b"new"}, version="2", check=True
    )
    assert "ptk/docs/obsolete.rst" in changed
    assert (tmp_path / ".github/ptk/docs/a.rst").read_text() == "old"
    adapter.sync(tmp_path, {"ptk/docs/a.rst": b"new"}, version="2", check=False)
    assert not (tmp_path / ".github/ptk/docs/obsolete.rst").exists()
    assert custom.read_text() == "custom"


def test_unowned_conflict_preflights_before_any_file_is_written(tmp_path, monkeypatch):
    repository(tmp_path, "consumer")
    grant_maintainer(tmp_path)
    conflict = tmp_path / ".github/skills/ptk-vmr/SKILL.md"
    conflict.parent.mkdir(parents=True)
    conflict.write_text("custom VMR skill")
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(cli, ["maintainer", "sync", "agent"])
    assert result.exit_code != 0 and "unowned" in result.output
    assert not (tmp_path / ".vscode/tasks.json").exists()
    assert not (tmp_path / ".github/ptk/manifest.json").exists()
    assert conflict.read_text() == "custom VMR skill"


def test_manifest_paths_and_symlinks_cannot_escape_project(tmp_path):
    adapter = AuthoringFiles()
    with pytest.raises(PtkError, match="invalid managed"):
        adapter.sync(tmp_path, {"ptk/../../outside": b"bad"}, version="1", check=False)
    outside = tmp_path / "outside"
    outside.mkdir()
    try:
        (tmp_path / ".github").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks unavailable")
    with pytest.raises(PtkError, match="symlinked"):
        adapter.sync(tmp_path, {"ptk/docs/a.rst": b"bad"}, version="1", check=False)
    assert not list(outside.iterdir())


def test_vmr_editor_setup_uses_selected_repository(tmp_path, monkeypatch):
    a, b = workspace(tmp_path)
    grant_maintainer(a.parent)
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(cli, ["firmware", "maintainer", "sync", "agent"])
    assert result.exit_code == 0, result.output
    assert (a.parent / ".github/skills/ptk-vmr/SKILL.md").exists()
    assert not (b.parent / ".github").exists()
    assert (
        CliRunner().invoke(cli, ["firmware", "maintainer", "sync", "tasks"]).exit_code
        == 0
    )
    tasks = json.loads((a.parent / ".vscode/tasks.json").read_text())
    assert tasks["tasks"][0]["command"] == "ptk"
    assert tasks["tasks"][0]["args"][:2] == ["firmware", "run"]


def test_bundle_ignores_local_config_and_generated_examples(tmp_path):
    root = Path(__file__).resolve().parents[1]
    assets = source_files(root)
    assert len(
        [
            name
            for name in assets
            if name.startswith("skills/") and name.endswith("/SKILL.md")
        ]
    ) == len(SKILLS)
    assert all(
        "local.ptk.yml" not in name and ".gen.version.ptk.yml" not in name
        for name in assets
    )
    assert all("_logs" not in name and "__pycache__" not in name for name in assets)
