# Configuration Schema Reference

Authoritative reference for the pydantic v2 models in `xc_ce_utils.core_engine.config.config_models`. Every YAML key recognised by `xc-ce-utils` ultimately lands in one of these models.

> **How to read this page.** Every model section lists the fields *as declared in the model class* and the YAML form a config author would write. Field tables use `extra="allow"` unless noted, which means unknown keys are preserved (not rejected) — this is intentional for forward compatibility.

---

## Model graph

```text
main_conf.yml  →  (assembled by ConfigLoader, recursive !include)
                  │
                  ├─ build configuration  → BuildConfig
                  │                          ├─ DEFAULT_PARAMETERS → DefaultParameters
                  │                          └─ ACTIONS[name]      → ActionConfig
                  │                                                  ├─ DEFAULT_PARAMETERS    → ActionDefaults
                  │                                                  ├─ DEFAULT_PARAMETERS_CX → ActionDefaults
                  │                                                  ├─ PHASES[name]          → StepConfig   (legacy)
                  │                                                  ├─ SETS[name]            → StepConfig   (legacy)
                  │                                                  └─ steps[name]           → StepConfig   (new unified)
                  │
                  └─ project configuration  → ProjectConfig
                                              ├─ global_defaults → GlobalDefaults
                                              └─ variant_matrix  → parsed by VariantMatrix
```

---

## `StepConfig`

A single executable step (leaf) **or** a nested set of steps. Source: `core_engine/config/config_models.py`.

| Field | Type | Default | Notes |
|---|---|---|---|
| `type` | `str` | — | Step type, e.g. `cmake_build`. Aliased from `step_type` for backward compatibility. |
| `steps` | `Dict[str, StepConfig]` | `None` | Present on **set** nodes only; absent on leaves. |
| `parallel` | `bool` | `False` | When `True` on a set, child steps run in parallel. |
| `execute_if` | `Optional[Dict]` | `None` | Conditional execution predicate (see *Execution Control* below). |
| `game_stopper` | `bool` | `True` | If `False`, a step failure does **not** abort subsequent steps. |
| `non_blocking` | `bool` | `False` | Equivalent shorthand; takes precedence over `game_stopper`. |
| `wait_idle_before` / `wait_idle_after` | `bool` | `False` | Insert an implicit `wait_idle` synchronisation around this step. |
| `only_cx_pipelines` | `bool` | `False` | Skip step unless running under a CX (CI) pipeline. |
| `skip_on_cx` | `bool` | `False` | Skip step when running under a CX (CI) pipeline (local-only step). |
| `only_variants` | `List[str]` | `[]` | Restrict step to these variant aliases. |
| `omit_variants` | `List[str]` | `[]` | Skip step on these variant aliases. |
| `variant_overrides` | `Optional[Dict[str, Dict]]` | `None` | Per-variant field overrides applied via `resolve_for_variant()`. |
| `variant_overrides_cx` | `Optional[Dict[str, Dict]]` | `None` | CX-only variant overrides (CI). |
| `title` | `Optional[str]` | step name | Displayed in summaries / reports. |
| `description` | `Optional[str]` | `""` | Free-form explanation. |
| `id` | `Optional[str]` | `None` | Stable identifier used by traceability and reports. |
| `add_to_report` | `bool` | `True` | Include in the final report. |
| `customer_visible` | `bool` | `False` | Render in customer-facing summaries. |
| `log` | `Optional[Dict]` | `None` | Per-step logger config. |

Plus arbitrary keys consumed by the step's own `config_fields` (e.g. `source_dir`, `preset`, `targets`).

### YAML — leaf

```yaml
cmake_set-up:
  type: cmake_set-up
  source_dir: SW
  preset: ${VARIANT_PRESET}
  build_options:
    BUILD_TESTS: "ON"
```

### YAML — set

```yaml
configure:
  parallel: false
  execute_if: { variant_setting: [build_type, debug] }
  steps:
    cmake_set-up: { type: cmake_set-up, ... }
    install_deps:
      type: conan_command
      params: [install, conanfile.py, -of, conan_install]
```

### `resolve_for_variant(variant_alias)`

Returns a copy of the dict with `variant_overrides` merged in for `variant_alias`. Used by `ExecutionAction` immediately before instantiating the step. CX overrides win over plain overrides when running in CI.

---

## `ActionDefaults`

Default parameters for an action's execution (`from`/`to` phase bracketing, build type, ccache toggle).

| Field | YAML key | Type | Default | Description |
|---|---|---|---|---|
| `from_phase` | `from` | `Optional[str]` | `None` | First phase to execute. Aliased from `from` because `from` is a Python keyword. |
| `to_phase` | `to` | `Optional[str]` | `None` | Last phase to execute (inclusive). |
| `build_type` | `build_type` | `Optional[str]` | `None` | E.g. `debug`, `release`. |
| `ccache` | `ccache` | `Optional[bool]` | `None` | Enable / disable ccache (also affected by global `--no-cache`). |

`extra="allow"` — additional keys are kept and forwarded as default kwargs to step factories.

---

## `ActionConfig`

A single named action under `BuildConfig.ACTIONS`.

| Field | YAML key | Type | Description |
|---|---|---|---|
| `description` | `description` | `str` | Used as the click `--help` text. |
| `only_cx_pipelines` | `only_cx_pipelines` | `bool` | Hide / disable outside CX pipelines. |
| `only_variants` | `only_variants` | `List[str]` | Action allowed only on these variant aliases. |
| `omit_variants` | `omit_variants` | `List[str]` | Action denied on these variant aliases. |
| `action_group` | `action_group` | `Optional[str]` | CLI sub-group placement (e.g. `config`). When `None`, the action is top-level. |
| `DEFAULT_PARAMETERS` | `DEFAULT_PARAMETERS` | `ActionDefaults` | Defaults for **local** runs. |
| `DEFAULT_PARAMETERS_CX` | `DEFAULT_PARAMETERS_CX` | `Optional[ActionDefaults]` | Overrides applied on top of `DEFAULT_PARAMETERS` when running under CI. |
| `PHASES` | `PHASES` | `Dict[str, StepConfig]` | **Legacy** ordered phases. |
| `SETS` | `SETS` | `Optional[Dict[str, StepConfig]]` | **Legacy** automation sets. |
| `steps` | `steps` | `Optional[Dict[str, StepConfig]]` | **New** unified ordered dict; takes precedence when present. |
| `variant_overrides` | `variant_overrides` | `Optional[Dict[str, Dict]]` | Action-level per-variant overrides. |
| `variant_overrides_cx` | `variant_overrides_cx` | `Optional[Dict[str, Dict]]` | Action-level per-variant CX overrides. |

### Methods of interest

- `get_unified_steps() -> Dict[str, Any]` — Returns `steps` if defined, otherwise migrates legacy `PHASES + SETS` into a single ordered dict.
- `get_effective_defaults(is_cx: bool) -> ActionDefaults` — Deep-merges `DEFAULT_PARAMETERS_CX` on top of `DEFAULT_PARAMETERS` when `is_cx=True`.
- `validate_phase_references()` — Validator hook that warns when `from`/`to` references point to non-existent phases.

---

## `BuildConfig` / `DefaultParameters`

Top-level shape of `build_conf.yml` (typically `!include`-d from `main_conf.yml`):

```yaml
DEFAULT_PARAMETERS:
  action: build           # default action when none is given

ACTIONS:
  build:    { description: "Full pipeline",   PHASES: {...} }
  test:     { description: "Run tests",       PHASES: {...}, SETS: {...} }
  smoke_test: { description: "HIL smoke",     steps: {...}, action_group: hil }
```

| Model | Field | Type | Notes |
|---|---|---|---|
| `DefaultParameters` | `action` | `Optional[str]` | Action invoked when the user passes no subcommand. |
| `BuildConfig` | `DEFAULT_PARAMETERS` | `DefaultParameters` | — |
| `BuildConfig` | `ACTIONS` | `Dict[str, ActionConfig]` | Keyed by lower-case action name. |

---

## `ProjectConfig` / `GlobalDefaults`

Top-level shape of `project_conf.yml`:

| Field | YAML key | Type | Description |
|---|---|---|---|
| `PROJECT` | `PROJECT` | `str` | Human-readable project name (used in headers and the project folder name). |
| `package_name` | `package_name` | `str` | Conan package name. |
| `global_defaults` | `global_defaults` | `GlobalDefaults` | Shared `requires` / `tool_requires` / `test_requires` / `build_options`. |
| `variant_matrix` | `variant_matrix` | `Dict[str, Any]` | Variant matrix levels — parsed by `VariantMatrix` (see [variant_matrix.md](variant_matrix.md)). |

`GlobalDefaults` fields:

| Field | Type | Notes |
|---|---|---|
| `requires` | `Dict[str, Any]` | Production package requires shared by all variants. |
| `tool_requires` | `Any` | Build-time tool requires (kept as `Any` to allow lists or dicts). |
| `test_requires` | `Dict[str, Any]` | Test-only requires. |
| `build_options` | `Dict[str, Any]` | Conan options applied to every variant. |

All four are merged with each variant's own settings during `VariantMatrix.get_variants()`.

---

## Validation Behaviour

| Concern | Behaviour |
|---|---|
| Unknown keys | Allowed everywhere (`extra="allow"`). They are preserved on the model instance and may be consumed by downstream code. |
| Missing required keys | Pydantic raises `ValidationError`. The CLI re-raises as `ConfigurationError` with the field path. |
| Type coercion | Pydantic v2 strict mode is **not** enabled; `"true"` will coerce to `True` for `bool` fields. |
| Cross-field validation | `ActionConfig.validate_phase_references` warns (does not error) on missing `from`/`to` targets — a phase may legitimately live in `SETS`. |

---

## Example: full minimal `main_conf.yml`

```yaml
PROJECT: my_ecu
package_name: my_ecu

global_defaults:
  requires:
    autosar/4.4.0: {}
  tool_requires: { cmake/3.27.0: null }
  build_options:
    fpu: hard

variant_matrix:
  platform:
    description: Target platform

variants:
  tc377:
    alias: "1"
    version: "1.0.0"
    settings: { arch: tricore }

DEFAULT_PARAMETERS:
  action: build

ACTIONS:
  build:
    description: Compile + link
    DEFAULT_PARAMETERS:
      from: configure
      to: package
    steps:
      configure:
        steps:
          cmake_set-up: { type: cmake_set-up, source_dir: SW }
      compile:
        type: cmake_build
      package:
        type: conan_command
        params: [export-pkg, ., --name, my_ecu]
```
