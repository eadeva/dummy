# Environment Setup

> ⚠️ **Historical reference.** As of PR #47 the orchestration uses the `SetupPhase` chain documented in [environment_setup_flow.md](environment_setup_flow.md). The mixins described below are still present as thin shims for backward compatibility, but new code should add a `SetupPhase` under `xc_ce_utils/core_engine/setup/phases/` rather than extending a mixin.

The `core_engine/setup/` package handles one-time environment preparation before action execution. It uses a **mixin pattern** — `EnvironmentSetup` inherits from five specialized mixins, each responsible for one aspect of the development environment.

## Class: `EnvironmentSetup`

```python
class EnvironmentSetup(
    ConanSetupMixin,
    BazelSetupMixin,
    DevmateSetupMixin,
    VSCodeSetupMixin,
    GitHooksSetupMixin
):
```

Manages a versioned project folder at `~/.{project}_xc-ce-utils_{major_version}/` containing setup state files. Uses SHA-256 file hashing and JSON state markers to avoid redundant setup on subsequent runs.

### When Setup Runs

`EnvironmentSetup` is called by `ExecutionAction.setup()` at the start of every action. Each mixin checks its own state markers and only performs work when configuration has changed.

### Cross-Platform

All mixins work on Windows and Linux. CI environments are auto-detected, and some setup steps (e.g. DevMate PAT prompts) are skipped in CI.

## Mixins

### ConanSetupMixin

**File:** `setup/setup_conan.py`

Full Conan lifecycle management:

- **CLI resolution**: Finds the correct `conan` binary (handles frozen PyInstaller executables)
- **Config install**: `conan config install` from configured source, with file-lock coordination for parallel builds
- **Remote setup**: Configures Artifactory and other Conan remotes with authentication
- **Login**: Handles Conan remote login with credentials from environment or keyring
- **Environment parsing**: Reads `conanbuildenv` shell scripts and extracts environment variable changes into Python `os.environ`
- **Tool installation**: Installs additional tools from `conan_tools.yml` (e.g. specific compiler versions)

### BazelSetupMixin

**File:** `setup/setup_bazel.py`

Bazel cache management:

- **`.bazelrc` validation**: Checks and migrates the user-level `~/.bazelrc` disk cache path
- **Project-level config**: Writes `.bazelrc.cache` with cache directory settings
- **Auth config**: Writes `.bazelrc.auth` for remote cache authentication

### DevmateSetupMixin

**File:** `setup/setup_devmate.py`

DevMate Personal Access Token (PAT) management:

- **Staleness check**: Verifies PAT age (5-week renewal cycle)
- **PAT prompt**: Interactive workflow to update the PAT when expired
- **VS Code advisory**: Notifies user if VS Code restart is needed

### VSCodeSetupMixin

**File:** `setup/vscode/extensions.py`

VS Code extension management:

- **Change detection**: SHA-256 hash of `extensions.json` to detect config changes
- **Install on demand**: Runs `code --install-extension` for each extension in the config via `./build.ps1 config vs-code refresh-extensions`; the automatic installation during setup is deactivated
- **Skipped in CI**: No VS Code operations in CI environments

### VSCodeConfigGenerationMixin

**File:** `setup/vscode/config_generation.py`

VS Code/Copilot file generation:

- **VS Code config generation**: Regenerates tasks/settings/extensions artifacts
- **Copilot instructions generation**: Refreshes `.github/copilot-instructions.md`
- **Orchestration split**: Kept separate from extension installation to keep setup concerns isolated

### GitHooksSetupMixin

**File:** `setup/setup_git_hooks.py`

Git hooks management:

- **Change detection**: Hash-based comparison of hook script source directory
- **Hook installation**: Copies hook scripts to `.git/hooks/` when the source changes
- **State persistence**: Stores hook hash in Git config

## State Management

Each mixin persists its state in the versioned project folder:

```text
~/.myproject_xc-ce-utils_4/
├── setup_state.json          # Mixin state markers
├── conan_config_hash         # Conan config install hash
├── vscode_extensions_hash    # VS Code extensions config hash
└── git_hooks_hash            # Git hooks source hash
```

This ensures that setup operations are **idempotent** — running the build multiple times only performs setup work when configuration files have actually changed.

## Dev Tooling Provider Override

`dynamic_cli` supports overriding the dev-tooling provider implementation at startup through:

- `XC_CE_UTILS_DEV_TOOLING_PROVIDER=module:attribute`

Where `attribute` can be:

- A provider instance implementing the dev-tooling provider port
- A zero-argument factory returning that provider instance

Behavior:

- Missing/empty env var: default provider is used
- Invalid format/import/attribute/factory signature: logs a warning and falls back to default provider

This is primarily intended for extraction/migration experiments and test-time wiring.
