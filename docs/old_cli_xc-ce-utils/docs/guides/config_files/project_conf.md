# `project_conf.yml` â€” Project Identity & Variant Matrix

Defines the project's identity, global defaults inherited by every variant, the variant-matrix schema, and the concrete variants.

## Schema

```yaml
PROJECT: MyProject                        # Project name (must match main_conf)
package_name: my-project                  # Conan package name (Conan projects only)
company: bosch                            # Vendor name (used in Conan package refs)

# === Global defaults inherited by every variant (deep-merged) ===
global_defaults:
  vector_conf: ../vector/vector_default.yml    # Vector DaVinci configuration
  tresos_conf: ../tresos/tresos_default.yml    # EB tresos configuration
  settings:                                    # Conan settings (Conan projects only; ignored otherwise)
    os: baremetal
    compiler: tasking
    compiler.version: 6.3
    build_type: Release
  build_requires: {}                           # See requirements.md
  tool_requires: ../requirements/default_tool_requires.yml
  test_requires: {}
  build_options:                               # Build switches / preprocessor defines
    WATCHDOG: 1
    SECUREBOOT: 0

# === Variant matrix shape (declares the dimension hierarchy) ===
variant_matrix:
  customer:
    description: "Customer variant"
    subvariants:
      hw_variant:
        description: "HW/Sample variant"
        subvariants:
          sw_variant:
            description: "SW variant"

# === Concrete variants (leaves of the matrix) ===
variants:
  platform:                                    # customer
    tc377:                                     # hw_variant
      minimal:                                 # sw_variant
        description: "GW 2WP Platform TC377 minimal variant"
        alias: pl7
        version: ../versioning/version.json
        vector_conf: ../vector/vector_conf_platform_tc377.yml
        tresos_conf: ../tresos/tresos_conf_platform_tc377.yml
        build_requires: {}
        tool_requires: ../requirements/tool_requires_platform_tc377.yml
        test_requires: {}
        build_options: {}
      eol:
        description: "GW 2WP Platform TC377 EOL variant"
        alias: pl7eol
        version: ../versioning/version.json
        tool_requires: ../requirements/tool_requires_platform_tc377.yml
        build_options: {}
    tc397:
      premium:
        description: "GW 2WP Platform TC397 premium variant"
        alias: pl9
        default: true                          # CLI uses this when no -var is given
        version: ../versioning/version.json
        build_options:
          XOTA: 1
          BUILD_SLAVE_CORE3: 1
```

## Top-Level Fields

| Field | Required | Description |
|---|---|---|
| `PROJECT` | yes | Project name (must match `main_conf.yml`). |
| `package_name` | no* | Conan package name. Required for Conan projects. |
| `company` | no* | Conan vendor. Required for Conan projects. |
| `global_defaults` | no | Defaults deep-merged into every variant before per-variant overrides. |
| `variant_matrix` | yes | Declares dimension names and hierarchy. The leaves of `variants` must match this shape. |
| `variants` | yes | Concrete variants. Tree shape mirrors `variant_matrix`. |

## Variant Properties

| Property | Description |
|---|---|
| `alias` | **Required.** Short CLI identifier (e.g. `pl7`, `v1`). Must be unique across the matrix. |
| `default` | Mark as the default variant (used when no `-var` is given). |
| `description` | Human-readable text shown in CLI help. |
| `version` | Path to a version JSON, or inline dict (see [versioning.md](versioning.md)). **Optional** — when absent, the variant falls back to the project-wide `RB_VERSIONING` value (static file or `git-managed`). |
| `settings` | Conan settings (`os`, `compiler`, `build_type`, â€¦). **Conan projects only.** Deep-merged over `global_defaults.settings`. |
| `build_requires` | Build dependencies. See [Requirements files](requirements.md). |
| `tool_requires` | Tool dependencies. See [Requirements files](requirements.md). |
| `test_requires` | Test-only dependencies. |
| `build_options` | Build options / preprocessor defines / linker flags. Deep-merged. |
| `vector_conf` | Path to a Vector DaVinci configuration. |
| `tresos_conf` | Path to an EB tresos configuration. |
| `options` | Free-form per-variant options consumed by steps. |

## Variant-Matrix Concept

The matrix is **n-dimensional**. Common patterns:

- **Single dimension**: `variant_matrix: { platform: {} }` â€” flat list of platforms.
- **Two dimensions**: customer â†’ hw_variant â€” each customer can have multiple hardware variants.
- **Three dimensions**: customer â†’ hw_variant â†’ sw_variant (as shown above).

The leaves of `variants` **must** match the declared depth and dimension names exactly. The matrix can declare a deeper structure than what is populated â€” empty leaves are simply not produced.

## Merge Behavior

For every variant the final dict is computed as:

```text
deep_merge(global_defaults, variant_dict)
```

- Dicts are merged recursively.
- Scalars in the variant override scalars in `global_defaults`.
- Lists are **replaced**, not appended.
- Empty dicts (`{}`) in a variant **do not** clear the corresponding global default â€” to suppress a default explicitly, set the field to `null` or override individual keys.

## Aliases & Resolution

The CLI accepts variants in several forms (all resolved by `VariantMatrix.get_variant()`):

| Form | Example |
|---|---|
| Alias | `pl7` |
| Path | `platform/tc377/minimal` |
| Index | `1` (1-based, ordered as listed in `variants`) |
| Comma list | `pl7,pl9` |
| Space list | `pl7 pl9` |
| All | `-all` (no value) |

## Minimal Example

```yaml
PROJECT: TinyProject

variant_matrix:
  platform:
    description: "Hardware platform"

variants:
  platform:
    x86_64:
      alias: x
      default: true
      description: "Linux x86_64 build"
```

## See Also

- [Variant Matrix](../../core_engine/reference/variant_matrix.md) â€” implementation classes and merge details
- [Requirements files](requirements.md) â€” `*_requires` resolver types
- [Versioning](versioning.md)
