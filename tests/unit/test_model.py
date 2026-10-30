import pytest
from pydantic import ValidationError

from ptk.domain.config.model import (
    JobSpec,
    ParamSpec,
    PtkConfig,
    PythonSpec,
    StepSpec,
)
from ptk.domain.workflows import WorkflowSpec


@pytest.mark.parametrize(
    "fields",
    [
        {"actions": {}},
        {"project": {"name": "demo", "default_action": "build"}},
    ],
)
def test_old_job_configuration_names_are_not_accepted(fields):
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        PtkConfig.model_validate({"project": {"name": "demo"}, **fields})


def test_workflow_requires_job_and_schema_uses_job_names():
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        WorkflowSpec.model_validate({"jobs": {"check": {"action": "build"}}})
    schema = PtkConfig.model_json_schema()
    assert "jobs" in schema["properties"] and "actions" not in schema["properties"]
    assert "JobSpec" in schema["$defs"] and "ActionSpec" not in schema["$defs"]


def test_step_short_forms():
    assert StepSpec.model_validate({"compile": "make"}).run == "make"
    assert StepSpec.model_validate({"compile": ["make", "-j4"]}).run == ["make", "-j4"]
    step = StepSpec.model_validate(
        {"checks": {"parallel": True, "steps": [{"a": "x"}, {"b": "y"}]}}
    )
    assert step.kind == "set" and [s.name for s in step.steps] == ["a", "b"]
    assert [s.name for s in step.walk()] == ["checks", "a", "b"]


@pytest.mark.parametrize(
    "raw, message",
    [
        ({"x": {"run": "a", "uses": "b"}}, "exactly one of"),
        ({"x": {"run": "a", "parallel": True}}, "only allowed for step sets"),
        (
            {"x": {"uses": "a", "python": {"uvx": "ruff"}}},
            "only allowed together with run",
        ),
        ({"x": {"run": "a", "with": {"k": 1}}}, "only allowed together with uses"),
        ({"x": {"steps": [{"a": "1"}, {"a": "2"}]}}, "duplicate step name"),
        ({"bad name": "x"}, "step name"),
    ],
)
def test_step_rules(raw, message):
    with pytest.raises(ValidationError, match=message):
        StepSpec.model_validate(raw)


def test_python_spec_exactly_one():
    assert PythonSpec.model_validate(
        {"uvx": "ruff==0.6", "with": "ruff-lsp"}
    ).with_ == ["ruff-lsp"]
    with pytest.raises(ValidationError, match="exactly one"):
        PythonSpec.model_validate({"uvx": "a", "project": "b"})
    with pytest.raises(ValidationError, match="'with' is only allowed"):
        PythonSpec.model_validate({"venv": {"packages": ["a"]}, "with": ["b"]})


def test_params_convert_and_validate():
    assert ParamSpec(type="int", default="4").default == 4
    assert ParamSpec(type="bool").convert("yes") is True
    assert ParamSpec(type="list").convert("a, b") == ["a", "b"]
    with pytest.raises(ValidationError, match="choices"):
        ParamSpec(type="choice")
    with pytest.raises(ValueError, match="one of"):
        ParamSpec(type="choice", choices=["a"]).convert("b")
    with pytest.raises(ValidationError, match="reserved"):
        JobSpec.model_validate({"params": {"from": {}}, "steps": [{"a": "x"}]})


def test_reserved_job_names_and_defaults():
    with pytest.raises(ValidationError, match="reserved"):
        PtkConfig.model_validate(
            {"project": {"name": "x"}, "jobs": {"config": {"steps": [{"a": "b"}]}}}
        )
    cfg = PtkConfig.model_validate({"project": {"name": "x"}})
    assert (
        cfg.layout.builds == "_builds"
        and cfg.logging_history_backups == 3
        and cfg.report_formats == ["html"]
    )
