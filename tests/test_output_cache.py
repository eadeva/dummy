"""Opt-in local reuse through real command, built-in and workflow execution."""

import json
import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from pydantic import ValidationError

from ptk.adapters.output_cache import LocalOutputCache
from ptk.adapters.reporting import exporters, html
from ptk.application.use_cases.run import Cancelled, RunRequest
from ptk.bootstrap import create_app
from ptk.domain.config.model import JobSpec, StepSpec
from ptk.domain.reporting.model import from_summary
from ptk.domain.reporting.summary import run_summary
from ptk.drivers.cli.main import cli
from tests.cli_runner import CliRunner
from tests.project_files import write_project


def command(code):
    return [sys.executable, "-c", "from pathlib import Path; " + code]


def producer():
    return {
        "run": command(
            "Path('input').write_text(Path('source').read_text()); p=Path('calls'); p.write_text((p.read_text() if p.exists() else '')+'R')"
        ),
        "outputs": ["input"],
        "cache": True,
    }


def consumer():
    return {
        "run": command(
            "Path('output').write_text(Path('input').read_text()); p=Path('calls'); p.write_text(p.read_text()+'C')"
        ),
        "needs": ["root"],
        "outputs": ["output"],
        "cache": True,
    }


@pytest.fixture
def project(tmp_path):
    model = {
        "project": {"name": "reuse"},
        "jobs": {"go": {"steps": {"root": producer(), "child": consumer()}}},
    }
    (tmp_path / "source").write_text("one")
    write_project(tmp_path / ".main.ptk.yml", model)
    return tmp_path, model


def run(root, *, env=None, cancel=None, builtins=None, **options):
    app = create_app(environ={"PATH": os.environ.get("PATH", ""), **(env or {})})
    project = app.load_project.execute(root)
    prepared = app.prepare_run(project).execute(
        project, RunRequest(job="go", **options)
    )
    runner = app.run_job(project)
    if builtins:
        runner._builtins.update(builtins)
    result = runner.execute(prepared, app.log_observers(prepared), cancel)
    return result, prepared


def invoke(root, *args):
    result = CliRunner(env={"PTK_ROLE": "user", "PTK_CI": "0"}).invoke(
        cli, args, cwd=root, catch_exceptions=False
    )
    assert result.exit_code == 0, result.output
    return result.output


def save(root, model):
    write_project(root / ".main.ptk.yml", model)


@pytest.mark.parametrize("model", [StepSpec, JobSpec])
@pytest.mark.parametrize(
    "options",
    [
        {"cache": True},
        {"outputs": [""]},
        {"outputs": ["a", "a"]},
        {"outputs": "a"},
        {"outputs": [1]},
        {"cache": "true", "outputs": ["a"]},
    ],
)
def test_invalid_contract(model, options):
    with pytest.raises(ValidationError):
        model.model_validate(
            {
                **(
                    {"uses": "echo"}
                    if model is StepSpec
                    else {"steps": {"one": {"uses": "echo"}}}
                ),
                **options,
            }
        )


def test_root_executes_and_consumer_reuses_content_despite_new_mtime(project):
    root, _ = project
    first, _ = run(root)
    second, _ = run(root)
    assert (root / "calls").read_text() == "RCR"
    assert not second.steps[0].reused_from
    reused = second.steps[1]
    assert reused.reused_from == first.run_id
    assert reused.attempts == 0 and reused.exit_code is None and not reused.log_file
    assert second.ok
    (root / "source").write_text("two")
    third, _ = run(root)
    assert not third.steps[1].reused_from
    assert (root / "calls").read_text() == "RCRRC"


@pytest.mark.parametrize(
    "change",
    [
        "missing",
        "changed",
        "missing_dependency",
        "no_cache",
        "undeclared_dependency",
        "undeclared_consumer",
        "corrupt_receipt",
    ],
)
def test_misses_execute_normally(project, change):
    root, model = project
    run(root)
    child = model["jobs"]["go"]["steps"]["child"]
    if change == "missing":
        (root / "output").unlink()
    elif change == "changed":
        (root / "output").write_text("wrong")
    elif change == "missing_dependency":
        model["jobs"]["go"]["steps"]["root"]["outputs"] = ["nonexistent"]
    elif change == "no_cache":
        child["cache"] = False
    elif change == "undeclared_dependency":
        parent = model["jobs"]["go"]["steps"]["root"]
        parent.pop("cache")
        parent.pop("outputs")
    elif change == "undeclared_consumer":
        child.pop("cache")
        child.pop("outputs")
    else:
        for file in (root / ".ptk/output-cache/v1").glob("*.json"):
            file.write_text("bad json")
    save(root, model)
    result, _ = run(root)
    assert result.ok and not result.steps[1].reused_from
    assert (root / "calls").read_text() == "RCRC"


def test_builtin_operations_use_same_cache(project):
    root, model = project
    child = model["jobs"]["go"]["steps"]["child"]
    child.pop("run")
    child["uses"] = "echo"
    calls = []

    def operation(step, out, ctx):
        calls.append(step.name)
        (ctx.root / "output").write_text("built in")
        return 0

    save(root, model)
    run(root, builtins={"echo": operation})
    result, _ = run(root, builtins={"echo": operation})
    assert calls == ["child"] and result.steps[1].reused_from


@pytest.mark.parametrize("change", ["command", "parameter", "environment", "secret"])
def test_resolved_configuration_changes_invalidate_and_receipts_are_digest_only(
    project, change
):
    root, model = project
    job = model["jobs"]["go"]
    job["params"] = {"value": {"default": "first"}}
    model["credentials"] = {"service": {"fields": ["token"], "env": {"token": "TOKEN"}}}
    job["steps"]["child"]["secrets"] = {"CREDENTIAL": "service.token"}
    save(root, model)
    env = {"TOKEN": "secret-before"}
    run(root, env=env)
    options = {}
    if change == "command":
        job["steps"]["child"]["run"][-1] += "; print('changed')"
        save(root, model)
    elif change == "parameter":
        options["params"] = {"value": "second"}
    elif change == "environment":
        job["env"] = {"REUSE_SETTING": "changed"}
        save(root, model)
    else:
        env["TOKEN"] = "secret-after"
    result, _ = run(root, env=env, **options)
    assert not result.steps[1].reused_from
    for file in (root / ".ptk/output-cache/v1").glob("*.json"):
        assert "secret-" not in file.read_text()
        assert set(json.loads(file.read_text())) == {
            "version",
            "inputs",
            "outputs",
            "run_id",
        }


def test_failure_never_reuses_and_invalidates_previous_attempt(project):
    root, model = project
    run(root)
    child = model["jobs"]["go"]["steps"]["child"]
    original = child["run"]
    child["run"] = command("raise SystemExit(3)")
    save(root, model)
    failed, _ = run(root)
    assert not failed.ok and not failed.steps[1].reused_from
    child["run"] = original
    save(root, model)
    again, _ = run(root)
    assert not again.steps[1].reused_from


def test_allowed_failure_and_cancellation_do_not_release_cached_work(project):
    root, model = project
    run(root)
    model["jobs"]["go"]["steps"]["root"].update(
        run=command("raise SystemExit(2)"), continue_on_error=True
    )
    save(root, model)
    result, _ = run(root)
    assert result.ok and not result.steps[1].reused_from
    cancel = Cancelled()
    cancel.set()
    result, _ = run(root, cancel=cancel)
    assert result.status == "cancelled" and not any(
        step.reused_from for step in result.steps
    )


def test_only_step_and_forced_runs_do_not_reuse_or_refresh_cache(project):
    root, _ = project
    run(root)
    forced, _ = run(root, no_cache_ptk=True)
    assert not any(step.reused_from for step in forced.steps)
    again, _ = run(root)
    assert not again.steps[1].reused_from
    alone, _ = run(root, only_step="child")
    assert not alone.steps[1].reused_from


def test_directory_fingerprint_tracks_content_names_and_modes_not_mtime(tmp_path):
    cache = LocalOutputCache(tmp_path)
    folder = tmp_path / "out"
    folder.mkdir()
    file = folder / "a"
    file.write_text("abc")

    def digest():
        return cache.fingerprint([str(folder)], Cancelled())

    first = digest()
    file.touch()
    assert digest() == first
    old = file.stat()
    file.write_text("xyz")
    os.utime(file, ns=(old.st_atime_ns, old.st_mtime_ns))
    assert digest() != first
    file.write_text("abc")
    assert digest() == first
    file.rename(folder / "b")
    assert digest() != first
    file = folder / "b"
    file.rename(folder / "a")
    extra = folder / "new"
    extra.mkdir()
    assert digest() != first
    extra.rmdir()
    assert digest() == first
    link = folder / "link"
    link.symlink_to(folder / "a")
    assert digest() is None
    link.unlink()
    token = Cancelled()
    token.set()
    assert cache.fingerprint([str(folder)], token) is None


def test_reports_distinguish_reuse_from_new_execution(project):
    root, _ = project
    first, _ = run(root)
    result, prepared = run(root)
    summary = run_summary(prepared.plan, result)
    report = from_summary(summary, [])
    assert report.steps[1].attempts == 0 and report.steps[1].reused_from == first.run_id
    assert report.graph["nodes"][1]["status"] == "reused"
    rendered = html.render(report, link_root=root)
    assert 'class="badge reused">Reused' in rendered and first.run_id in rendered
    assert "Steps reused" in rendered
    assert "reused" in exporters.to_markdown(
        report
    ) and first.run_id in exporters.to_markdown(report)
    xml = ET.fromstring(exporters.to_junit(report))
    skipped = xml.find("testsuite/testcase[@name='child']/skipped")
    assert skipped is not None and first.run_id in skipped.attrib["message"]


@pytest.mark.parametrize(
    "args",
    [
        ("--no-cache-ptk", "go"),
        ("go", "--no-cache-ptk"),
        ("run", "go", "--no-cache-ptk"),
    ],
)
def test_cli_flag_and_dry_run(project, args):
    root, _ = project
    invoke(root, "go")
    receipts = {
        p: p.read_bytes() for p in (root / ".ptk/output-cache/v1").glob("*.json")
    }
    invoke(root, *args, "--dry-run")
    assert all(p.read_bytes() == content for p, content in receipts.items())
    assert (root / "calls").read_text() == "RC"
    invoke(root, *args)
    assert (root / "calls").read_text() == "RCRC"


def workflow_project(root):
    (root / "source").write_text("same")
    build = producer()
    package = consumer()
    package.pop("needs")
    model = {
        "project": {"name": "reuse"},
        "jobs": {
            "build": {"cache": True, "outputs": ["input"], "steps": {"produce": build}},
            "package": {
                "cache": True,
                "outputs": ["output"],
                "steps": {"consume": package},
            },
        },
        "workflows": {
            "all": {
                "jobs": {
                    "last": {"job": "package", "needs": ["first"]},
                    "first": {"job": "build"},
                }
            }
        },
    }
    save(root, model)
    return model


@pytest.mark.parametrize(
    "args",
    [
        ("all", "--no-cache-ptk"),
        ("workflow", "run", "all", "--no-cache-ptk"),
        ("--no-cache-ptk", "all"),
    ],
)
def test_workflow_roots_run_dependents_reuse_and_flag_propagates(tmp_path, args):
    workflow_project(tmp_path)
    invoke(tmp_path, "all")
    output = invoke(tmp_path, "workflow", "run", "all")
    assert "REUSED" in output
    assert (tmp_path / "calls").read_text() == "RCR"
    summaries = [
        json.loads(p.read_text())
        for p in tmp_path.glob("_reports/workflows/all/*/workflow.json")
    ]
    reused = [s for s in summaries if s["jobs"][0]["reused_from"]]
    assert len(reused) == 1
    invoke(tmp_path, *args)
    assert (tmp_path / "calls").read_text() == "RCRRC"
    invoke(tmp_path, "package")  # A standalone job always executes.
    assert (tmp_path / "calls").read_text() == "RCRRCC"


def test_join_checks_all_roots_regardless_of_yaml_order(project):
    root, model = project
    steps = model["jobs"]["go"]["steps"]
    join = steps["child"]
    join["needs"] = ["root", "other"]
    model["jobs"]["go"]["steps"] = {
        "join": join,
        "other": {"uses": "echo", "outputs": ["other-output"]},
        "root": steps["root"],
    }
    (root / "other-output").write_text("a")
    save(root, model)
    run(root)
    result, _ = run(root)
    assert result.steps[0].reused_from
    (root / "other-output").write_text("b")
    result, _ = run(root)
    assert not result.steps[0].reused_from
    assert all(not step.reused_from for step in result.steps[1:])


def test_changed_producer_config_with_identical_outputs_keeps_consumer_reusable(
    project,
):
    root, model = project
    run(root)
    model["jobs"]["go"]["steps"]["root"]["run"][-1] += "; print('new producer')"
    save(root, model)
    result, _ = run(root)
    assert result.steps[1].reused_from


def test_declared_step_paths_resolve_against_cwd_and_job_paths_against_repository(
    project,
):
    root, model = project
    job = model["jobs"]["go"]
    job["outputs"] = ["${steps.child.build_dir}"]
    job["steps"]["child"].update(
        cwd="${run.build_dir}", run=command("Path('output').write_text('made')")
    )
    save(root, model)
    _, prepared = run(root)
    output_dir = root / "_builds/default/go/child"
    assert prepared.plan.outputs == [str(output_dir)]
    assert prepared.plan.steps[1].outputs == [str(output_dir / "output")]
    result, _ = run(root)
    assert result.steps[1].reused_from


def test_storage_failure_falls_back_without_failing_work(project, monkeypatch):
    root, _ = project

    def unavailable(*args):
        raise OSError("receipt store unavailable")

    monkeypatch.setattr(LocalOutputCache, "write", unavailable)
    result, _ = run(root)
    assert result.ok and (root / "calls").read_text() == "RC"
    assert "PTK cache receipt not written" in Path(result.log_file).read_text()


def test_gui_launch_and_whole_job_cannot_be_cached():
    with pytest.raises(ValidationError, match="GUI jobs cannot"):
        JobSpec(
            gui=True,
            cache=True,
            outputs=["window"],
            steps={"launch": {"run": "viewer"}},
        )
    with pytest.raises(ValidationError, match="launch step cannot"):
        JobSpec(
            gui=True,
            steps={"launch": {"run": "viewer", "cache": True, "outputs": ["window"]}},
        )


def test_workflow_flag_disables_nested_step_cache_even_without_job_cache(project):
    root, model = project
    model["workflows"] = {"all": {"jobs": {"go": {"job": "go"}}}}
    save(root, model)
    invoke(root, "all")
    invoke(root, "all")
    assert (root / "calls").read_text() == "RCR"
    invoke(root, "all", "--no-cache-ptk")
    assert (root / "calls").read_text() == "RCRRC"


@pytest.mark.parametrize(
    "args",
    [
        ("--no-cache-ptk", "demo", "go"),
        ("demo", "go", "--no-cache-ptk"),
        ("--no-cache-ptk", "all"),
        ("all", "--no-cache-ptk"),
    ],
)
def test_workspace_flag_reaches_repository_jobs(project, tmp_path, args):
    from tests.project_files import write_workflows

    root, model = project
    member = root / "member"
    member.mkdir()
    (member / "source").write_text("one")
    save(member, model)
    (root / ".main.ptk.yml").write_text("virtual_monorepo: true\nmembers: [member]\n")
    write_workflows(root / "workflows", {"all": {"jobs": {"go": {"job": "demo:go"}}}})
    invoke(root, "demo", "go")
    invoke(root, "demo", "go")
    assert (member / "calls").read_text() == "RCR"
    invoke(root, *args)
    assert (member / "calls").read_text() == "RCRRC"


def test_no_cache_bypasses_lookup_hashing_and_write(project, monkeypatch):
    root, _ = project
    run(root)

    def forbidden(*args):
        pytest.fail("cache used during forced run")

    for name in ("read", "fingerprint", "write"):
        monkeypatch.setattr(LocalOutputCache, name, forbidden)
    result, _ = run(root, no_cache_ptk=True)
    assert result.ok and not any(step.reused_from for step in result.steps)


@pytest.mark.parametrize("scope", ["job", "step"])
@pytest.mark.parametrize("output", ["${params.unknown}", "${params.empty}"])
def test_invalid_output_substitution_is_actionable_usage_error(project, scope, output):
    root, model = project
    job = model["jobs"]["go"]
    job["params"] = {"empty": {"default": ""}}
    (job if scope == "job" else job["steps"]["child"])["outputs"] = [output]
    save(root, model)
    result = CliRunner(env={"PTK_ROLE": "user", "PTK_CI": "0"}).invoke(
        cli, ["go", "--dry-run"], cwd=root, catch_exceptions=False
    )
    assert result.exit_code == 2 and "error:" in result.output
    assert not (root / "calls").exists()
