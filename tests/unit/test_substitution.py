import pytest

from ptk.domain.config.substitution import (
    Scope,
    SubstitutionError,
    references,
    substitute,
)


def make_scope(**kw):
    return Scope(
        env={"HOME": "/home/u"},
        vars={
            "root": "${project.root}/out",
            "dir": "${vars.root}/${vh.variant}",
            "loop": "${vars.loop}",
        },
        namespaces={
            "project": {"root": "/p"},
            "vh": {"variant": "b_us", "features": {"core": {"N": 8}}},
            "params": {"jobs": 4, "fast": True},
        },
        **kw,
    )


def test_typed_single_reference_and_text_interpolation():
    s = make_scope()
    assert s("${params.jobs}") == 4
    assert s("-j${params.jobs}") == "-j4"
    assert s("--fast=${params.fast}") == "--fast=true"
    assert s(["${vh.features.core.N}", "x"]) == [8, "x"]


def test_vars_resolve_recursively_and_detect_cycles():
    s = make_scope()
    assert s("${vars.dir}") == "/p/out/b_us"
    with pytest.raises(SubstitutionError, match="circular"):
        s("${vars.loop}")


def test_env_defaults_and_errors():
    s = make_scope()
    assert s("${env:HOME}") == "/home/u"
    assert s("${env:MISSING:-fallback}") == "fallback"
    with pytest.raises(SubstitutionError, match="not set"):
        s("${env:MISSING}")


def test_unknown_names_have_suggestions():
    s = make_scope()
    with pytest.raises(SubstitutionError, match="did you mean 'jobs'"):
        s("${params.job}")
    with pytest.raises(SubstitutionError, match="unknown namespace 'parms'"):
        s("${parms.jobs}")


def test_escape_and_references():
    assert substitute("$${not.a.ref} ${a}", lambda r: "X") == "${not.a.ref} X"
    assert references("a ${vars.x} $${y} ${env:Z}") == ["vars.x", "env:Z"]


def test_secret_resolver():
    s = make_scope(secret=lambda ref: f"<{ref}>")
    assert s("${secret:artifactory.token}") == "<artifactory.token>"
