"""The bundled form contract must follow all models, not a sampled field list."""

import json

import pytest
from pydantic import BaseModel, Field, create_model
from scripts import generate_config_schema as generator

from ptk.application.use_cases import project
from ptk.domain.config.model import (
    CredentialSpec,
    PtkConfig,
    ReportingSpec,
    ToolbaseSource,
)


def test_form_only_adds_factory_defaults_to_authored_yaml_schema():
    base = project.ExportSchema().execute()
    form = generator.generate_schema()

    def without_added_defaults(actual, expected):
        if isinstance(expected, dict):
            assert actual.keys() - expected.keys() <= {"default"}
            return {
                key: without_added_defaults(actual[key], value)
                for key, value in expected.items()
            }
        if isinstance(expected, list):
            assert len(actual) == len(expected)
            return [
                without_added_defaults(a, b)
                for a, b in zip(actual, expected, strict=True)
            ]
        return actual

    assert without_added_defaults(form, base) == base
    definitions = form["$defs"]
    assert "name" not in definitions["StepBody"]["properties"]
    assert "name" not in definitions["WorkflowBody"]["properties"]
    assert "with" in definitions["StepBody"]["properties"]
    assert "with_" not in definitions["StepBody"]["properties"]
    assert form["required"] == []  # Includes can supply the project.
    assert "default" not in form["properties"]["virtual_monorepo"]
    for name, field, model in (
        ("ReportingSpec", "formats", ReportingSpec()),
        ("CredentialSpec", "providers", CredentialSpec()),
        ("ToolbaseSource", "bin", ToolbaseSource(package="demo", version="1")),
    ):
        assert definitions[name]["properties"][field]["default"] == getattr(
            model, field
        )


def test_new_nested_optional_fields_aliases_types_and_defaults_are_generated(
    monkeypatch,
):
    class FutureOptions(BaseModel):
        label: str | None = None
        enabled: bool = True
        count: int = 7
        ratio: float = 0.25
        values: list[str] = Field(default_factory=lambda: ["new"])
        with_: dict[str, int] = Field(
            default_factory=lambda: {"count": 2}, alias="with"
        )

    future = create_model(
        "FutureConfig", __base__=PtkConfig, future_options=(FutureOptions | None, None)
    )
    monkeypatch.setattr(project, "PtkConfig", future)
    schema = generator.generate_schema()
    assert "future_options" in schema["properties"]
    assert "future_options" not in schema["required"]
    assert schema["properties"]["future_options"]["anyOf"] == [
        {"$ref": "#/$defs/FutureOptions"},
        {"type": "null"},
    ]
    fields = schema["$defs"]["FutureOptions"]["properties"]
    assert fields["label"]["anyOf"] == [{"type": "string"}, {"type": "null"}]
    for field, kind, value in (
        ("enabled", "boolean", True),
        ("count", "integer", 7),
        ("ratio", "number", 0.25),
        ("values", "array", ["new"]),
        ("with", "object", {"count": 2}),
    ):
        assert fields[field]["type"] == kind
        assert fields[field]["default"] == value
    assert "with_" not in fields


@pytest.mark.parametrize("change", ["field", "type", "default", "definition"])
def test_check_detects_drift_without_rewriting(tmp_path, capsys, change):
    target = tmp_path / "schema.json"
    schema = generator.generate_schema()
    fields = schema["$defs"]["ParamSpec"]["properties"]
    if change == "field":
        del fields["env"]
    elif change == "type":
        fields["required"]["type"] = "string"
    elif change == "default":
        fields["required"]["default"] = True
    else:
        del schema["$defs"]["ReportingSpec"]
    target.write_text(json.dumps(schema), encoding="utf-8")
    before = target.read_bytes()
    assert generator.main(["--check", "--output", str(target)]) == 1
    assert target.read_bytes() == before
    error = capsys.readouterr().err
    assert generator.REGENERATE in error
    assert "--- " in error and "+++ generated from PTK models" in error


def test_generation_is_repeatable_and_check_ignores_json_formatting(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "schema.json"
    args = ["--output", str(target)]
    assert generator.main([*args, "--check"]) == 1
    assert not target.exists()
    assert generator.main(args) == 0
    before = target.read_bytes()
    assert b"\r\n" not in before
    assert generator.main(args) == 0
    assert target.read_bytes() == before
    target.write_text(json.dumps(json.loads(before), sort_keys=True, indent=4))
    assert generator.main([*args, "--check"]) == 0
    target.write_text("{invalid json}")
    assert generator.main([*args, "--check"]) == 1


def test_input_dependent_factory_cannot_silently_lose_its_default():
    class InputDependent(BaseModel):
        name: str
        derived: str = Field(default_factory=lambda data: data["name"])

    with pytest.raises(ValueError, match="validated input data"):
        InputDependent.model_json_schema(
            schema_generator=generator.EditorSchemaGenerator
        )
