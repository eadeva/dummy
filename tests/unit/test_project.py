import pytest

from ptk.domain.errors import ConfigError
from tests.conftest import MINIMAL


def test_layers_ci_local_and_overrides(write, load):
    root = write(
        {
            ".main.ptk.yml": MINIMAL + "vars: {where: main, a: 1}\n",
            "cx.ptk.yml": "vars: {where: ci}",
            "local.ptk.yml": "vars: {where: local, b: 2}",
        }
    )
    project = load(root)
    assert project.config.vars == {"where": "local", "a": 1, "b": 2}
    assert project.layers == [".main.ptk.yml", "local.ptk.yml"]
    ci = load(
        root,
        environ={"GITHUB_ACTIONS": "true"},
        overrides=["vars.where=cli", "vars.n=5"],
    )
    assert ci.ci and ci.config.vars["where"] == "cli" and ci.config.vars["n"] == 5
    assert ci.layers[:3] == [".main.ptk.yml", "cx.ptk.yml", "local.ptk.yml"]


def test_found_from_subdirectory(write, load):
    root = write({".main.ptk.yml": MINIMAL, "src/deep/x.txt": ""})
    assert load(root / "src" / "deep").root == root


def test_unknown_keys_with_suggestions_and_lines(write, load):
    root = write(
        {
            ".main.ptk.yml": """
        project: {name: demo}
        actions:
          build:
            stpes: []
    """
        }
    )
    with pytest.raises(ConfigError) as exc:
        load(root)
    text = str(exc.value)
    assert (
        ".main.ptk.yml:4: actions.build.stpes: unknown key 'stpes' (did you mean 'steps'?)"
        in text
    )


def test_semantic_errors(write, load):
    root = write(
        {
            ".main.ptk.yml": """
        project: {name: demo, default_action: biuld}
        vars: {x: "${vars.y}"}
        actions:
          build:
            requires_tools: [cmak]
            params: {jobs: {type: int, default: 2}}
            steps:
              - compile: {run: "make -j${params.job}", when: "params.jobs > 1 and FOO"}
              - leak: {run: "curl -H ${secret:repo.token}"}
    """
        }
    )
    with pytest.raises(ConfigError) as exc:
        load(root)
    text = str(exc.value)
    for expected in [
        "unknown action 'biuld' (did you mean 'build'?)",
        "unknown variable 'vars.y'",
        "unknown tool 'cmak'",
        "unknown parameter 'params.job' (did you mean 'jobs'?)",
        "unknown name 'FOO' in condition",
        "never on command lines",
    ]:
        assert expected in text, expected
    assert "actions.build.steps.compile.when" in text


def test_version_check(write, load):
    root = write({".main.ptk.yml": "ptk_version: '>=99'\n" + MINIMAL})
    with pytest.raises(ConfigError, match="needs ptk >=99"):
        load(root)
    root2 = write({".main.ptk.yml": "ptk_version: 'not a range'\n" + MINIMAL})
    with pytest.raises(ConfigError, match="invalid version range"):
        load(root2)


def test_maintainers_file(write, load):
    root = write(
        {
            ".main.ptk.yml": MINIMAL,
            "maintainers.ptk.yml": "maintainers: [{email: a@b.c}]",
        }
    )
    assert load(root).maintainers.maintainers[0].email == "a@b.c"
    write({"maintainers.ptk.yml": "maintainers: [{name: nobody}]"})
    with pytest.raises(ConfigError, match="needs 'email' and/or 'user'"):
        load(root)


def test_demo_project_is_valid(load):
    from tests.conftest import DEMO

    project = load(DEMO)
    assert set(project.config.actions) == {"build", "deploy"}
    assert project.config.actions["deploy"].audience == "maintainer"
    assert project.maintainers is not None
