# Environment Setup Flow

This page documents the **boot sequence** of `xc-ce-utils` — from the moment a developer runs `./build.ps1` until an action starts executing — and the **chain-of-responsibility** that powers `EnvironmentSetup.run_setup`.

For the day-to-day mixin API of each individual setup concern (Conan, Bazel, git hooks, VS Code, Devmate) see the legacy reference at [environment_setup.md](environment_setup.md). This page focuses on the *flow* and the *new phase pipeline* introduced in PR #47.

---

## Boot Sequence

```{uml} ../../_diagrams/boot_sequence.puml
```

### What happens before Click parses argv

A surprising amount of work happens *before* the CLI sees its first argument:

1. **`build.ps1` / `build.sh`** — Reads `XC_CE_UTILS_VERSION` from `config/main_conf.yml`, ensures the matching `xc-ce-utils.exe` is installed under `C:\tools\xc-ce-utils\<version>` (or `~/.local/share/xc-ce-utils/<version>` on Linux), and forwards `argv` to it.
2. **`platform_setup.ensure_utf8_stdout()`** — On Windows, reconfigures `sys.stdout`/`sys.stderr` to UTF-8 so emoji and box-drawing chars in log output render correctly under CP1252 consoles.
3. **`cli/environment_setup_orchestrator.run_environment_setup()`** — Sets `REPO_PATH` if unset, then checks `_should_skip_environment_setup()`: if `argv` contains `--help`, `-h`, `--version`, or one of the dedicated setup subcommands (`clean-older-versions`, `force-setup`, `full-setup`, `clang-setup`, `hooks-setup`, `refresh-bazel-cache`, `devmate-setup`), it returns immediately **without importing `EnvironmentSetup` at all** (fast path). Otherwise:
   - `EnvironmentSetup.ensure_conan_env(repo_path)` initialises `CONAN_HOME`, `CONAN_USER_HOME`, and `CONAN_DEFAULT_PROFILE_PATH` **before any `conan` import**. This is critical: importing Conan after these env vars are set would otherwise cause Conan to materialise its default profile in the user's home directory instead of in the project-scoped folder. Idempotent — a no-op when `CONAN_HOME` is already exported (e.g. by CI).
   - If `XC_CE_SETUP_DONE` is not yet set in the environment, constructs `EnvironmentSetup(repo_path)` and calls `run_setup()` — this is where the 12-phase chain (below) runs — then sets `XC_CE_SETUP_DONE=1` so re-entrant invocations within the same process skip it.
4. **`cli/entrypoint.create_dynamic_cli(repo_root)`** — Loads `main_conf.yml` via `ConfigLoader` (with recursive `!include` resolution and `$ENV{}`/`$VAR{}` substitution), builds the `VariantMatrix`, and assembles the click root group via `core_engine/cli/root_group.create_root_group(self)`. Per-action commands are then attached via `core_engine/cli/command_factory`.
5. **Action dispatch** — `core_engine/cli/variant_executor.execute_action_with_arguments(...)` resolves variants, expands `from_phase`/`to_phase`, and invokes `ExecutionAction.run()`.

### Project-scoped state folder

`EnvironmentSetup._compute_project_folder` derives a versioned per-project folder:

| Environment | Path |
|---|---|
| Local (Linux/macOS) | `~/.{project_name}_xc-ce-utils_{major}/` |
| Local (Windows) | `%USERPROFILE%\.{project_name}_xc-ce-utils_{major}/` |
| GitHub Actions (Windows) | `C:\workflows\{project_name}_xc-ce-utils_{major}\` |
| GitHub Actions (Linux) | `/tmp/workflows/{project_name}_xc-ce-utils_{major}/` |

The major-version suffix means upgrading from `xc-ce-utils 4.x` to `5.x` does **not** invalidate the existing setup — both versions get their own folder.

This folder holds:

| File | Purpose |
|---|---|
| `.conan/` | Conan home (cache, profiles, remotes) |
| `.xc_ce_setup_state.json` | Persisted phase state (see below) |
| `.xc_ce_builder_setup_complete` | First-time-setup marker with timestamp |
| `.xc_ce_setup.lock` | `filelock` file preventing concurrent setup runs |
| `.{requirements_file}.hash` | SHA-256 hashes for change detection |

---

## The Setup Phase Chain

`EnvironmentSetup.run_setup()` used to be a ~300-line procedural function. PR #47 split it into a chain of single-responsibility phases.

```{uml} ../../_diagrams/setup_phases.puml
```

### Anatomy of a phase

A phase is a small class implementing `SetupPhase` (see `core_engine/setup/phases/base.py`):

```python
class SetupPhase(ABC):
    name: str = ""

    @abstractmethod
    def should_run(self, ctx: SetupContext) -> bool:
        """Side-effect-free decision based on ctx.state / ctx.config."""

    @abstractmethod
    def run(self, ctx: SetupContext) -> None:
        """Perform the work; mutate ctx.state in place."""
```

The shared `SetupContext` carries everything a phase needs:

| Field | Description |
|---|---|
| `setup` | Back-reference to the `EnvironmentSetup` instance (gives access to mixin helpers and folder paths) |
| `config` | The build configuration loaded from `main_conf.yml` |
| `state` | Mutable dict persisted as `.xc_ce_setup_state.json` after the loop |
| `first_time_setup` | `True` when no marker file exists yet |
| `force` | `True` when the caller passed `force=True` |
| `is_ci` | `True` under GitHub Actions / generic `CI=true` environments |
| `needs_credential_check` | `True` on first setup, on force, or when stored credentials are older than 5 weeks |

### Registered phases (in order)

```python
def default_setup_phases():
    return [
        CredentialValidationPhase(),
        CredentialRenewalReminderPhase(),
        ConanSetupPhase(),
        ConanToolsPhase(),
        GitHooksMigrationPhase(),
        GitHooksPhase(),
        ClangSetupPhase(),
        ApplyConanEnvPhase(),
        BazelDiskCachePhase(),
        BazelRemoteCachePhase(),
        # VSCodeExtensionsPhase deactivated (on demand: config vs-code refresh-extensions)
        DevmatePATPhase(),
    ]
```

| # | Phase | `should_run` trigger | What `run` does |
|---|---|---|---|
| 1 | `CredentialValidationPhase` | First setup, `force`, or credentials older than 5 weeks | Validates stored credentials against configured remotes; prompts interactively if invalid (skipped in CI) |
| 2 | `CredentialRenewalReminderPhase` | Credentials approaching expiry | Logs a warning recommending re-authentication; non-blocking |
| 3 | `ConanSetupPhase` | First setup or `force` | `conan config install` from configured source with file-lock; configures remotes |
| 4 | `ConanToolsPhase` | `conan_tools.yml` SHA changed | Installs additional tool packages declared in `conan_tools.yml` |
| 5 | `GitHooksMigrationPhase` | Legacy hook layout detected | Migrates pre-existing hooks to the managed layout (idempotent) |
| 6 | `GitHooksPhase` | Hook source dir SHA changed | Installs / refreshes the project's managed git hooks |
| 7 | `ClangSetupPhase` | Windows + not CI, `CLANG_CONFIG` resolves + `enabled: true`, and (`config/clang/clang_conf.yml` changed or first setup/`force`) | Resolves the clang toolchain config and deploys the Phase-D clang pre-commit hooks into the `.pre-commit-config.yaml` produced by `GitHooksPhase` |
| 8 | `ApplyConanEnvPhase` | Always | Parses `conanbuildenv` shell scripts and exports variables into `os.environ` |
| 9 | `BazelDiskCachePhase` | First setup, or user `.bazelrc` out of date | Validates / migrates the disk cache path in `~/.bazelrc` |
| 10 | `BazelRemoteCachePhase` | Always | Writes project-level `.bazelrc.cache` and `.bazelrc.auth` for remote cache |
| 11 | ~~`VSCodeExtensionsPhase`~~ | **Deactivated** — not part of the setup chain | VS Code extensions are installed on demand with `./build.ps1 config vs-code refresh-extensions` |
| 12 | `DevmatePATPhase` | Not in CI, on first setup or `force` | Interactive prompt for a DevMate Personal Access Token; stored via keyring |

```{note}
`config/clang/clang_conf.yml` in row 7 is the common **default** path, not
guaranteed — the actual config root is the parent directory of wherever
`main_conf.yml` resolves (overridable per project via `.xc-ce-utils`). See
[main_conf.yml's Discovery Order](../../guides/config_files/main_conf.md#discovery-order).
```


> **Behaviour preservation.** Phase order matches the legacy in-line implementation **exactly** so the `.xc_ce_setup_state.json` format is byte-compatible — upgrading does not force developers to redo setup.

### Concurrency

`EnvironmentSetup` acquires a `filelock` on `.xc_ce_setup.lock` before running the chain. Parallel `build.ps1` invocations (common in CI matrix jobs) serialise their setup — second-and-later callers wait for the lock holder to finish. An `atexit` handler releases the lock on Ctrl+C / process exit.

### Logging

Each `run_setup` invocation gets its own log file at `_log/xc-ce-utils-setup/xc-ce-utils_setup.log`. The build configuration as actually loaded (after `!include` and substitution) is dumped to `_build/xc-ce-utils-setup/configuration.json` for debugging.

---

## Environment Isolation

After the setup chain runs, `core_engine/setup/env_isolation.py` may strip the inherited environment down to a known-good baseline before action execution. This is enabled per-action via `actions.<name>.env_isolation` in `main_conf.yml`.

| Concept | Behaviour |
|---|---|
| **Disabled mode** | `env_isolation.enabled: false` — no environment changes; legacy behaviour. |
| **Enabled mode** | Removes every env var except those in `bypass_env_vars`. `CONAN_HOME` is **always** preserved automatically. |
| **PATH filtering** | When enabled, `PATH` is reduced to entries matching `bypass_path_elements`. On Windows, the `WindowsPowerShell` directory is kept implicitly to avoid breaking PowerShell subprocesses (see commit `842ccb8`). |

The resolved environment is logged at DEBUG and (optionally) dumped to `_build/<variant>/env_isolation.json` for diagnostics.

---

## Diagnostic Hooks

When a setup-related problem needs reproducing, the following files are the first port of call:

| Path | Use |
|---|---|
| `_log/xc-ce-utils-setup/xc-ce-utils_setup.log` | Full ordered transcript of the last `run_setup` |
| `_build/xc-ce-utils-setup/configuration.json` | The configuration as actually loaded (after `!include` + env substitution) |
| `<project_folder>/.xc_ce_setup_state.json` | Persisted phase state — delete to force everything from scratch |
| `<project_folder>/.xc_ce_builder_setup_complete` | First-setup marker with timestamp |
| `_log/xc-ce-utils.jsonl` | Always-on structured JSON Lines log of the current run (truncated per invocation). Each record carries `trace_id` when one is active — set automatically by `variant_executor` to `f"{action}-{variant_alias}"`. Disable with `XC_CE_UTILS_JSON_LOG=0`, relocate with `XC_CE_UTILS_JSON_LOG_PATH`. |

To re-run setup unconditionally without deleting state:

```powershell
.\build.ps1 config setup --force
```

(or any action — `--force` is honoured by the root group and propagated to `EnvironmentSetup`.)
