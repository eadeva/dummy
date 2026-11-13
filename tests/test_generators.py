import json
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from ptk.domain.variants.generators import GENERATORS
from ptk.domain.variants.model import ProductLineSpec
from ptk.domain.variants.rules import resolve
from ptk.drivers.cli.main import cli
from tests.cli_runner import CliRunner
from tests.project_files import write_project


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


def test_nine_generators_and_language_values(tmp_path):
    resolved = variant()
    results = {k: fn(resolved) for k, fn in GENERATORS.items()}
    assert len(results) == 9
    for files in results.values():
        for filename, content in files.items():
            (tmp_path / filename).write_text(content)
    assert "#define VARIANT_CORE_ENABLED 1" in (tmp_path / "variant.h").read_text()
    bazel = json.loads((tmp_path / "variant.bazel.json").read_text())
    assert bazel["schema_version"] == 1 and bazel["values"]["VARIANT_CORE_SIZE"] == 4
    assert "VARIANT_COMPONENT_CORE := 1" in (tmp_path / "variant.mk").read_text()
    assert "VARIANT_CORE_TEXT = hello world" in (tmp_path / "variant.ninja").read_text()
    assert 'VARIANT_CORE_SIZE = "4"' in (tmp_path / "variant.inc").read_text()
    assert "${VARIANT_CORE_ENABLED}\t1" in (tmp_path / "variant.robot").read_text()
    assert "VARIANT_CORE_ENABLED = true" in (tmp_path / "variant.gni").read_text()
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
        + '\nif(NOT VARIANT_CORE_SIZE EQUAL 4 OR NOT VARIANT_CORE_TEXT STREQUAL "hello world")\nmessage(FATAL_ERROR "wrong values")\nendif()\n'
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


def definitions_line():
    return ProductLineSpec.model_validate(
        {
            "components": {
                "can": {"definitions": {"CAN_FD": True}},
                "eth": {"build_options": {"MACSEC": "STD_OFF"}},
            },
            "variants": {
                "base": {"abstract": True, "definitions": {"LEVEL": 1}},
                "cgw_cs": {
                    "extends": "base",
                    "components": ["can"],
                    "build_options": {"__TASKING__": 0},
                    "definitions": {"LEVEL": 2, "MARKER": None},
                },
                "cgw-plus": {"extends": "base"},
            },
        }
    )


def test_definitions_resolve_build_options_and_variant_names():
    resolved = resolve(definitions_line(), "cgw_cs")
    assert resolved.definitions == {
        "BO_CGW_CS": True,
        "BO_CGW_PLUS": False,
        "CAN_FD": True,
        "LEVEL": 2,
        "BO___TASKING__": 0,
        "MARKER": None,
    }
    plus = resolve(definitions_line(), "cgw-plus").definitions
    assert plus["BO_CGW_PLUS"] is True and plus["BO_MACSEC"] == "STD_OFF"
    assert plus["CAN_FD"] is True and plus["LEVEL"] == 1


def test_definitions_are_exported_to_build_formats():
    resolved = resolve(definitions_line(), "cgw_cs")
    cmake = GENERATORS["cmake"](resolved)["variant.cmake"]
    assert "add_compile_definitions([[BO_CGW_CS=1]])" in cmake
    assert "add_compile_definitions([[BO_CGW_PLUS=0]])" in cmake
    assert "add_compile_definitions([[MARKER]])" in cmake
    assert "set(BO___TASKING__ [[0]])" in cmake
    header = GENERATORS["header"](resolved)["variant.h"]
    assert "#ifndef LEVEL\n#define LEVEL 2\n#endif" in header
    assert "#define MARKER\n" in header
    flags = (
        "-DBO_CGW_CS=1 -DBO_CGW_PLUS=0 -DCAN_FD=1 -DLEVEL=2 -DBO___TASKING__=0 -DMARKER"
    )
    assert f"VARIANT_CPPFLAGS := {flags}" in GENERATORS["make"](resolved)["variant.mk"]
    ninja = GENERATORS["ninja"](resolved)["variant.ninja"]
    assert f"VARIANT_CPPFLAGS = {flags}" in ninja
    assert "VARIANT_DEFINES = BO_CGW_CS=1 BO_CGW_PLUS=0" in ninja
    assert (
        f'VARIANT_CPPFLAGS = "{flags}"' in GENERATORS["yocto"](resolved)["variant.inc"]
    )
    assert (
        'VARIANT_DEFINES = ["BO_CGW_CS=1", "BO_CGW_PLUS=0"'
        in (GENERATORS["gn"](resolved)["variant.gni"])
    )
    bazel = json.loads(GENERATORS["bazel"](resolved)["variant.bazel.json"])
    assert bazel["schema_version"] == 1 and bazel["definitions"][-1] == "MARKER"


def test_flat_definition_formats_reject_whitespace():
    from ptk.domain.errors import PtkError

    resolved = resolve(definitions_line(), "cgw_cs")
    resolved.definitions["TEXT"] = "a b"
    for name in ("make", "ninja", "yocto"):
        with pytest.raises(PtkError, match="whitespace"):
            GENERATORS[name](resolved)
    assert "[[TEXT=a b]]" in GENERATORS["cmake"](resolved)["variant.cmake"]


def test_cmake_project_receives_compile_definitions(tmp_path):
    cmake, ninja = shutil.which("cmake"), shutil.which("ninja")
    if not ninja:
        pytest.skip("Ninja not installed")
    (tmp_path / "variant.cmake").write_text(
        GENERATORS["cmake"](resolve(definitions_line(), "cgw_cs"))["variant.cmake"]
    )
    (tmp_path / "CMakeLists.txt").write_text(
        "cmake_minimum_required(VERSION 3.16)\nproject(demo NONE)\n"
        "include(variant.cmake)\nget_directory_property(defs COMPILE_DEFINITIONS)\n"
        'if(NOT "BO_CGW_CS=1;BO_CGW_PLUS=0" IN_LIST defs AND NOT defs MATCHES "BO_CGW_CS=1;BO_CGW_PLUS=0")\n'
        'message(FATAL_ERROR "missing definitions: ${defs}")\nendif()\n'
    )
    result = subprocess.run(
        [
            cmake,
            "-G",
            "Ninja",
            f"-DCMAKE_MAKE_PROGRAM={ninja}",
            "-S",
            str(tmp_path),
            "-B",
            str(tmp_path / "out"),
        ],
        check=False,
        capture_output=True,
        text=True,
        errors="replace",
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize(
    "spec",
    [
        {"definitions": {"1BAD": 1}},
        {"build_options": {"A-B": 1}},
        {"definitions": {"X": "a\nb"}},
    ],
)
def test_definitions_reject_invalid_names_and_values(spec):
    with pytest.raises(ValueError):
        ProductLineSpec.model_validate({"variants": {"v": spec}})


def test_variant_build_option_collisions_are_rejected():
    from ptk.domain.variants.rules import validate

    line = ProductLineSpec.model_validate({"variants": {"a-b": {}, "a_b": {}}})
    assert any("collides" in message for _, message in validate(line))


def test_builtin_generation_copy_clean(tmp_path):
    config = tmp_path / ".main.ptk.yml"
    write_project(
        config,
        yaml.safe_dump(
            {
                "repository": {"alias": "demo", "config_path": "."},
                "project": {"name": "builtins"},
                "configs": {"ruff": {}},
                "variants": {"variants": {"demo": {}}},
                "jobs": {
                    "go": {
                        "steps": {
                            "ensure": {
                                "uses": "tools.ensure",
                                "with": {"tools": []},
                            },
                            "gen": {
                                "generators": list(GENERATORS),
                                "needs": ["ensure"],
                            },
                            "copy": {
                                "uses": "files.copy",
                                "with": {
                                    "files": "_builds/demo/go/gen/variant.h",
                                    "to": "_bin/demo",
                                },
                                "needs": ["gen"],
                            },
                            "clean": {
                                "uses": "files.clean",
                                "with": {"paths": ["_builds/demo/go/gen"]},
                                "needs": ["copy"],
                            },
                        }
                    }
                },
            }
        ),
    )
    result = CliRunner().invoke(cli, ["-V", "demo", "go"], cwd=Path(config).parent)
    assert result.exit_code == 0, result.output
    assert (tmp_path / "_bin/demo/variant.h").exists()
    assert not (tmp_path / "_builds/demo/go/gen").exists()
    assert not (tmp_path / "ruff-base.toml").exists()


def test_file_cleanup_and_generation_reject_path_escape(tmp_path):
    from types import SimpleNamespace

    from ptk.adapters.builtins import file_cleaner
    from ptk.adapters.variant_files import variant_writer
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
    generate = variant_writer({"escape": lambda _: {"../../.main.ptk.yml": "bad"}})
    with pytest.raises(PtkError, match="must be inside"):
        generate(["escape"], variant(), ctx.build_dir, lambda _: None, None)
    assert protected.read_text() == "keep"
