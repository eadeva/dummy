"""Project-owned Bazel adapter for PTK's variant.bazel.json data contract.

Copy this resource into the consuming repository. PTK neither loads nor
executes it. See the variant-generation guide for MODULE.bazel and CLI setup.
"""

_SETTINGS = '''"""Typed, non-command-line settings supplied by the resolved PTK variant."""
def _value_impl(ctx):
    return []

bool_value = rule(implementation = _value_impl, build_setting = config.bool())
int_value = rule(implementation = _value_impl, build_setting = config.int())
string_value = rule(implementation = _value_impl, build_setting = config.string())
'''

def _ptk_variants_impl(ctx):
    source = ctx.os.environ.get("PTK_VARIANT_FILE")
    if not source:
        fail("Pass --repo_env=PTK_VARIANT_FILE=/absolute/path/to/variant.bazel.json")
    # read() tracks the input so regenerating a selected snapshot invalidates
    # the repository even when its path stays unchanged.
    document = json.decode(ctx.read(ctx.path(source)))
    if type(document) != "dict" or document.get("schema_version") != 1:
        fail("Expected PTK Bazel variant schema_version 1")
    values = document.get("values")
    if type(values) != "dict" or type(values.get("VARIANT_NAME")) != "string":
        fail("Expected a values dictionary with VARIANT_NAME")
    declarations = [
        'load(":settings.bzl", "bool_value", "int_value", "string_value")',
        'package(default_visibility = ["//visibility:public"])',
        'exports_files(["variant.bzl"])',
    ]
    for name, value in values.items():
        if not name.startswith("VARIANT_") or not name or any([c not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_" for c in name.elems()]):
            fail("Invalid PTK variant symbol: " + name)
        if value == None:
            # Inactive non-boolean features have no typed setting; components
            # should gate their targets with VARIANT_COMPONENT_<COMPONENT>.
            continue
        kind = type(value)
        if kind not in ["bool", "int", "string"]:
            fail("Unsupported PTK variant value for " + name + ": " + kind)
        declarations.append("%s_value(name = %s, build_setting_default = %s)" % (kind, repr(name), repr(value)))
    ctx.file("BUILD.bazel", "\n".join(declarations) + "\n")
    ctx.file("settings.bzl", _SETTINGS)
    ctx.file("variant.bzl", "# Resolved PTK configuration.\nVARIANT = " + repr(values) + "\n")

ptk_variants = repository_rule(
    implementation = _ptk_variants_impl,
    environ = ["PTK_VARIANT_FILE"],
    local = True,
)
