import pytest
from pydantic import ValidationError

from ptk.domain.config.model import (
    ActionSpec,
    ParamSpec,
    PtkConfig,
    PythonSpec,
    StepSpec,
)


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
        ActionSpec.model_validate({"params": {"from": {}}, "steps": [{"a": "x"}]})


def test_reserved_action_names_and_defaults():
    with pytest.raises(ValidationError, match="reserved"):
        PtkConfig.model_validate(
            {"project": {"name": "x"}, "actions": {"config": {"steps": [{"a": "b"}]}}}
        )
    cfg = PtkConfig.model_validate({"project": {"name": "x"}})
    assert cfg.layout.builds == "_builds" and cfg.logging.level == "info"
