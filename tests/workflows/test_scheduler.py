"""Dependency scheduling, failure propagation and cooperative cancellation."""

import threading
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from ptk.application.use_cases.run import Cancelled
from ptk.application.use_cases.workflow import CallOutcome, PrepareWorkflow, RunWorkflow
from ptk.domain.errors import PtkError
from ptk.domain.execution.model import Status
from ptk.domain.workflows import WorkflowSpec


def prepare(node, invocation):
    return "app", SimpleNamespace(
        project=SimpleNamespace(root=Path(".")),
        plan=SimpleNamespace(
            variant=None, job=invocation, walk=list, outputs=[], skip_reason=None
        ),
    )


def plan(jobs, **options):
    return PrepareWorkflow().execute(
        "checks", WorkflowSpec(jobs=jobs, **options), prepare
    )


def test_diamond_overlaps_siblings_and_waits_for_both_before_join():
    prepared = plan(
        {
            "join": {"needs": ["left", "right"]},
            "left": {"needs": "root"},
            "right": {"needs": "root"},
            "root": {},
        },
        max_workers=2,
    )
    barrier = threading.Barrier(2)
    finished = set()
    lock = threading.Lock()

    def run(node, cancel):
        with lock:
            assert set(node.spec.needs) <= finished
        if node.id in {"left", "right"}:
            barrier.wait(timeout=5)
        with lock:
            finished.add(node.id)
        return CallOutcome(Status.PASSED)

    result = RunWorkflow().execute(prepared, run, Cancelled())
    assert result.status == Status.PASSED
    assert [job.id for job in result.jobs] == ["join", "left", "right", "root"]
    assert result.jobs[0].needs == ["left", "right"]


def test_ready_dependent_starts_without_waiting_for_unrelated_branch():
    prepared = plan(
        {
            "fast": {},
            "slow": {},
            "dependent": {"needs": "fast"},
        },
        max_workers=2,
    )
    dependent = threading.Event()

    def run(node, cancel):
        if node.id == "slow":
            assert dependent.wait(5), "scheduler waited for a whole wave"
        if node.id == "dependent":
            dependent.set()
        return CallOutcome(Status.PASSED)

    assert RunWorkflow().execute(prepared, run, Cancelled()).status == Status.PASSED


def test_worker_limit_bounds_ready_jobs():
    prepared = plan({name: {} for name in "abcd"}, max_workers=2)
    barrier, lock = threading.Barrier(2), threading.Lock()
    active = maximum = 0

    def run(node, cancel):
        nonlocal active, maximum
        with lock:
            active += 1
            maximum = max(maximum, active)
        barrier.wait(timeout=5)
        with lock:
            active -= 1
        return CallOutcome(Status.PASSED)

    assert RunWorkflow().execute(prepared, run, Cancelled()).status == Status.PASSED
    assert maximum == 2


@pytest.mark.parametrize("outcome", [Status.FAILED, Status.SKIPPED, Status.CANCELLED])
def test_unsuccessful_prerequisite_blocks_its_chain_but_not_independent_jobs(outcome):
    prepared = plan(
        {
            "broken": {},
            "child": {"needs": "broken"},
            "grandchild": {"needs": "child"},
            "independent": {},
        }
    )
    calls = []

    def run(node, cancel):
        calls.append(node.id)
        return CallOutcome(outcome if node.id == "broken" else Status.PASSED)

    result = RunWorkflow().execute(prepared, run, Cancelled())
    assert set(calls) == {"broken", "independent"}
    assert result.jobs[1].status == result.jobs[2].status == Status.SKIPPED
    assert f"broken ({outcome.value})" in result.jobs[1].message
    assert "child (skipped)" in result.jobs[2].message


def test_tolerated_failure_releases_dependents_and_retains_failed_report():
    prepared = plan(
        {
            "broken": {"continue_on_error": True},
            "next": {"needs": "broken"},
        }
    )
    result = RunWorkflow().execute(
        prepared,
        lambda node, _: CallOutcome(
            Status.FAILED if node.id == "broken" else Status.PASSED
        ),
        Cancelled(),
    )
    assert result.status == Status.PASSED and result.has_errors
    assert result.jobs[0].status == Status.FAILED and result.jobs[0].allowed_failure
    assert result.jobs[1].status == Status.PASSED


def test_cancel_reaches_active_job_and_prevents_queued_and_dependent_calls():
    prepared = plan(
        {
            "first": {"continue_on_error": True},
            "queued": {},
            "dependent": {"needs": "first"},
        },
        max_workers=1,
    )
    cancel, calls = Cancelled(), []

    def run(node, token):
        assert token is cancel
        calls.append(node.id)
        token.set()
        return CallOutcome(Status.CANCELLED)

    result = RunWorkflow().execute(prepared, run, cancel)
    assert result.status == Status.CANCELLED and calls == ["first"]
    assert all(
        job.status == Status.CANCELLED and not job.allowed_failure
        for job in result.jobs
    )


def test_pre_cancelled_workflow_never_launches_jobs():
    prepared = plan({"one": {}})
    cancel = Cancelled()
    cancel.set()
    result = RunWorkflow().execute(
        prepared, lambda *_: pytest.fail("launched job"), cancel
    )
    assert result.status == Status.CANCELLED


def test_run_error_becomes_failed_result_with_reason():
    def run(*_):
        raise PtkError("job lock held")

    result = RunWorkflow().execute(plan({"one": {}}), run, Cancelled())
    assert result.status == Status.FAILED
    assert result.jobs[0].message == "job lock held"


def test_transitive_dependencies_order_distinct_jobs_even_in_reverse_yaml_order():
    prepared = plan(
        {
            "package": {"needs": "test"},
            "test": {"needs": "build"},
            "build": {},
        }
    )
    calls = []

    def run(node, _):
        calls.append(node.id)
        return CallOutcome(Status.PASSED)

    RunWorkflow().execute(prepared, run, Cancelled())
    assert calls == ["build", "test", "package"]


def test_repeated_jobs_are_rejected_even_with_one_worker():
    with pytest.raises(ValueError, match="only be chosen once per workflow"):
        WorkflowSpec(
            jobs={"build": {}, "app:build": {}}, max_workers=1
        ).validate_job_targets("app")


def test_repeated_jobs_remain_invalid_when_ordered():
    with pytest.raises(ValueError, match="only be chosen once per workflow"):
        WorkflowSpec(
            jobs={"app:build": {}, "build": {"needs": "app:build"}}
        ).validate_job_targets("app")


def test_local_and_qualified_owner_job_are_one_identity():
    from ptk.domain.config.model import PtkConfig

    common = {
        "repository": {"alias": "app", "config_path": "config"},
        "project": {"name": "app"},
    }
    with pytest.raises(ValidationError, match="only be chosen once per workflow"):
        PtkConfig.model_validate(
            {
                **common,
                "workflows": {"verify": {"jobs": {"build": {}, "app:build": {}}}},
            }
        )
    config = PtkConfig.model_validate(
        {
            **common,
            "workflows": {
                "verify": {"jobs": {"build": {}, "other:build": {}}},
                "another": {"jobs": {"build": {}}},
            },
        }
    )
    assert len(config.workflows["verify"].jobs) == 2


@pytest.mark.parametrize(
    "jobs,message",
    [
        ({"build": {"needs": "missing"}}, "unknown invocation 'missing'"),
        ({"build": {"needs": "build"}}, "cannot need itself"),
        (
            {"a": {"needs": ["b", "b"]}, "b": {}},
            "must not repeat",
        ),
        (
            {
                "a": {"needs": "c"},
                "b": {"needs": "a"},
                "c": {"needs": "b"},
            },
            "a -> b -> c -> a",
        ),
    ],
)
def test_invalid_graphs_are_rejected_when_loading(jobs, message):
    with pytest.raises(ValidationError, match=message):
        WorkflowSpec(jobs=jobs)


@pytest.mark.parametrize(
    "value",
    [
        {"steps": {"build": {"run": "build"}}},
        {"parallel": True, "jobs": {"build": {}}},
        {"jobs": {"build": {"repo": "app"}}},
        {"jobs": {"group": {"steps": {"build": {"run": "build"}}}}},
        {"jobs": {"build": "build"}},
        {"jobs": {}},
        {"jobs": {"build": {"job": "build"}}},
        {"jobs": {"repo:other:build": {}}},
        {"jobs": {"build": {"needs": None}}},
    ],
)
def test_invalid_and_removed_workflow_shapes_are_rejected(value):
    with pytest.raises(ValidationError):
        WorkflowSpec.model_validate(value)


def test_required_output_failure_blocks_workflow_consumer_even_if_tolerated():
    prepared = plan(
        {
            "produce": {"continue_on_error": True},
            "consume": {"needs": "produce"},
        }
    )
    calls = []

    def run(node, cancel):
        calls.append(node.id)
        return CallOutcome(Status.FAILED, output_contract_failure=True)

    result = RunWorkflow().execute(prepared, run, Cancelled())
    assert calls == ["produce"]
    assert result.status == Status.FAILED
    assert not result.jobs[0].allowed_failure
    assert result.jobs[1].status == Status.SKIPPED


def test_disabled_job_skips_and_blocks_only_its_branch():
    prepared = plan(
        {
            "produce": {},
            "consume": {"needs": "produce"},
            "other": {},
        }
    )
    prepared.jobs[0].prepared.plan.skip_reason = "job condition is false: cx"
    calls = []

    def run(node, cancel):
        calls.append(node.id)
        return CallOutcome(Status.PASSED)

    result = RunWorkflow().execute(prepared, run, Cancelled())
    assert calls == ["other"]
    assert [job.status for job in result.jobs] == [
        Status.SKIPPED,
        Status.SKIPPED,
        Status.PASSED,
    ]
