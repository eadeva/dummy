# Steps

This section is the authoritative reference for every step type registered with `StepRegistry`. The page below covers how steps are registered and what the base class consumes; the category pages list every step, its parameters, and a runnable YAML snippet.

```{toctree}
:maxdepth: 1
:caption: Steps by Category

build_wrappers
conan
shell_files_vars
interactive
timers_threads
quality
taco
deploy_reports
elf_binary
t32
winidea
canoe
power
com
network
artifactory
vendor
```

## Registry mechanism

`StepRegistry` (`core_engine/domain/step_registry.py`) maps `step_type` strings to `ExecutionStep` subclasses through a decorator:

```python
from xc_ce_utils.core_engine.domain.step_registry import StepRegistry


@StepRegistry.register("cmake_build")
class CMakeBuildStep(WrappedStep):
    WRAPPER_NAME = "cmake"
    ...


# One class can register multiple step types and override its category
@StepRegistry.register("t32_setup", "t32_close", category="Hardware")
class T32Step(ExecutionStep): ...
```

Category is resolved in order: explicit `category=` argument → `CATEGORY_MAP` lookup → `"Uncategorized"`.

Lookup is exception-safe:

```python
step_class = StepRegistry.get("cmake_build")  # raises ConfigurationError if absent
step = step_class(name, config, context)
```

Each registry entry stores: `step_class`, `category`, `config_fields`, `env_vars`.

## Base-class configuration

`ExecutionStep` / `TestStep` / `WrappedStep` (in `core_engine/steps/base.py`) consume a fixed set of keys before delegating to the step-specific `execute()`:

```yaml
my_step:
  type: cmake_build           # Required — maps to StepRegistry
  game_stopper: true          # Abort run on failure
  non_blocking: false         # Run in a background thread
  execute_if:                 # Conditional — match against global_variables
    SOME_VAR: expected_value
  wait_idle_before: 5         # Seconds to wait before execute()
  wait_idle_after: 0          # Seconds to wait after execute()
  only_variants: [v1]         # Run only for these variants
  omit_variants: [v2]         # Skip for these variants
  variant_overrides:          # Per-variant deep-merge of this step's config
    v1:
      cmake_target: special
```

## Conventions used in the category pages

- **Base class** — one of `ExecutionStep`, `TestStep`, `WrappedStep`.
- **Wrapper** — `WrappedStep` subclasses declare `WRAPPER_NAME` and obtain the wrapper through `self.get_wrapper()`.
- **Resource pool** — `self.resources` (dict of dicts) holds long-lived objects (CANoe apps, T32 sessions, COM ports, SSH clients, threads, timers, power supplies, downloaders, log files).
- **`game_stopper: true`** in a heading — that step is a game-stopper by default; failure aborts the entire run.
- **CI-only** — the step early-returns or behaves differently when `is_running_in_ci()` is `False`.
- **`output_variable`** — when present, the result is stored in `self.global_variables[output_variable]` for downstream steps.
- Paths are workspace-relative unless noted.

## Special-behavior index

| Behavior | Steps |
|---|---|
| `game_stopper: true` by default | `t32_setup`, `canoe_open` |
| CI-only (no-op outside CI) | `deploy`, `oss`, `artifactory_cleanup` |
| CI auto-enables flag | `qac` (`create_baseline` defaults to `is_running_in_ci()`) |
| CI forces `headless=True` | all `winidea_*`, all `canoe_*` |
| Generates JUnit XML automatically | `canoe_execute_test_*`, anything subclassing `TestStep` |
| Writes `global_variables[output_variable]` | `file_find`, `dir_find`, `file_text_log_scan`, `art_download`, `art_download_central`, `bin_compute_file_crc`, `elf_read_symbols`, `elf_list_sections`, `t32_get_state`, `user_input` |

## Resource-pool keys

| Key | Owners |
|---|---|
| `canoes` | `canoe_*` |
| `lauterbachs` | `t32_*` |
| `com_ports` | `com_*` |
| `ssh_connections` | `ssh_*` |
| `winidea` | `winidea_*` |
| `threads` | non-blocking steps + `thread_stop` |
| `timers` | `timer_*`, `wait_idle` |
| `power_supplies` | `power_supply_*`, `voltcraft_*` |
| `artifactory_downloaders` | `art_downloader_setup`, `art_download`, `art_download_central` |
| `log_files` | base class (all steps) |
