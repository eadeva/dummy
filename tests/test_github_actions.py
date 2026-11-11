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
from ptk.drivers.cli.github_workflows import (
    MARKER,
    CxSettings,
    render_job,
    render_workflow,
)
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
    if os.name != "nt":  # Windows has no executable mode bits
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
                "build": {},
                "test": {"needs": ["build"]},
            }
        }
    )


def settings(vmr=False):
    checkout = (
        {"manifest-url": "https://example.invalid/manifest.git", "app-id": "1400"}
        if vmr
        else None
    )
    return CxSettings(
        runner_group="linux",
        image="registry.example.invalid/build:1",
        login="robot@example.invalid",
        token_secret="FIRMWARE_ROBOT_ARTIFACTORY_TOKEN",
        pmt_repository="XC-CE/pmt",
        pmt_version="v26.45.00",
        checkout=checkout,
        private_key_secret="APP_KEY" if vmr else None,
        vmr=vmr,
    )


def render(workflow, vmr=False):
    return yaml.safe_load(
        render_workflow(
            "verify",
            workflow,
            settings(vmr),
            job_files={
                key: f"call-{key.replace(':', '-')}.yml" for key in workflow.jobs
            },
            env={},
            optional=set(),
        )
    )


def test_generated_workflow_calls_one_job_workflow_per_entry():
    data = render(spec())
    assert set(data["on"]) == {"workflow_call"}
    setup = data["jobs"]["setup"]
    assert "maintainer matrix --workflow" in setup["steps"][-1]["run"]
    assert setup["runs-on"] == {"group": "linux"}
    assert setup["container"]["credentials"]["password"] == (
        "${{ secrets.FIRMWARE_ROBOT_ARTIFACTORY_TOKEN }}"
    )
    assert setup["steps"][0]["uses"] == (
        "XC-CE/pmt/.github/actions/checkout-or-repo-init@v26.45.00"
    )
    build, test = data["jobs"]["job_build"], data["jobs"]["job_test"]
    assert build["needs"] == ["setup"]
    assert test["needs"] == ["setup", "job_build"]
    assert build["uses"] == "./.github/workflows/call-build.yml"
    assert build["secrets"] == "inherit"
    assert build["with"]["matrix"] == "${{ needs.setup.outputs.matrix_job_build }}"
    assert data["on"]["workflow_call"]["secrets"] == {
        "FIRMWARE_ROBOT_ARTIFACTORY_TOKEN": {"required": True}
    }


def test_job_workflow_runs_ptk_between_ptk_transfers():
    text = render_job(
        "build",
        settings(),
        {"FIRMWARE_ROBOT_FOSSID_TOKEN": "${{ secrets.FIRMWARE_ROBOT_FOSSID_TOKEN }}"},
        {"FIRMWARE_ROBOT_FOSSID_TOKEN"},
    )
    assert text.startswith(MARKER) and "&id" not in text
    data = yaml.safe_load(text)
    job = data["jobs"]["run"]
    assert job["strategy"]["matrix"] == "${{ fromJSON(inputs.matrix) }}"
    names = [step["name"] for step in job["steps"]]
    assert names == [
        "Checkout",
        "Trust the checkout",
        "Download producer outputs",
        "Run PTk job",
        "Upload declared outputs",
        "Enforce required output contract",
    ]
    steps = {step["name"]: step for step in job["steps"]}
    download, upload = (
        steps["Download producer outputs"],
        steps["Upload declared outputs"],
    )
    assert "ptk maintainer cx download" in download["run"]
    assert download["if"] == "${{ toJSON(matrix.producers) != '[]' }}"
    assert "ptk maintainer cx upload" in upload["run"]
    assert upload["if"] == "${{ !cancelled() }}"
    for step in (download, upload):
        assert step["env"]["PTK_ARTIFACT_USER"] == "robot@example.invalid"
        assert step["env"]["PTK_ARTIFACT_TOKEN"] == (
            "${{ secrets.FIRMWARE_ROBOT_ARTIFACTORY_TOKEN }}"
        )
    run = steps["Run PTk job"]
    assert run["env"]["FIRMWARE_ROBOT_FOSSID_TOKEN"].startswith("${{ secrets.")
    assert run["continue-on-error"] == "${{ inputs.continue-on-error }}"
    # JSON and secrets reach the shell through env, never through the script text.
    assert all("${{" not in step.get("run", "") for step in job["steps"])
    assert data["on"]["workflow_call"]["secrets"] == {
        "FIRMWARE_ROBOT_ARTIFACTORY_TOKEN": {"required": True},
        "FIRMWARE_ROBOT_FOSSID_TOKEN": {"required": False},
    }


def test_custom_checkout_replaces_the_pmt_checkout():
    from dataclasses import replace

    custom = {"uses": "org/repo/.github/actions/repo-init@develop", "with": {"a": "b"}}
    rendered = yaml.safe_load(
        render_job(
            "build", replace(settings(), vmr=True, custom_checkout=custom), {}, set()
        )
    )
    assert rendered["jobs"]["run"]["steps"][0] == {"name": "Checkout", **custom}
    assert "checkout-ref" in rendered["on"]["workflow_call"]["inputs"]


def test_vmr_checkout_uses_repo_init_with_the_github_app():
    data = render(spec(), vmr=True)
    checkout = data["jobs"]["setup"]["steps"][0]
    assert checkout["with"]["manifest-url"] == "https://example.invalid/manifest.git"
    assert checkout["with"]["app-id"] == "1400"
    inputs = data["on"]["workflow_call"]["inputs"]
    assert {"manifest-branch", "checkout-ref"} <= set(inputs)
    assert data["jobs"]["job_build"]["with"]["checkout-ref"] == (
        "${{ inputs.checkout-ref }}"
    )
    assert data["on"]["workflow_call"]["secrets"]["APP_KEY"] == {"required": True}


def configure_workflow(project):
    root, model = project
    model["jobs"]["test"].pop("when")
    model["jobs"]["test"]["steps"]["compile"]["secrets"] = {"TOKEN": "fossid.token"}
    model["credentials"] = {
        "artifactory": {"fields": ["user", "token"], "user_field": "user"},
        "fossid": {"fields": ["token"], "optional": True},
    }
    model["cx"] = {
        "technical_user": "robot",
        "runner_group": "linux",
        "image": "registry.example.invalid/build:1",
        "artifactory_credential": "artifactory",
        "pmt": {"version": "v26.45.00"},
    }
    model["workflows"] = {
        "verify": {
            "jobs": {
                "build": {},
                "test": {"needs": ["build"]},
            }
        }
    }
    write_project(root / ".main.ptk.yml", model)
    return root


def test_matrix_exports_dependencies_for_each_variant(project):
    root = configure_workflow(project)
    result = invoke(root, "maintainer", "matrix", "--workflow", "verify", cx=True)
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert len(data["jobs"]["build"]["include"]) == 2
    for row in data["jobs"]["test"]["include"]:
        producer = row["producers"][0]
        assert producer["invocation"] == "job_build" and producer["job"] == "build"
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
        cx=True,
    )
    assert result.exit_code == 0 and "matrix_job_build=" in result.output


def test_generation_replaces_only_marked_files_and_backs_up_on_request(project):
    root = configure_workflow(project)
    result = invoke(root, "maintainer", "gen-workflows", "verify")
    assert result.exit_code == 0, result.output
    folder = root / ".github/workflows"
    assert {p.name for p in folder.iterdir()} == {
        "call-verify.yml",
        "call-build.yml",
        "call-test.yml",
    }
    test = yaml.safe_load((folder / "call-test.yml").read_text())
    run = next(s for s in test["jobs"]["run"]["steps"] if s["name"] == "Run PTk job")
    assert run["env"]["FIRMWARE_ROBOT_FOSSID_TOKEN"] == (
        "${{ secrets.FIRMWARE_ROBOT_FOSSID_TOKEN }}"
    )
    assert test["jobs"]["run"]["container"]["credentials"]["password"] == (
        "${{ secrets.FIRMWARE_ROBOT_ARTIFACTORY_TOKEN }}"
    )
    (folder / "call-build.yml").write_text("custom workflow")
    result = invoke(root, "maintainer", "gen-workflows", "verify")
    assert result.exit_code == 0 and "Warning:" in result.output
    assert "Unchanged" in result.output
    assert (folder / "call-build.yml").read_text() == "custom workflow"
    result = invoke(root, "maintainer", "gen-workflows", "verify", "--replace-unmarked")
    assert result.exit_code == 0, result.output
    [backup] = (root / ".github/workflows_backup").iterdir()
    assert (backup / "call-build.yml").read_text() == "custom workflow"
    assert (folder / "call-build.yml").read_text().startswith(MARKER)


def test_yaml_twin_of_a_generated_file_is_backed_up_and_replaced(tmp_path):
    from ptk.drivers.cli.github_workflows import _write

    twin = tmp_path / "workflows/call-sbom.yaml"
    twin.parent.mkdir()
    twin.write_text("hand-written")
    backup = tmp_path / "workflows_backup/now"
    _write(twin.with_suffix(".yml"), "new", replace_unmarked=False, backup=backup)
    assert twin.read_text() == "hand-written"
    _write(twin.with_suffix(".yml"), "new", replace_unmarked=True, backup=backup)
    assert (
        not twin.exists() and (backup / "call-sbom.yaml").read_text() == "hand-written"
    )
    assert twin.with_suffix(".yml").read_text() == "new"


def test_generation_requires_cx_configuration(project):
    root = configure_workflow(project)
    model = project[1]
    model.pop("cx")
    write_project(root / ".main.ptk.yml", model)
    result = invoke(root, "maintainer", "gen-workflows", "verify")
    assert result.exit_code != 0 and "cx.ptk.yml" in result.output


def test_generation_denied_in_cx_for_nonmaintainer(project):
    root = configure_workflow(project)
    result = invoke(root, "maintainer", "gen-workflows", cx=True, maintainer=False)
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
    monkeypatch.setenv("PTK_CX", "1")
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
    (tmp_path / "config/ptk/credentials.ptk.yml").write_text(
        "artifactory:\n  fields: [token]\n"
    )
    (tmp_path / "config/ptk/cx.ptk.yml").write_text(
        "technical_user: robot\nrunner_group: linux\nimage: registry.example.invalid/ptk:1\n"
        "artifactory_credential: artifactory\npmt: {version: v26.45.00}\n"
    )
    grant_maintainer(tmp_path)
    result = invoke(tmp_path, "maintainer", "gen-workflows", "verify")
    assert result.exit_code == 0, result.output
    document = yaml.safe_load(
        (tmp_path / ".github/workflows/call-verify.yml").read_text()
    )
    assert document["jobs"]["job_package"]["needs"] == [
        "setup",
        "job_check",
        "job_test",
        "job_extension",
    ]
    assert set(document["jobs"]) == {
        "setup",
        "job_check",
        "job_test",
        "job_package",
        "job_docs",
        "job_extension",
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


def test_vmr_member_needs_cx_vmr_checkout(tmp_path):
    from tests.conftest import grant_maintainer
    from tests.workflows.test_cli import repository

    (tmp_path / ".main.ptk.yml").write_text("virtual_monorepo: true\nmembers: [app]\n")
    repository(tmp_path / "app", workflows={"verify": {"jobs": {"build": {}}}})
    config = next((tmp_path / "app").rglob("project.ptk.yml")).parent
    (config / "credentials.ptk.yml").write_text("artifactory:\n  fields: [token]\n")
    cx = (
        "technical_user: robot\nrunner_group: linux\nimage: registry.example.invalid/b:1\n"
        "artifactory_credential: artifactory\npmt: {version: v26.45.00}\n"
    )
    (config / "cx.ptk.yml").write_text(cx)
    grant_maintainer(tmp_path)
    grant_maintainer(tmp_path / "app")
    result = invoke(tmp_path, "maintainer", "gen-workflows", "app/verify")
    assert result.exit_code != 0 and "cx.vmr" in result.output
    (config / "cx.ptk.yml").write_text(
        cx
        + "vmr:\n  manifest_url: https://example.invalid/manifest.git\n"
        + "  app_id: 1400\n  private_key: APP_KEY\n"
    )
    result = invoke(tmp_path, "maintainer", "gen-workflows", "app/verify")
    assert result.exit_code == 0, result.output
    data = yaml.safe_load(
        (tmp_path / "app/.github/workflows/call-verify.yml").read_text()
    )
    assert data["jobs"]["setup"]["steps"][0]["with"]["app-id"] == "1400"
    assert data["on"]["workflow_call"]["inputs"]["project-directory"]["default"] == (
        "app"
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
                "repository": "cx",
                "base_path": alias,
                "events": {"push": {"path": "branch"}},
            },
        }
        if alias == "app":
            model["variants"]["variants"]["debug"]["repo_variants"] = {"tools": "host"}
            model["workflows"] = {
                "verify": {
                    "jobs": {
                        "tools:build": {},
                        "build": {"needs": ["tools:build"]},
                    }
                }
            }
        write_project(root / ".main.ptk.yml", model)
        grant_maintainer(root)
    result = invoke(
        tmp_path, "app", "maintainer", "matrix", "--workflow", "verify", cx=True
    )
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    [row] = data["jobs"]["build"]["include"]
    assert row["variant"] == "debug" and row["working_directory"] == "app"
    assert row["producers"][0]["variant"] == "host"
    assert row["producers"][0]["working_directory"] == "tools"
    assert row["producers"][0]["invocation"] == "repo_tools_job_build"


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


def test_invalid_output_contract_cannot_publish_even_available_files(artifacts):
    root, row, manifest, store = artifacts
    manifest["outputs_valid"] = False
    with pytest.raises(ValueError, match="required output contract"):
        actions.upload(manifest, root, row["upload"]["url"], row, "run1", {}, store)
    assert not store.files


def test_generated_jobs_remain_defined_and_guard_empty_variant_matrices():
    document = render(spec())
    assert set(document["jobs"]) == {"setup", "job_build", "job_test"}
    for name in ("job_build", "job_test"):
        assert f"has_jobs_{name}" in document["jobs"]["setup"]["outputs"]
        assert f"has_jobs_{name} == 'true'" in document["jobs"][name]["if"]
    assert "needs.job_build.result == 'success'" in document["jobs"]["job_test"]["if"]


def test_local_needs_are_not_github_dependencies():
    workflow = WorkflowSpec.model_validate(
        {"jobs": {"build": {}, "sbom": {"local_needs": "build"}}}
    )
    document = render(workflow)
    assert document["jobs"]["job_sbom"]["needs"] == ["setup"]
    assert "job_build" not in document["jobs"]["job_sbom"]["if"]


def test_tolerated_job_failure_is_passed_to_the_job_workflow():
    workflow = spec()
    workflow.jobs["build"].continue_on_error = True
    document = render(workflow)
    assert document["jobs"]["job_build"]["with"]["continue-on-error"] is True
    assert document["jobs"]["job_test"]["with"]["continue-on-error"] is False
    job = yaml.safe_load(render_job("build", settings(), {}, set()))["jobs"]["run"]
    check = job["steps"][-1]
    assert check["if"] == "${{ !cancelled() && inputs.continue-on-error }}"
    assert check["env"]["PTK_OUTPUTS_VALID"] == (
        "${{ steps.upload.outputs.outputs-valid }}"
    )
    assert "exit 1" in check["run"]


def named_row(row, name="build_debug_1.0.0+3.gabc"):
    return {**row, "upload": {**row["upload"], "name": name}}


def test_named_uploads_land_in_the_destination_with_readable_names(artifacts, tmp_path):
    root, row, manifest, store = artifacts
    row = named_row(row)
    manifest["files"][0]["properties"] = {
        **manifest["files"][0]["properties"],
        "artifact_type": "binaries",
    }
    address = actions.upload(
        manifest, root, row["upload"]["url"], row, "run1", {"quality": "ok"}, store
    )
    base = row["upload"]["url"]
    assert address == base + "build_debug_1.0.0%2B3.gabc.ptk-manifest.json"
    assert list(store.files) == [
        base + "build_debug_1.0.0%2B3.gabc_binaries.bin",
        base + "build_debug_1.0.0%2B3.gabc_symbols.zip",
        address,
    ]
    first = store.properties[base + "build_debug_1.0.0%2B3.gabc_binaries.bin"]
    assert first["artifact_type"] == "binaries" and first["quality"] == "ok"
    consumer = tmp_path / "consumer"
    consumer.mkdir()
    assert actions.download([row], consumer, "run1", store) == [
        "dist/app.bin",
        "symbols",
    ]
    assert (consumer / "symbols/run.sh").is_file()


def test_single_named_output_keeps_the_plain_name(artifacts):
    root, row, manifest, store = artifacts
    manifest["files"] = manifest["files"][1:]
    row = named_row(row)
    actions.upload(manifest, root, row["upload"]["url"], row, "run1", {}, store)
    assert row["upload"]["url"] + "build_debug_1.0.0%2B3.gabc.zip" in store.files


def test_named_download_rejects_foreign_files(artifacts, tmp_path):
    root, row, manifest, store = artifacts
    row = named_row(row)
    address = actions.upload(
        manifest, root, row["upload"]["url"], row, "run1", {}, store
    )
    document = json.loads(store.files[address])
    document["files"][0]["remote_path"] = "other_job.zip"
    store.files[address] = json.dumps(document).encode()
    with pytest.raises(ValueError, match="escapes"):
        actions.download([row], tmp_path, "run1", store)


def test_nested_output_of_one_producer_is_restored_once(artifacts, tmp_path):
    root, row, manifest, store = artifacts
    nested = {**manifest["files"][1], "relative_path": "symbols/empty"}
    nested["path"] = str(root / "symbols/empty")
    manifest["files"].append(nested)
    row = named_row(row)
    actions.upload(manifest, root, row["upload"]["url"], row, "run1", {}, store)
    consumer = tmp_path / "consumer"
    consumer.mkdir()
    assert actions.download([row], consumer, "run1", store) == [
        "dist/app.bin",
        "symbols",
    ]
    assert (consumer / "symbols/empty").is_dir()


def test_named_destination_requires_one_path_segment():
    from ptk.domain.artifacts import ArtifactoryStructure, destination

    spec = ArtifactoryStructure.model_validate(
        {
            "url": "https://example.invalid/artifactory",
            "repository": "ci",
            "name": "${run.job}_${run.variant}",
            "events": {
                "push": {
                    "branch": {"path": "dev"},
                    "tag": {"path": "releases", "name": "${run.job}_release"},
                }
            },
        }
    )
    values = {"run.job": "build", "run.variant": "debug"}

    def scope(text):
        for key, value in values.items():
            text = text.replace("${" + key + "}", value)
        return text

    branch = destination(spec, scope, event="push", ref_type="branch", job="build")
    tag = destination(spec, scope, event="push", ref_type="tag", job="build")
    assert branch["name"] == "build_debug" and tag["name"] == "build_release"
    values["run.variant"] = "a/b"
    with pytest.raises(ValueError, match="one path segment"):
        destination(spec, scope, event="push", ref_type="branch", job="build")


def test_upload_command_reports_failed_job_without_outputs(project, tmp_path):
    root = project[0]
    output = invoke(
        root,
        "maintainer",
        "cx",
        "upload",
        cx=True,
        env={
            "PTK_PRODUCER": "{}",
            "PTK_GITHUB_RESULT": str(tmp_path / "missing.json"),
            "PTK_JOB_OUTCOME": "failure",
            "PTK_ARTIFACT_USER": "robot",
            "PTK_ARTIFACT_TOKEN": "secret",
            "GITHUB_REPOSITORY": "o/r",
            "GITHUB_RUN_ID": "1",
        },
    )
    assert output.exit_code == 0, output.output
    assert output.output.splitlines() == ["outputs-valid=false"]


def test_download_command_rejects_producer_outside_needs(project):
    output = invoke(
        project[0],
        "maintainer",
        "cx",
        "download",
        "--root",
        str(project[0]),
        cx=True,
        env={
            "PTK_PRODUCERS": '[{"invocation": "job_build"}]',
            "PTK_NEEDS": '{"setup": {}}',
            "PTK_ARTIFACT_USER": "robot",
            "PTK_ARTIFACT_TOKEN": "secret",
            "GITHUB_REPOSITORY": "o/r",
            "GITHUB_RUN_ID": "1",
        },
    )
    assert output.exit_code != 0 and "not declared" in output.output


def test_qualified_workflow_keys_generate_distinct_portable_ids_and_matching_outputs():
    from ptk.domain.workflows import workflow_job_id

    keys = ["setup", "app:build", "app_cbuild", "app_build", "build"]
    assert len({workflow_job_id(key) for key in keys}) == len(keys)
    workflow = WorkflowSpec(
        jobs={
            key: {} if i == 0 else {"needs": keys[i - 1]} for i, key in enumerate(keys)
        }
    )
    rendered = render(workflow)
    for i, key in enumerate(keys):
        identity = workflow_job_id(key)
        job = rendered["jobs"][identity]
        assert job["name"] == key
        assert job["needs"] == ["setup", *([workflow_job_id(keys[i - 1])] if i else [])]
        assert f"matrix_{identity}" in rendered["jobs"]["setup"]["outputs"]
        assert f"matrix_{identity}" in job["with"]["matrix"]


@pytest.mark.parametrize(
    ("target", "expected"),
    [
        ("build", "job_build"),
        ("setup", "job_setup"),
        ("backend:build", "repo_backend_job_build"),
        ("my_repo:build_debug", "repo_my_repo_job_build_debug"),
        ("my-repo:build-debug", "repo_my-repo_job_build-debug"),
    ],
)
def test_readable_workflow_job_ids(target, expected):
    from ptk.domain.workflows import workflow_job_id

    assert workflow_job_id(target) == expected


def test_ambiguous_generated_ids_rejected_before_workflow_execution():
    with pytest.raises(ValueError) as error:
        WorkflowSpec(jobs={"a_job_b:c": {}, "a:b_job_c": {}})
    message = str(error.value)
    assert "a_job_b:c" in message
    assert "a:b_job_c" in message
    assert "repo_a_job_b_job_c" in message
    assert "rename" in message


def test_render_rechecks_ids_after_programmatic_workflow_mutation():
    workflow = WorkflowSpec(jobs={"a_job_b:c": {}})
    workflow.jobs["a:b_job_c"] = workflow.jobs["a_job_b:c"]
    with pytest.raises(ValueError, match="same generated ID"):
        render(workflow)
