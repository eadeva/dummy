# Action Files â€” Anatomy of `build.yml`, `doc.yml`, â€¦

Each action file defines **one named pipeline of steps**. The file is referenced from `actions_conf.yml`. This page documents every field accepted at the action level and at each step level.

## Top-Level Action Fields

```yaml
description: "Compile and link the project"
action_group: build                  # Optional: groups action under a CI/IDE category

# Defaults the user can override with CLI flags
DEFAULT_PARAMETERS:
  from: cmake_configure              # First step (inclusive)
  to: deploy                         # Last step (inclusive)
  build_type: Release
  ccache: true

# Overrides applied when running in CI
DEFAULT_PARAMETERS_CX:
  ccache: false

# Run this action only for these variant aliases
only_variants: [pl7, pl9]            # Optional whitelist
omit_variants: [pl9eol]              # Optional blacklist
only_cx_pipelines: [release, nightly] # Optional CI-pipeline filter

# Per-variant overrides (deep-merged into the steps below)
variant_overrides:
  pl9eol:
    DEFAULT_PARAMETERS:
      build_type: Debug

variant_overrides_cx:                # CI-only per-variant overrides
  pl9:
    DEFAULT_PARAMETERS:
      ccache: false

# The actual pipeline (required)
steps:
  cmake_configure:
    type: cmake_set-up
    cmake_preset: default
  compile:
    type: cmake_build
  test:
    type: cmake_build
    cmake_target: tests
    execute_if: { build_type: Debug }
  deploy:
    type: deploy
    deploy_target: _bin/{{ variant_path }}
```

### Action-Level Field Reference

| Field | Type | Description |
|---|---|---|
| `description` | str | Human-readable text shown in `--help`. |
| `action_group` | str | Logical grouping (CI categories, VS Code task folders). |
| `DEFAULT_PARAMETERS` | dict | Defaults visible to steps and CLI. CLI flags can override. Common keys: `from`, `to`, `build_type`, `ccache`, action-specific params. |
| `DEFAULT_PARAMETERS_CX` | dict | CI overrides of `DEFAULT_PARAMETERS`. |
| `steps` | dict | **Required.** Ordered map of step name â†’ step config. |
| `only_variants` | list[str] | Restrict execution to these variant aliases. |
| `omit_variants` | list[str] | Exclude these variant aliases. |
| `only_cx_pipelines` | list[str] | Restrict execution to these CI pipeline names. |
| `variant_overrides` | dict | Per-variant overrides applied to `DEFAULT_PARAMETERS` and step bodies. |
| `variant_overrides_cx` | dict | CI per-variant overrides. |

## Step Fields

Each entry under `steps:` is either a **leaf step** (has `type:`) or a **composite set** (has `steps:`).

### Common Step Fields

| Field | Description |
|---|---|
| `type` | **Required for leaf steps.** Registered step type (e.g. `cmake_build`, `conan_command`, `deploy`). See [Step Reference](../../core_engine/reference/step_reference.md). |
| `steps` | If present, this is a composite set containing child steps. |
| `parallel` | `true` â†’ execute child steps in parallel threads. |
| `game_stopper` | Default `true`. If `false`, step failure does **not** abort the action. |
| `non_blocking` | Run in a background thread; the action continues without waiting. |
| `execute_if` | Conditional: `{variable: expected_value}`. Step is skipped if the variable does not match. |
| `wait_idle_before` / `wait_idle_after` | Seconds to wait before/after the step. |
| `only_variants` / `omit_variants` | Variant filter for the step. |
| `only_cx_pipelines` | CI-pipeline filter for the step. |
| `variant_overrides` | Per-variant deep-merge into the step body. |
| `variant_overrides_cx` | CI per-variant deep-merge. |

Any additional keys (e.g. `cmake_preset`, `deploy_target`, `conan_profile`) are passed straight to the step implementation. See the per-step pages under [Step Reference](../../core_engine/reference/step_reference.md) for what each step accepts.

## Composite Sets (Nesting)

Steps can be nested arbitrarily:

```yaml
steps:
  preparation:                       # composite set
    steps:
      install_deps:
        type: conan_command
        params: [install, conanfile.py, -of, conan_install]
      configure:
        type: cmake_set-up
  compilation:
    parallel: true                   # children run in parallel
    steps:
      build_app:
        type: cmake_build
      build_tests:
        type: cmake_build
        cmake_target: tests
```

The `--from` / `--to` CLI flags address steps at the **top level only** by their step name.

## From/To Phase Range

```powershell
.\build.ps1 -var pl9 build --from cmake_configure --to compile
```

The `from`/`to` defaults in `DEFAULT_PARAMETERS` provide sensible bounds; CLI flags override them.

## Variant Overrides Example

```yaml
steps:
  build_app:
    type: cmake_build
    cmake_target: app
    variant_overrides:
      pl7:
        cmake_target: app_tc377
      pl9eol:
        cmake_target: app_eol
    variant_overrides_cx:
      pl9:
        cmake_extra_args: ["-DCI_BUILD=1"]
```

## Real-World Example (compact)

```yaml
description: "Static code analysis with Helix QAC"
only_variants: [pl7, pl9]
action_group: quality
DEFAULT_PARAMETERS:
  build_type: Debug
steps:
  qac_analysis:
    type: sca
    sca_tool: helix_qac
    adapt_datastore: true
```

### Helix QAC Datastore Note

For `qac` / `sfa` / `sca` actions that use project datastore templates, prefer `adapt_datastore: true`.

- `{{ qac_exe_path }}` is resolved from the active `xc-ce-utils` runtime location.
- Legacy datastore entries that still point `QAC_CONFIG_PATH` to `_internal/xc_ce_utils/helix_qac` are normalized at runtime.

## See Also

- [Step Reference](../../core_engine/reference/step_reference.md) â€” all step types and their parameters
- [actions_conf.yml](actions_conf.md)
- [Configuration Guide](../config_guide.md)
