"""The live workflow transcript keeps metadata, identity and failures together."""

import pytest
from tests.project_files import write_workflows
from tests.workflows.test_cli import command, invoke, repository


def test_workspace_transcript_identifies_equal_jobs_and_resolved_versions(tmp_path):
    (tmp_path / ".main.ptk.yml").write_text("virtual_monorepo: true\nmembers: [a, b]\n")
    for alias, version in [("a", "1.0.0"), ("b", "2.0.0")]:
        repository(
            tmp_path / alias,
            alias,
            jobs={"build": command("print('tool output')")},
            extra={
                "versioning": {"project": {"source": "literal", "version": version}},
            },
        )
    write_workflows(
        tmp_path / "workflows",
        {
            "verify": {
                "jobs": {
                    "first": {"job": "a:build"},
                    "second": {"job": "b:build"},
                }
            }
        },
    )
    result = invoke(tmp_path, "workflow", "run", "verify")
    assert result.exit_code == 0, result.output
    assert "[workspace][verify] report: " in result.output
    for alias in ["a", "b"]:
        assert f"[default][{alias}:build] report: " in result.output
    log = next(tmp_path.glob("_reports/workflows/verify/*/workflow.log"))
    text = log.read_text()
    for output in [result.output, text]:
        assert "WORKFLOW [workspace][verify] | START" in output
        assert "WORKFLOW SUMMARY [workspace][verify] | PASSED" in output
        assert "Jobs: 2 passed | 0 failed | 0 skipped" in output
        for alias, version in [("a", "1.0.0"), ("b", "2.0.0")]:
            assert (
                f"Repository: {alias} | Project: {alias} | Project version: {version}"
                in output
            )
            assert f"JOB [default][{alias}:build] | START" in output
            assert f"[default][{alias}:build][run] tool output" in output
            assert f"JOB SUMMARY [default][{alias}:build] | PASSED" in output
            assert f"[default][{alias}:build] Project:" in output
        assert "\x1b" not in output
    assert "tool output" in text


def test_failed_and_blocked_jobs_close_with_clear_workflow_counts(tmp_path):
    repository(
        tmp_path,
        jobs={"bad": command("raise SystemExit(2)"), "blocked": command("pass")},
        workflows={
            "verify": {
                "jobs": {
                    "bad": {"job": "bad"},
                    "blocked": {"job": "blocked", "needs": ["bad"]},
                }
            }
        },
    )
    result = invoke(tmp_path, "workflow", "run", "verify")
    assert result.exit_code == 1, result.output
    text = next(tmp_path.glob("_reports/workflows/verify/*/workflow.log")).read_text()
    assert "JOB SUMMARY [default][bad] | FAILED" in text
    assert "WORKFLOW SUMMARY [default][verify] | FAILED" in text
    assert "Jobs: 0 passed | 1 failed | 1 skipped" in text
    summary = text.split("WORKFLOW SUMMARY", 1)[1]
    assert "[default][blocked]" in summary and "SKIPPED" in summary
    assert "What failed: [default][bad][run] | FAILED | exit code 2" in summary
    assert "JOB [default][blocked] | START" not in text


@pytest.mark.parametrize("verbosity", [[], ["-vv"]])
def test_workflow_header_masks_prepared_metadata_before_jobs_start(tmp_path, verbosity):
    job = command("print('done')")
    job["steps"]["run"]["secrets"] = {"TOKEN": "api.token"}
    repository(
        tmp_path,
        jobs={"build": job},
        workflows={"verify": {"jobs": {"build": {"job": "build"}}}},
        extra={
            "credentials": {"api": {"providers": ["env"]}},
            "versioning": {"project": {"source": "literal", "version": "9.8.7"}},
        },
    )
    result = invoke(
        tmp_path,
        *verbosity,
        "workflow",
        "run",
        "verify",
        env={"PTK_CRED_API_TOKEN": "9.8.7"},
    )
    assert result.exit_code == 0, result.output
    transcript = next(tmp_path.glob("_reports/workflows/verify/*/workflow.log"))
    aggregate = tmp_path / "_logs/default/build/run.log"
    report_texts = [path.read_text() for path in transcript.parent.rglob("*.html")]
    report_texts += [path.read_text() for path in transcript.parent.rglob("*.json")]
    for text in [
        *report_texts,
        result.output,
        transcript.read_text(),
        aggregate.read_text(),
    ]:
        assert "9.8.7" not in text
    for text in [result.output, transcript.read_text(), aggregate.read_text()]:
        assert "Project version: ********" in text
        assert "\x00" not in text
        assert ("trace: env TOKEN=********" in text) is bool(verbosity)
    raw_step = tmp_path / "_logs/default/build/steps/run.log"
    assert "done" in raw_step.read_text()
    assert "JOB [default][build]" not in raw_step.read_text()


@pytest.mark.parametrize("allowed_at", ["step", "workflow"])
def test_workflow_recap_retains_allowed_failures_and_exact_step_identity(
    tmp_path, allowed_at
):
    failed = command("raise SystemExit(3)")
    failed["steps"]["run"]["continue_on_error"] = allowed_at == "step"
    repository(
        tmp_path,
        jobs={"bad": failed, "after": command("print('after ran')")},
        workflows={
            "verify": {
                "jobs": {
                    "try-build": {
                        "job": "bad",
                        "continue_on_error": allowed_at == "workflow",
                    },
                    "next": {"job": "after", "needs": ["try-build"]},
                }
            }
        },
        extra={"variants": {"default": "debug", "variants": {"debug": {}}}},
    )
    result = invoke(tmp_path, "workflow", "run", "verify")
    assert result.exit_code == 0, result.output
    transcript = next(
        tmp_path.glob("_reports/workflows/verify/*/workflow.log")
    ).read_text()
    for text in (result.output, transcript):
        assert "[debug][after][run] after ran" in text
        summary = text.split("WORKFLOW SUMMARY [debug][verify] | PASSED", 1)[1]
        assert (
            "What failed: [debug][bad][run] | FAILED | allowed failure | exit code 3"
            in summary
        )
        assert "invocation: try-build" in summary and "invocation: next" in summary
        assert (
            "Jobs: 1 passed | 1 failed"
            if allowed_at == "workflow"
            else "Jobs: 2 passed | 0 failed"
        ) in summary


def test_workflow_recap_identifies_job_failure_before_any_step_started(tmp_path):
    repository(tmp_path, workflows={"verify": {"jobs": {"build": {"job": "build"}}}})
    lock = tmp_path / ".ptk/locks/default/build.lock"
    lock.parent.mkdir(parents=True)
    lock.write_text("held by another run")
    result = invoke(tmp_path, "workflow", "run", "verify")
    assert result.exit_code == 1, result.output
    summary = result.output.split("WORKFLOW SUMMARY [default][verify] | FAILED", 1)[1]
    assert "What failed: [default][build] | FAILED" in summary
    assert "resource is locked" in summary
    assert "JOB [default][build] | START" not in result.output
