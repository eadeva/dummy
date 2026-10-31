"""Workflow setup metadata is bounded, executable, portable and read-only."""

import json

import pytest
from click.shell_completion import BashComplete

from ptk.application.use_cases.run import RunJob
from ptk.application.use_cases.versioning import VersionService
from ptk.drivers.cli.main import cli
from tests.cli_runner import CliRunner
from tests.conftest import grant_maintainer
from tests.project_files import write_project
from tests.test_command_access import snapshot
from tests.test_git_metadata import git, pr, repo

AT = "2026-10-31T12:34:56+00:00"


@pytest.fixture
def project(tmp_path):
    repo(tmp_path)

    def job(**fields):
        return {
            "steps": {
                "compile": {"uses": "echo", "with": {"message": "matrix execution"}}
            },
            **fields,
        }

    model = {
        "repository": {"alias": "firmware", "config_path": "config"},
        "project": {"name": "Firmware"},
        "versioning": {"project": {"source": "literal", "version": "1.2.3"}},
        "variants": {
            "default": "debug",
            "variants": {
                "base": {"abstract": True},
                "debug": {"extends": ["base"], "aliases": ["dev"]},
                "release": {"extends": ["base"], "aliases": ["prod"]},
            },
        },
        "jobs": {
            "build": job(
                outputs=[
                    "${steps.compile.build_dir}/application.bin",
                    "dist/${run.variant}/metadata.json",
                ]
            ),
            "package": job(only_variants=["release"], outputs=["dist/package.zip"]),
            "test": job(omit_variants=["release"]),
            "cx": job(only_cx=True),
            "private": job(audience="maintainer"),
        },
        "artifactory": {
            "url": "https://artifacts.example.invalid/artifactory",
            "repository": "ci-local",
            "base_path": "projects/${project.alias}",
            "events": {
                "push": {
                    "branch": {
                        "path": "branches/${github.ref_name}/${date.utc.timestamp}"
                    },
                    "tag": {"path": "tags/${github.ref_name}"},
                }
            },
            "jobs": {
                "build": {"path": "${run.variant}/build"},
                "package": {"path": "packages/${run.variant}"},
            },
        },
    }
    write_project(tmp_path / ".main.ptk.yml", model)
    grant_maintainer(tmp_path)
    return tmp_path, model


def invoke(root, *args, ci=False, maintainer=True, env=None):
    return CliRunner(
        env={
            "PTK_ROLE": "" if maintainer else "user",
            "PTK_CI": "1" if ci else "0",
            "GITHUB_EVENT_NAME": "push",
            "GITHUB_REF_TYPE": "branch",
            "GITHUB_REF_NAME": "feature/reuse",
            "GITHUB_EVENT_PATH": "",
            **(env or {}),
        }
    ).invoke(cli, args, cwd=root, catch_exceptions=False)


def export(root, *args, **options):
    result = invoke(root, "maintainer", "matrix", "--at", AT, *args, **options)
    assert result.exit_code == 0, result.output
    return json.loads(result.output)


def test_local_matrix_exports_only_eligible_pairs_aliases_and_destinations(
    project, monkeypatch
):
    root, _ = project
    monkeypatch.setattr(
        RunJob, "execute", lambda *_args, **_kwargs: pytest.fail("executed a job")
    )
    before = snapshot(root)
    data = export(root)
    assert set(data) == {"schema_version", "matrix", "upload_base"}
    assert data["schema_version"] == 1
    rows = data["matrix"]["include"]
    assert [(r["variant"], r["job"]) for r in rows] == [
        ("debug", "build"),
        ("debug", "private"),
        ("debug", "test"),
        ("release", "build"),
        ("release", "package"),
        ("release", "private"),
    ]
    first = rows[0]
    assert set(first) == {
        "repository",
        "variant",
        "aliases",
        "job",
        "command",
        "version",
        "commit",
        "upload",
    }
    assert first["repository"] == "firmware" and first["aliases"] == ["dev"]
    assert first["command"] == ["ptk", "-V", "debug", "run", "build"]
    assert "outputs" not in first and "inputs" not in first
    assert first["version"] == "1.2.3"
    assert first["commit"] == git(root, "rev-parse", "HEAD")
    base = "projects/firmware/branches/feature/reuse/2026_10_31_1234"
    assert data["upload_base"] == {
        "repository": "ci-local",
        "path": base,
        "url": "https://artifacts.example.invalid/artifactory/ci-local/" + base + "/",
    }
    assert first["upload"]["path"] == base + "/debug/build"
    assert first["upload"]["base_path"] == base
    assert snapshot(root) == before
    assert export(root) == data


def test_cx_exports_without_human_identity_but_does_not_elevate_permissions(project):
    root, _ = project
    data = export(root, ci=True, maintainer=False)
    assert {r["job"] for r in data["matrix"]["include"]} == {
        "build",
        "test",
        "package",
        "cx",
    }
    for args in [
        ("maintainer", "sync", "configs"),
        ("maintainer", "private"),
        ("maintainer", "artifacts", "destination", "--job", "build"),
    ]:
        before = snapshot(root)
        denied = invoke(root, *args, ci=True, maintainer=False)
        assert denied.exit_code != 0 and "maintainer-only" in denied.output
        assert snapshot(root) == before


def test_normal_users_cannot_export_or_force_cx(project):
    root, _ = project
    before = snapshot(root)
    for args in [
        ("maintainer", "matrix"),
        ("maintainer", "matrix", "--help"),
        ("--ci", "maintainer", "matrix"),
    ]:
        result = invoke(root, *args, maintainer=False)
        assert result.exit_code != 0 and "maintainer-only" in result.output
    assert snapshot(root) == before


def test_hidden_from_help_completion_and_editor_inventory(project, monkeypatch):
    root, _ = project
    monkeypatch.chdir(root)
    monkeypatch.setenv("PTK_ROLE", "")
    monkeypatch.setenv("PTK_CI", "0")
    assert "matrix" not in invoke(root, "maintainer", "--help").output
    complete = BashComplete(cli, {}, "ptk", "_PTK_COMPLETE")
    assert "matrix" not in {
        item.value for item in complete.get_completions(["maintainer"], "")
    }
    inventory = json.loads(invoke(root, "describe", "--json").output)
    assert '"name": "matrix"' not in json.dumps(inventory)
    assert "workflow" in invoke(root, "maintainer", "matrix", "--help").output


def test_alias_filters_deduplicate_and_emit_invocable_arguments(project):
    root, _ = project
    result = invoke(
        root,
        "-V",
        "prod,release",
        "maintainer",
        "matrix",
        "--job",
        "package",
        "--at",
        AT,
    )
    assert result.exit_code == 0, result.output
    [row] = json.loads(result.output)["matrix"]["include"]
    assert row["variant"] == "release" and row["aliases"] == ["prod"]
    executed = invoke(root, *row["command"][1:])
    assert executed.exit_code == 0, executed.output
    assert "matrix execution" in executed.output


def test_github_format_is_exactly_three_safe_output_lines(project):
    root, _ = project
    expected = export(root, ci=True, maintainer=False)
    result = invoke(
        root,
        "maintainer",
        "matrix",
        "--at",
        AT,
        "--format",
        "github",
        ci=True,
        maintainer=False,
    )
    assert result.exit_code == 0, result.output
    outputs = dict(line.split("=", 1) for line in result.output.splitlines())
    assert set(outputs) == {"matrix", "upload_base", "has_jobs"}
    assert json.loads(outputs["matrix"]) == expected["matrix"]
    assert json.loads(outputs["upload_base"]) == expected["upload_base"]
    assert outputs["has_jobs"] == "true"


def test_no_variants_outputs_or_upload_config_are_not_inferred(project):
    root, model = project
    model.pop("variants")
    model.pop("artifactory")
    model["jobs"] = {
        "check": {"steps": {"one": {"uses": "echo", "outputs": ["step-file"]}}}
    }
    write_project(root / ".main.ptk.yml", model)
    [row] = export(root)["matrix"]["include"]
    assert row["variant"] is None and row["aliases"] == []
    assert row["command"] == ["ptk", "run", "check"]
    assert "outputs" not in row and row["upload"] is None
    assert export(root)["upload_base"] is None


def test_empty_matrix_has_guard_for_downstream_jobs(project):
    root, _ = project
    data = export(root, "--job", "cx")
    assert data["matrix"] == {"include": []} and data["upload_base"] is None
    result = invoke(root, "maintainer", "matrix", "--job", "cx", "--format", "github")
    assert "has_jobs=false" in result.output


@pytest.mark.parametrize(
    "args",
    [
        ("-V", "unknown", "maintainer", "matrix"),
        ("-V", "base", "maintainer", "matrix"),
        ("maintainer", "matrix", "--job", "unknown"),
        ("maintainer", "matrix", "--at", "2026-10-31T12:00:00"),
        ("maintainer", "matrix", "--event", "unknown"),
        ("--clean", "maintainer", "matrix"),
        ("--re-run", "maintainer", "matrix"),
        ("--set", "vars.example=value", "maintainer", "matrix"),
    ],
)
def test_invalid_selections_routes_and_mutation_flags_fail_without_partial_json(
    project, args
):
    root, _ = project
    before = snapshot(root)
    result = invoke(root, *args)
    assert result.exit_code == 2 and "error:" in result.output
    assert not result.stdout.strip()
    assert snapshot(root) == before


@pytest.mark.parametrize(
    "template",
    [
        "${run.id}/out",
        "${env:MISSING}/out",
        "${date.timestamp}/out",
        "${params.name}/out",
    ],
)
def test_output_paths_are_left_to_job_execution(project, template):
    root, model = project
    model["jobs"]["build"]["params"] = {"name": {"required": True}}
    model["jobs"]["build"]["outputs"] = [template]
    write_project(root / ".main.ptk.yml", model)
    data = export(root, "--job", "build")
    assert len(data["matrix"]["include"]) == 2
    assert all(
        "outputs" not in row and "artifact" not in row and "inputs" not in row
        for row in data["matrix"]["include"]
    )


def test_invalid_variant_fails_without_partial_json(project):
    root, model = project
    model["variants"]["components"] = {
        "core": {"features": {"SIZE": {"type": "int", "default": 3, "max": 9}}}
    }
    model["variants"]["variants"]["release"]["features"] = {"core.SIZE": 99}
    write_project(root / ".main.ptk.yml", model)
    result = invoke(root, "maintainer", "matrix", "--job", "build")
    assert result.exit_code == 2 and "invalid variant" in result.output
    assert not result.stdout.strip()


def test_event_repository_override_applies_to_base_and_job_destinations(project):
    root, model = project
    model["artifactory"]["events"]["release"] = {
        "repository": "release-local",
        "path": "releases/current",
    }
    write_project(root / ".main.ptk.yml", model)
    data = export(root, "--event", "release", "--job", "package")
    [row] = data["matrix"]["include"]
    base = data["upload_base"]
    assert base["repository"] == row["upload"]["repository"] == "release-local"
    assert base["path"] == "projects/firmware/releases/current"
    assert row["upload"]["url"] == base["url"] + "packages/release/"


def test_variant_specific_upload_bases_remain_explicit_per_row(project):
    root, model = project
    model["artifactory"]["base_path"] += "/${run.variant}"
    write_project(root / ".main.ptk.yml", model)
    data = export(root, "--job", "build")
    assert data["upload_base"] is None
    bases = {row["upload"]["base_path"] for row in data["matrix"]["include"]}
    assert len(bases) == 2 and all("projects/firmware/" in base for base in bases)


def test_member_alias_routes_to_own_matrix_in_cx(project, tmp_path):
    root, model = project
    member = root / "member"
    member.mkdir()
    write_project(member / ".main.ptk.yml", model)
    (root / ".main.ptk.yml").write_text("virtual_monorepo: true\nmembers: [member]\n")
    result = invoke(
        root,
        "firmware",
        "maintainer",
        "matrix",
        "--job",
        "build",
        "--at",
        AT,
        ci=True,
        maintainer=False,
    )
    assert result.exit_code == 0, result.output
    rows = json.loads(result.output)["matrix"]["include"]
    assert {r["repository"] for r in rows} == {"firmware"}
    assert all(r["command"][0] == "ptk" and "outputs" not in r for r in rows)


def test_version_identity_and_destination_share_one_discovery(project, monkeypatch):
    root, model = project
    model["artifactory"]["jobs"]["build"]["path"] = "${version.current.value}/build"
    write_project(root / ".main.ptk.yml", model)
    calls = []

    def discover(_self, _project, variant, job):
        calls.append((variant, job))
        return {"projects": {"firmware": {"value": f"1.0.{len(calls)}"}}}

    monkeypatch.setattr(VersionService, "resolve", discover)
    rows = export(root, "--job", "build")["matrix"]["include"]
    assert len(calls) == len(rows) == 2
    assert all(
        row["upload"]["path"].endswith(f"/{row['version']}/build") for row in rows
    )


def test_matrix_commit_identifies_pr_source_not_synthetic_merge(project):
    root, model = project
    checkout = root / "checkout"
    env, head, merge, _, _ = pr(checkout, root)
    write_project(checkout / ".main.ptk.yml", model)
    grant_maintainer(checkout)
    rows = export(
        checkout,
        "--event",
        "push",
        "--job",
        "build",
        ci=True,
        maintainer=False,
        env=env,
    )["matrix"]["include"]
    assert head != merge
    assert {row["commit"] for row in rows} == {head}


def test_unconfigured_version_is_null_without_inventing_a_value(project):
    root, model = project
    model.pop("versioning")
    write_project(root / ".main.ptk.yml", model)
    assert all(row["version"] is None for row in export(root)["matrix"]["include"])
