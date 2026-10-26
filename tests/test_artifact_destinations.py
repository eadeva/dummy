"""Read-only destination routing, date snapshots, VMR ownership and CLI outputs."""

import json
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from ptk.bootstrap import create_app
from ptk.drivers.cli.main import cli

AT = "2026-10-26T15:07:00+01:00"


def make_project(root, alias="demo", extra=None):
    config = root / "config"
    config.mkdir(parents=True)
    (root / ".main.ptk.yml").write_text(
        yaml.safe_dump(
            {
                "repository": {"alias": alias, "config_path": "config"},
                "include": "project.ptk.yml",
            }
        )
    )
    data = {
        "project": {"name": alias},
        "versioning": {"project": {"source": "literal", "version": "1.2.3"}},
        "variants": {"default": "debug", "variants": {"debug": {}, "release": {}}},
        "jobs": {
            "package": {"steps": [{"build": {"uses": "echo"}}]},
            "docs": {"steps": [{"html": {"uses": "echo"}}]},
        },
        **(extra or {}),
    }
    (config / "project.ptk.yml").write_text(yaml.safe_dump(data))
    structure = {
        "url": "https://example.invalid/artifactory",
        "repository": "generic-ci-local",
        "base_path": "projects/${project.alias}",
        "events": {
            "push": {
                "branch": {
                    "path": "branches/${github.ref_name}/${date.timestamp}/${github.run_id}-${github.run_attempt}"
                },
                "tag": {
                    "path": "tags/${version.current.sort_key}_v${version.current.value}"
                },
            },
            "pull_request": {
                "path": "pull-requests/${github.event.pull_request.number}/${github.run_id}"
            },
            "release": {
                "repository": "generic-releases-local",
                "path": "releases/${version.current.sort_key}_v${version.current.value}",
            },
            "workflow_dispatch": {"path": "manual/${date.utc.timestamp}"},
        },
        "jobs": {"package": {"path": "packages/${run.variant}"}},
    }
    (config / "artifactory_structure.ptk.yaml").write_text(
        yaml.safe_dump({"artifactory": structure})
    )
    return root


def invoke(root, *args, env=None):
    return CliRunner(
        env={
            "PTK_ROLE": "user",
            "PTK_CI": "0",
            "GITHUB_EVENT_PATH": "",
            "GITHUB_EVENT_NAME": "push",
            "GITHUB_REF_TYPE": "branch",
            "GITHUB_REF_NAME": "feature/login",
            "GITHUB_RUN_ID": "123",
            "GITHUB_RUN_ATTEMPT": "2",
            **(env or {}),
        }
    ).invoke(
        cli,
        [
            "-c",
            str(root / ".main.ptk.yml"),
            "artifacts",
            "destination",
            "--job",
            "package",
            "--at",
            AT,
            *args,
        ],
        catch_exceptions=False,
    )


def test_discovery_branch_slashes_date_variant_and_no_side_effects(tmp_path):
    root = make_project(tmp_path)
    before = {
        p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()
    }
    result = invoke(root, "-V", "release")
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert (
        data["path"]
        == "projects/demo/branches/feature/login/2026_10_26_1507/123-2/packages/release"
    )
    assert (
        data["url"]
        == "https://example.invalid/artifactory/generic-ci-local/" + data["path"] + "/"
    )
    assert before == {
        p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()
    }
    assert not (root / "_reports").exists()


@pytest.mark.parametrize(
    "event,kind,repository,path",
    [
        ("push", "tag", "generic-ci-local", "tags/0001_0002_0003_v1.2.3"),
        ("release", "tag", "generic-releases-local", "releases/0001_0002_0003_v1.2.3"),
        ("workflow_dispatch", "branch", "generic-ci-local", "manual/2026_10_26_1407"),
    ],
)
def test_tag_release_and_manual_routes(tmp_path, event, kind, repository, path):
    root = make_project(tmp_path)
    result = invoke(root, "--event", event, env={"GITHUB_REF_TYPE": kind})
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["repository"] == repository
    assert data["path"] == f"projects/demo/{path}/packages/debug"


def test_pr_payload_github_outputs_omitted_job_suffix_and_overlays(tmp_path):
    root = make_project(tmp_path)
    event_file = root / "event.json"
    event_file.write_text(
        json.dumps({"pull_request": {"number": 42}, "token": "do-not-expose"})
    )
    (root / "config/local.ptk.yml").write_text("artifactory: {base_path: local}\n")
    result = invoke(
        root,
        "--job",
        "docs",
        "--format",
        "github",
        env={"GITHUB_EVENT_NAME": "pull_request", "GITHUB_EVENT_PATH": str(event_file)},
    )
    assert result.exit_code == 0, result.output
    assert "path=local/pull-requests/42/123\n" in result.output
    assert "do-not-expose" not in result.output
    assert {line.split("=", 1)[0] for line in result.output.splitlines()} == {
        "url",
        "path",
        "repository",
    }


@pytest.mark.parametrize(
    "args,env,message",
    [
        (["--event", "unknown"], {}, "no Artifactory destination"),
        ([], {"GITHUB_REF_NAME": "../outside"}, "cannot contain"),
        ([], {"GITHUB_REF_NAME": "bad\noutput=x"}, "control characters"),
        ([], {"GITHUB_REF_TYPE": "other"}, "ref type"),
        (["--job", "missing"], {}, "unknown job"),
        (["--at", "2026-10-26T15:07"], {}, "timezone offset"),
        (["-V", "unknown"], {}, "unknown variant"),
    ],
)
def test_invalid_resolution_fails_without_uploading(tmp_path, args, env, message):
    result = invoke(make_project(tmp_path), *args, env=env)
    assert result.exit_code != 0 and message in result.output


def test_unknown_fields_and_template_typos_include_file_provenance(tmp_path):
    root = make_project(tmp_path)
    path = root / "config/artifactory_structure.ptk.yaml"
    path.write_text(path.read_text().replace("date.timestamp", "date.timestmp"))
    result = invoke(root)
    assert result.exit_code != 0
    assert (
        "artifactory_structure.ptk.yaml" in result.output
        and "date.timestmp" in result.output
    )
    path.write_text(
        path.read_text().replace("date.timestmp", "date.timestamp") + "uploads: []\n"
    )
    result = invoke(root)
    assert result.exit_code != 0 and "unknown key 'uploads'" in result.output


def test_vmr_member_uses_own_alias_and_version(tmp_path, monkeypatch):
    (tmp_path / ".main.ptk.yml").write_text(
        "virtual_monorepo: true\nmembers: [one, two]\n"
    )
    for name in ("one", "two"):
        make_project(tmp_path / name, name)
    monkeypatch.chdir(tmp_path)
    runner = CliRunner(env={"PTK_ROLE": "user", "PTK_CI": "0", "GITHUB_EVENT_PATH": ""})
    result = runner.invoke(
        cli,
        [
            "two",
            "artifacts",
            "destination",
            "--job",
            "package",
            "--event",
            "release",
            "--at",
            AT,
        ],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["path"].startswith("projects/two/releases/")


def test_destination_command_and_job_audience_are_enforced(tmp_path):
    from tests.conftest import grant_maintainer

    root = make_project(
        tmp_path, extra={"command_audience": {"artifacts": "maintainer"}}
    )
    assert "maintainer-only" in invoke(root).output
    grant_maintainer(root)
    assert invoke(root, env={"PTK_ROLE": ""}).exit_code == 0


def test_published_example_is_packaged_and_resolves_without_github(tmp_path):
    import shutil

    example = Path(__file__).resolve().parents[1] / "examples/artifacts"
    shutil.copytree(example, tmp_path / "example")
    result = invoke(tmp_path / "example", "--event", "release")
    assert result.exit_code == 0, result.output
    assert "0001_0002_0003_v1.2.3" in result.output
    app = create_app()
    assert (
        app.load_project.execute(
            config_file=tmp_path / "example/.main.ptk.yml"
        ).config.artifactory
        is not None
    )
