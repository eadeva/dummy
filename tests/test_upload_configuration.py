"""Completed jobs expose literal outputs and a reusable upload configuration."""

import json
import os
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from ptk.adapters.reporting import exporters, html
from ptk.application.use_cases.run import RunRequest
from ptk.bootstrap import create_app
from ptk.domain.config.model import JobSpec, StepSpec
from ptk.domain.reporting.model import from_summary
from ptk.drivers.cli.main import cli
from tests.cli_runner import CliRunner
from tests.project_files import write_project
from tests.test_git_metadata import git, repo


@pytest.fixture
def project(tmp_path):
    repo(tmp_path)
    model = {
        "repository": {"alias": "firmware", "config_path": "config"},
        "project": {"name": "Firmware"},
        "versioning": {"project": {"source": "literal", "version": "1.2.3"}},
        "variants": {"default": "debug", "variants": {"debug": {"aliases": ["dev"]}}},
        "layout": {"root": "generated", "builds": "work", "logs": "logs"},
        "jobs": {
            "build": {
                "outputs": ["${steps.compile.build_dir}/${run.id}/app.bin"],
                "steps": {
                    "compile": {
                        "run": [
                            sys.executable,
                            "-c",
                            "from pathlib import Path; import sys; p=Path(sys.argv[1]); p.mkdir(parents=True); (p/'app.bin').write_bytes(b'binary'); (p/'symbols').mkdir(); (p/'symbols'/'app.map').write_text('symbols')",
                            "${run.build_dir}/${run.id}",
                        ],
                        "outputs": [
                            {
                                "path": "${run.build_dir}/${run.id}/app.bin",
                                "artifact_type": "binaries",
                            },
                            {
                                "path": "${run.build_dir}/${run.id}/symbols",
                                "artifact_type": "symbols",
                            },
                        ],
                    }
                },
            }
        },
    }
    write_project(tmp_path / ".main.ptk.yml", model)
    return tmp_path, model


def execute(root, **options):
    app = create_app(environ={"PATH": os.environ.get("PATH", ""), "PTK_CI": "1"})
    project = app.load_project.execute(root)
    prepared = app.prepare_run(project).execute(
        project, RunRequest(job="build", **options)
    )
    result = app.run_job(project).execute(prepared, app.log_observers(prepared))
    return result, prepared


def test_runtime_paths_properties_and_summary_report_roundtrip(project):
    root, _ = project
    result, prepared = execute(root, variant="dev")
    assert result.ok
    manifest = json.loads(Path(result.upload_file).read_text())
    assert manifest["schema_version"] == 1 and manifest["run_id"] == result.run_id
    assert manifest["repository"] == "firmware"
    assert (
        len(manifest["files"]) == len(result.outputs) == 2
    )  # Job/step duplicate is combined.
    first, second = manifest["files"]
    assert Path(first["path"]).read_bytes() == b"binary"
    assert result.run_id in first["path"]
    assert first["properties"] == {
        "version": "1.2.3",
        "commit": git(root, "rev-parse", "HEAD"),
        "variant_alias": ["debug", "dev"],
        "job": "build",
        "step": "compile",
        "artifact_type": "binaries",
    }
    assert (
        second["kind"] == "directory"
        and second["properties"]["artifact_type"] == "symbols"
    )
    folder = Path(prepared.plan.dirs["log_dir"])
    summary = json.loads((folder / "run.json").read_text())
    assert summary["outputs"] == result.outputs
    assert summary["upload_file"] == result.upload_file
    transcript = (folder / "run.log").read_text()
    assert "Output [compile: binaries]:" in transcript
    assert result.upload_file in transcript
    report = from_summary(summary, [])
    for content in (
        exporters.to_json(report),
        exporters.to_markdown(report),
        html.render(report),
    ):
        assert (
            "app.bin" in content and "upload.json" in content and "symbols" in content
        )


def test_cli_prints_outputs_and_upload_configuration(project):
    root, _ = project
    result = CliRunner(env={"PTK_CI": "1", "PTK_ROLE": "user"}).invoke(
        cli, ["-V", "dev", "run", "build"], cwd=root
    )
    assert result.exit_code == 0, result.output
    assert "Output [compile: binaries]:" in result.output
    assert "Upload configuration:" in result.output and "upload.json" in result.output


def test_missing_outputs_and_failed_producer_are_not_upload_candidates(project):
    root, model = project
    compile = model["jobs"]["build"]["steps"]["compile"]
    compile["outputs"].append("missing.txt")
    compile["run"][2] += "; sys.exit(7)"
    write_project(root / ".main.ptk.yml", model)
    result, _ = execute(root)
    assert not result.ok
    assert json.loads(Path(result.upload_file).read_text())["files"] == []
    assert any(item["reason"] == "missing" for item in result.outputs)
    assert any(
        item["reason"] == "producer did not complete successfully"
        for item in result.outputs
    )


def test_successful_step_outputs_remain_available_if_later_step_fails(project):
    root, model = project
    model["jobs"]["build"]["steps"]["fail"] = {
        "run": [sys.executable, "-c", "raise SystemExit(8)"],
        "needs": ["compile"],
    }
    model["jobs"]["build"]["outputs"].append("old-job-output")
    (root / "old-job-output").write_text("stale")
    write_project(root / ".main.ptk.yml", model)
    result, _ = execute(root)
    manifest = json.loads(Path(result.upload_file).read_text())
    assert not result.ok and len(manifest["files"]) == 2
    assert all(item["properties"]["step"] == "compile" for item in manifest["files"])
    assert any(
        item["path"].endswith("old-job-output") and not item["available"]
        for item in result.outputs
    )


def test_untyped_job_output_and_missing_metadata_remain_explicit(tmp_path):
    write_project(
        tmp_path / ".main.ptk.yml",
        {
            "project": {"name": "No metadata"},
            "jobs": {
                "build": {
                    "outputs": ["artifact.txt"],
                    "steps": {
                        "make": {
                            "run": [
                                sys.executable,
                                "-c",
                                "from pathlib import Path; Path('artifact.txt').write_text('content')",
                            ],
                        }
                    },
                }
            },
        },
    )
    result, _ = execute(tmp_path)
    [item] = json.loads(Path(result.upload_file).read_text())["files"]
    assert item["properties"] == {
        "job": "build",
        "step": None,
        "variant_alias": ["default"],
        "version": None,
        "commit": None,
    }


def test_dry_run_writes_no_upload_configuration(project):
    root, _ = project
    result = CliRunner(env={"PTK_CI": "1", "PTK_ROLE": "user"}).invoke(
        cli, ["run", "build", "--dry-run"], cwd=root
    )
    assert result.exit_code == 0, result.output
    assert not list(root.rglob("upload.json"))


def test_masked_output_paths_are_not_upload_candidates(project):
    root, model = project
    job = model["jobs"]["build"]
    job["outputs"] = ["${params.token}.bin"]
    job["params"] = {"token": {"type": "secret", "required": True}}
    job["steps"] = {"make": {"uses": "echo"}}
    token = "private-output-token"
    (root / f"{token}.bin").write_text("data")
    write_project(root / ".main.ptk.yml", model)
    result, _ = execute(root, params={"token": token})
    text = Path(result.upload_file).read_text()
    assert token not in text and json.loads(text)["files"] == []
    assert token not in json.dumps(result.outputs)


def test_upload_write_failure_preserves_job_result_and_output_summary(
    project, monkeypatch
):
    from ptk.adapters import uploads

    root, _ = project
    original = uploads.os.replace

    def fail_upload(source, target):
        if Path(target).name == "upload.json":
            raise OSError("upload file is read-only")
        return original(source, target)

    monkeypatch.setattr(uploads.os, "replace", fail_upload)
    result, prepared = execute(root)
    assert result.ok and result.upload_file is None
    assert result.upload_problem and "read-only" in result.upload_problem
    assert len(result.outputs) == 2
    assert (
        "Cannot write upload configuration"
        in Path(prepared.layout.run_log("debug", "build")).read_text()
    )


def test_history_keeps_previous_upload_configuration(project):
    root, _ = project
    first, prepared = execute(root)
    second, _ = execute(root)
    assert second.run_id != first.run_id
    history = Path(prepared.plan.dirs["log_dir"]) / "_history" / first.run_id
    assert json.loads((history / "upload.json").read_text())["run_id"] == first.run_id
    assert json.loads((history / "run.json").read_text())["upload_file"] == str(
        history / "upload.json"
    )


@pytest.mark.parametrize(
    "outputs",
    [
        [{"path": ""}],
        [{"path": "x"}, "x"],
        [{"path": "x", "artifact_type": ""}],
        [{"path": "x", "typo": "binary"}],
        [{"path": 123}],
    ],
)
@pytest.mark.parametrize("kind", [JobSpec, StepSpec])
def test_invalid_typed_outputs_are_rejected(outputs, kind):
    with pytest.raises(ValidationError):
        kind.model_validate(
            {
                "outputs": outputs,
                **(
                    {"steps": {"make": {"uses": "echo"}}}
                    if kind is JobSpec
                    else {"uses": "echo"}
                ),
            }
        )


def test_typed_outputs_keep_cache_reuse_provenance(project):
    root, model = project
    model["jobs"]["build"] = {
        "steps": {
            "produce": {
                "run": [
                    sys.executable,
                    "-c",
                    "from pathlib import Path; Path('input').write_text('same')",
                ],
                "outputs": ["input"],
            },
            "consume": {
                "run": [
                    sys.executable,
                    "-c",
                    "from pathlib import Path; Path('output').write_text('cached')",
                ],
                "needs": ["produce"],
                "outputs": [{"path": "output", "artifact_type": "binaries"}],
                "cache": True,
            },
        }
    }
    write_project(root / ".main.ptk.yml", model)
    first, _ = execute(root)
    second, _ = execute(root)
    assert second.steps[1].reused_from == first.run_id
    [item] = [
        item
        for item in json.loads(Path(second.upload_file).read_text())["files"]
        if item["properties"]["step"] == "consume"
    ]
    assert (
        item["reused_from"] == first.run_id
        and item["properties"]["artifact_type"] == "binaries"
    )


def test_workflow_snapshot_keeps_original_upload_configuration(project):
    from ptk.adapters.workflow_files import snapshot_logs

    root, _ = project
    first, prepared = execute(root)
    summary = json.loads((Path(prepared.plan.dirs["log_dir"]) / "run.json").read_text())
    snapshot = snapshot_logs(summary, root / "workflow" / "child")
    second, _ = execute(root)
    assert first.run_id != second.run_id
    assert snapshot["upload_file"] != second.upload_file
    assert (
        json.loads(Path(snapshot["upload_file"]).read_text())["run_id"] == first.run_id
    )


def test_partial_run_does_not_publish_stale_job_outputs(project):
    root, model = project
    model["jobs"]["build"]["outputs"] = ["old-job-output"]
    (root / "old-job-output").write_text("old")
    write_project(root / ".main.ptk.yml", model)
    result, _ = execute(root, only_step="compile")
    manifest = json.loads(Path(result.upload_file).read_text())
    assert result.ok and len(manifest["files"]) == 2
    assert all(item["properties"]["step"] == "compile" for item in manifest["files"])
    assert any(
        item["step"] is None and not item["available"] for item in result.outputs
    )
