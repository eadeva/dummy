---
name: ptk-variant-model
description: Add or change ptk components, features, inherited variants, aliases or
  step conditions.
---

# ptk-variant-model

1. Read `src/ptk/domain/variants/model.py` and `rules.py`.

2. Keep features UPPER_SNAKE_CASE; use component names for component declarations and generated COMPONENT_* names in conditions.

3. Use enum features for finite choices. Declare min/max for bounded integer features.

4. Use abstract parents and `extends` for shared values; inspect merged `data` for toolchain defaults.

5. Update conditions and substitutions when renaming a feature or variant.

6. Run `ptk variant list`, `ptk variant check --strict`, and `ptk variant show NAME`.

7. Explain surprising values with `ptk variant explain NAME FEATURE` before changing dependency rules.

8. Dry-run every concrete affected variant; verify both executed and skipped steps.

9. Edit configuration files directly: variant set/new/gui and external generators are not implemented yet.
