---
name: ptk-variant-model
description: Add or change ptk components, features, inherited variants, aliases or
  step conditions.
---

# ptk-variant-model

First follow the [project discovery and execution guide](../../../docs/guides/agent-guide.rst). Apply it even when this skill is invoked directly; examples are syntax references, not project defaults.

1. Read [configuration](../../../docs/guides/configuration.rst) and the installed variant schema. Discover existing components/features/defaults and aliases; a project without variants is valid. Add a variant model only when needed by the request.

2. Register component directories in `project.ptk.yml`. Put features, dependencies and local constraints in `component.variants.ptk.yml` beside the component code. Put the project default and global constraints in `project.variants.ptk.yml`, and each variant body in `variants/<name>.ptk.yml`.

3. Keep features UPPER_SNAKE_CASE; use component names for component declarations and generated COMPONENT_* names in conditions.

4. Use enum features for finite choices. Declare min/max for bounded integer features.

5. Use abstract parents and `extends` for shared values; inspect merged `data` for toolchain defaults.

6. Update conditions and substitutions when renaming a feature or variant.

7. Run `ptk variant list`, `ptk validate --variants --strict`, and `ptk variant show NAME`.

8. Explain surprising values with `ptk variant explain NAME FEATURE` before changing dependency rules.

9. Select the smallest set of affected concrete variants covering changed branches; inspect both included and skipped steps. Do not invent a debug/release split or select abstract parents.

10. Edit the owning variant document; inspection commands are `list`, `show` and `explain`. Use `ptk validate --variants` for validation. Validate before running. Select a variant globally with `ptk -V NAME JOB` or `ptk -V a,b JOB`; use `ptk JOB --all-variants` for every concrete variant. Place `-V` before the repository alias in VMR mode.

11. Use `variant.generate` for bundled formats or enabled generator plugins. See [docs/reference/plugins.rst](../../../docs/reference/plugins.rst) for names, outputs and format restrictions.

Temporary feature overrides on jobs do not change files. Workflows retain their
per-job variant selections; global `-V` does not override them. Maintainers alone
can force `--ci`/`--no-ci`; all users retain automatic CX detection. See
[configuration](../../../docs/guides/configuration.rst).
