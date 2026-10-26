---
name: ptk-variant-model
description: Add or change ptk components, features, inherited variants, aliases or
  step conditions.
---

# ptk-variant-model

1. Read [docs/configuration.rst](../../../docs/configuration.rst) and inspect the variant models in `ptk setup config schema`.

2. Keep features UPPER_SNAKE_CASE; use component names for component declarations and generated COMPONENT_* names in conditions.

3. Use enum features for finite choices. Declare min/max for bounded integer features.

4. Use abstract parents and `extends` for shared values; inspect merged `data` for toolchain defaults.

5. Update conditions and substitutions when renaming a feature or variant.

6. Run `ptk variant list`, `ptk variant check --strict`, and `ptk variant show NAME`.

7. Explain surprising values with `ptk variant explain NAME FEATURE` before changing dependency rules.

8. Dry-run every concrete affected variant; verify both executed and skipped steps.

9. Use `ptk variant set/new --dry-run` before updating local overlays; `variant gui` exports a validated standalone copy. Run matrices with `--all-variants` or `-V a,b`.

10. Use `variant.generate` for bundled formats or enabled generator plugins. See [docs/plugins.rst](../../../docs/plugins.rst) for names, outputs and format restrictions.

Persistent `variant new`, `variant set` and `variant gui` commands require a listed
maintainer, including preview flags. Normal developers use `-V NAME` or temporary
feature overrides on jobs. Maintain login IDs as strings in `maintainers.ptk.yml`;
see [configuration](../../../docs/configuration.rst).
