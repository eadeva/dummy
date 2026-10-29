# Configuration Guide

This guide explains the hierarchical YAML/JSON configuration system at the heart of XC-CE Utils. It covers the top-level configuration, variants, actions, and overrides. For exhaustive per-file references see the [Detail Pages](#detail-pages) at the bottom.

```{important}
**Conan is optional.** XC-CE Utils ships full Conan support but you do not have to use it. Projects that build with CMake/Bazel/Make + Artifactory artefacts or Toolbase tools can leave Conan entirely disabled by setting `CONAN_ENABLED: false` in `main_conf.yml`. The `requires:` / `tool_requires:` keys in `project_conf.yml` accept three resolver types â€” see [Requirements files](config_files/requirements.md).
```

## Configuration Hierarchy

The configuration is fully modular â€” each concern lives in its own YAML file and directory if desired. `ConfigLoader` resolves any string ending in `.yml`, `.yaml`, or `.json` as a **file reference** and loads it in-place, recursively. All paths are relative to the directory of the referencing file. This means every level of the configuration can be split into separate files for clarity and reusability.
All other path references other than configuration files (.yml, .yaml or .json) must be either absolute paths or relative to repository root folder.

Configuration structure example:

```text
config/
â”œâ”€â”€ main_conf.yml                 # Entry point â€” references all other configs
â”œâ”€â”€ project/
â”‚   â””â”€â”€ project_conf.yml          # Variant matrix, global defaults, package info
â”œâ”€â”€ actions/
â”‚   â”œâ”€â”€ actions_conf.yml          # Action registry â€” each action references its own file
â”‚   â”œâ”€â”€ build.yml                 # Build action definition
â”‚   â”œâ”€â”€ doc.yml                   # Documentation generation action
â”‚   â”œâ”€â”€ sca.yml                   # Static code analysis action
â”‚   â”œâ”€â”€ sfa.yml                   # Static flow analysis action
â”‚   â”œâ”€â”€ oss.yml                   # Open-source scanning action
â”‚   â”œâ”€â”€ tools/                    # Tool-launching actions (grouped in subdirectory)
â”‚   â”‚   â”œâ”€â”€ davinci.yml
â”‚   â”‚   â””â”€â”€ helix.yml
â”‚   â””â”€â”€ cleanup/                  # Maintenance actions (grouped in subdirectory)
â”‚       â”œâ”€â”€ conan_cache_cleanup.yml
â”‚       â””â”€â”€ remotes_cleanup.yml
â”œâ”€â”€ artifactories/
â”‚   â””â”€â”€ artifactory_conf.yml      # Artifactory definitions
â”œâ”€â”€ versioning/
â”‚   â””â”€â”€ version.json              # Semantic version fields
â”œâ”€â”€ cx/
â”‚   â””â”€â”€ cx_conf.yml               # CI-specific overrides (optional)
â”œâ”€â”€ oss/
â”‚   â””â”€â”€ oss_conf.yml              # Open-source scanning config (optional)
â””â”€â”€ requirements/
    â””â”€â”€ default_tool_requires.yml # Tool requirements shared across variants
```

Because file references are resolved recursively, you can organise actions into subdirectories and nest configurations as deeply as needed. Adding a new action is as simple as creating a YAML file and referencing it from `actions_conf.yml`.

## Main Configuration (`main_conf.yml`)

The single entry point loaded by `DynamicCLIGenerator`. Every other file is reached by following a chain of file references starting here.

```yaml
# Project identity & tool versions
PROJECT: MyProject
PYTHON_VERSION: 3.12.0.1
XC_CE_UTILS_VERSION: 4.19.0

# Optional: disable Conan entirely (default: true)
# CONAN_ENABLED: false

# File references (auto-loaded by ConfigLoader)
PROJECT_CONFIG: project/project_conf.yml
ACTIONS: actions/actions_conf.yml
ARTIFACTORIES: artifactories/artifactory_conf.yml
RB_VERSIONING: versioning/version.json              # Must be in a separate file when using XC-CE utils workflows
# RB_VERSIONING: git-managed                        # Alternative: derive version from git tags (see config_files/versioning.md)
CX_CONFIG: cx/cx_conf.yml
OSS_CONFIG: oss/oss_conf.yml
ENV_ISOLATION: env/env_isolation.yml
```

Required top-level keys: `ACTIONS`, `PROJECT_CONFIG`. All other keys are optional. Full field reference: [main_conf.yml](config_files/main_conf.md).

## Variable Substitution

`ConfigLoader` supports two substitution patterns:

| Pattern | Source | Example |
|---|---|---|
| `{{ variable }}` | Variables dict passed to `ConfigLoader(variables={...})` | `{{ PROJECT_ROOT }}/output` |
| `$ENV{VAR_NAME}` | `os.environ` | `$ENV{GITHUB_WORKSPACE}` |

Both keys and values in YAML dicts are subject to substitution. Missing environment variables are left as-is by default (configurable with `allow_missing_env_vars=False`).

## Project Configuration (`project_conf.yml`)

Defines the project identity and variant matrix:

```yaml
PROJECT: MyProject
package_name: my-project
company: bosch

global_defaults:
  settings:
    os: baremetal
    compiler: tasking
  requires: {}
  tool_requires: ../requirements/default_tool_requires.yml
  test_requires: {}
  build_options:
    shared: False

variant_matrix:
  customer:
    description: "Customer Variant"
    subvariants:
      sample:
        description: "HW Sample Variant"
        subvariants:
          sw_variant:
            description: "SW Variant"

variants:
  platform:
    tc377:
      minimal:
        description: "GW 2WP Platform TC377 minimal variant"                # Variant description
        alias: pl7                                                          # Variant alias for action execution
        version: ../versioning/version.json                                 # Variant specific version
        vector_conf: ../vector/vector_conf_platform_tc377.yml               # Needed for variant specific vector generation
        build_requires: {}                                                  # Variant specific build dependencies
        tool_requires: ../requirements/tool_requires_platform_tc377.yml     # Variant specific tool dependencies
        test_requires: {}                                                   # Variant specific test dependencies
        build_options: {}                                                   # Variant specific build options/switches
      eol:
        description: "GW 2WP Platform TC377 EOL variant"
        alias: pl7eol
        version: ../versioning/version.json
        vector_conf: ../vector/vector_conf_platform_tc377.yml
        build_requires: {}
        tool_requires: ../requirements/tool_requires_platform_tc377.yml
        test_requires: {}
        build_options: {}

    tc397:
      premium:
        description: "GW 2WP Platform TC397 premium variant"
        alias: pl9
        default: true
        version: ../versioning/version.json
        build_requires: {}
        tool_requires: {}
        test_requires: {}
        build_options:
          XOTA: 1
          BUILD_SLAVE_CORE3: 1
```

### Variant Properties

| Property | Description |
|---|---|
| `alias` | **Required.** Short CLI identifier (e.g. `v1`, `1`) |
| `default` | Mark as the default variant |
| `description` | Human-readable text for CLI help |
| `version` | Path to version file (or inline dict) |
| `settings` | Conan settings (`os`, `compiler`, `build_type`, â€¦) â€” **only used by Conan-based projects, ignored otherwise** â€” merged over global defaults |
| `build_requires` | Build dependencies â€” see [Requirements files](config_files/requirements.md) |
| `tool_requires` | Tool dependencies â€” see [Requirements files](config_files/requirements.md) |
| `test_requires` | Test-only dependencies |
| `build_options` | Build options/switches passed to the compiler/linker |
| `vector_conf` | Path to Vector DaVinci configuration (if applicable) |
| `tresos_conf` | Path to EB tresos configuration (if applicable) |

```{note}
Each `*_requires` value can resolve to **one of three resolver types**, selected by the `type:` field in the referenced requirements file:

- `type: conan` (or omitted with a Conan-shaped value) â€” resolved as a Conan package from a Conan-typed artifactory.
- `type: artifact` â€” downloaded as a raw artefact (zip/tar/directory) from a generic Artifactory repository.
- `type: toolbase` â€” installed via the system Toolbase (Windows).

Full resolver-by-resolver reference: [Requirements files](config_files/requirements.md).
```

## Actions Configuration (`actions_conf.yml`)

Defines what the build system can execute. The actions configuration is **modular** â€” `actions_conf.yml` acts as a registry that maps action names to individual YAML files. Each action file is self-contained and can be added, removed, or reorganised independently.

### Action Registry

The top-level `actions_conf.yml` lists all available actions. Each value is a **file reference** that `ConfigLoader` resolves automatically:

```yaml
DEFAULT_PARAMETERS:
  action: build              # Default action when no command is given

ACTIONS:
  build: build.yml           # Each action in its own file
  doc: doc.yml
  sca: sca.yml
  sfa: sfa.yml
  oss: oss.yml
  davinci: tools/davinci.yml       # Actions can be grouped in subdirectories
  helix: tools/helix.yml
  conan-cache-cleanup: cleanup/conan_cache_cleanup.yml
```

To add a new action, create a YAML file and add one line to `actions_conf.yml`. To remove an action, delete (or comment out) that line. Actions can also be defined inline in `actions_conf.yml` for simple cases.

### Action Definition

Each action file (e.g. `build.yml`) defines a named pipeline of **steps**:

```yaml
description: "Compile and link the project"
DEFAULT_PARAMETERS:
  from: cmake_configure     # First step to execute
  to: deploy              # Last step to execute
  build_type: Release
  ccache: true
DEFAULT_PARAMETERS_CX:    # Overrides when running in CI
  ccache: false
steps:
  cmake_configure:
    type: cmake_set-up
    cmake_preset: default
  cmake_compile:
    type: cmake_build
  deploy:
    type: deploy
    deploy_target: _bin/{{ variant_path }}
```

Simpler actions need only a few lines:

```yaml
# sca.yml
description: "Static code analysis with Helix QAC"
only_variants: [v1, v2]
steps:
  qac_analysis:
    type: sca
```

```yaml
# doc.yml
description: "Generate Sphinx documentation"
only_variants: [v1]
action_group: docs
steps:
  generate_docs:
    type: docascode
```

### Step Configuration

Each step maps to a registered step type in the `StepRegistry` (90+ types available). For the full catalogue â€” per-step parameters, behavior, and YAML examples â€” see the [Step Reference](../core_engine/reference/step_reference.md).

| Field | Description |
|---|---|
| `type` | **Required.** Step type name (e.g. `cmake_build`, `conan_command`, `deploy`) |
| `steps` | If present, this is a **composite set** containing child steps |
| `parallel` | Execute child steps in parallel threads |
| `game_stopper` | If `true` (default), failure aborts the entire action |
| `non_blocking` | Run in a background thread |
| `execute_if` | Conditional execution: `{variable: expected_value}` |
| `wait_idle_before` / `wait_idle_after` | Delay in seconds |
| `only_variants` / `omit_variants` | Filter by variant alias |
| `only_cx_pipelines` | Execute only in specific CI pipelines |
| `variant_overrides` | Per-variant configuration overrides (deep-merged) |
| `variant_overrides_cx` | Per-variant CI overrides (deep-merged) |

### Composite Sets (Nesting)

Steps can be nested arbitrarily:

```yaml
steps:
  preparation:
    steps:                      # This is a set, not a leaf step
      install_deps:
        type: conan_command
        params: [install, conanfile.py, -of, conan_install]
      configure:
        type: cmake_set-up
  compilation:
    parallel: true              # Run children in parallel
    steps:
      build_app:
        type: cmake_build
      build_tests:
        type: cmake_build
        cmake_target: tests
```

### From/To Phase Range

Actions define `from` and `to` in `DEFAULT_PARAMETERS` to select a subset of the step pipeline. The CLI `--clean` flag maps to executing only the clean-related steps.

## CX (CI) Overrides

When running in a CI environment (detected via `CI`, `GITHUB_ACTIONS` environment variables), three override layers are applied via deep merge:

| Level | Local field | CI override field |
|---|---|---|
| Action defaults | `DEFAULT_PARAMETERS` | `DEFAULT_PARAMETERS_CX` |
| Action variants | `variant_overrides` | `variant_overrides_cx` |
| Step variants | `variant_overrides` | `variant_overrides_cx` |

This allows different behavior in CI (e.g. disabling ccache, switching build types, adding upload steps).

## Pydantic Validation

Configurations are validated at load time against Pydantic models:

- `MainConfig` â€” top-level container
- `ProjectConfig` â€” project identity and variant matrix
- `BuildConfig` â€” actions container
- `ActionConfig` â€” single action with defaults and steps
- `StepConfig` â€” leaf step or composite set

All models use `extra = "allow"`, so step-specific fields (e.g. `cmake_preset`, `deploy_target`) pass through to the step implementation without requiring schema changes.

Run validation standalone:

```powershell
.\build.ps1 validate
```

## Configuration Tips

- **Use file references** to keep individual YAML files small and focused.
- **Use `global_defaults`** in `project_conf.yml` to avoid repeating settings across variants.
- **Use `variant_overrides`** instead of duplicating entire action configs per variant.
- **Use `DEFAULT_PARAMETERS_CX`** to customize CI behavior without affecting local builds.
- **Never commit secrets** â€” use `$ENV{VAR_NAME}` for credentials and tokens.

## Detail Pages

This guide is the entry point. For exhaustive field-by-field references on each individual config file, see:

| File | Purpose |
|---|---|
| [main_conf.yml](config_files/main_conf.md) | Top-level entry point and file references |
| [project_conf.yml](config_files/project_conf.md) | Project identity, global defaults, variant matrix |
| [actions_conf.yml](config_files/actions_conf.md) | Action registry mapping names â†’ action files |
| [Action files (`build.yml`, `doc.yml`, â€¦)](config_files/action_file.md) | Individual action pipelines and step composition |
| [Requirements files](config_files/requirements.md) | `tool_requires` / `build_requires` / `test_requires` â€” Conan, Artifactory, Toolbase |
| [artifactory_conf.yml](config_files/artifactory_conf.md) | Artifactory endpoint definitions |
| [versioning/version.json](config_files/versioning.md) | Semantic version fields (`RB_VERSIONING`) — static file or `git-managed` mode |
| [cx/cx_conf.yml](config_files/cx_conf.md) | CI-specific configuration |
| [oss/oss_conf.yml](config_files/oss_conf.md) | Open-source scanning configuration |
| [env/env_isolation.yml](config_files/env_isolation.md) | Environment-variable isolation rules |

See also: [Variant Matrix](../core_engine/reference/variant_matrix.md), [Step Reference](../core_engine/reference/step_reference.md).
