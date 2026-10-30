---
name: ptk-development
description: Modify ptk core code, adapters, use cases or extension interfaces.
---

# ptk-development

Use this skill only in PTK's own source checkout. Confirm the checkout, project instructions and declared dependency groups first; do not impose PTK's development layout or test commands on consuming projects. For project-specific configuration, use [configuration authoring](../ptk-config-authoring/SKILL.md).

1. Read `docs/guides/development.rst`, `docs/architecture/index.rst`, the relevant requirements and tests before changing code. Treat `reference/development-plan.md` as historical context, not a current specification.

2. Keep dependencies inward: drivers -> application -> domain; adapters implement ports; wire concrete implementations in bootstrap.

3. Keep domain logic pure. Use fakes for use cases and real temporary processes/files for adapter tests.

4. Distinguish implemented behavior from roadmap promises; inspect registered built-ins and commands before documenting them.

5. Fix the smallest coherent problem and cover the observable failure rather than duplicating implementation in tests.

6. Run `uv run pytest`, `uv run ruff check`, `uv run ruff format --check` and the Sphinx warning-as-error build.

7. Exercise Windows-specific paths in Windows CX; do not claim cross-platform success from Linux alone.

8. Update docs, examples and relevant authoring skills with behavior changes. Keep secrets and generated workspace outputs out of git.

9. Review CX results before marking a milestone complete; record explicit remaining limitations in PLAN.md.

10. Keep PTK Python interfaces internal. Use `docs/reference/builtins.rst` for built-in operations and [reusable Python tools](../../../docs/guides/python-tools.rst) for external commands. Do not introduce plugin discovery or callback registration.

11. For startup changes, profile before editing and run `scripts/benchmark_cli.py`
    before/after sequentially in the same Python environment. Preserve all command
    visibility and live configuration semantics. Bound repeated work with tests;
    do not add timing thresholds on shared CX runners. See `docs/guides/performance.rst`.
