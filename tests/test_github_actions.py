"""Artifact transport round trips and generated callable workflow contracts."""

import json
import os
import shutil
import stat
import sys
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from ptk.adapters import github_actions as actions
from ptk.domain.workflows import WorkflowSpec
from ptk.drivers.cli.github_workflows import render_workflow
from tests.project_files import write_project
from tests.test_matrix_export import invoke
from tests.test_matrix_export import project as matrix_project


@pytest.fixture
def project(tmp_path):
    return matrix_project.__wrapped__(tmp_path)


class Store:
    def __init__(self):
        self.files = {}
        self.properties = {}

    def transfer(self, address, path, *, upload=False, properties=None):
        if upload:
            self.files[address] = path.read_bytes()
            self.properties[address] = properties
        else:
            path.write_bytes(self.files[address])


@pytest.fixture
def artifacts(tmp_path):
    root = tmp_path / "producer"
    root.mkdir()
    (root / "dist").mkdir()
    (root / "dist/app.bin").write_bytes(b"firmware\x00")
    (root / "symbols").mkdir()
    (root / "symbols/empty").mkdir()
    (root / "symbols/run.sh").write_text("echo hi")
    (root / "symbols/run.sh").chmod(0o755)
    row = {
        "repository": "firmware",
        "job": "build",
        "variant": "debug",
        "version": "1",
        "commit": "a" * 40,
        "invocation": "compile",
        "upload": {"url": "https://example.invalid/repo/build/"},
    }
    props = {
        **{k: row[k] for k in ("job", "version", "commit")},
        "variant_alias": ["debug", "dev"],
        "step": "compile",
    }
    manifest = {
        "schema_version": 1,
        "repository": "firmware",
        "run_id": "run1",
        "files": [
            {
                "path": str(root / rel),
                "relative_path": rel,
                "kind": kind,
                "properties": props,
            }
            for rel, kind in [("dist/app.bin", "file"), ("symbols", "directory")]
        ],
    }
    return root, row, manifest, Store()


def test_file_and_zip_roundtrip_to_different_checkout(artifacts, tmp_path):
    root, row, manifest, store = artifacts
    manifest["files"][0]["upload_path"] = "custom/bin"
    address = actions.upload(
        manifest, root, row["upload"]["url"], row, "run1", {"quality": "checked"}, store
    )
    assert list(store.files)[-1] == address
    assert any("/custom/bin" in path for path in store.files)
    assert any(path.endswith("symbols.zip") for path in store.files)
    consumer = tmp_path / "consumer"
    consumer.mkdir()
    (consumer / "symbols").mkdir()
    (consumer / "symbols/stale").write_text("old")
    assert actions.download([row], consumer, "run1", store) == [
        "dist/app.bin",
        "symbols",
    ]
    assert (consumer / "dist/app.bin").read_bytes() == b"firmware\x00"
    assert (consumer / "symbols/empty").is_dir()
    assert not (consumer / "symbols/stale").exists()
    assert stat.S_IMODE((consumer / "symbols/run.sh").stat().st_mode) == 0o755
    assert next(p for p in store.properties.values() if p)["quality"] == "checked"


def test_vmr_download_restores_producer_repository(artifacts, tmp_path):
    root, row, manifest, store = artifacts
    row["working_directory"] = "repos/producer"
    actions.upload(manifest, root, row["upload"]["url"], row, "run1", {}, store)
    checkout = tmp_path / "vmr"
    checkout.mkdir()
    actions.download([row], checkout, "run1", store)
    assert (checkout / "repos/producer/dist/app.bin").is_file()


@pytest.mark.parametrize(
    "path", ["../escape", "/absolute", "a/../b", "a//b", "a\\b", "C:/x", ".", "a\nb"]
)
def test_unsafe_relative_paths_rejected(path):
    with pytest.raises(ValueError):
        actions.relative(path)


def test_symlinks_and_external_outputs_rejected_before_transfer(artifacts, tmp_path):
    root, row, manifest, store = artifacts
    (root / "symbols/link").symlink_to(tmp_path)
    with pytest.raises(ValueError, match="symlink"):
        actions.upload(manifest, root, row["upload"]["url"], row, "run1", {}, store)
    assert not store.files
    (root / "symbols/link").unlink()
    manifest["files"][0].pop("relative_path")
    with pytest.raises(ValueError):
        actions.upload(manifest, root, row["upload"]["url"], row, "run1", {}, store)


def test_wrong_identity_and_property_overrides_rejected(artifacts):
    root, row, manifest, store = artifacts
    with pytest.raises(ValueError, match="identity"):
        actions.upload(
            manifest, root, row["upload"]["url"], row, "run1", {"job": "other"}, store
        )
    manifest["files"][0]["properties"]["commit"] = "wrong"
    with pytest.raises(ValueError, match="identity"):
        actions.upload(manifest, root, row["upload"]["url"], row, "run1", {}, store)
    assert not store.files


def test_checksum_failure_does_not_replace_any_outputs(artifacts, tmp_path):
    root, row, manifest, store = artifacts
    actions.upload(manifest, root, row["upload"]["url"], row, "run1", {}, store)
    remote = next(k for k in store.files if k.endswith(".zip"))
    store.files[remote] = b"broken"
    consumer = tmp_path / "consumer"
    consumer.mkdir()
    with pytest.raises(ValueError, match="SHA256"):
        actions.download([row], consumer, "run1", store)
    assert list(consumer.iterdir()) == []


def test_scope_and_variant_isolate_manifests(artifacts):
    _, row, _, _ = artifacts
    assert actions.location(row, "run1") != actions.location(row, "run2")
    assert actions.location(row, "run1") != actions.location(
        {**row, "variant": "release"}, "run1"
    )


def test_overlapping_producer_paths_fail_before_restore(artifacts, tmp_path):
    root, row, manifest, store = artifacts
    actions.upload(manifest, root, row["upload"]["url"], row, "run1", {}, store)
    consumer = tmp_path / "consumer"
    consumer.mkdir()
    with pytest.raises(ValueError, match="overlap"):
        actions.download([row, row], consumer, "run1", store)
    assert not list(consumer.iterdir())


@pytest.mark.parametrize(
    "name", ["../escape", "/absolute", "a/../../escape", "C:/escape"]
)
def test_zip_slip_rejected(tmp_path, name):
    archive = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr(name, "bad")
    destination = tmp_path / "destination"
    destination.mkdir()
    with pytest.raises(ValueError):
        actions.unpack(archive, destination)
    assert not list(destination.iterdir())


def test_curl_credentials_not_in_arguments_or_errors(monkeypatch, tmp_path):
    seen = []

    def run(args, **kwargs):
        seen.append((args, kwargs))
        return SimpleNamespace(returncode=22)

    monkeypatch.setattr(actions.subprocess, "run", run)
    with pytest.raises(RuntimeError, match="exit 22"):
        actions.Curl("robot", "secret").transfer(
            "https://example.invalid/file", tmp_path / "x", upload=True
        )
    assert "secret" not in str(seen[0][0])
    assert "robot:secret" in seen[0][1]["input"]
    assert "--disable" in seen[0][0] and "--location" not in seen[0][0]


def spec():
    return WorkflowSpec.model_validate(
        {
            "jobs": {
                "compile": {"job": "build"},
                "check": {"job": "test", "needs": ["compile"]},
            }
        }
    )


def test_generated_workflow_has_setup_needs_docker_and_actions():
    text = render_workflow(
        "verify", spec(), action_repository="eadeva/dummy", action_ref="v1"
    )
    data = yaml.safe_load(text)
    assert set(data["on"]) == {"workflow_call"}
    assert "maintainer matrix --workflow" in data["jobs"]["setup"]["steps"][-1]["run"]
    assert data["jobs"]["compile"]["needs"] == ["setup"]
    assert data["jobs"]["check"]["needs"] == ["setup", "compile"]
    steps = data["jobs"]["check"]["steps"]
    assert [s.get("uses", "").split("/")[-1].split("@")[0] for s in steps] == [
        "checkout",
        "ptk-download",
        "ptk-run-job",
        "ptk-upload",
    ]
    assert steps[1]["with"]["working-directory"] == "."
    assert all("container" in job for job in data["jobs"].values())
    assert "&id" not in text


def test_vmr_template_has_only_checkout_todos():
    text = render_workflow(
        "verify", spec(), action_repository="eadeva/dummy", action_ref="v1", vmr=True
    )
    assert "actions/checkout" not in text
    data = yaml.safe_load(text)
    for job in data["jobs"].values():
        assert job["steps"][0]["name"] == "TODO: VMR checkout"
        assert "exit 1" in job["steps"][0]["run"]


def configure_workflow(project):
    root, model = project
    model["jobs"]["test"].pop("omit_variants")
    model["workflows"] = {
        "verify": {
            "jobs": {
                "compile": {"job": "build"},
                "check": {"job": "test", "needs": ["compile"]},
            }
        }
    }
    write_project(root / ".main.ptk.yml", model)
    return root


def test_matrix_exports_dependencies_for_each_variant(project):
    root = configure_workflow(project)
    result = invoke(root, "maintainer", "matrix", "--workflow", "verify", ci=True)
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert len(data["jobs"]["compile"]["include"]) == 2
    for row in data["jobs"]["check"]["include"]:
        producer = row["producers"][0]
        assert producer["invocation"] == "compile" and producer["job"] == "build"
        assert producer["variant"] == row["variant"]
        assert producer["upload"]["base_url"] == row["upload"]["base_url"]
    result = invoke(
        root,
        "maintainer",
        "matrix",
        "--workflow",
        "verify",
        "--format",
        "github",
        ci=True,
    )
    assert result.exit_code == 0 and "matrix_compile=" in result.output


def test_generation_never_overwrites_existing_workflow(project):
    root = configure_workflow(project)
    result = invoke(root, "maintainer", "gen-workflows", "verify")
    assert result.exit_code == 0, result.output
    path = root / ".github/workflows/ptk-verify.yml"
    path.write_text("custom workflow")
    result = invoke(root, "maintainer", "gen-workflows", "verify")
    assert result.exit_code == 0 and "Warning:" in result.output
    assert path.read_text() == "custom workflow"


def test_generation_denied_in_cx_for_nonmaintainer(project):
    root = configure_workflow(project)
    result = invoke(root, "maintainer", "gen-workflows", ci=True, maintainer=False)
    assert result.exit_code != 0
    assert not (root / ".github/workflows").exists()


def test_run_action_real_job_exposes_exact_manifest(project, monkeypatch, tmp_path):
    root, model = project
    model["jobs"]["build"]["outputs"] = [
        "dist/out.txt",
        {"path": "${run.reports_dir}", "artifact_type": "reports"},
    ]
    model["jobs"]["build"]["steps"] = {
        "create": {
            "run": [
                sys.executable,
                "-c",
                "from pathlib import Path; Path('dist').mkdir(exist_ok=True); Path('dist/out.txt').write_text('ok')",
            ]
        }
    }
    write_project(root / ".main.ptk.yml", model)
    output = tmp_path / "outputs"
    output.touch()
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    monkeypatch.setenv("PTK_CI", "1")
    monkeypatch.setenv(
        "PATH",
        str(Path(__file__).resolve().parents[1] / ".venv/bin")
        + os.pathsep
        + os.environ["PATH"],
    )
    assert actions.run_job(root, "build", "debug", {}) == 0
    lines = dict(line.split("=", 1) for line in output.read_text().splitlines())
    paths = json.loads(lines["output-paths"])
    assert paths[0] == "dist/out.txt"
    assert (root / paths[1] / "report.html").is_file()
    manifest = json.loads(Path(lines["uploads-json"]).read_text())
    assert manifest["files"][0]["relative_path"] == "dist/out.txt"


def test_real_verify_configuration_generates_callable_workflow(tmp_path):
    from tests.conftest import grant_maintainer

    source = Path(__file__).resolve().parents[1]
    shutil.copy(source / ".main.ptk.yml", tmp_path)
    shutil.copytree(source / "config", tmp_path / "config")
    grant_maintainer(tmp_path)
    result = invoke(tmp_path, "maintainer", "gen-workflows", "verify")
    assert result.exit_code == 0, result.output
    document = yaml.safe_load(
        (tmp_path / ".github/workflows/ptk-verify.yml").read_text()
    )
    assert document["jobs"]["package"]["needs"] == [
        "setup",
        "check",
        "test",
        "extension",
    ]
    assert set(document["jobs"]) == {
        "setup",
        "check",
        "test",
        "package",
        "docs",
        "extension",
    }


def test_manifest_identity_supports_upload_without_setup_row(artifacts):
    root, row, manifest, store = artifacts
    manifest["producer"] = actions.identity(row)
    actions.upload(manifest, root, row["upload"]["url"], {}, "run1", {}, store)
    assert store.files


def test_zip_symlink_rejected(tmp_path):
    path = tmp_path / "link.zip"
    with zipfile.ZipFile(path, "w") as bundle:
        entry = zipfile.ZipInfo("link")
        entry.create_system = 3
        entry.external_attr = (stat.S_IFLNK | 0o777) << 16
        bundle.writestr(entry, "/etc/passwd")
    with pytest.raises(ValueError, match="symlinks"):
        actions.unpack(path, tmp_path / "out")


def test_upload_failure_does_not_publish_manifest(artifacts):
    root, row, manifest, store = artifacts
    original = store.transfer

    def transfer(address, path, **kwargs):
        if address.endswith(".zip"):
            raise RuntimeError("failed")
        original(address, path, **kwargs)

    store.transfer = transfer
    with pytest.raises(RuntimeError):
        actions.upload(manifest, root, row["upload"]["url"], row, "run1", {}, store)
    assert not any(address.endswith("manifest.json") for address in store.files)


def test_empty_output_set_publishes_manifest(artifacts, tmp_path):
    root, row, manifest, store = artifacts
    manifest["files"] = []
    actions.upload(manifest, root, row["upload"]["url"], row, "run1", {}, store)
    assert len(store.files) == 1
    assert actions.download([row], tmp_path, "run1", store) == []


def test_vmr_detection_replaces_normal_checkout(tmp_path):
    from tests.conftest import grant_maintainer
    from tests.workflows.test_cli import repository

    (tmp_path / ".main.ptk.yml").write_text("virtual_monorepo: true\nmembers: [app]\n")
    repository(
        tmp_path / "app", workflows={"verify": {"jobs": {"build": {"job": "build"}}}}
    )
    grant_maintainer(tmp_path)
    grant_maintainer(tmp_path / "app")
    result = invoke(tmp_path, "maintainer", "gen-workflows", "app/verify")
    assert result.exit_code == 0, result.output
    text = (tmp_path / "app/.github/workflows/ptk-verify.yml").read_text()
    assert "VMR checkout" in text and "actions/checkout" not in text
    assert (
        yaml.safe_load(text)["on"]["workflow_call"]["inputs"]["project-directory"][
            "default"
        ]
        == "app"
    )


def test_vmr_matrix_maps_producer_variants_and_directories(tmp_path):
    from tests.conftest import grant_maintainer
    from tests.test_git_metadata import repo

    (tmp_path / ".main.ptk.yml").write_text(
        "virtual_monorepo: true\nmembers: [app, tools]\n"
    )
    grant_maintainer(tmp_path)
    for alias, variant in [("app", "debug"), ("tools", "host")]:
        root = tmp_path / alias
        root.mkdir()
        repo(root)
        model = {
            "repository": {"alias": alias, "config_path": "config"},
            "project": {"name": alias},
            "variants": {"default": variant, "variants": {variant: {}}},
            "jobs": {
                "build": {
                    "steps": {"echo": {"uses": "echo", "with": {"message": "ok"}}}
                }
            },
            "artifactory": {
                "url": "https://example.invalid/artifactory",
                "repository": "ci",
                "base_path": alias,
                "events": {"push": {"path": "branch"}},
            },
        }
        if alias == "app":
            model["variants"]["variants"]["debug"]["repo_variants"] = {"tools": "host"}
            model["workflows"] = {
                "verify": {
                    "jobs": {
                        "tool": {"job": "tools:build"},
                        "build": {"job": "build", "needs": ["tool"]},
                    }
                }
            }
        write_project(root / ".main.ptk.yml", model)
        grant_maintainer(root)
    result = invoke(
        tmp_path, "app", "maintainer", "matrix", "--workflow", "verify", ci=True
    )
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    [row] = data["jobs"]["build"]["include"]
    assert row["variant"] == "debug" and row["working_directory"] == "app"
    assert row["producers"][0]["variant"] == "host"
    assert row["producers"][0]["working_directory"] == "tools"


def test_verify_jobs_declare_disjoint_portable_outputs():
    from ptk.application.use_cases.run import RunRequest
    from ptk.bootstrap import create_app

    root = Path(__file__).resolve().parents[1]
    app = create_app()
    project = app.load_project.execute(root)
    for job in ("check", "test", "docs", "extension", "package"):
        prepared = app.prepare_run(project).execute(
            project, RunRequest(job=job, variant="default", dry_run=True)
        )
        plan = prepared.plan
        outputs = [*plan.outputs, *[p for step in plan.steps for p in step.outputs]]
        assert outputs, job
        for output in outputs:
            assert Path(output).is_relative_to(root)
        for i, left in enumerate(outputs):
            for right in outputs[i + 1 :]:
                assert not Path(left).is_relative_to(right)
                assert not Path(right).is_relative_to(left)
        assert project.config.jobs[job].cache is False
    extension = project.config.jobs["extension"].steps["package"]
    assert extension.outputs[0].artifact_type == "vscode-extension"
    assert extension.run[-2:] == ["--out", "${run.bin_dir}/project-toolkit.vsix"]


def test_download_action_rejects_selector_not_in_needs(monkeypatch):
    monkeypatch.setattr(actions.sys, "argv", ["actions", "download"])
    monkeypatch.setenv("PTK_ACTION_TECHNICAL_USER", "robot")
    monkeypatch.setenv("PTK_ACTION_TOKEN", "secret")
    monkeypatch.setenv("PTK_ACTION_ARTIFACT_SCOPE", "scope")
    monkeypatch.setenv("PTK_ACTION_PRODUCERS", '[{"invocation":"other"}]')
    monkeypatch.setenv("PTK_ACTION_NEEDS", '{"setup":{}}')
    with pytest.raises(ValueError, match="not declared"):
        actions.main()


def test_run_action_keeps_failure_and_exposes_completed_manifest(monkeypatch, tmp_path):
    manifest = tmp_path / "upload.json"
    manifest.write_text('{"files":[]}')
    output = tmp_path / "outputs"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))

    def run(command, **kwargs):
        assert command[-2] == "--params"
        Path(kwargs["env"]["PTK_GITHUB_RESULT"]).write_text(
            json.dumps({"upload_file": str(manifest)})
        )
        return SimpleNamespace(returncode=7)

    monkeypatch.setattr(actions.subprocess, "run", run)
    assert actions.run_job(tmp_path, "build", "debug", {}) == 7
    assert "uploads-json=" in output.read_text()
    assert "output-paths=[]" in output.read_text()
