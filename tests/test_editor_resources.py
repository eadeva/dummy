"""Skills installed in consumer repositories must be usable without a PTk checkout."""

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


def test_agent_setup_installs_skills_and_working_offline_links(tmp_path, monkeypatch):
    repository(tmp_path, "consumer")
    grant_maintainer(tmp_path)
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    assert runner.invoke(cli, ["maintainer", "sync", "agent", "--check"]).exit_code == 1
    assert not (tmp_path / ".github").exists()
    result = runner.invoke(cli, ["maintainer", "sync", "agent"])
    assert result.exit_code == 0, result.output
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
        == "PTk Log Analyzer"
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
    assert not (tmp_path / ".github/ptk/manifest.json").exists()
    assert conflict.read_text() == "custom VMR skill"
    declined = CliRunner().invoke(
        cli, ["maintainer", "sync", "agent", "--force"], input="n\n"
    )
    assert declined.exit_code != 0
    assert ".github/skills/ptk-vmr/SKILL.md" in declined.output
    assert conflict.read_text() == "custom VMR skill"
    accepted = CliRunner().invoke(
        cli, ["maintainer", "sync", "agent", "--force"], input="y\n"
    )
    assert accepted.exit_code == 0, accepted.output
    assert conflict.read_text() != "custom VMR skill"
    assert (tmp_path / ".github/ptk/manifest.json").exists()


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


def test_bundle_ignores_local_config_and_generated_examples(tmp_path):
    root = Path(__file__).resolve().parents[1]
    assets = source_files(root)
    assert not any("plugin" in name for name in assets)
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


def test_all_installed_reference_links_are_self_contained(tmp_path):
    from scripts.prepare_package import check_skill_links

    SetupAuthoring(AuthoringFiles(), "review").execute(tmp_path)
    check_skill_links(tmp_path)
    assert not (tmp_path / "src").exists()
    assert not (tmp_path / "pyproject.toml").exists()
    assert (tmp_path / ".github/ptk/docs/guides/local-setup.rst").is_file()
    assert not (tmp_path / ".github/skills/ptk-development").exists()
    assert not (tmp_path / ".github/skills/ptk-docs-writing").exists()


def test_managed_config_readme_sync_check_update_conflict_and_relocation(
    tmp_path, monkeypatch
):
    from ptk.application.use_cases import init_readme
    from ptk.bootstrap import create_app

    app = create_app(environ={})
    app.init_project.execute(tmp_path, config_path="config/ptk")
    readme = tmp_path / "config/ptk/README.md"
    original = readme.read_text()
    monkeypatch.setattr(
        init_readme, "TEMPLATE", init_readme.TEMPLATE + "\nNew PTk guidance.\n"
    )
    assert app.setup_authoring.execute(
        tmp_path, config_path="config/ptk", check=True
    ).paths
    assert readme.read_text() == original
    app.setup_authoring.execute(tmp_path, config_path="config/ptk")
    assert "New PTk guidance." in readme.read_text()
    readme.write_text("local edit")
    manifest = tmp_path / ".github/ptk/manifest.json"
    before = manifest.read_bytes()
    with pytest.raises(PtkError, match="preserving locally changed"):
        app.setup_authoring.execute(tmp_path, config_path="other/deep/config")
    assert readme.read_text() == "local edit" and manifest.read_bytes() == before
    readme.write_text(original + "\nNew PTk guidance.\n", newline="")
    app.setup_authoring.execute(tmp_path, config_path="other/deep/config")
    relocated = tmp_path / "other/deep/config/README.md"
    assert not readme.exists()
    assert "../../../.github/agents/ptk-expert.agent.md" in relocated.read_text()
    assert (
        json.loads(manifest.read_text())["configuration_readme"]["path"]
        == "other/deep/config/README.md"
    )


def test_readme_sync_rejects_unowned_files_and_unsafe_paths(tmp_path):
    adapter = AuthoringFiles()
    readme = tmp_path / "README.md"
    readme.write_text("project owned")
    with pytest.raises(PtkError, match="unowned"):
        adapter.sync(
            tmp_path,
            {},
            version="1",
            check=False,
            configuration_readme=("README.md", b"generated"),
        )
    assert not (tmp_path / ".github").exists()
    for path in ("../README.md", ".git/README.md", "config/not-readme.md"):
        with pytest.raises(PtkError, match="invalid configuration README"):
            adapter.sync(
                tmp_path,
                {},
                version="1",
                check=False,
                configuration_readme=(path, b"generated"),
            )
