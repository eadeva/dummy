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


def test_named_step_mapping_and_dependencies():
    job = JobSpec.model_validate(
        {
            "steps": {
                "compile": {"run": ["make", "-j4"]},
                "test": {"uses": "echo", "needs": "compile"},
            }
        }
    )
    assert job.steps["test"].needs == ["compile"]
    assert job.steps["compile"].kind == "run"


@pytest.mark.parametrize(
    "raw",
    [
        [{"compile": "make"}],
        {"compile": "make"},
        {"compile": ["make"]},
        {"compile": {"run": "make", "parallel": True}},
        {"compile": {"run": "make", "background": True}},
        {"compile": {"steps": {"nested": {"run": "make"}}}},
        {"compile": {"run": "make", "name": "old"}},
    ],
)
def test_only_current_step_format_is_accepted(raw):
    with pytest.raises(ValidationError):
        JobSpec.model_validate({"steps": raw})


@pytest.mark.parametrize(
    "raw, message",
    [
        ({"run": "a", "uses": "b"}, "exactly one of"),
        ({"uses": "a", "python": {"uvx": "ruff"}}, "only allowed together with run"),
        ({"run": "a", "with": {"k": 1}}, "only allowed together with uses"),
    ],
)
def test_step_rules(raw, message):
    with pytest.raises(ValidationError, match=message):
        StepSpec.model_validate(raw)


@pytest.mark.parametrize(
    "steps, message",
    [
        ({"bad name": {"run": "x"}}, "invalid step ID"),
        ({"a": {"run": "x", "needs": "missing"}}, "unknown"),
        ({"a": {"run": "x", "needs": "a"}}, "cannot need itself"),
        ({"a": {"run": "x"}, "b": {"run": "x", "needs": ["a", "a"]}}, "repeat"),
        ({"a": {"run": "x", "needs": "b"}, "b": {"run": "x", "needs": "a"}}, "cycle"),
    ],
)
def test_invalid_step_graph_is_rejected(steps, message):
    with pytest.raises(ValidationError, match=message):
        JobSpec.model_validate({"steps": steps})


@pytest.mark.parametrize("other", ["Compile", "compile."])
def test_step_ids_have_distinct_portable_output_folders(other):
    with pytest.raises(ValidationError, match="share an output folder"):
        JobSpec.model_validate(
            {"steps": {"compile": {"uses": "echo"}, other: {"uses": "echo"}}}
        )


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
        JobSpec.model_validate(
            {"params": {"only_step": {}}, "steps": {"a": {"run": "x"}}}
        )


def test_reserved_job_names_and_defaults():
    with pytest.raises(ValidationError, match="reserved"):
        PtkConfig.model_validate(
            {
                "project": {"name": "x"},
                "jobs": {"config": {"steps": {"a": {"run": "b"}}}},
            }
        )
    cfg = PtkConfig.model_validate({"project": {"name": "x"}})
    assert (
        cfg.layout.builds == "_builds"
        and cfg.logging_history_backups == 3
        and cfg.report_formats == ["html"]
    )
