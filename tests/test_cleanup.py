"""Destructive operations are scoped and preflighted before any deletion."""

import json

import pytest
import yaml
from click.testing import CliRunner

from ptk.drivers.cli.main import cli
from tests.workflows.test_cli import command, invoke, repository

ROOTS = ("_builds", "_bin", "_logs", "_reports")


def seed(root, variant="debug", job="build", roots=ROOTS):
    paths = []
    for name in roots:
        path = root / name / variant / job / "marker"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("keep")
        paths.append(path)
    return paths


def variant_config(**extra):
    return {
        "variants": {"default": "debug", "variants": {"debug": {}, "release": {}}},
        **extra,
    }


def test_clean_scope_no_execution_or_required_parameters(tmp_path):
    job = command("from pathlib import Path; Path('ran').touch()")
    job["params"] = {
        "required": {"required": True},
        "secret": {"type": "secret", "required": True},
    }
    repository(tmp_path, jobs={"build": job}, extra=variant_config())
    deleted = seed(tmp_path)
    kept = seed(tmp_path, "release") + seed(tmp_path, job="other")
    preview = invoke(tmp_path, "-V", "debug", "-c", "dry-run", "build")
    assert preview.exit_code == 0, preview.output
    assert all(p.exists() for p in deleted + kept)
    result = invoke(tmp_path, "-V", "debug", "-c", "build")
    assert result.exit_code == 0, result.output
    assert not any(p.exists() for p in deleted)
    assert all(p.exists() for p in kept)
    assert not (tmp_path / "ran").exists()


def test_rerun_and_all_variant_preflight(tmp_path):
    repository(
        tmp_path,
        jobs={"build": command("from pathlib import Path; Path('ran').touch()")},
        extra=variant_config(),
    )
    paths = seed(tmp_path)
    result = invoke(tmp_path, "-V", "debug,missing", "-rr", "build")
    assert result.exit_code == 2
    assert all(p.exists() for p in paths)
    result = invoke(tmp_path, "-V", "debug", "-rr", "build")
    assert result.exit_code == 0, result.output
    assert not any(p.exists() for p in paths)
    assert (tmp_path / "ran").exists()


def test_configured_folders_confirmation_and_all(tmp_path):
    repository(tmp_path)
    names = ("build-output", "binaries", "logs", "reports")
    (tmp_path / "config/folder_structure.ptk.yml").write_text(
        yaml.safe_dump(
            {
                "layout": dict(
                    zip(("builds", "bin", "logs", "reports"), names, strict=True)
                )
            }
        )
    )
    paths = seed(tmp_path, roots=names) + seed(tmp_path, "release", roots=names)
    default = seed(tmp_path)
    result = invoke(tmp_path, "clean-all")
    assert result.exit_code != 0
    assert all(p.exists() for p in paths)
    result = invoke(tmp_path, "clean-all", "--yes")
    assert result.exit_code == 0, result.output
    assert not any(p.exists() for p in paths)
    assert all(p.exists() for p in default)


def test_unsafe_config_and_active_job_refuse_before_deletion(tmp_path):
    repository(tmp_path)
    paths = seed(tmp_path, "default")
    lock = tmp_path / ".ptk/locks/default/build.lock"
    lock.parent.mkdir(parents=True)
    lock.write_text("active")
    result = invoke(tmp_path, "clean-all", "--yes")
    assert result.exit_code == 2 and "locked" in result.output
    assert all(p.exists() for p in paths)
    lock.unlink()
    (tmp_path / "config/folder_structure.ptk.yml").write_text(
        "layout: {reports: config}\n"
    )
    result = invoke(tmp_path, "clean-all", "--yes")
    assert result.exit_code == 2 and "protected" in result.output
    assert all(p.exists() for p in paths)


def test_symlink_output_refused(tmp_path):
    root = tmp_path / "repo"
    repository(root)
    outside = tmp_path / "outside"
    outside.mkdir()
    marker = outside / "keep"
    marker.touch()
    try:
        (root / "_bin").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks unavailable")
    paths = seed(root, roots=("_builds", "_logs", "_reports"))
    result = invoke(root, "clean-all", "--yes")
    assert result.exit_code == 2 and "unsafe" in result.output
    assert marker.exists() and all(p.exists() for p in paths)


def workspace(tmp_path, mapping):
    (tmp_path / ".main.ptk.yml").write_text("virtual_monorepo: true\nmembers: [a, b]\n")
    variants = variant_config()
    variants["variants"]["variants"]["debug"]["repo_variants"] = mapping
    repository(
        tmp_path / "a",
        "a",
        extra=variants,
        workflows={
            "verify": {
                "steps": [{"own": "build"}, {"other": {"repo": "b", "job": "build"}}]
            }
        },
    )
    repository(tmp_path / "b", "b", extra=variant_config())


def test_mapping_and_invalid_mapping_cleanup_preflight(tmp_path, monkeypatch):
    workspace(tmp_path, {})
    monkeypatch.chdir(tmp_path)
    paths = seed(tmp_path / "a") + seed(tmp_path / "b", "release")
    runner = CliRunner(env={"PTK_CI": "0", "PTK_ROLE": "user"})
    args = ["-V", "debug", "-c", "a", "workflow", "run", "verify"]
    result = runner.invoke(cli, args)
    assert result.exit_code == 2 and "missing repo_variants" in result.output, (
        result.output
    )
    assert all(p.exists() for p in paths)
    p = tmp_path / "a/config/project.ptk.yml"
    data = yaml.safe_load(p.read_text())
    data["variants"]["variants"]["debug"]["repo_variants"] = {"b": "release"}
    p.write_text(yaml.safe_dump(data))
    kept = seed(tmp_path / "b")
    result = runner.invoke(cli, args)
    assert result.exit_code == 0, result.output
    assert "b/build [release]" in result.output
    assert not any(p.exists() for p in paths)
    assert all(p.exists() for p in kept)
    result = runner.invoke(cli, ["vmr-clean-all", "--yes"])
    assert result.exit_code == 0, result.output
    assert not any(p.exists() for p in kept)


def test_job_filters_error_steps_skip_and_only_cx_hidden(tmp_path):
    jobs = {
        "build": {**command("pass"), "only_variants": ["release"]},
        "ci": {**command("pass"), "only_cx": True},
        "check": {
            "steps": [
                {
                    "skip": {
                        "uses": "echo",
                        "with": {"message": "never"},
                        "omit_variants": ["debug"],
                    }
                },
                {"cx": {"uses": "echo", "with": {"message": "never"}, "only_cx": True}},
            ]
        },
    }
    repository(tmp_path, jobs=jobs, extra=variant_config())
    result = invoke(tmp_path, "-c", "build")
    assert result.exit_code == 2 and "only_variants" in result.output
    result = invoke(tmp_path, "describe", "--json")
    assert "ci" not in [
        j["name"] for j in json.loads(result.output)["projects"][0]["jobs"]
    ]
    result = invoke(tmp_path, "dry-run", "check")
    assert (
        result.exit_code == 0
        and "omit_variants" in result.output
        and "only_cx" in result.output
    )


def test_old_workflow_variant_rejected(tmp_path):
    repository(
        tmp_path,
        workflows={
            "verify": {"steps": [{"bad": {"job": "build", "variant": "debug"}}]}
        },
    )
    result = invoke(tmp_path, "workflow", "dry-run", "verify")
    assert result.exit_code == 2 and "variant" in result.output


@pytest.mark.parametrize("mapped", ["missing", "abstract"])
def test_invalid_mapping_preserves_all_outputs(tmp_path, monkeypatch, mapped):
    workspace(tmp_path, {"b": mapped})
    p = tmp_path / "b/config/project.ptk.yml"
    data = yaml.safe_load(p.read_text())
    data["variants"]["variants"]["abstract"] = {"abstract": True}
    p.write_text(yaml.safe_dump(data))
    monkeypatch.chdir(tmp_path)
    paths = seed(tmp_path / "a") + seed(tmp_path / "b")
    result = CliRunner(env={"PTK_CI": "0"}).invoke(cli, ["-c", "a", "verify"])
    assert result.exit_code == 2, result.output
    assert all(p.exists() for p in paths)


def test_inherited_mapping_and_workflow_rerun(tmp_path, monkeypatch):
    workspace(tmp_path, {})
    p = tmp_path / "a/config/project.ptk.yml"
    data = yaml.safe_load(p.read_text())
    data["variants"]["variants"]["base"] = {
        "abstract": True,
        "repo_variants": {"b": "release"},
    }
    data["variants"]["variants"]["debug"]["extends"] = ["base"]
    p.write_text(yaml.safe_dump(data))
    paths = seed(tmp_path / "a") + seed(tmp_path / "b", "release")
    monkeypatch.chdir(tmp_path)
    runner = CliRunner(env={"PTK_CI": "0"})
    result = runner.invoke(
        cli, ["-V", "debug", "-rr", "workflow", "dry-run", "a/verify"]
    )
    assert result.exit_code == 0, result.output
    assert all(p.exists() for p in paths)
    result = runner.invoke(cli, ["-V", "debug", "-rr", "workflow", "run", "a/verify"])
    assert result.exit_code == 0, result.output
    assert not any(p.exists() for p in paths)
    assert (tmp_path / "a/_logs/debug/build/run.json").is_file()
    assert (tmp_path / "b/_logs/release/build/run.json").is_file()


def test_vmr_all_preflights_last_member_and_cleans_workspace_reports(
    tmp_path, monkeypatch
):
    workspace(tmp_path, {"b": "release"})
    monkeypatch.chdir(tmp_path)
    paths = seed(tmp_path / "a") + seed(tmp_path / "b") + seed(tmp_path)
    lock = tmp_path / "b/.ptk/locks/debug/build.lock"
    lock.parent.mkdir(parents=True)
    lock.touch()
    runner = CliRunner(env={"PTK_CI": "0"})
    result = runner.invoke(cli, ["vmr-clean-all", "--yes"])
    assert result.exit_code == 2 and "locked" in result.output
    assert all(p.exists() for p in paths)
    lock.unlink()
    result = runner.invoke(cli, ["vmr-clean-all", "--yes"])
    assert result.exit_code == 0, result.output
    assert not any(p.exists() for p in paths)


def test_clean_all_refuses_git_tracked_outputs(tmp_path):
    import subprocess

    repository(tmp_path)
    paths = seed(tmp_path)
    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "add", "_reports"], check=True)
    result = invoke(tmp_path, "clean-all", "--yes")
    assert result.exit_code == 2 and "Git-tracked" in result.output
    assert all(p.exists() for p in paths)


def test_clean_all_variants_and_custom_reporting(tmp_path):
    repository(tmp_path, extra=variant_config(reporting={"dir": "custom-reports"}))
    paths = (
        seed(tmp_path)
        + seed(tmp_path, "release")
        + seed(tmp_path, roots=("custom-reports",))
    )
    kept = seed(tmp_path, job="another")
    result = invoke(tmp_path, "-c", "build", "--all-variants")
    assert result.exit_code == 0, result.output
    assert not any(p.exists() for p in paths)
    assert all(p.exists() for p in kept)
