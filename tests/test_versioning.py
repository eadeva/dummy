"""Version discovery, run consistency and portable build generator contracts."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from ptk.adapters.versioning import VersionIO, generate, write_generated
from ptk.application.use_cases.run import RunRequest
from ptk.bootstrap import create_app
from ptk.domain.errors import PtkError
from ptk.domain.versioning import VersionSource
from ptk.drivers.cli.main import cli
from tests.project_files import project_files, read_project, write_project


def project(write, config):
    return write(project_files(yaml.safe_dump({"project": {"name": "demo"}, **config})))


def test_run_snapshot_env_and_generators_are_consistent(write, load):
    root = project(
        write,
        {
            "versioning": {
                "project": {"source": "file", "path": "VERSION"},
                "components": {
                    "core": {},
                    "sdk": {"source": "literal", "version": "7.2.1"},
                },
            },
            "jobs": {
                "build": {
                    "steps": [
                        {
                            "change": {
                                "run": [
                                    sys.executable,
                                    "-c",
                                    "from pathlib import Path; Path('VERSION').write_text('9.0.0')",
                                ]
                            }
                        },
                        {
                            "capture": {
                                "run": [
                                    sys.executable,
                                    "-c",
                                    "import os,json; from pathlib import Path; Path('env.json').write_text(json.dumps({k:v for k,v in os.environ.items() if k.startswith('PTK_VERSION_')}))",
                                ]
                            }
                        },
                        {
                            "header": {
                                "uses": "version.generate",
                                "with": {
                                    "format": "header",
                                    "output": "generated/version.h",
                                },
                            }
                        },
                        {
                            "cmake": {
                                "uses": "version.generate",
                                "with": {
                                    "format": "cmake",
                                    "output": "generated/version.cmake",
                                },
                            }
                        },
                        {
                            "echo": {
                                "uses": "echo",
                                "with": {
                                    "message": "${version.projects.demo.components.core.value}"
                                },
                            }
                        },
                    ]
                }
            },
        },
    )
    (root / "VERSION").write_text("1.2.3")
    app = create_app()
    p = load(root)
    prepared = app.prepare_run(p).execute(p, RunRequest(job="build"))
    assert not Path(prepared.version_file).exists()
    result = app.run_job(prepared.project).execute(prepared)
    assert str(result.status) == "passed"
    env = json.loads((root / "env.json").read_text())
    assert env["PTK_VERSION_DEMO"] == "1.2.3"
    assert env["PTK_VERSION_DEMO_COMPONENT_CORE"] == "1.2.3"
    assert env["PTK_VERSION_DEMO_COMPONENT_SDK"] == "7.2.1"
    snapshot = yaml.safe_load(Path(env["PTK_VERSION_FILE"]).read_text())
    assert snapshot["projects"]["demo"]["components"]["core"]["inherited"]
    header = root / "generated/version.h"
    assert '#define PTK_VERSION_DEMO "1.2.3"' in header.read_text()
    assert (
        "set(PTK_VERSION_DEMO [[1.2.3]])"
        in (root / "generated/version.cmake").read_text()
    )
    before = header.stat().st_mtime_ns
    _, content = generate(snapshot, "header")
    assert not write_generated(header, content)
    assert header.stat().st_mtime_ns == before
    next_run = app.prepare_run(p).execute(p, RunRequest(job="build"))
    assert next_run.versions["projects"]["demo"]["value"] == "9.0.0"
    assert next_run.version_file != prepared.version_file


def test_dry_run_discovers_without_writing(write, load):
    root = project(
        write,
        {
            "versioning": {"project": {"source": "literal", "version": "2.0.0"}},
            "jobs": {"go": {"steps": [{"echo": {"uses": "echo"}}]}},
        },
    )
    result = CliRunner().invoke(
        cli, ["-C", str(root / ".main.ptk.yml"), "dry-run", "go"]
    )
    assert result.exit_code == 0, result.output
    assert not list(root.rglob(".gen.version.ptk.yml"))


def test_git_variant_lines_and_dirty_policy(write, load):
    root = project(
        write,
        {
            "variants": {"default": "a", "variants": {"a": {}, "b": {}}},
            "versioning": {
                "project": {"source": "git", "strip_prefix": "v"},
                "variants": {
                    "a": {
                        "project": {
                            "source": "git",
                            "match": "v1.*",
                            "strip_prefix": "v",
                        }
                    },
                    "b": {
                        "project": {
                            "source": "git",
                            "match": "v2.*",
                            "strip_prefix": "v",
                        }
                    },
                },
                "components": {"core": {}},
            },
        },
    )

    def git(*args):
        return subprocess.check_output(["git", *args], cwd=root, text=True).strip()

    git("init", "-q")
    git("config", "user.name", "PTK Test")
    git("config", "user.email", "test@example.invalid")
    git("add", ".")
    git("commit", "-qm", "initial")
    git("tag", "v1.2.3")
    git("tag", "v2.4.0")
    app = create_app()
    p = load(root)
    assert app.versions().resolve(p, "a")["projects"]["demo"]["value"] == "1.2.3"
    assert (
        app.versions().resolve(p, "b")["projects"]["demo"]["components"]["core"][
            "value"
        ]
        == "2.4.0"
    )
    (root / "tracked").write_text("new")
    git("add", "tracked")
    git("commit", "-qm", "next")
    item = app.versions().resolve(p, "a")["projects"]["demo"]
    assert item["value"].startswith("1.2.3+1.g")
    assert item["git"]["distance"] == 1
    (root / "tracked").write_text("dirty")
    assert (
        app.versions().resolve(p, "a")["projects"]["demo"]["value"].endswith(".dirty")
    )
    io = VersionIO(app.runner, app.host)
    with pytest.raises(PtkError, match="dirty"):
        io.discover(VersionSource(source="git", dirty="error"), root)
    with pytest.raises(PtkError, match="discovery command failed"):
        io.discover(VersionSource(source="git", match="absent-*"), root)
    # Local file:// clone exercises the real shallow-checkout guard.
    clone = root.parent / (root.name + "-shallow")
    subprocess.run(
        ["git", "clone", "-q", "--depth=1", root.as_uri(), str(clone)], check=True
    )
    with pytest.raises(PtkError, match="shallow"):
        io.discover(VersionSource(source="git"), clone)


def test_file_env_command_and_fallback_sources(tmp_path):
    app = create_app(environ={**os.environ, "RELEASE_VERSION": "2026.10"})
    io = VersionIO(app.runner, app.host)
    (tmp_path / "pyproject.toml").write_text('[project]\nversion = "1.4.0"\n')
    item = io.discover(
        VersionSource(
            source="file", path="pyproject.toml", format="toml", key="project.version"
        ),
        tmp_path,
    )
    assert item["minor"] == 4
    assert "major" not in io.discover(
        VersionSource(source="env", variable="RELEASE_VERSION"), tmp_path
    )
    assert (
        io.discover(
            VersionSource(
                source="command",
                command=[sys.executable, "-c", "print('v3.2.1')"],
                strip_prefix="v",
            ),
            tmp_path,
        )["value"]
        == "3.2.1"
    )
    fallback = VersionSource(
        source="env",
        variable="MISSING",
        fallback=VersionSource(source="literal", version="0.0.0"),
    )
    assert io.discover(fallback, tmp_path)["fallback_used"]
    (tmp_path / "version.h").write_text('#define MY_VERSION "4.5.6"')
    assert (
        io.discover(
            VersionSource(
                source="file",
                path="version.h",
                regex=r'MY_VERSION "(?P<version>[^"]+)"',
            ),
            tmp_path,
        )["value"]
        == "4.5.6"
    )


def test_normalized_names_and_suffix_collisions_fail(write, load):
    root = project(
        write,
        {
            "versioning": {
                "project": {"source": "literal", "version": "1.0.0"},
                "components": {"core": {}, "core-major": {}},
            }
        },
    )
    with pytest.raises(PtkError, match="collision"):
        create_app().versions().resolve(load(root))


def test_vmr_explicit_dependencies_and_cycle(tmp_path):
    (tmp_path / ".repo").mkdir()
    (tmp_path / ".repo/project.list").write_text("engine\nfrontend\n")
    for name in ("engine", "frontend"):
        root = tmp_path / name
        root.mkdir()
        target = tmp_path / ".repo/projects" / f"{name}.git"
        target.mkdir(parents=True)
        (root / ".git").write_text(f"gitdir: ../.repo/projects/{name}.git\n")
        config = {
            "repository": {"alias": name, "config_path": "."},
            "project": {"name": name},
            "versioning": {"project": {"source": "literal", "version": "1.0.0"}},
        }
        if name == "engine":
            config["versioning"]["dependencies"] = {"frontend": {"variant": "release"}}
        else:
            config["variants"] = {"default": "release", "variants": {"release": {}}}
        write_project(root / ".main.ptk.yml", yaml.safe_dump(config))
    app = create_app()
    p = app.load_project.execute(config_file=tmp_path / "engine/.main.ptk.yml")
    snapshot = app.versions().resolve(p)
    assert set(snapshot["projects"]) == {"engine", "frontend"}
    assert snapshot["projects"]["frontend"]["variant"] == "release"
    path = tmp_path / "frontend/.main.ptk.yml"
    config = read_project(path)
    config["versioning"]["dependencies"] = {"engine": {}}
    write_project(path, yaml.safe_dump(config))
    with pytest.raises(PtkError, match="cycle"):
        app.versions().resolve(p)


@pytest.mark.parametrize("format", ["header", "cmake", "msbuild", "json", "python"])
def test_generator_escaping(format):
    from ptk.domain.versioning import resolved

    value = 'custom"$x;\\path]]<&'
    snapshot = {
        "projects": {
            "demo": {**resolved(value, raw=value, source="literal"), "components": {}}
        }
    }
    name, text = generate(snapshot, format)
    assert name.startswith("version.")
    if format == "python":
        ns = {}
        exec(text, ns)  # noqa: S102 - validate our generated Python output
        assert ns["PTK_VERSION_DEMO"] == value
    elif format == "json":
        assert json.loads(text)["PTK_VERSION_DEMO"] == value
    elif format == "msbuild":
        import xml.etree.ElementTree as ET

        assert "%24" in ET.fromstring(text).find("PropertyGroup/PTK_VERSION_DEMO").text
    elif format == "cmake":
        assert "[=[" in text
    else:
        assert '\\"' in text


def test_cli_and_generated_input_exclusion(write):
    root = project(
        write,
        {
            "versioning": {"project": {"source": "literal", "version": "1.0.0"}},
        },
    )
    runner = CliRunner()
    base = ["-C", str(root / ".main.ptk.yml")]
    for cmd in ("show", "check"):
        result = runner.invoke(cli, [*base, "version", cmd])
        assert result.exit_code == 0, result.output
    path = root / ".gen.version.ptk.yml"
    assert (
        runner.invoke(
            cli, [*base, "version", "generate", "--output", str(path)]
        ).exit_code
        == 0
    )
    assert runner.invoke(cli, [*base, "setup", "config", "validate"]).exit_code == 0
    assert runner.invoke(cli, [*base, "version", "bump", "patch"]).exit_code != 0


def test_semver_and_custom_strings_are_distinguished():
    from ptk.domain.versioning import resolved

    for value in ("2026.10", "1.2.3-dev..x", "1.2.3-01"):
        assert "major" not in resolved(value, raw=value, source="literal")
    result = resolved("1.2.3-rc.1+build.2", raw="tag", source="git")
    assert result["prerelease"] == "rc.1"
    assert result["build_metadata"] == "build.2"
