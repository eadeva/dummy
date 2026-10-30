import pytest
import yaml

from ptk.application.use_cases.tools import tools_for_jobs
from ptk.domain.config.model import PtkConfig
from ptk.domain.errors import ConfigError
from tests.project_files import project_files

MAIN = """\
project:
  name: shared
jobs:
  build:
    params:
      jobs:
        type: int
      own:
        type: int
        default: 2
    steps:
      echo:
        uses: echo
  test:
    requires_tools: []
    params:
      jobs:
        type: int
        default: 3
    steps:
      echo:
        uses: echo
"""


def configured(write, *, build=None, **settings):
    model = yaml.safe_load(MAIN)
    model.update(settings)
    model["jobs"]["build"].update(build or {})
    return write(project_files(yaml.safe_dump(model)))


def test_per_tool_override_disable_and_preserve_unmentioned(write, load):
    root = configured(
        write,
        tools={
            "cmake": {"version": ">=3", "check": "cmake --version", "choco": "cmake"},
            "git": {"check": "git --version"},
            "ninja": {"check": "ninja --version"},
        },
        requires_tools=["cmake", "git"],
        param_defaults={"jobs": 8, "own": 99, "undeclared": 20},
        build={
            "requires_tools": {"cmake": {"version": ">=4"}, "git": False, "ninja": True}
        },
    )
    p = load(root)
    assert p.config.jobs["build"].required_tool_names == ["cmake", "ninja"]
    assert p.config.jobs["test"].required_tool_names == ["cmake", "git"]
    scoped = tools_for_jobs(p, ["build"])
    assert scoped.config.tools["cmake"].version == ">=4"
    assert scoped.config.tools["cmake"].choco == "cmake"
    assert p.config.tools["cmake"].version == ">=3"
    assert p.config.jobs["build"].params["jobs"].default == 8
    assert p.config.jobs["build"].params["own"].default == 2
    assert p.config.jobs["test"].params["jobs"].default == 3
    assert "undeclared" not in p.config.jobs["build"].params
    assert (
        p.location(("jobs", "build", "params", "jobs", "default")).file
        == "project.ptk.yml"
    )
    assert len(p.layers) == len(set(p.layers)) == 5


def test_explicit_requirement_override_merges_with_shared_defaults(write, load):
    root = configured(
        write,
        tools={"a": {}, "b": {}, "c": {}},
        requires_tools=["a"],
        build={"requires_tools": ["b"]},
        param_defaults={"jobs": 16},
    )
    assert load(root).config.jobs["build"].required_tool_names == ["a", "b"]
    p = load(
        root,
        overrides=[
            "jobs.build.requires_tools.c=true",
            "jobs.build.requires_tools.a=false",
        ],
    )
    assert p.config.jobs["build"].required_tool_names == ["b", "c"]
    assert p.config.jobs["build"].params["jobs"].default == 16


def test_each_conventional_document_is_loaded_once(write, load):
    p = load(configured(write, vars={"items": ["one"]}, param_defaults={"jobs": 4}))
    assert p.config.vars["items"] == ["one"]
    assert len(p.files) == len(set(p.files)) == 4


def test_global_default_validated_for_each_parameter(write, load):
    with pytest.raises(ConfigError, match="project.ptk.yml"):
        load(configured(write, param_defaults={"jobs": "wrong"}))


def test_required_and_explicit_null_do_not_inherit_defaults():
    p = PtkConfig.model_validate(
        {
            "project": {"name": "test"},
            "param_defaults": {"a": 4, "b": 8},
            "jobs": {
                "go": {
                    "params": {
                        "a": {"type": "int", "required": True},
                        "b": {"type": "int", "default": None},
                    },
                    "steps": {"echo": {"uses": "echo"}},
                }
            },
        }
    )
    assert p.jobs["go"].params["a"].default is None
    assert p.jobs["go"].params["b"].default is None


def test_global_tools_without_jobs_and_true_preserves_settings():
    p = PtkConfig.model_validate(
        {"project": {"name": "test"}, "tools": {"git": {}}, "requires_tools": ["git"]}
    )
    assert p.requires_tools == {"git": True}
    p = PtkConfig.model_validate(
        {
            "project": {"name": "test"},
            "requires_tools": {"git": {"version": ">=2"}},
            "tools": {"git": {}},
            "jobs": {
                "go": {"requires_tools": ["git"], "steps": {"x": {"uses": "echo"}}}
            },
        }
    )
    assert p.jobs["go"].requires_tools["git"].version == ">=2"


def test_tool_checks_and_install_selection_use_job_settings(write, load):
    from ptk.application.ports import ProcessOutcome
    from ptk.bootstrap import create_app

    class Runner:
        def run(self, command, out, cancel=None):
            out("3.29.0")
            return ProcessOutcome(0)

        def which(self, name, path=None):
            return name

    root = configured(
        write,
        tools={"cmake": {"version": ">=3", "uv_tool": "cmake"}, "git": {}},
        requires_tools=["cmake", "git"],
        build={"requires_tools": {"cmake": {"version": ">=4"}, "git": False}},
    )
    p = load(root)
    app = create_app(environ={}, runner=Runner())
    assert app.tools.required(p, ["build"]) == ["cmake"]
    assert app.tools.required(p, ["test"]) == ["cmake", "git"]
    assert app.tools.problems(p, "build")[0].required == ">=4"
    assert app.tools.problems(p, "test") == []
    scoped = tools_for_jobs(p, ["build"])
    results = app.tools.setup(scoped, ["cmake"], dry_run=True)
    assert results[0].outcome.startswith("would install")
    with pytest.raises(Exception, match="different settings"):
        tools_for_jobs(p, ["build", "test"])
