---
name: ptk-variant-model
description: Add or change ptk components, features, inherited variants, aliases or
  step conditions.
---

# ptk-variant-model

1. Read [docs/configuration.rst](../../../docs/configuration.rst) and inspect the variant models in `ptk maintainer config schema`.

2. Register component directories in `project.ptk.yml`. Put features, dependencies and local constraints in `component.variants.ptk.yml` beside the component code. Put the project default and global constraints in `project.variants.ptk.yml`, and each variant body in `variants/<name>.ptk.yml`.

3. Keep features UPPER_SNAKE_CASE; use component names for component declarations and generated COMPONENT_* names in conditions.

3. Use enum features for finite choices. Declare min/max for bounded integer features.

4. Use abstract parents and `extends` for shared values; inspect merged `data` for toolchain defaults.

5. Update conditions and substitutions when renaming a feature or variant.

6. Run `ptk variant list`, `ptk validate --variants --strict`, and `ptk variant show NAME`.

7. Explain surprising values with `ptk variant explain NAME FEATURE` before changing dependency rules.

8. Dry-run every concrete affected variant; verify both executed and skipped steps.

9. Edit the source variant YAML directly; the CLI is read-only (`list`, `show`, `explain`, `check`). Validate before running. Select a variant globally with `ptk -V NAME JOB` or `ptk -V a,b JOB`; use `ptk JOB --all-variants` for every concrete variant. Place `-V` before the repository alias in VMR mode.

10. Use `variant.generate` for bundled formats or enabled generator plugins. See [docs/plugins.rst](../../../docs/plugins.rst) for names, outputs and format restrictions.

Temporary feature overrides on jobs do not change files. Workflows retain their
per-job variant selections; global `-V` does not override them. Maintainers alone
can force `--ci`/`--no-ci`; all users retain automatic CI detection. See
[configuration](../../../docs/configuration.rst).
