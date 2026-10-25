"""Repository discovery and VMR dispatch through the real CLI."""

import os

import pytest
import yaml
from click.testing import CliRunner

from ptk.adapters.config.source import FileConfigSource
from ptk.adapters.workspace import repositories, workspace_root
from ptk.bootstrap import create_app
from ptk.domain.errors import PtkError
from ptk.drivers.cli.main import cli


def repository(root, alias, *, config_path="config"):
    root.mkdir(parents=True, exist_ok=True)
    (root / config_path).mkdir(parents=True, exist_ok=True)
    main = root / ".main.ptk.yml"
    main.write_text(
        yaml.safe_dump(
            {
                "repository": {"alias": alias, "config_path": config_path},
                "project": {"name": alias, "default_action": "build"},
                "include": ["actions.ptk.yml"],
            }
        )
    )
    (root / config_path / "actions.ptk.yml").write_text(
        yaml.safe_dump(
            {
                "vars": {"value": alias},
                "actions": {
                    "build": {
                        "steps": [
                            {
                                "hello": {
                                    "uses": "echo",
                                    "with": {"message": "${vars.value}"},
                                }
                            }
                        ]
                    }
                },
            }
        )
    )
    return main


def workspace(tmp_path):
    (tmp_path / ".repo").mkdir()
    (tmp_path / ".repo" / "project.list").write_text("nested/a\nb\nignored\n")
    a = repository(tmp_path / "nested/a", "firmware")
    b = repository(tmp_path / "b", "bootloader")
    for main in (a, b):
        target = tmp_path / ".repo/projects" / main.parent.relative_to(tmp_path)
        target.mkdir(parents=True)
        (main.parent / ".git").write_text(
            f"gitdir: {os.path.relpath(target, main.parent)}\n"
        )
    (tmp_path / "ignored").mkdir()
    return a, b


def test_config_base_execution_root_and_overlays(tmp_path, monkeypatch):
    main = repository(tmp_path, "firmware", config_path="tooling/ptk")
    config = main.parent / "tooling/ptk"
    (config / "tools.ptk.yml").write_text("tools: {ninja: {version: '>=1'}}")
    (config / "build.tools.ptk.yml").write_text(
        "actions: {build: {requires_tools: {ninja: true}}}"
    )
    (config / "cx.ptk.yml").write_text("vars: {value: cx}")
    (config / "local.ptk.yml").write_text("vars: {value: local}")
    (config / "maintainers.ptk.yml").write_text("maintainers: [{email: a@b.c}]")
    (tmp_path / "local.ptk.yml").write_text("vars: {value: wrong}")
    p = create_app(environ={}).load_project.execute(config, ci=True)
    assert p.root == tmp_path and p.config_root == config
    assert p.config.vars["value"] == "local"
    assert p.config.actions["build"].required_tool_names == ["ninja"]
    assert p.maintainers is not None
    # The generated command executes relative to repo root, not config dir.
    (config / "actions.ptk.yml").write_text(
        yaml.safe_dump(
            {
                "actions": {
                    "build": {
                        "steps": [
                            {
                                "copy": {
                                    "uses": "files.copy",
                                    "with": {
                                        "files": ["input.txt"],
                                        "to": "out",
                                    },
                                }
                            }
                        ]
                    }
                }
            }
        )
    )
    (tmp_path / "input.txt").write_text("repo-root")
    (config / "build.tools.ptk.yml").unlink()
    monkeypatch.chdir(config)
    result = CliRunner().invoke(cli, ["build"])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "out/input.txt").read_text() == "repo-root"


def test_vmr_cli_isolates_repositories_and_preserves_commands(tmp_path, monkeypatch):
    a, b = workspace(tmp_path)
    monkeypatch.chdir(tmp_path)
    runner = CliRunner(env={"PTK_ROLE": "user"})
    help_result = runner.invoke(cli, ["--help"])
    assert help_result.exit_code == 0, help_result.output
    assert "firmware" in help_result.output and "bootloader" in help_result.output
    assert runner.invoke(cli, []).exit_code == 0
    for alias, entry in [("firmware", a), ("bootloader", b)]:
        for command in [["--help"], ["setup", "config", "validate"], ["build"], []]:
            result = runner.invoke(cli, [alias, *command])
            assert result.exit_code == 0, result.output
        assert (entry.parent / "_logs").is_dir()
    override = runner.invoke(cli, ["--set", "vars.value=changed", "firmware", "build"])
    assert override.exit_code == 0 and "changed" in override.output
    normal = runner.invoke(cli, ["bootloader", "build"])
    assert "changed" not in normal.output and normal.exit_code == 0
    monkeypatch.chdir(a.parent / "config")
    nested = runner.invoke(cli, ["bootloader", "build"])
    assert nested.exit_code == 0, nested.output
    explicit = runner.invoke(cli, ["-c", str(a), "build"])
    assert explicit.exit_code == 0, explicit.output


def test_vmr_permissions_are_per_repository(tmp_path, monkeypatch):
    a, _b = workspace(tmp_path)
    data = yaml.safe_load(a.read_text())
    data["command_audience"] = {"setup.config": "maintainer"}
    a.write_text(yaml.safe_dump(data))
    monkeypatch.chdir(tmp_path)
    runner = CliRunner(env={"PTK_ROLE": "user"})
    result = runner.invoke(cli, ["firmware", "setup", "config", "validate"])
    assert result.exit_code != 0 and "maintainer-only" in result.output
    result = runner.invoke(cli, ["bootloader", "setup", "config", "validate"])
    assert result.exit_code == 0, result.output


def test_metadata_is_required_and_contained(tmp_path):
    main = tmp_path / ".main.ptk.yml"
    for text, message in [
        ("project: {name: missing}", "requires repository"),
        ("repository: {alias: bad_name, config_path: .}", "alias"),
        ("repository: {alias: ok, config_path: ..}", "within the repository"),
        ("repository: {alias: ok, config_path: absent}", "does not exist"),
    ]:
        main.write_text(text)
        with pytest.raises(PtkError, match=message):
            create_app(environ={}).load_project.execute(tmp_path)


def test_no_legacy_discovery_or_parent_repo_leak(tmp_path):
    (tmp_path / "main.ptk.yml").write_text("project: {name: old}")
    with pytest.raises(PtkError, match="no .main"):
        FileConfigSource().find_main(tmp_path)
    repository(tmp_path, "outer")
    child = tmp_path / "child"
    (child / ".git").mkdir(parents=True)
    with pytest.raises(PtkError, match="no .main"):
        FileConfigSource().find_main(child)
    deep = child / "deep"
    repository(deep, "misplaced")
    with pytest.raises(PtkError, match="must be at repository root"):
        FileConfigSource().find_main(deep)


def test_vmr_alias_conflicts_and_member_containment(tmp_path):
    _a, b = workspace(tmp_path)
    data = yaml.safe_load(b.read_text())
    data["repository"]["alias"] = "firmware"
    b.write_text(yaml.safe_dump(data))
    with pytest.raises(PtkError, match="duplicate repository alias"):
        repositories(tmp_path)
    (tmp_path / ".repo/project.list").write_text("../outside\n")
    with pytest.raises(PtkError, match="escapes workspace"):
        repositories(tmp_path)


def test_gitdir_pointer_identifies_vmr_but_not_regular_worktree(tmp_path):
    root = tmp_path / "workspace"
    target = root / ".repo/projects/a.git"
    target.mkdir(parents=True)
    member = tmp_path / "external"
    member.mkdir()
    (member / ".git").write_text(f"gitdir: {target}\n")
    assert workspace_root(member) == root
    regular = tmp_path / "ordinary/.git/worktrees/a"
    regular.mkdir(parents=True)
    (member / ".git").write_text(f"gitdir: {regular}\n")
    assert workspace_root(member) is None


def test_symlink_git_and_unindexed_workspaces(tmp_path):
    root = tmp_path / "workspace"
    target = root / ".repo/projects/a.git"
    target.mkdir(parents=True)
    main = repository(root / "nested/a", "a")
    try:
        (main.parent / ".git").symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks unavailable")
    assert workspace_root(main.parent) == root
    with pytest.raises(PtkError, match="missing VMR project index.*repo sync"):
        repositories(root)
    (root / ".repo/project.list").write_text("nested/a\n")
    assert repositories(root) == {"a": main}


def test_nested_include_bases_and_source_locations(tmp_path):
    main = repository(tmp_path, "demo")
    (tmp_path / "config/parts").mkdir()
    (tmp_path / "config/actions.ptk.yml").write_text(
        "include: [parts/values.ptk.yml]\n"
    )
    (tmp_path / "config/parts/values.ptk.yml").write_text("vars: {value: fragment}\n")
    data = yaml.safe_load(main.read_text())
    data["project"].pop("default_action")
    main.write_text(yaml.safe_dump(data))
    project = create_app(environ={}).load_project.execute(tmp_path)
    assert project.config.vars["value"] == "fragment"
    assert "config/parts/values.ptk.yml:1" in str(project.location(("vars", "value")))
    with pytest.raises(PtkError, match="cannot be overridden"):
        create_app(environ={}).load_project.execute(
            tmp_path, overrides=["repository.config_path=.."]
        )


def test_vmr_help_tasks_and_variant_edits(tmp_path, monkeypatch):
    import json

    a, _b = workspace(tmp_path)
    data = yaml.safe_load(a.read_text())
    data["variants"] = {"variants": {"debug": {}, "release": {}}}
    a.write_text(yaml.safe_dump(data))
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, ["firmware", "help", "--no-open"])
    assert result.exit_code == 0, (result.output, result.exception)
    assert "ptk firmware build" in (a.parent / ".ptk/help.html").read_text()
    result = runner.invoke(cli, ["firmware", "setup", "vscode", "tasks"])
    assert result.exit_code == 0, result.output
    tasks = json.loads((a.parent / ".vscode/tasks.json").read_text())
    assert tasks["tasks"][0]["command"] == "ptk firmware"
    result = runner.invoke(cli, ["firmware", "variant", "set", "debug"])
    assert result.exit_code == 0, result.output
    assert (a.parent / "config/local.ptk.yml").is_file()
    assert not (a.parent / "local.ptk.yml").exists()


def test_unselected_repository_broken_include_does_not_block_command(
    tmp_path, monkeypatch
):
    _a, b = workspace(tmp_path)
    (b.parent / "config/actions.ptk.yml").unlink()
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(cli, ["firmware", "build"])
    assert result.exit_code == 0, result.output
    result = CliRunner().invoke(cli, ["bootloader", "setup", "config", "validate"])
    assert result.exit_code != 0 and "included file not found" in result.output


def test_shared_workspace_views_and_no_global_installer(tmp_path, monkeypatch):
    workspace(tmp_path)
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    for args in (
        ["repos"],
        ["setup", "config", "validate"],
        ["setup", "config", "show", "project.name"],
        ["variant", "list"],
        ["report", "list"],
        ["report", "summary"],
    ):
        result = runner.invoke(cli, args)
        assert result.exit_code == 0, (args, result.output, result.exception)
    result = runner.invoke(cli, ["setup", "install"])
    assert result.exit_code != 0
    result = runner.invoke(cli, ["setup", "config", "show", "project.name"])
    assert "[firmware]" in result.output and "[bootloader]" in result.output


def test_shared_credentials_merge_conflicts_and_namespace(tmp_path, monkeypatch):
    from ptk.bootstrap import create_app

    a, b = workspace(tmp_path)
    for file in (a, b):
        data = yaml.safe_load(file.read_text())
        data["credentials"] = {
            "shared": {"providers": ["vault"]},
            "different": {"providers": ["vault"], "description": file.parent.name},
        }
        file.write_text(yaml.safe_dump(data))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PTK_VAULT_FILE", str(tmp_path / "vault.json"))
    monkeypatch.setenv("PTK_VAULT_PASSWORD", "synthetic-password")
    runner = CliRunner()
    result = runner.invoke(cli, ["setup", "creds", "list"])
    assert result.exit_code == 0, result.output
    assert (
        "firmware/different" in result.output
        and "bootloader/different" in result.output
    )
    assert "shared.token [bootloader, firmware]" in result.output
    assert (
        runner.invoke(
            cli, ["setup", "creds", "set", "different"], input="ambiguous\n"
        ).exit_code
        != 0
    )
    result = runner.invoke(
        cli, ["setup", "creds", "set", "shared"], input="shared-synthetic\n"
    )
    assert result.exit_code == 0, (result.output, result.exception)
    result = runner.invoke(
        cli,
        ["setup", "creds", "set", "firmware/different"],
        input="private-synthetic\n",
    )
    assert result.exit_code == 0, result.output
    one, two = create_app(), create_app()
    ap, bp = (
        one.load_project.execute(config_file=a),
        two.load_project.execute(config_file=b),
    )
    assert one.credentials(ap).resolve("shared.token") == two.credentials(bp).resolve(
        "shared.token"
    )
    assert (
        one.credentials(ap).keys("different")[0].storage_ref
        != two.credentials(bp).keys("different")[0].storage_ref
    )
    # Listing a locked vault must not retrieve or prompt for a value.
    monkeypatch.delenv("PTK_VAULT_PASSWORD")
    result = runner.invoke(cli, ["setup", "creds", "list"])
    assert result.exit_code == 0 and "not read or verified" in result.output
    assert "shared-synthetic" not in result.output
