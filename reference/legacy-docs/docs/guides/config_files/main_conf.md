# `main_conf.yml` — Top-Level Configuration

The entry-point configuration loaded at startup. Every other configuration file is reached through a chain of **file references** that begin here. `ConfigLoader` resolves any string value ending in `.yml`, `.yaml`, or `.json` as a file path (relative to the referencing file) and inlines its content recursively.

## Discovery Order

XC-CE Utils resolves the main configuration in this order:

1. `./.xc-ce-utils` (in the invocation working directory), key `main_conf: <path>`
2. `<repo_root>/config/main_conf.yml`
3. `<repo_root>/config/main_conf.json`
4. `./build_environment/xc-ce-utils/main_conf.yml`

If `./.xc-ce-utils` is missing or invalid and a fallback path is found, the file is automatically created or repaired. The written `main_conf` path is stored relative to `repo_root` when possible.

## Schema

```yaml
# === Project identity (required) ===
PROJECT: MyProject                        # Project name; used in paths and CI

# === Tool versions ===
XC_CE_UTILS_VERSION: 4.19.0               # Pinned xc-ce-utils version (wrapper consumes this)
PYTHON_VERSION: 3.12.0.1                  # Optional: Python version when using `python -m xc_ce_utils`

# === Feature toggles ===
CONAN_ENABLED: true                       # Optional, default true. Set false for projects that
                                          # do not use Conan (Artifactory + CMake/Make/Bazel only).
INTERACTIVE_FAILURE_ASSISTANCE: true      # Optional, default true. Offer AI troubleshooting after a failed action.
BEHAVIOUR_REPORT_OPENING: on-errors       # Optional, default on-errors: always | on-errors | never (open the unified report after a run).

# === Required file references ===
PROJECT_CONFIG: project/project_conf.yml  # **Required** — variant matrix, global defaults
ACTIONS: actions/actions_conf.yml         # **Required** — action registry

# === Optional file references ===
ARTIFACTORIES: artifactories/artifactory_conf.yml   # Artifactory endpoints (needed for Artifactory/Conan)
RB_VERSIONING: versioning/version.json              # Semantic version fields; required by xc-ce-workflows
# RB_VERSIONING: git-managed                        # Alternative: derive version from git tags instead of a file
CX_CONFIG: cx/cx_conf.yml                           # CI-specific overrides
OSS_CONFIG: oss/oss_conf.yml                        # Open-source scanning configuration
ENV_ISOLATION: env/env_isolation.yml                # Environment isolation rules
```

## Field Reference

| Key | Required | Type | Description |
|---|---|---|---|
| `PROJECT` | yes | str | Project identifier. Used in paths, CI artefacts, Conan package names. |
| `ACTIONS` | yes | str / dict | File reference to `actions_conf.yml`, or an inline action registry. |
| `PROJECT_CONFIG` | yes | str / dict | File reference to `project_conf.yml`, or an inline project config. |
| `XC_CE_UTILS_VERSION` | recommended | str | Version consumed by `build.ps1` / `build.sh` wrappers to download the correct executable. |
| `PYTHON_VERSION` | no | str | Python version expectation; used by some integrations. |
| `CONAN_ENABLED` | no | bool | Default `true`. Set `false` to skip all Conan setup and treat `*_requires` as non-Conan only. |
| `INTERACTIVE_FAILURE_ASSISTANCE` | no | bool | Default `true`. After a failed action, offer to analyze the failure with an AI assistant (GitHub Copilot CLI / Gemini CLI). Never prompts in CI or without a terminal. |
| `BEHAVIOUR_REPORT_OPENING` | no | str | When to open the unified HTML report in the browser after a local run: `always`, `on-errors` (only if the run had errors) or `never`. Never opens in CI. Default `on-errors`; invalid values log a warning and use the default. Independent of `INTERACTIVE_FAILURE_ASSISTANCE`. |
| `ARTIFACTORIES` | no* | str / dict | Required if any action downloads from Artifactory or uses Conan remotes. |
| `RB_VERSIONING` | no* | str / dict | Required when using `xc-ce-workflows` CI pipelines that compute/publish versions. Either a file reference to `version.json`, an inline dict, the literal string `git-managed` (optionally `git-managed:<tag glob>`), or `variant-git-managed` for one version per variant (see [versioning/version.json](versioning.md#git-managed-mode)). |
| `CX_CONFIG` | no | str / dict | Pipeline-conditional knobs; merged into action defaults when running in CI. |
| `OSS_CONFIG` | no | str / dict | Configuration for the OSS scanning action. |
| `ENV_ISOLATION` | no | str / dict | Restricts which host environment variables and `PATH` entries leak into the build. |

\* Required only when the corresponding feature is used.

## Variable Substitution

`ConfigLoader` supports two substitution patterns; both keys and values are substituted:

| Pattern | Source | Example |
|---|---|---|
| `{{ variable }}` | Variables dict passed to `ConfigLoader(variables={...})` | `{{ PROJECT_ROOT }}/output` |
| `$ENV{VAR_NAME}` | `os.environ` | `$ENV{GITHUB_WORKSPACE}` |

Missing environment variables are left as-is by default (configurable with `allow_missing_env_vars=False`).

## Minimal Example

```yaml
PROJECT: MyTinyProject
ACTIONS:
  ACTIONS:
    build:
      steps:
        compile:
          type: cmake_build
PROJECT_CONFIG:
  PROJECT: MyTinyProject
  variants:
    default:
      alias: d
      default: true
```

## Real-World Example (GW_2WP)

```yaml
PROJECT: GW_2WP
XC_CE_UTILS_VERSION: 4.18.0
ENV_ISOLATION: env/env_isolation.yml

PROJECT_CONFIG: project/project_conf.yml
ARTIFACTORIES: artifactories/artifactory_conf.yml
ACTIONS: actions/actions_conf.yml
RB_VERSIONING: versioning/version.json
CX_CONFIG: cx/cx_conf.yml
OSS_CONFIG: oss/oss_conf.yml
```

## See Also

- [Configuration Guide](../config_guide.md)
- [project_conf.yml](project_conf.md)
- [actions_conf.yml](actions_conf.md)
- [Environment isolation](env_isolation.md)
