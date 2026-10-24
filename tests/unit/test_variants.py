import pytest
from pydantic import ValidationError

from ptk.domain.errors import UnknownNameError
from ptk.domain.variants import conventions
from ptk.domain.variants import rules as vr
from ptk.domain.variants.model import FeatureSpec, ProductLineSpec

LINE = {
    "default": "high",
    "components": {
        "core": {"features": {"LOG": {"type": "enum", "values": ["WARN", "DEBUG"]}}},
        "display": {
            "requires_components": ["core"],
            "features": {
                "SIZE": {"type": "int", "min": 5, "max": 15, "default": 8},
                "BIG_UI": {"type": "bool", "depends_on": "SIZE >= 10"},
            },
        },
        "camera": {
            "requires_components": ["display"],
            "features": {"NIGHT": {"type": "bool"}},
        },
    },
    "constraints": [
        {
            "expr": "not (COMPONENT_CAMERA and SIZE < 7)",
            "message": "camera needs >= 7 inch",
        }
    ],
    "variants": {
        "base": {
            "abstract": True,
            "components": ["core", "display"],
            "data": {"conan": {"profile": "x", "opts": {"a": 1}}},
        },
        "high": {
            "extends": "base",
            "aliases": ["1", "h"],
            "components": ["core", "display", "camera"],
            "features": {"SIZE": 12, "BIG_UI": True, "NIGHT": True},
            "data": {"conan": {"opts": {"b": 2}}},
        },
        "low": {"extends": "base", "aliases": [2], "features": {"BIG_UI": True}},
    },
}


@pytest.fixture
def line():
    return ProductLineSpec.model_validate(LINE)


def test_aliases_default_and_data_merge(line):
    assert vr.find(line, "1") == "high" and vr.find(line, "2") == "low"
    assert vr.default_variant(line) == "high"
    r = vr.resolve(line, vr.find(line, "h"))
    assert r.ok, r.issues
    assert r.aliases == ["1", "h"]
    assert r.data == {"conan": {"profile": "x", "opts": {"a": 1, "b": 2}}}
    with pytest.raises(UnknownNameError, match="did you mean 'high'"):
        vr.find(line, "hihg")


def test_depends_on_conflict_is_reported(line):
    r = vr.resolve(line, "low")
    assert not r.ok
    assert any("dependency 'SIZE >= 10'" in i.message for i in r.errors)
    assert r.features["NIGHT"].source == "inactive"


def test_validate_reports_alias_clash_and_unknown_symbols():
    data = {
        **LINE,
        "variants": {**LINE["variants"], "other": {"aliases": ["1"]}},
        "constraints": ["SIZ > 3"],
    }
    problems = dict(vr.validate(ProductLineSpec.model_validate(data)))
    assert any("already used by variant 'high'" in m for m in problems.values())
    assert any("did you mean 'SIZE'" in m for m in problems.values())


def test_explain_and_conventions(line):
    text = "\n".join(vr.explain(line, "low", "BIG_UI"))
    assert "NOT satisfied" in text and "low: True" in text
    r = vr.resolve(line, "high")
    env = conventions.environment(line, r)
    assert (
        env["VH_VARIANT"] == "high"
        and env["VH_SIZE"] == "12"
        and env["VH_COMPONENT_CAMERA"] == "1"
    )
    assert "BO_SIZE" not in env
    on, off = conventions.tags(line, r)
    assert (
        "feature_log_warn" in on
        and "feature_log_debug" in off
        and "component_camera" in on
    )
    assert conventions.namespace(r)["features"]["SIZE"] == 12


def test_feature_spec_validation():
    assert FeatureSpec(type="enum", values=["A", "B"]).default == "A"
    assert FeatureSpec(type="int").parse_text("0x10") == 16
    with pytest.raises(ValidationError):
        FeatureSpec(type="int", min=5, default=1)
    with pytest.raises(ValidationError):
        ProductLineSpec.model_validate({"components": {"Bad": {}}})
