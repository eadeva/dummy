---
name: ptk-plugin-development
description: Build, register, test or troubleshoot PTK step, reporter, contributor, installer, secret-provider or generator plugins using explicit installed-distribution selection.
---

# PTK plugin development

First follow the [project discovery and execution guide](../../../docs/guides/agent-guide.rst). Apply it even when this skill is invoked directly; examples are syntax references, not project defaults.

1. Read [plugin authoring contracts](references/contracts.md) for callable contracts and provider interfaces; use [plugin configuration](../../../docs/reference/plugins.rst) for YAML selection. Choose the smallest entry-point group that matches the task.
2. Start from [examples/plugin/pyproject.toml](../../../examples/plugin/pyproject.toml) and [examples/plugin/ptk_example/__init__.py](../../../examples/plugin/ptk_example/__init__.py). Keep the distribution name separate from entry-point names. In a disposable example environment, install [examples/plugin](../../../examples/plugin) into the Python environment containing PTK, select `plugins: [ptk-example-extension]`, and use `uses: example.check`.
3. Treat plugins as trusted code. Import only explicitly selected distributions; reject duplicate and reserved entry-point names. Do not add automatic package installation during discovery.
4. Send messages through the supplied `out` callback, never print secrets. Poll `ctx.cancel.is_set()` during work; Python handlers cannot be forcibly killed. Make retries repeatable and report actionable failures with `PtkError`.
5. For generators, return relative filename-to-text mappings. For installers, provide an explicit discoverable binary location; built-in versioned download/Python caches do not automatically isolate arbitrary plugin installers.
6. Test an installed distribution's entry points, not only a direct function call. Create an integration test using the bundled plugin example as a starting point. Verify unselected plugins are not imported, cancellation is honored, collisions fail, and a real job reaches the handler.
7. For an external plugin, document and test its own supported PTK versions and public contract. Update PTK contract documentation only when working on PTK itself; run the owning project's relevant checks.
