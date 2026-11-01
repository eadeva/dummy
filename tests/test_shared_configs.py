"""Shared base configs: merge rules, sync/check/diff, ruff extend, validation."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from ptk.domain import shared_configs as sc
from ptk.domain.errors import PtkError
from ptk.drivers.cli.main import cli
from tests.cli_runner import CliRunner
from tests.conftest import grant_maintainer


def test_deep_merge_and_delete():
    base = {"A": 1, "B": {"x": 1, "y": 2}, "L": [1, 2]}
    assert sc.deep_merge(base, {"B": {"y": 3, "x": None}, "L": [9], "C": True}) == {
        "A": 1,
        "B": {"y": 3},
        "L": [9],
        "C": True,
    }
    assert base["B"] == {"x": 1, "y": 2}  # base untouched


def test_clang_tidy_checks_and_options():
    base = {
        "Checks": "-*,bugprone-*,cert-*,-readability-magic-numbers",
        "CheckOptions": [{"key": "a", "value": "1"}, {"key": "b", "value": "2"}],
        "FormatStyle": "file",
    }
    overlay = {
        "Checks": "-cert-*,readability-magic-numbers,google-*",
        "CheckOptions": {"b": "3", "a": None, "c": "4"},
    }
    merged = sc.merge_clang_tidy(base, overlay)
    assert (
        merged["Checks"] == "-*,bugprone-*,-cert-*,readability-magic-numbers,google-*"
    )
    assert merged["CheckOptions"] == [
        {"key": "b", "value": "3"},
        {"key": "c", "value": "4"},
    ]
    assert list(merged) == ["Checks", "CheckOptions", "FormatStyle"]


def test_pre_commit_merge():
    base = {
        "repos": [
            {
                "repo": "r1",
                "rev": "v1",
                "hooks": [{"id": "a"}, {"id": "b", "args": ["x"]}],
            },
            {"repo": "r2", "rev": "v1", "hooks": [{"id": "c"}]},
        ]
    }
    overlay = {
        "default_stages": ["pre-commit"],
        "repos": [
            {
                "repo": "r1",
                "rev": "v2",
                "hooks": [
                    {"id": "a", "disable": True},
                    {"id": "b", "args": ["y"]},
                    {"id": "d"},
                ],
            },
            {"repo": "r2", "disable": True},
            {
                "repo": "local",
                "hooks": [{"id": "mine", "entry": "x", "language": "system"}],
            },
        ],
    }
    merged = sc.merge_pre_commit(base, overlay)
    assert merged["default_stages"] == ["pre-commit"]
    assert [r["repo"] for r in merged["repos"]] == ["r1", "local"]
    assert merged["repos"][0] == {
        "repo": "r1",
        "rev": "v2",
        "hooks": [{"id": "b", "args": ["y"]}, {"id": "d"}],
    }


@pytest.fixture
def external(tmp_path):
    from ptk.adapters.shared_configs import GitConfigFiles
    from ptk.application.use_cases.configs import SharedConfigs
    from ptk.bootstrap import create_app
    from tests.project_files import write_project
    from tests.test_git_metadata import git, repo

    upstream = tmp_path / "upstream"
    upstream.mkdir()
    repo(upstream)
    (upstream / "style.yaml").write_text(
        "BasedOnStyle: LLVM\nIndentWidth: 4\nColumnLimit: 100\n"
    )
    (upstream / "ruff.toml").write_text('[lint]\nextend-select = ["I"]\n')
    (upstream / "hook.py").write_text('#!/usr/bin/env python\nprint("hook")\n')
    (upstream / "hook.py").chmod(0o755)
    git(upstream, "add", ".")
    git(upstream, "commit", "-m", "bases")
    git(upstream, "tag", "v1.0.0")
    root = tmp_path / "consumer"
    root.mkdir()
    config = {
        "repository": {"alias": "app", "config_path": "config"},
        "project": {"name": "Consumer"},
        "configs": {
            "source": {"repository": str(upstream), "revision": "v1.0.0"},
            "clang-format": {
                "files": [
                    {
                        "source": "style.yaml",
                        "destination": "config/external/clang-format.yaml",
                        "overlay": "config/format.overlay.yaml",
                        "output": ".clang-format",
                    }
                ]
            },
            "ruff": {
                "files": [
                    {
                        "source": "ruff.toml",
                        "destination": "config/external/ruff-base.toml",
                    }
                ]
            },
            "scripts": {
                "files": [
                    {"source": "hook.py", "destination": "scripts/shared/hook.py"}
                ]
            },
        },
    }
    write_project(root / ".main.ptk.yml", config)
    grant_maintainer(root)
    (root / "config/format.overlay.yaml").write_text("ColumnLimit: 120\n")
    adapter = GitConfigFiles()
    service = SharedConfigs(adapter)

    def project():
        return create_app().load_project.execute(root)

    return root, upstream, config, service, adapter, project


def test_external_sync_retains_pristine_bases_merges_and_tracks_provenance(external):
    import json

    from ptk.application.use_cases.configs import LOCK

    root, upstream, _, service, _, project = external
    plan = service.plan(project())
    assert any("ColumnLimit: 120" in item.diff(root) for item in plan)
    assert not (root / ".clang-format").exists()
    service.sync(project())
    assert (root / "config/external/clang-format.yaml").read_bytes() == (
        upstream / "style.yaml"
    ).read_bytes()
    assert yaml.safe_load((root / ".clang-format").read_text())["ColumnLimit"] == 120
    assert "Generated by PTK" in (root / ".clang-format").read_text()
    assert not (root / "ruff.toml").exists()
    assert (root / "config/external/ruff-base.toml").stat().st_mode & 0o200
    assert (root / "scripts/shared/hook.py").stat().st_mode & 0o111
    lock = json.loads((root / "config" / LOCK).read_text())
    assert not (root / LOCK).exists()
    assert len(lock["commit"]) == 40
    assert lock["files"]["config/external/clang-format.yaml"]["kind"] == "external-base"
    assert lock["files"][".clang-format"]["kind"] == "generated"
    assert all(item.status == "up to date" for item in service.check(project()))


def test_check_never_fetches_or_creates_cache(external, monkeypatch):
    root, _, _, service, adapter, project = external
    monkeypatch.setattr(
        adapter, "snapshot", lambda *a: pytest.fail("read-only check fetched")
    )
    assert any(item.status != "up to date" for item in service.check(project()))
    assert not (root / ".ptk").exists()


def test_overlay_changes_only_generated_output(external):
    root, _, _, service, _, project = external
    service.sync(project())
    base = (root / "config/external/clang-format.yaml").read_bytes()
    (root / "config/format.overlay.yaml").write_text("IndentWidth: 2\n")
    assert any(item.status != "up to date" for item in service.check(project()))
    service.sync(project())
    assert (root / "config/external/clang-format.yaml").read_bytes() == base
    assert yaml.safe_load((root / ".clang-format").read_text())["IndentWidth"] == 2


def test_modified_file_blocks_every_destination(external):
    root, _, _, service, _, project = external
    service.sync(project())
    target = root / "config/external/ruff-base.toml"
    target.chmod(0o644)
    target.write_text("local edits")
    before = (root / ".clang-format").read_bytes()
    (root / "config/format.overlay.yaml").write_text("IndentWidth: 2\n")
    from ptk.domain.errors import PtkError

    with pytest.raises(PtkError, match="locally modified"):
        service.sync(project())
    assert (
        target.read_text() == "local edits"
        and (root / ".clang-format").read_bytes() == before
    )


def test_tag_is_pinned_and_offline_reuse_works(external):
    from tests.test_git_metadata import git

    root, upstream, _, service, _, project = external
    service.sync(project())
    before = (root / "config/external/ruff-base.toml").read_bytes()
    (upstream / "ruff.toml").write_text("line-length=120\n")
    git(upstream, "add", ".")
    git(upstream, "commit", "-m", "update")
    git(upstream, "tag", "-f", "v1.0.0")
    service.sync(project())
    assert (root / "config/external/ruff-base.toml").read_bytes() == before
    upstream.rename(upstream.with_name("offline"))
    assert all(item.status == "up to date" for item in service.sync(project()))


def test_new_revision_updates_all_groups_and_preserves_overlay(external):
    from ptk.domain.errors import PtkError
    from tests.project_files import write_project
    from tests.test_git_metadata import git

    root, upstream, config, service, _, project = external
    service.sync(project())
    (upstream / "style.yaml").write_text("IndentWidth: 8\nColumnLimit: 80\n")
    git(upstream, "add", ".")
    git(upstream, "commit", "-m", "update")
    git(upstream, "tag", "v2.0.0")
    config["configs"]["source"]["revision"] = "v2.0.0"
    write_project(root / ".main.ptk.yml", config)
    with pytest.raises(PtkError, match="all configuration groups"):
        service.sync(project(), ["clang-format"])
    service.sync(project())
    assert yaml.safe_load((root / ".clang-format").read_text()) == {
        "IndentWidth": 8,
        "ColumnLimit": 120,
    }


@pytest.mark.parametrize(
    "path",
    [
        "../escape",
        "/absolute",
        "a/../b",
        "a\\b",
        ".git/config",
        ".ptk/state",
        ".main.ptk.yml",
    ],
)
def test_unsafe_destination_rejected(path):
    from pydantic import ValidationError

    from ptk.domain.config.model import ConfigFileMapping

    with pytest.raises(ValidationError):
        ConfigFileMapping(source="a", destination=path)


def test_paths_cannot_overlap_or_overwrite_overlays():
    from pydantic import ValidationError

    from ptk.domain.config.model import SharedConfigsSpec

    base = {
        "source": {
            "repository": "https://example.invalid/configs",
            "revision": "v1.0.0",
        },
        "clang-format": {
            "files": [
                {
                    "source": "a",
                    "destination": "external/a",
                    "overlay": "mine.yml",
                    "output": "out",
                }
            ]
        },
    }
    base["other"] = {"files": [{"source": "b", "destination": "mine.yml"}]}
    with pytest.raises(ValidationError, match="overlays must be separate"):
        SharedConfigsSpec.model_validate(base)
    base["other"]["files"][0]["destination"] = "external/a/child"
    with pytest.raises(ValidationError, match="cannot overlap"):
        SharedConfigsSpec.model_validate(base)


def test_links_missing_source_and_old_builtin_rejected(external):
    from pydantic import ValidationError

    from ptk.domain.config.model import StepSpec
    from ptk.domain.errors import PtkError
    from tests.project_files import write_project
    from tests.test_git_metadata import git

    root, upstream, config, service, _, project = external
    with pytest.raises(ValidationError):
        StepSpec(uses="configs.sync")
    (upstream / "link").symlink_to("style.yaml")
    git(upstream, "add", ".")
    git(upstream, "commit", "-m", "link")
    config["configs"]["source"]["revision"] = git(upstream, "rev-parse", "HEAD")
    config["configs"]["scripts"]["files"][0]["source"] = "link"
    write_project(root / ".main.ptk.yml", config)
    with pytest.raises(PtkError, match="regular Git file"):
        service.sync(project())
    assert not (root / ".clang-format").exists()
    config["configs"]["scripts"]["files"][0]["source"] = "missing"
    write_project(root / ".main.ptk.yml", config)
    with pytest.raises(PtkError, match="not found"):
        service.sync(project())


def test_cli_maintainer_only_and_read_only_validation(external):
    root, _, _, _, _, _ = external
    runner = CliRunner(env={"PTK_ROLE": "user"})
    for args in (
        ["maintainer", "sync", "configs"],
        ["maintainer", "sync", "configs", "--diff"],
        ["maintainer", "sync", "configs", "--check"],
    ):
        denied = runner.invoke(cli, args, cwd=root)
        assert denied.exit_code != 0 and "maintainer-only" in denied.output
    assert not (root / ".ptk").exists()
    check = runner.invoke(cli, ["validate", "--generated"], cwd=root)
    assert check.exit_code == 1 and not (root / ".ptk").exists()
    result = CliRunner(env={"PTK_ROLE": ""}).invoke(
        cli, ["maintainer", "sync", "configs"], cwd=root
    )
    assert result.exit_code == 0, result.output
    check = runner.invoke(cli, ["validate", "--generated"], cwd=root)
    assert check.exit_code == 0, check.output


def test_checkout_write_permissions_do_not_invalidate_content_check(external):
    root, _, _, service, _, project = external
    service.sync(project())
    base = root / "config/external/clang-format.yaml"
    base.chmod(0o644)
    assert all(item.status == "up to date" for item in service.check(project()))
    service.sync(project())
    assert base.stat().st_mode & 0o200
    base.chmod(0o644)
    base.write_text("IndentWidth: 9\n")
    assert any(item.status != "up to date" for item in service.check(project()))


def test_commit_revision_and_removed_mapping_preserve_existing_files(external):
    import json

    from ptk.application.use_cases.configs import LOCK
    from tests.project_files import write_project
    from tests.test_git_metadata import git

    root, upstream, config, service, _, project = external
    config["configs"]["source"]["revision"] = git(upstream, "rev-parse", "HEAD")
    write_project(root / ".main.ptk.yml", config)
    service.sync(project())
    del config["configs"]["ruff"]
    write_project(root / ".main.ptk.yml", config)
    service.sync(project())
    assert (root / "config/external/ruff-base.toml").is_file()
    assert (
        "config/external/ruff-base.toml"
        not in json.loads((root / "config" / LOCK).read_text())["files"]
    )
    assert all(item.status == "up to date" for item in service.check(project()))


def test_deviations_report_keeps_customizations_separate_from_modified_bases(
    external, monkeypatch
):
    root, _, _, service, adapter, project = external
    service.sync(project())
    monkeypatch.setattr(adapter, "snapshot", lambda *a: pytest.fail("report fetched"))
    report = service.write_deviations(project(), "_reports/deviations.json")
    assert report["modified_base_files"] == []
    assert len(report["deviations"]) == 1
    change = report["deviations"][0]
    assert "-ColumnLimit: 100" in change["diff"]
    assert "+ColumnLimit: 120" in change["diff"]
    assert "Generated by PTK" not in change["diff"]
    assert change["output_matches_sync"] is True
    (root / "config/external/ruff-base.toml").write_text("changed")
    report = service.write_deviations(project(), "_reports/deviations.json")
    assert report["modified_base_files"] == ["config/external/ruff-base.toml"]
    assert len(report["deviations"]) == 1
    (root / "config/external/clang-format.yaml").write_text("changed")
    report = service.deviations(project())
    assert report["deviations"] == []
    assert len(report["modified_base_files"]) == 2


def test_deviations_report_handles_missing_outputs_and_protects_authored_files(
    external,
):
    root, _, _, service, _, project = external
    service.sync(project())
    (root / ".clang-format").unlink()
    report = service.deviations(project())
    assert report["unavailable"] == [
        {"path": ".clang-format", "reason": "output missing"}
    ]
    for path in [
        "config/format.overlay.yaml",
        "config/external/ruff-base.toml",
        ".main.ptk.yml",
        "../outside.json",
    ]:
        with pytest.raises(PtkError):
            service.write_deviations(project(), path)
    (root / "own.json").write_text("{}")
    with pytest.raises(PtkError):
        service.write_deviations(project(), "own.json")


def test_deviations_cli_writes_json(external):
    import json

    root, _, _, service, _, project = external
    service.sync(project())
    result = CliRunner().invoke(cli, ["maintainer", "configs-report"], cwd=root)
    assert result.exit_code == 0, result.output
    assert json.loads((root / "_reports/config-deviations.json").read_text())[
        "deviations"
    ]


def test_sync_replaces_prior_read_only_copies_with_writable_files(external):
    import json

    from ptk.application.use_cases.configs import LOCK

    root, _, _, service, _, project = external
    service.sync(project())
    lock = json.loads((root / "config" / LOCK).read_text())
    for path, record in lock["files"].items():
        record["mode"] &= ~0o222
        (root / path).chmod(record["mode"])
    (root / "config" / LOCK).write_text(json.dumps(lock))
    service.sync(project())
    assert all((root / path).stat().st_mode & 0o200 for path in lock["files"])


def test_report_uses_current_output_and_marks_edits(external):
    root, _, _, service, _, project = external
    service.sync(project())
    (root / ".clang-format").write_text("ColumnLimit: 180\n")
    report = service.deviations(project())
    assert report["modified_base_files"] == []
    assert report["deviations"][0]["output_matches_sync"] is False
    assert "+ColumnLimit: 180" in report["deviations"][0]["diff"]


@pytest.mark.parametrize("config_path", [".", "settings/ptk"])
def test_lock_follows_repository_configuration_directory(external, config_path):
    from ptk.application.use_cases.configs import LOCK
    from tests.project_files import write_project

    root, _, config, service, _, project = external
    config["repository"]["config_path"] = config_path
    write_project(root / ".main.ptk.yml", config)
    service.sync(project())
    assert (root / config_path / LOCK).is_file()
    assert all(item.status == "up to date" for item in service.check(project()))
    assert service.deviations(project())["modified_base_files"] == []
    with pytest.raises(PtkError):
        service.write_deviations(project(), (Path(config_path) / LOCK).as_posix())


def test_root_lock_is_not_used_as_fallback(external):
    from ptk.application.use_cases.configs import LOCK

    root, _, _, service, _, project = external
    service.sync(project())
    (root / "config" / LOCK).rename(root / LOCK)
    assert any(item.status != "up to date" for item in service.check(project()))
    with pytest.raises(PtkError, match="synchronize"):
        service.deviations(project())
