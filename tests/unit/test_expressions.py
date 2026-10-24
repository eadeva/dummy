import pytest

from ptk.domain import expressions as ex


def test_evaluate_flat_and_dotted_names():
    symbols = {
        "A": True,
        "N": 5,
        "M": "EU",
        "U": None,
        "params": {"dry_run": True, "jobs": 4},
        "os": "linux",
    }
    assert ex.evaluate("A and N >= 5 and M in ['EU', 'US']", symbols)
    assert ex.evaluate("params.dry_run and params.jobs == 4", symbols)
    assert not ex.evaluate("U", symbols)
    assert not ex.evaluate("U > 3", symbols)  # unset never satisfies an ordering
    assert not ex.evaluate("params.missing", symbols)
    assert ex.evaluate("os != 'windows'", symbols)


def test_names_returns_dotted_names():
    assert ex.names("A or params.jobs > 2 and vars.x == 'y'") == {
        "A",
        "params.jobs",
        "vars.x",
    }


def test_zero_and_empty_string_are_truthy():
    assert ex.evaluate("X", {"X": 0}) and ex.evaluate("X", {"X": ""})


@pytest.mark.parametrize(
    "bad", ["__import__('os')", "A + 1", "A[0]", "f(x)", "(lambda: 1)()", "'a'.upper"]
)
def test_rejects_code(bad):
    with pytest.raises(ex.ExpressionError):
        ex.parse(bad)
