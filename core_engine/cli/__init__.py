"""CLI subpackage for xc-ce-utils.

This package houses focused helpers that were previously tangled inside
the former ``core_engine/dynamic_cli.py`` monolith (now fully folded into
this subpackage; see ``generator.py`` and ``entrypoint.py``). Each module
owns a small, well-defined slice (help rendering, option parsing,
command/group creation, variant execution) so the CLI generator stays a
thin entry point.

This subpackage is a *driving adapter*: it may only depend on
``xc_ce_utils.core_engine.application`` (the public application-layer API)
and ``xc_ce_utils.core_engine.domain`` (shared vocabulary), never on
``xc_ce_utils.core_engine.adapters`` or ``application`` submodules directly.
See ``tests/unit/test_architecture_boundaries.py`` for the enforced rule.
"""
