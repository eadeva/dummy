"""Pure execution domain: parameters, planning, environment, commands."""

from __future__ import annotations

import pytest

from ptk.domain.config.model import ActionSpec, ParamSpec
from ptk.domain.config.substitution import Scope
from ptk.domain.execution import environment as envs
from ptk.domain.execution.commands import PythonRuntime, build_command
from ptk.domain.execution.params import ParamError, resolve_params
from ptk.domain.execution.planning import PlanContext, PlanError, plan_action


def action(steps: list) -> ActionSpec:
    return ActionSpec.model_validate({"steps": steps})


def ctx(**kwargs) -> PlanContext:
    symbols = kwargs.pop("symbols", {})
    params = kwargs.pop("params", {})
    return PlanContext(
        symbols=symbols,
        scope_for=lambda path: Scope(
            namespaces={"params": params, "run": {"step": "/".join(path)}}
        ),
        **kwargs,
    )


# --------------------------------------------------------------------------- params


def test_param_precedence_and_sources():
    specs = {
        "jobs": ParamSpec(type="int", default=8, env="JOBS"),
        "mode": ParamSpec(default="fast"),
    }
    values, sources = resolve_params(
        specs, cli={"jobs": "2"}, file_values={"mode": "slow"}, environ={"JOBS": "4"}
    )
    assert values == {"jobs": 2, "mode": "slow"}
    assert sources == {"jobs": "command line", "mode": "params file"}
    values, sources = resolve_params(specs, environ={"JOBS": "4"})
    assert (
        values["jobs"] == 4
        and sources["jobs"] == "env:JOBS"
        and sources["mode"] == "default"
    )


def test_param_errors():
    specs = {
        "jobs": ParamSpec(type="int", default=8),
        "token": ParamSpec(required=True),
    }
    with pytest.raises(ParamError, match="did you mean 'jobs'"):
        resolve_params(specs, cli={"jbos": "1", "token": "x"})
    with pytest.raises(ParamError, match="'token' is required"):
        resolve_params(specs)
    with pytest.raises(ParamError, match="parameter 'jobs'"):
        resolve_params(specs, cli={"jobs": "many", "token": "x"})


# --------------------------------------------------------------------------- planning

STEPS = [
    {"prepare": "echo prepare"},
    {"build": ["make", "-j", "${params.jobs}"]},
    {
        "checks": {
            "parallel": True,
            "steps": [
                {"lint": {"run": "lint", "when": "LINT"}},
                {"test": {"run": ["pytest"], "passthrough": True}},
            ],
        }
    },
    {"package": "zip"},
]


def test_plan_substitutes_and_evaluates_conditions():
    steps = plan_action(
        action(STEPS).steps, ctx(symbols={"LINT": False}, params={"jobs": 4})
    )
    build = steps[1]
    assert build.run == ["make", "-j", "4"]
    lint, test = steps[2].children
    assert lint.skip_reason == "condition is false: LINT"
    assert test.skip_reason is None and test.label == "checks/test"


def test_from_to_range():
    steps = plan_action(
        action(STEPS).steps, ctx(params={"jobs": 1}), start="build", end="checks"
    )
    assert [s.skip_reason is None for s in steps] == [False, True, True, False]
    assert steps[2].children[1].skip_reason is None
    with pytest.raises(PlanError, match="did you mean 'build'"):
        plan_action(action(STEPS).steps, ctx(), start="biuld")
    with pytest.raises(PlanError, match="comes after"):
        plan_action(
            action(STEPS).steps, ctx(params={"jobs": 1}), start="package", end="build"
        )


def test_skipped_set_skips_children():
    steps = plan_action(action(STEPS).steps, ctx(params={"jobs": 1}), end="build")
    assert all(child.skip_reason for child in steps[2].children)


def test_passthrough():
    steps = plan_action(
        action(STEPS).steps, ctx(params={"jobs": 1}, passthrough=["-k", "a b"])
    )
    assert steps[2].children[1].run == ["pytest", "-k", "a b"]
    with pytest.raises(PlanError, match="no selected step"):
        plan_action(
            action(STEPS).steps, ctx(params={"jobs": 1}, passthrough=["x"]), end="build"
        )


def test_passthrough_ambiguous_needs_args_for():
    steps = [
        {"a": {"run": "x", "passthrough": True}},
        {"b": {"run": "y", "passthrough": True}},
    ]
    with pytest.raises(PlanError, match="ambiguous"):
        plan_action(action(steps).steps, ctx(passthrough=["1"]))
    planned = plan_action(action(steps).steps, ctx(args_for={"b": ["--fast", "it's"]}))
    assert planned[1].run == "y --fast 'it'\"'\"'s'"
    with pytest.raises(PlanError, match="does not accept"):
        plan_action(action([{"a": "x"}]).steps, ctx(args_for={"a": ["1"]}))


def test_unknown_reference_is_reported_with_step():
    with pytest.raises(PlanError, match="step 'build'.*did you mean"):
        plan_action(
            action([{"build": "make ${params.jbos}"}]).steps, ctx(params={"jobs": 1})
        )


# --------------------------------------------------------------------------- environment


def test_base_environment_isolation_and_path():
    host = {"PATH": "/usr/bin", "HOME": "/h", "SECRET_THING": "x", "KEEPME": "1"}
    env = envs.base_environment(
        host,
        os_name="linux",
        isolate=True,
        keep=["KEEPME"],
        set_={"A": "1"},
        unset=[],
        path_prepend=["/opt/bin"],
        path_append=["/usr/bin"],
    )
    assert env == {"PATH": "/opt/bin:/usr/bin", "HOME": "/h", "KEEPME": "1", "A": "1"}


def test_windows_path_is_case_insensitive():
    env = envs.base_environment(
        {"Path": r"C:\Windows", "Temp": "t"},
        os_name="windows",
        isolate=False,
        keep=[],
        set_={},
        unset=["TEMP"],
        path_prepend=[r"C:\tools"],
        path_append=[],
    )
    assert env == {"Path": r"C:\tools;C:\Windows"}


# --------------------------------------------------------------------------- commands


def one(run, **spec):
    return plan_action(action([{"s": {"run": run, **spec}}]).steps, ctx())[0]


def test_list_runs_directly_and_string_through_shell():
    cmd = build_command(
        one(["make", "all"]), env={}, cwd="/p", os_name="linux", python=None
    )
    assert cmd.argv == ["make", "all"] and cmd.shell is None
    cmd = build_command(
        one("make all && echo ok"), env={}, cwd="/p", os_name="linux", python=None
    )
    assert cmd.shell == "make all && echo ok"


@pytest.mark.parametrize(
    ("run", "expected"),
    [
        ("tools/x.sh --fast", ["bash", "tools/x.sh", "--fast"]),
        ("tools\\x.bat a", ["cmd", "/c", "tools\\x.bat", "a"]),
        (
            ["x.ps1", "-V"],
            [
                "pwsh",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                "x.ps1",
                "-V",
            ],
        ),
        ("gen.py --out 'a b'", ["uv", "run", "--no-project", "gen.py", "--out", "a b"]),
    ],
)
def test_script_detection(run, expected):
    cmd = build_command(
        one(run),
        env={},
        cwd=".",
        os_name="windows" if "\\" in str(run) else "linux",
        python=None,
    )
    assert cmd.argv == expected


def test_python_runtime_for_scripts_and_commands():
    runtime = PythonRuntime(
        "venv",
        script_prefix=["/v/bin/python"],
        path_prepend="/v/bin",
        env={"VIRTUAL_ENV": "/v"},
    )
    cmd = build_command(
        one("tool.py -x"),
        env={"PATH": "/usr/bin"},
        cwd=".",
        os_name="linux",
        python=runtime,
    )
    assert cmd.argv == ["/v/bin/python", "tool.py", "-x"]
    assert cmd.env == {"PATH": "/v/bin:/usr/bin", "VIRTUAL_ENV": "/v"}
    cmd = build_command(
        one("pytest -q"), env={}, cwd=".", os_name="linux", python=runtime
    )
    assert cmd.argv == ["pytest", "-q"]  # found through PATH of the venv
    uvx = PythonRuntime(
        "uvx",
        script_prefix=["uv", "run"],
        command_prefix=["uv", "tool", "run", "--from", "ruff"],
    )
    cmd = build_command(
        one(["ruff", "check"]), env={}, cwd=".", os_name="linux", python=uvx
    )
    assert cmd.argv == ["uv", "tool", "run", "--from", "ruff", "ruff", "check"]
