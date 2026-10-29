# Variant Matrix

The `VariantMatrix` and `Variant` classes in `core_engine/variant_matrix.py` manage the multi-dimensional build variant system.

## Concept

A **variant** represents one specific combination of build dimensions — typically hardware platform, customer, and software configuration. Each variant has its own Conan settings, dependencies, build options, and output paths.

Example variant matrix structure:

```text
hardware/
├── arm_v7/
│   ├── oem_b    (alias: v2)
│   └── eol      (alias: v2e)
└── arm_v8/
    ├── oem_a    (alias: v1)
    └── eol      (alias: v1e)
```

## Configuration

Variants are defined in `config/project/project_conf.yml`:

```yaml
variant_matrix:
  hardware:
    description: "Hardware platform"
    subvariants:
      customer:
        description: "Customer configuration"

variants:
  hardware/arm_v8/oem_a:
    alias: v1
    default: true
    description: "ARM v8 OEM-A"
    version: ../versioning/version.json
    settings:
      os: baremetal
      compiler: gcc_arm
      compiler.version: 12.2
    requires:
      bsp/arm_v8: "[^2.0.0]@vendor/stable"
    build_options:
      with_diagnostics: True
```

## Class: `VariantMatrix`

Parses the `PROJECT_CONFIG` and builds the complete variant tree.

### Key Methods

| Method | Description |
|---|---|
| `get_variant(alias_or_path)` | Resolve a variant by alias (`v1`) or path (`hardware/arm_v8/oem_a`) |
| `get_default_variant()` | Return the variant marked `default: true` |
| `get_default_variant_alias()` | Return the default variant's alias string |
| `get_all_variants()` | Return list of all `Variant` objects |
| `get_all_variant_aliases()` | Return list of all alias strings |

### Variant Resolution

The CLI accepts variants in multiple formats:

- **Alias**: `v1`, `1`, `v2e`
- **Path**: `hardware/arm_v8/oem_a`
- **Index**: numeric position in the variant list
- **Comma-separated**: `v2,v1`
- **Space-separated**: `v2 v1`

`get_variant()` tries alias first, then path, then index.

## Class: `Variant`

Represents a single resolved variant. Constructed from the variant dict and `global_defaults`.

### Properties

| Property | Type | Description |
|---|---|---|
| `alias` | `str` | **Required.** Short identifier |
| `variant_values` | `dict` | Dimension key-value pairs (e.g. `{hardware: arm_v8, customer: oem_a}`) |
| `variant_path` | `str` | Slash-separated path (e.g. `hardware/arm_v8/oem_a`) |
| `description` | `str` | Human-readable description |
| `version` | `dict` | Version information. **Optional** — falls back to the project-wide `RB_VERSIONING` value (static file or `git-managed`) when the variant defines no `version` of its own. |
| `settings` | `dict` | Conan settings (merged: global_defaults + variant) |
| `requires` | `dict` | Conan requires (merged) |
| `tool_requires` | `dict` | Conan tool_requires (merged) |
| `test_requires` | `dict` | Test dependencies (merged) |
| `build_options` | `dict` | Build options (merged) |
| `options` | `dict` | Additional options |
| `vector_conf` | `str` | Path to Vector DaVinci config |
| `tresos_conf` | `str` | Path to EB tresos config |

### Merge Behavior

Variant-level settings are **deep-merged** over `global_defaults`. This means:

- Variant `settings` extend (not replace) global settings
- Variant `requires` add to global requires
- Individual keys can be overridden per-variant

### Key Methods

| Method | Returns |
|---|---|
| `get_variant_alias()` | Alias string |
| `get_version()` | Version dict |
| `get_settings()` | Merged settings dict |
| `get_build_options()` | Merged build options dict |
| `get_features()` | Feature list |
| `get_description()` | Description string |
