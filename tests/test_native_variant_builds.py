"""Real consumers; GN/Bazel integration is opt-in via PTK_TEST_GN/PTK_TEST_BAZEL."""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from ptk.domain.variants.generators import GENERATORS
from tests.test_generators import variant


def execute(args, root, timeout=120):
    result = subprocess.run(
        args, check=False, cwd=root, capture_output=True, text=True, timeout=timeout
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout


def export(root, name, resolved):
    for filename, text in GENERATORS[name](resolved).items():
        (root / filename).write_text(text, encoding="utf-8")


def test_make_consumes_values_without_expanding_project_text(tmp_path):
    make = shutil.which("make")
    if not make:
        pytest.skip("GNU Make not installed")
    resolved = variant()
    resolved.features["core.TEXT"].value = 'cost$5#tag "quoted"'
    export(tmp_path, "make", resolved)
    (tmp_path / "Makefile").write_text(
        "include variant.mk\n$(file >observed.txt,$(VARIANT_CORE_TEXT))\nall:;\n"
    )
    execute([make, "--no-print-directory"], tmp_path)
    assert (tmp_path / "observed.txt").read_text().strip() == resolved.values[
        "core.TEXT"
    ]


def test_gn_imports_generated_values(tmp_path):
    gn = os.environ.get("PTK_TEST_GN")
    if not gn:
        pytest.skip("set PTK_TEST_GN to a GN executable")
    resolved = variant()
    resolved.features["core.TEXT"].value = 'cost$5#tag "quoted"\\path'
    export(tmp_path, "gn", resolved)
    (tmp_path / ".gn").write_text('buildconfig = "//BUILDCONFIG.gn"\n')
    (tmp_path / "BUILDCONFIG.gn").write_text('set_default_toolchain("//:tc")\n')
    (tmp_path / "BUILD.gn").write_text("""import("//variant.gni")
assert(VARIANT_CORE_ENABLED)
assert(VARIANT_CORE_SIZE == 4)
assert(VARIANT_CORE_TEXT == "cost\\$5#tag \\"quoted\\"\\\\path")
write_file("$root_build_dir/observed.txt", [VARIANT_CORE_TEXT])
toolchain("tc") {
  tool("stamp") {
    command = "touch {{output}}"
    description = "STAMP {{output}}"
  }
}
group("check") {}
""")
    execute([gn, "gen", "out"], tmp_path)
    assert (tmp_path / "out/observed.txt").read_text().strip() == resolved.values[
        "core.TEXT"
    ]
    assert (tmp_path / "out/build.ninja").is_file()


def test_bazel_helper_settings_constants_and_snapshot_invalidation(tmp_path):
    bazel = os.environ.get("PTK_TEST_BAZEL")
    if not bazel:
        pytest.skip("set PTK_TEST_BAZEL to a Bazel executable (Bzlmod)")
    helper = Path(__file__).parents[1] / "docs/resources/bazel/ptk_variants.bzl"
    shutil.copy(helper, tmp_path / helper.name)
    (tmp_path / "MODULE.bazel").write_text(
        'ptk_variants = use_repo_rule("//:ptk_variants.bzl", "ptk_variants")\nptk_variants(name = "ptk_variant")\n'
    )
    (tmp_path / "probe.bzl").write_text("""def _probe(ctx):
    output = ctx.actions.declare_file(ctx.label.name + ".txt")
    ctx.actions.write(output, ctx.attr.value)
    return [DefaultInfo(files = depset([output]))]
probe = rule(implementation = _probe, attrs = {"value": attr.string()})
""")
    (tmp_path / "BUILD.bazel").write_text("""load(":probe.bzl", "probe")
load("@ptk_variant//:variant.bzl", "VARIANT")
config_setting(name = "large", flag_values = {"@ptk_variant//:VARIANT_CORE_SIZE": "9", "@ptk_variant//:VARIANT_CORE_ENABLED": "true"})
config_setting(name = "text", flag_values = {"@ptk_variant//:VARIANT_CORE_TEXT": "updated"})
probe(name = "selection", value = select({":large": "large", "//conditions:default": "small"}))
probe(name = "string_selection", value = select({":text": "updated", "//conditions:default": "original"}))
probe(name = "constant", value = VARIANT["VARIANT_CORE_TEXT"])
""")
    startup = [bazel, "--batch"]
    trust = os.environ.get("PTK_TEST_BAZEL_TRUSTSTORE")
    if trust:
        startup.append("--host_jvm_args=-Djavax.net.ssl.trustStore=" + trust)
    cache = tmp_path / "cache"
    args = startup + [
        f"--output_base={cache}",
        "build",
        "--lockfile_mode=off",
        "--symlink_prefix=/",
        f"--repo_env=PTK_VARIANT_FILE={tmp_path / 'variant.bazel.json'}",
        "//:selection",
        "//:string_selection",
        "//:constant",
    ]
    resolved = variant()
    resolved.features["core.TEXT"].value = 'cost$5#tag "quoted"\\path'
    for size, text, expected in [
        (4, resolved.values["core.TEXT"], "small"),
        (9, "updated", "large"),
    ]:
        resolved.features["core.SIZE"].value = size
        resolved.features["core.TEXT"].value = text
        export(tmp_path, "bazel", resolved)
        execute(args, tmp_path, timeout=240)
        outputs = list(cache.glob("execroot/*/bazel-out/*/bin/constant.txt"))
        assert len(outputs) == 1
        output = outputs[0].parent
        assert (output / "constant.txt").read_text() == text
        assert (output / "selection.txt").read_text() == expected
        assert (output / "string_selection.txt").read_text() == (
            "updated" if size == 9 else "original"
        )
    # The helper rejects a future data contract before project actions can run.
    (tmp_path / "variant.bazel.json").write_text(json.dumps({"schema_version": 99}))
    failed = subprocess.run(
        args, check=False, cwd=tmp_path, capture_output=True, text=True, timeout=120
    )
    assert failed.returncode != 0 and "schema_version 1" in failed.stderr
