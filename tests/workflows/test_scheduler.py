"""Nested workflow concurrency and cooperative action cancellation."""

import threading
import time
from pathlib import Path
from types import SimpleNamespace

from ptk.application.use_cases.run import Cancelled
from ptk.application.use_cases.workflow import CallOutcome, PrepareWorkflow, RunWorkflow
from ptk.domain.execution.model import Status
from ptk.domain.workflows import WorkflowSpec


def prepare(node, path):
    return "app", SimpleNamespace(
        project=SimpleNamespace(root=Path(".")),
        plan=SimpleNamespace(variant=None, action=node.action, walk=list),
    )


def test_global_concurrency_limit_applies_across_nested_groups():
    spec = WorkflowSpec(
        parallel=True,
        max_workers=2,
        steps=[
            {"left": {"parallel": True, "steps": [{"a": "a"}, {"b": "b"}]}},
            {"right": {"parallel": True, "steps": [{"c": "c"}, {"d": "d"}]}},
        ],
    )
    plan = PrepareWorkflow().execute("checks", spec, prepare)
    lock, active, maximum, done = threading.Lock(), 0, 0, []

    def run(node, cancel):
        nonlocal active, maximum
        with lock:
            active += 1
            maximum = max(maximum, active)
        time.sleep(0.03)
        with lock:
            active -= 1
            done.append(node.spec.action)
        return CallOutcome(Status.PASSED)

    result = RunWorkflow().execute(plan, run, Cancelled())
    assert result.status == Status.PASSED
    assert maximum <= 2
    assert sorted(done) == ["a", "b", "c", "d"]


def test_cancel_reaches_active_action_and_prevents_queued_and_later_calls():
    spec = WorkflowSpec(
        max_workers=1,
        steps=[
            {"group": {"parallel": True, "steps": [{"a": "a"}, {"b": "b"}]}},
            {"later": "later"},
        ],
    )
    plan = PrepareWorkflow().execute("checks", spec, prepare)
    cancel, calls = Cancelled(), []

    def run(node, token):
        assert token is cancel
        calls.append(node.spec.action)
        token.set()
        return CallOutcome(Status.CANCELLED)

    result = RunWorkflow().execute(plan, run, cancel)
    assert result.status == Status.CANCELLED
    assert calls == ["a"]
    assert result.steps[1].status == Status.CANCELLED


def test_failed_parallel_sibling_finishes_and_group_continue_on_error():
    spec = WorkflowSpec(
        steps=[
            {
                "group": {
                    "parallel": True,
                    "continue_on_error": True,
                    "steps": [{"a": "a"}, {"b": "b"}],
                }
            },
            {"later": "later"},
        ]
    )
    plan = PrepareWorkflow().execute("checks", spec, prepare)
    calls = []

    def run(node, cancel):
        calls.append(node.spec.action)
        return CallOutcome(Status.FAILED if node.spec.action == "a" else Status.PASSED)

    result = RunWorkflow().execute(plan, run, Cancelled())
    assert result.status == Status.PASSED
    assert result.steps[0].allowed_failure
    assert set(calls[:2]) == {"a", "b"} and calls[2] == "later"
