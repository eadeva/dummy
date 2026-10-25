"""Bounded discovery and explicit workspace membership on real filesystems."""

from collections import Counter
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from ptk.adapters.config.yaml_loader import YamlConfigReader
from ptk.adapters.workspace import WorkspaceDiscovery, repositories, workspace_root
from ptk.bootstrap import create_app
from ptk.domain.errors import PtkError
from ptk.drivers.cli.main import cli

from .test_workspace import repository, workspace


def test_repo_proximity_does_not_grant_membership(tmp_path, monkeypatch):
    a, _ = workspace(tmp_path)
    standalone = repository(tmp_path / "standalone", "independent")
    (standalone.parent / ".git").mkdir()
    assert workspace_root(tmp_path) == tmp_path
    assert workspace_root(tmp_path / "nested") is None
    assert workspace_root(standalone.parent / "config") is None
    assert workspace_root(a.parent / "config") == tmp_path
    # A nested Git repository stops lookup before the outer member's pointer.
    nested = a.parent / "nested"
    (nested / ".git").mkdir(parents=True)
    assert workspace_root(nested) is None
    monkeypatch.chdir(standalone.parent / "config")
    result = CliRunner().invoke(cli, ["build"])
    assert result.exit_code == 0, result.output
    assert "independent" in result.output


@pytest.mark.parametrize("git_kind", ["projects/a.git", "worktrees/a.git"])
def test_relative_git_pointer_from_deep_subdirectory(tmp_path, git_kind):
    metadata = tmp_path / ".repo" / git_kind
    metadata.mkdir(parents=True)
    main = repository(tmp_path / "nested/a", "a")
    (main.parent / ".git").write_text(f"gitdir: ../../.repo/{git_kind}\n")
    assert workspace_root(main.parent / "config") == tmp_path


def test_broken_git_pointer_reports_a_cli_error(tmp_path, monkeypatch):
    repository(tmp_path, "demo")
    (tmp_path / ".git").write_text("gitdir: missing.git\n")
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(cli, ["build"])
    assert result.exit_code != 0
    assert "cannot resolve Git metadata" in result.output


def test_missing_index_does_not_fall_back_to_scanning(tmp_path, monkeypatch):
    (tmp_path / ".repo").mkdir()
    repository(tmp_path / "nested/member", "member")
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(cli, ["repos"])
    assert result.exit_code != 0
    assert "missing VMR project index" in result.output and "repo sync" in result.output
    # Init is independent of existing workspace discovery and uses its target.
    result = CliRunner().invoke(cli, ["setup", "init", "new-member", "--yes"])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "new-member/.main.ptk.yml").is_file()


def test_manual_marker_discovers_direct_children_only(tmp_path, monkeypatch):
    (tmp_path / ".main.ptk.yml").write_text("virtual_monorepo: true\n")
    direct = repository(tmp_path / "direct", "direct")
    repository(tmp_path / "nested/hidden", "hidden")
    # A malformed entry deep in an unrelated tree must never be read.
    (tmp_path / "nested/hidden/.main.ptk.yml").write_text("[invalid")
    assert repositories(tmp_path) == {"direct": direct}
    assert workspace_root(direct.parent) is None
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    for args in (["repos"], ["direct", "build"], ["setup", "config", "validate"]):
        result = runner.invoke(cli, args)
        assert result.exit_code == 0, result.output
    assert "hidden" not in runner.invoke(cli, ["repos"]).output


def test_manual_members_are_explicit_nested_paths(tmp_path, monkeypatch):
    (tmp_path / ".main.ptk.yml").write_text(
        "virtual_monorepo: true\nmembers: [nested/a, b, ignored]\n"
    )
    a = repository(tmp_path / "nested/a", "a")
    b = repository(tmp_path / "b", "b")
    repository(tmp_path / "unlisted", "unlisted")
    assert repositories(tmp_path) == {"a": a, "b": b}
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(cli, ["a", "build"])
    assert result.exit_code == 0, result.output


@pytest.mark.parametrize("member", ["..", "../outside", ".", ".repo/data", ".git"])
def test_manual_members_are_contained(tmp_path, member):
    (tmp_path / ".main.ptk.yml").write_text(
        yaml.safe_dump({"virtual_monorepo": True, "members": [member]})
    )
    with pytest.raises(PtkError, match="escapes workspace"):
        repositories(tmp_path)


def test_member_symlink_cannot_escape_workspace(tmp_path):
    root = tmp_path / "workspace"
    root.mkdir()
    outside = repository(tmp_path / "outside", "outside")
    (root / ".main.ptk.yml").write_text("virtual_monorepo: true\nmembers: [linked]\n")
    try:
        (root / "linked").symlink_to(outside.parent, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks unavailable")
    with pytest.raises(PtkError, match="escapes workspace"):
        repositories(root)


def test_explicit_false_opts_out_without_changing_automatic_default(
    tmp_path, monkeypatch
):
    a, b = workspace(tmp_path)
    a.write_text(a.read_text() + "virtual_monorepo: false\n")
    assert workspace_root(a.parent / "config") is None
    assert workspace_root(b.parent / "config") == tmp_path
    assert repositories(tmp_path) == {"bootloader": b}
    monkeypatch.chdir(a.parent)
    result = CliRunner().invoke(cli, ["build"])
    assert result.exit_code == 0, result.output


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ('virtual_monorepo: "true"', "must be a boolean"),
        ("virtual_monorepo: true\nvirtual_monorepo: false", "duplicate key"),
        ("virtual_monorepo: true\nrepository: {}", "unknown workspace field"),
        ("virtual_monorepo: true\ninclude: [absent.yml]", "unknown workspace field"),
        ("virtual_monorepo: true\nmembers: nested/a", "valid list"),
        ("virtual_monorepo: true\nmembers: [42]", "valid string"),
        ("virtual_monorepo: true\nmembers: !include absent.yml", "literal YAML"),
        ("repository: !include absent.yml", "literal YAML"),
    ],
)
def test_discovery_metadata_is_strict_and_does_not_load_includes(
    tmp_path, text, message
):
    (tmp_path / ".main.ptk.yml").write_text(text)
    with pytest.raises(PtkError, match=message):
        workspace_root(tmp_path)


@pytest.mark.parametrize("layer", ["config/actions.ptk.yml", "config/local.ptk.yml"])
def test_discovery_flag_cannot_come_from_includes_or_overlays(tmp_path, layer):
    repository(tmp_path, "demo")
    (tmp_path / layer).write_text("virtual_monorepo: false\n")
    with pytest.raises(PtkError, match="must be defined in the entry file"):
        create_app().load_project.execute(tmp_path)


def test_discovery_flag_cannot_be_changed_on_cli(tmp_path):
    repository(tmp_path, "demo")
    with pytest.raises(PtkError, match="cannot be overridden"):
        create_app().load_project.execute(
            tmp_path, overrides=["virtual_monorepo=false"]
        )
    (tmp_path / ".main.ptk.yml").write_text("virtual_monorepo: true\n")
    with pytest.raises(PtkError, match="select a member"):
        create_app().load_project.execute(tmp_path)


def test_discovery_is_reused_for_versions_and_credentials(tmp_path, monkeypatch):
    a, b = workspace(tmp_path)
    for main in (a, b):
        config = yaml.safe_load(main.read_text())
        config["versioning"] = {"project": {"source": "literal", "version": "1.0"}}
        if main == a:
            config["versioning"]["dependencies"] = {"bootloader": {}}
        config["credentials"] = {"shared": {"providers": ["env"]}}
        main.write_text(yaml.safe_dump(config))
    reads = Counter()
    metadata_reads = Counter()
    original_read = Path.read_text
    original_metadata = YamlConfigReader.read

    def read(path, *args, **kwargs):
        if path.name == "project.list":
            reads[path] += 1
        return original_read(path, *args, **kwargs)

    def metadata(reader, path, **kwargs):
        if kwargs.get("metadata_only"):
            metadata_reads[path] += 1
        return original_metadata(reader, path, **kwargs)

    monkeypatch.setattr(Path, "read_text", read)
    monkeypatch.setattr(YamlConfigReader, "read", metadata)
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, ["firmware", "build"])
    assert result.exit_code == 0, result.output
    assert reads == {tmp_path / ".repo/project.list": 1}
    assert metadata_reads == {a: 1, b: 1}
    # The next invocation sees a changed index instead of a process-global cache.
    (tmp_path / ".repo/project.list").write_text("b\n")
    result = runner.invoke(cli, ["repos"])
    assert result.exit_code == 0, result.output
    assert "bootloader" in result.output and "firmware" not in result.output
    assert reads[tmp_path / ".repo/project.list"] == 2


def test_manual_routing_supplies_context_for_shared_services(tmp_path):
    (tmp_path / ".main.ptk.yml").write_text("virtual_monorepo: true\n")
    for alias in ("a", "b"):
        main = repository(tmp_path / alias, alias)
        config = yaml.safe_load(main.read_text())
        config["versioning"] = {"project": {"source": "literal", "version": "1.0"}}
        if alias == "a":
            config["versioning"]["dependencies"] = {"b": {}}
        config["credentials"] = {"shared": {"providers": ["vault"]}}
        main.write_text(yaml.safe_dump(config))
    discovery = WorkspaceDiscovery()
    entries = discovery.repositories(tmp_path)
    one, two = create_app(workspace=discovery), create_app(workspace=discovery)
    a = one.load_project.execute(config_file=entries["a"])
    b = two.load_project.execute(config_file=entries["b"])
    assert set(one.versions().resolve(a)["projects"]) == {"a", "b"}
    assert (
        one.credentials(a).keys("shared")[0].storage_ref
        == two.credentials(b).keys("shared")[0].storage_ref
    )
    standalone = create_app()
    assert (
        standalone.credentials(a).keys("shared")[0].storage_ref
        != one.credentials(a).keys("shared")[0].storage_ref
    )
