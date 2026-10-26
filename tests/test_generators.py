import ast
import shutil
import subprocess

import pytest
import yaml
from click.testing import CliRunner

from ptk.domain.variants.generators import GENERATORS
from ptk.domain.variants.model import ProductLineSpec
from ptk.domain.variants.rules import resolve
from ptk.drivers.cli.main import cli


def variant():
    return resolve(
        ProductLineSpec.model_validate(
            {
                "components": {
                    "core": {
                        "features": {
                            "ENABLED": {"default": True},
                            "SIZE": {"type": "int", "default": 4},
                            "TEXT": {"type": "string", "default": "hello world"},
                        }
                    }
                },
                "variants": {"demo": {}},
            }
        ),
        "demo",
    )


def test_seven_generators_and_language_values(tmp_path):
    resolved = variant()
    results = {k: fn(resolved) for k, fn in GENERATORS.items()}
    assert len(results) == 7
    for files in results.values():
        for filename, content in files.items():
            (tmp_path / filename).write_text(content)
    assert "#define VH_ENABLED 1" in (tmp_path / "variant.h").read_text()
    bazel = (tmp_path / "variant.bzl").read_text().split("VARIANT = ", 1)[1]
    assert ast.literal_eval(bazel)["VH_SIZE"] == 4
    assert "VH_COMPONENT_CORE := 1" in (tmp_path / "variant.mk").read_text()
    assert 'VH_SIZE = "4"' in (tmp_path / "variant.inc").read_text()
    assert "${VH_ENABLED}\t1" in (tmp_path / "variant.robot").read_text()
    assert ".. code-block:: json" in (tmp_path / "variant.rst").read_text()


def test_cmake_consumes_generated_values(tmp_path):
    cmake = shutil.which("cmake")
    assert cmake is not None, (
        "CMake is a dev dependency; run uv sync, then uv run ptk test"
    )
    version = subprocess.run(
        [cmake, "--version"],
        check=False,
        capture_output=True,
        text=True,
        errors="replace",
        timeout=30,
    )
    assert version.returncode == 0, (
        f"CMake executable: {cmake}\n{version.stdout}{version.stderr}"
    )
    path = tmp_path / "variant.cmake"
    path.write_text(
        GENERATORS["cmake"](variant())["variant.cmake"]
        + '\nif(NOT VH_SIZE EQUAL 4 OR NOT VH_TEXT STREQUAL "hello world")\nmessage(FATAL_ERROR "wrong values")\nendif()\n'
    )
    result = subprocess.run(
        [cmake, "-P", str(path)],
        check=False,
        capture_output=True,
        text=True,
        errors="replace",
        timeout=30,
    )
    assert result.returncode == 0, (
        f"CMake executable: {cmake}\n{version.stdout}"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        f"\nGenerated script:\n{path.read_text()}"
    )


def test_builtin_generation_copy_clean_and_configs(tmp_path):
    config = tmp_path / ".main.ptk.yml"
    config.write_text(
        yaml.safe_dump(
            {
                "repository": {"alias": "demo", "config_path": "."},
                "project": {"name": "builtins"},
                "configs": {"ruff": {}},
                "variants": {"variants": {"demo": {}}},
                "jobs": {
                    "go": {
                        "steps": [
                            {"sync": {"uses": "configs.sync"}},
                            {"ensure": {"uses": "tools.ensure", "with": {"tools": []}}},
                            {
                                "gen": {
                                    "uses": "variant.generate",
                                    "with": {"generators": list(GENERATORS)},
                                }
                            },
                            {
                                "copy": {
                                    "uses": "files.copy",
                                    "with": {
                                        "files": "_builds/demo/go/gen/variant.h",
                                        "to": "_bin/demo",
                                    },
                                }
                            },
                            {
                                "clean": {
                                    "uses": "files.clean",
                                    "with": {"paths": ["_builds/demo/go/gen"]},
                                }
                            },
                        ]
                    }
                },
            }
        )
    )
    result = CliRunner().invoke(cli, ["-c", str(config), "go", "-V", "demo"])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "_bin/demo/variant.h").exists()
    assert not (tmp_path / "_builds/demo/go/gen").exists()
    assert (tmp_path / "ruff-base.toml").exists()


def test_file_cleanup_and_generation_reject_path_escape(tmp_path):
    from types import SimpleNamespace

    from ptk.adapters.builtins import file_cleaner, variant_generator
    from ptk.domain.errors import PtkError

    protected = tmp_path / ".main.ptk.yml"
    protected.write_text("keep")
    ctx = SimpleNamespace(
        root=tmp_path,
        cancel=None,
        variant=variant(),
        build_dir=tmp_path / "_builds/gen",
    )
    clean = file_cleaner([tmp_path / "_builds"])
    with pytest.raises(PtkError, match="only permits descendants"):
        clean(SimpleNamespace(with_={"paths": [".main.ptk.yml"]}), lambda _: None, ctx)
    generate = variant_generator({"escape": lambda _: {"../../.main.ptk.yml": "bad"}})
    with pytest.raises(PtkError, match="must be inside"):
        generate(SimpleNamespace(with_={"generators": ["escape"]}), lambda _: None, ctx)
    assert protected.read_text() == "keep"
