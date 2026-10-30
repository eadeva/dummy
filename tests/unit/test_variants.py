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
                "BIG_UI": {"type": "bool", "depends_on": "display.SIZE >= 10"},
            },
        },
        "camera": {
            "requires_components": ["display"],
            "features": {"NIGHT": {"type": "bool"}},
        },
    },
    "constraints": [
        {
            "expr": "not (COMPONENT_CAMERA and display.SIZE < 7)",
            "message": "camera needs >= 7 inch",
        }
    ],
    "variants": {
        "base": {
            "abstract": True,
            "components": ["core", "display"],
            "data": {"toolchain": {"name": "x", "opts": {"a": 1}}},
        },
        "high": {
            "extends": "base",
            "aliases": ["1", "h"],
            "components": ["core", "display", "camera"],
            "features": {
                "display.SIZE": 12,
                "display.BIG_UI": True,
                "camera.NIGHT": True,
            },
            "data": {"toolchain": {"opts": {"b": 2}}},
        },
        "low": {
            "extends": "base",
            "aliases": [2],
            "features": {"display.BIG_UI": True},
        },
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
    assert r.data == {"toolchain": {"name": "x", "opts": {"a": 1, "b": 2}}}
    with pytest.raises(UnknownNameError, match="did you mean 'high'"):
        vr.find(line, "hihg")


def test_depends_on_conflict_is_reported(line):
    r = vr.resolve(line, "low")
    assert not r.ok
    assert any("dependency 'display.SIZE >= 10'" in i.message for i in r.errors)
    assert r.features["camera.NIGHT"].source == "inactive"


def test_validate_reports_alias_clash_and_unknown_symbols():
    data = {
        **LINE,
        "variants": {**LINE["variants"], "other": {"aliases": ["1"]}},
        "constraints": ["display.SIZ > 3"],
    }
    problems = dict(vr.validate(ProductLineSpec.model_validate(data)))
    assert any("already used by variant 'high'" in m for m in problems.values())
    assert any("did you mean 'display.SIZE'" in m for m in problems.values())


def test_explain_and_conventions(line):
    text = "\n".join(vr.explain(line, "low", "display.BIG_UI"))
    assert "NOT satisfied" in text and "low: True" in text
    r = vr.resolve(line, "high")
    env = conventions.environment(line, r)
    assert (
        env["VARIANT_NAME"] == "high"
        and env["VARIANT_DISPLAY_SIZE"] == "12"
        and env["VARIANT_COMPONENT_CAMERA"] == "1"
    )
    assert "BO_SIZE" not in env
    on, off = conventions.tags(line, r)
    assert (
        "feature_core_log_warn" in on
        and "feature_core_log_debug" in off
        and "component_camera" in on
    )
    assert conventions.namespace(r)["features"]["display"]["SIZE"] == 12


def test_feature_spec_validation():
    assert FeatureSpec(type="enum", values=["A", "B"]).default == "A"
    assert FeatureSpec(type="int").parse_text("0x10") == 16
    with pytest.raises(ValidationError):
        FeatureSpec(type="int", min=5, default=1)
    with pytest.raises(ValidationError):
        ProductLineSpec.model_validate({"components": {"Bad": {}}})


def test_repository_variant_mappings_inherit_and_override():
    line = ProductLineSpec.model_validate(
        {
            "variants": {
                "base": {
                    "abstract": True,
                    "repo_variants": {"a": "debug", "b": "test"},
                },
                "release": {"extends": ["base"], "repo_variants": {"a": "release"}},
            },
        }
    )
    result = vr.resolve(line, "release")
    assert result.repo_variants == {"a": "release", "b": "test"}
    assert result.model_dump()["repo_variants"] == result.repo_variants


def test_components_can_reuse_local_feature_names():
    line = ProductLineSpec.model_validate(
        {
            "components": {
                "core": {"features": {"LEVEL": {"type": "int", "default": 1}}},
                "network": {"features": {"LEVEL": {"type": "int", "default": 2}}},
            },
            "variants": {
                "base": {"abstract": True, "features": {"core.LEVEL": 3}},
                "product": {"extends": "base", "features": {"network.LEVEL": 4}},
            },
            "constraints": ["core.LEVEL < network.LEVEL"],
        }
    )
    assert vr.validate(line) == []
    result = vr.resolve(line, "product")
    assert result.ok and result.values == {"core.LEVEL": 3, "network.LEVEL": 4}
    assert conventions.environment(line, result)["VARIANT_NETWORK_LEVEL"] == "4"


def test_export_name_collisions_fail_validation():
    line = ProductLineSpec.model_validate(
        {
            "components": {
                "a": {"features": {"B_C": {}}},
                "a_b": {"features": {"C": {}}},
                "component": {"features": {"A": {}}},
            },
            "variants": {"product": {}},
        }
    )
    errors = vr.validate(line)
    assert len(errors) == 2 and all("collides" in message for _, message in errors)


def test_unqualified_features_and_old_export_configuration_are_rejected():
    with pytest.raises(ValidationError, match="component.FEATURE"):
        ProductLineSpec.model_validate({"variants": {"v": {"features": {"LEVEL": 1}}}})
    with pytest.raises(ValidationError, match="Extra inputs"):
        ProductLineSpec.model_validate({"env": {"prefix": "VH_"}})
    with pytest.raises(ValidationError, match="reserved expression namespace"):
        ProductLineSpec.model_validate({"components": {"params": {}}})
