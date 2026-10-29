# Project Onboarding

```{note}
**Audience:** maintainers integrating a *new* project repository with XC-CE Utils. If you just want to run an action in an already-configured project, see [Getting Started](getting_started.md) instead.
```

This page is the **minimal checklist** to onboard a new project. For the full reference of every configuration file and every step type, follow the links to the dedicated guides.

## Prerequisites

- Git Bash
- `build.ps1` (Windows) or `build.sh` (Linux) in your project root â€” copy from this repository's `bootstrap_scripts/` folder.

## Onboarding Checklist

### 1. Create the `config/` directory

XC-CE Utils discovers configuration through a central entry-config resolver. In a standard repository, `config/main_conf.yml` is the primary source and should always be present. The recommended modular layout is:

```text
config/
â”œâ”€â”€ main_conf.yml              # Root config â€” references all others
â”œâ”€â”€ project/project_conf.yml   # Variant matrix, project metadata
â”œâ”€â”€ actions/actions_conf.yml   # Actions, phases, step definitions
â”œâ”€â”€ artifactories/artifactory_conf.yml
â””â”€â”€ versioning/version.json
```

â†’ See [Configuration Guide](config_guide.md) for the full hierarchy and all optional sections, and [Configuration Files Reference](config_files/index.md) for each individual file's schema.

```{note}
Runtime discovery also supports `./.xc-ce-utils` (key `main_conf`) and `./build_environment/xc-ce-utils/main_conf.yml`.
If `./.xc-ce-utils` is missing or invalid and a valid fallback is found, XC-CE Utils auto-creates/repairs `./.xc-ce-utils`.
```

```{note}
If the XC-CE Utils workflows are used, automatic semantic versioning relies on `config/versioning/version.json` being present. Alternatively, set `RB_VERSIONING: git-managed` in `main_conf.yml` to derive the version from git tags instead — see [versioning/version.json](config_files/versioning.md#git-managed-mode).
```

### 2. Fill in `main_conf.yml`

Point each key at the corresponding configuration file. Paths are resolved relative to `main_conf.yml`.

â†’ See [main_conf.yml reference](config_files/main_conf.md) for the complete list of supported keys and defaults.

### 3. Define the variant matrix and variants

The variant matrix is fully customizable (any number of nested levels). Variants are concrete leaves of that matrix and declare their requirements (`build_requires`, `tool_requires`, `test_requires`), `build_options`, and an `alias` used on the CLI.

â†’ See [project_conf.yml reference](config_files/project_conf.md) and [Variant Matrix](../core_engine/reference/variant_matrix.md) for the schema and examples.

### 4. Register actions

In `actions_conf.yml`, register one entry per action â€” each can reference its own file or be defined inline:

```yaml
DEFAULT_PARAMETERS:
  action: build

ACTIONS:
  build: build.yml
  doc: doc.yml
```

Then create the per-action files (e.g. `build.yml`) listing the phases and steps to execute.

For Helix QAC actions (`qac`, `sfa`, `sca`), also provide a project datastore under `config/qac/` and enable datastore adaptation in the step configuration (`adapt_datastore: true`). This ensures `{{ qac_exe_path }}` resolves to the active `xc-ce-utils` runtime path.

â†’ See [actions_conf.yml reference](config_files/actions_conf.md) for action registration, and [Steps by Category](../core_engine/reference/steps/index.md) for the full catalog of available step types and their parameters.

### 5. Run the first build

```powershell
./build.ps1 --help              # Show available variants and actions
./build.ps1 -var <alias> build  # Build a specific variant
```

â†’ See [Getting Started](getting_started.md) for day-to-day CLI usage, variant selection, and troubleshooting.

## CI/CD Integration

â†’ See [CI/CD Workflows](../workflows/index.md).

## See Also

- [Getting Started](getting_started.md) â€” CLI usage, variant selection, troubleshooting
- [Configuration Guide](config_guide.md) â€” full config hierarchy and options
- [Configuration Files Reference](config_files/index.md) â€” per-file schema details
- [Steps by Category](../core_engine/reference/steps/index.md) â€” all available step types
- [Core Engine Architecture](../core_engine/index.md) â€” how the build system works internally
