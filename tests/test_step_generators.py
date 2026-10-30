"""Generators share the step lifecycle and never run during planning."""

import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
import yaml
from pydantic import ValidationError

from ptk.adapters.variant_files import variant_writer
from ptk.application.use_cases.run import RunRequest
from ptk.bootstrap import create_app
from ptk.domain.config.model import StepSpec
from ptk.domain.errors import PtkError
from ptk.domain.execution.model import Status
from tests.project_files import write_project
from tests.test_generators import variant


def prepare(tmp_path, steps, *, variants=True, **request):
    data = {"project": {"name": "generation"}, "jobs": {"go": {"steps": steps}}}
    if variants:
        data["variants"] = {
            "components": {
                "core": {"features": {"SIZE": {"type": "int", "default": 4}}}
            },
            "variants": {"demo": {}, "other": {"features": {"core.SIZE": 9}}},
        }
    write_project(tmp_path / ".main.ptk.yml", yaml.safe_dump(data, sort_keys=False))
    app = create_app()
    project = app.load_project.execute(tmp_path)
    prepared = app.prepare_run(project).execute(
        project, RunRequest(job="go", **request)
    )
    return app, project, prepared


@pytest.mark.parametrize("mode", ["command", "python", "builtin", "only"])
def test_generation_precedes_every_kind_of_step(tmp_path, mode):
    script = (
        "import json,os; from pathlib import Path; "
        "assert Path.cwd() == Path(os.environ['EXPECTED_ROOT']); "
        "p=Path(os.environ['GENERATED']); "
        "assert json.loads(p.read_text())['values']['VARIANT_CORE_SIZE']==7"
    )
    step = {"generators": ["bazel"]}
    if mode in {"command", "python"}:
        step["env"] = {
            "GENERATED": "${run.build_dir}/variant.bazel.json",
            "EXPECTED_ROOT": str(tmp_path),
        }
        if mode == "command":
            step["run"] = [sys.executable, "-c", script]
        else:
            (tmp_path / "check.py").write_text(script)
            step.update(run="check.py", python={"interpreter": "cli"})
    elif mode == "builtin":
        step.update(
            uses="files.copy",
            **{
                "with": {
                    "files": "${run.build_dir}/variant.bazel.json",
                    "to": "_bin/copied",
                }
            },
        )
    app, project, prepared = prepare(
        tmp_path, {"generate": step}, feature_overrides={"core.SIZE": "7"}
    )
    result = app.run_job(project).execute(prepared)
    assert result.ok, result.steps
    snapshot = tmp_path / "_builds/demo/go/generate/variant.bazel.json"
    assert json.loads(snapshot.read_text())["values"]["VARIANT_CORE_SIZE"] == 7
    if mode == "builtin":
        assert (
            tmp_path / "_bin/copied/variant.bazel.json"
        ).read_bytes() == snapshot.read_bytes()


@pytest.mark.parametrize("options", [{"dry_run": True}, {"graph": True}])
def test_planning_does_not_generate(tmp_path, options):
    _app, _project, prepared = prepare(
        tmp_path, {"gen": {"generators": ["cmake"]}}, **options
    )
    # Preparation is the same boundary used by dry-run and graph commands.
    assert prepared.plan.steps[0].spec.generators == ["cmake"]
    assert not list(tmp_path.rglob("variant.cmake"))


def test_skipped_and_blocked_steps_do_not_generate(tmp_path):
    app, project, prepared = prepare(
        tmp_path,
        {
            "skip": {"generators": ["cmake"], "when": "False"},
            "fail": {"run": [sys.executable, "-c", "raise SystemExit(1)"]},
            "blocked": {"generators": ["cmake"], "needs": ["fail"]},
        },
    )
    result = app.run_job(project).execute(prepared)
    assert not result.ok
    assert not list(tmp_path.rglob("variant.cmake"))


@pytest.mark.parametrize(
    "variants,names,message",
    [(False, ["cmake"], "selected variant"), (True, ["missing"], "unknown generator")],
)
def test_generator_preflight_prevents_all_execution(tmp_path, variants, names, message):
    with pytest.raises(PtkError, match=message):
        prepare(
            tmp_path,
            {"first": {"uses": "echo"}, "gen": {"generators": names}},
            variants=variants,
        )
    assert not (tmp_path / "_builds").exists()


def test_generation_failure_prevents_command(tmp_path):
    app, project, prepared = prepare(
        tmp_path,
        {
            "gen": {
                "generators": ["cmake"],
                "run": [
                    sys.executable,
                    "-c",
                    "from pathlib import Path; Path('ran').touch()",
                ],
            }
        },
    )
    engine = app.run_job(project)
    engine._variant_writer = variant_writer({"cmake": lambda _: {"../escape": "bad"}})
    result = engine.execute(prepared)
    assert not result.ok and result.steps[0].attempts == 1
    assert "inside the step directory" in result.steps[0].message
    assert not (tmp_path / "ran").exists()


def test_retry_regenerates_files_from_prepared_snapshot(tmp_path):
    script = """import json,os
from pathlib import Path
p=Path(os.environ['GENERATED'])
assert json.loads(p.read_text())['values']['VARIANT_CORE_SIZE']==4
marker=Path('retried')
if not marker.exists():
    marker.touch()
    p.write_text('overwritten by project script')
    raise SystemExit(1)
"""
    app, project, prepared = prepare(
        tmp_path,
        {
            "gen": {
                "generators": ["bazel"],
                "retries": 1,
                "run": [sys.executable, "-c", script],
                "env": {"GENERATED": "${run.build_dir}/variant.bazel.json"},
            }
        },
    )
    project.config.variants.components["core"].features["SIZE"].default = 100
    result = app.run_job(project).execute(prepared)
    assert result.ok and result.steps[0].attempts == 2


def test_variants_and_parallel_steps_keep_separate_outputs(tmp_path):
    app, project, first = prepare(
        tmp_path,
        {name: {"generators": ["bazel"]} for name in ["one", "two"]},
        variant="demo",
    )
    second = app.prepare_run(project).execute(
        project, RunRequest(job="go", variant="other")
    )
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(
            executor.map(lambda p: app.run_job(project).execute(p), [first, second])
        )
    assert all(r.ok for r in results)
    for name, size in [("demo", 4), ("other", 9)]:
        for step in ["one", "two"]:
            path = tmp_path / f"_builds/{name}/go/{step}/variant.bazel.json"
            assert json.loads(path.read_text())["values"]["VARIANT_CORE_SIZE"] == size


@pytest.mark.parametrize(
    "files",
    [
        {"../outside": "bad"},
        {"C:/outside": "bad"},
        {"nested\\outside": "bad"},
        {"A.txt": "one", "a.txt": "two"},
        {"a": "one", "a/b": "two"},
        {"valid.txt": "ok", "invalid.txt": "\ud800"},
    ],
)
def test_writer_validates_all_outputs_before_replacing_files(tmp_path, files):
    (tmp_path / "valid.txt").write_text("original")
    with pytest.raises(PtkError):
        variant_writer({"test": lambda _: files})(
            ["test"], variant(), tmp_path, lambda _: None, None
        )
    assert sorted(p.name for p in tmp_path.iterdir()) == ["valid.txt"]
    assert (tmp_path / "valid.txt").read_text() == "original"


def test_writer_rejects_symlinks_and_plugin_snapshot_mutation(tmp_path):
    folder = tmp_path / "step"
    folder.mkdir()
    try:
        (folder / "link").symlink_to(tmp_path, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks unavailable")
    with pytest.raises(PtkError, match="symlinks"):
        variant_writer({"bad": lambda _: {"link/out": "bad"}})(
            ["bad"], variant(), folder, lambda _: None, None
        )
    snapshot = variant()

    def mutate(value):
        value.features["core.SIZE"].value = 999
        return {"one": "one"}

    def observe(value):
        assert value.values["core.SIZE"] == 4
        return {"two": "two"}

    variant_writer({"a": mutate, "b": observe})(
        ["a", "b"], snapshot, folder, lambda _: None, None
    )
    assert snapshot.values["core.SIZE"] == 4


def test_cancellation_between_generators_prevents_outputs_and_command(tmp_path):
    app, project, prepared = prepare(
        tmp_path, {"gen": {"generators": ["cmake"], "uses": "echo"}}
    )
    cancel = threading.Event()

    def stop(_):
        cancel.set()
        return {"variant.cmake": "unwritten"}

    engine = app.run_job(project)
    engine._variant_writer = variant_writer({"cmake": stop})
    result = engine.execute(prepared, cancel=cancel)
    assert result.steps[0].status == Status.CANCELLED
    assert not list(tmp_path.rglob("variant.cmake"))


def test_step_generator_validation():
    with pytest.raises(ValidationError, match="unique"):
        StepSpec(generators=["cmake", "cmake"])
    with pytest.raises(ValidationError, match="run, uses or"):
        StepSpec(generators=[])


def test_generator_timeout_prevents_command(tmp_path):
    import time

    app, project, prepared = prepare(
        tmp_path,
        {
            "gen": {
                "generators": ["cmake"],
                "timeout": 0.01,
                "run": [
                    sys.executable,
                    "-c",
                    "from pathlib import Path; Path('ran').touch()",
                ],
            }
        },
    )

    def slow(_):
        time.sleep(0.03)
        return {"variant.cmake": "unwritten"}

    engine = app.run_job(project)
    engine._variant_writer = variant_writer({"cmake": slow})
    result = engine.execute(prepared)
    assert result.steps[0].status == Status.FAILED
    assert "timed out" in result.steps[0].message
    assert not (tmp_path / "ran").exists()
    assert not list(tmp_path.rglob("variant.cmake"))
