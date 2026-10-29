# WinIDEA / iSYSTEM

All steps share an explicit `config_fields` schema (in source). CI forces `headless=True`. Sessions live in `self.resources["winidea"]` keyed by `WINIDEA_ID`.

```{note}
**Shape: PARAMS-DICT.** All fields below are nested under a `params:` mapping, not flat siblings
of `type`. There are exactly 14 registered `winidea_*` types — several types mentioned in an
earlier version of this page (`winidea_run`, `winidea_stop`, `winidea_attach`, `winidea_program`,
`winidea_prepare`, `winidea_set_watch`, `winidea_read_watch`) do **not exist** and have been
removed from this page.
```

## `winidea_setup`

- **Source:** [`winidea_steps.py`](../../../../xc_ce_utils/core_engine/steps/winidea_steps.py)

```yaml
winidea_open:
  type: winidea_setup
  params:
    WINIDEA_ID: main
    device: TC397
    emulator_type: iC5000
    com_mode: usb
    winidea_dir: "C:/Program Files/iSYSTEM/winIDEA"
    workspace_dir: SW/winidea
    sym_path: "${APP_ELF}"
    headless: false
    keep_open: true
    connect_timeout: 30
    cores: { "0": { watch_conf: SW/winidea/core0_watches.yml } }
    default_core: "0"
    cores_to_debug: "0,1"
```

`workspace_file` (path to an existing `.xjrf`) is an alternative to `workspace_dir` — when set it
takes precedence and the workspace is opened as-is instead of being created from scratch.

## `winidea_configure_session`

```yaml
winidea_session:
  type: winidea_configure_session
  params:
    WINIDEA_ID: main
    program_files: ["_bin/firmware.hex"]
    symbol_files:
      app0: "${APP_ELF}"
    use_sym_for_pgm: false
    preset_pc:
      mode: entry_point
    session_actions: [reset, prepare, program, attach, run]
    watch_conf: SW/winidea/watches.yml
```

`preset_pc.mode` is one of `none` / `entry_point` / `address` (with an optional `symbol` key).
`watch_conf` (external YAML file) takes precedence over the inline `watch` dict if both are given.

## `winidea_flash_pflash` / `winidea_flash_dflash` / `winidea_flash_ucb` / `winidea_flash_pflash_dflash` / `winidea_flash_all`

- **Notes:** `verify` (bool, optional, default `true`) runs `program_verify` after programming;
  disable it if `get_status` crashes on your target.

```yaml
winidea_flash:
  type: winidea_flash_pflash
  params:
    WINIDEA_ID: main
    hex_file: _bin/firmware.hex
    verify: true
```

## `winidea_load_symbols`

```yaml
load_symbols:
  type: winidea_load_symbols
  params:
    WINIDEA_ID: main
    elf_file: "${APP_ELF}"
    source_remap: "C:/build=D:/src"
```

## `winidea_read_variables`

```yaml
read_vars:
  type: winidea_read_variables
  params:
    WINIDEA_ID: main
    expressions: ["my_global_counter", "app_state"]
    core: 0
```

## `winidea_check_counters`

```yaml
check_counters:
  type: winidea_check_counters
  params:
    WINIDEA_ID: main
    counters: ["idle_loop_count"]
    interval: 1.0
    nr_of_repetitions: 3
```

## `winidea_verify_variables`

```yaml
verify_vars:
  type: winidea_verify_variables
  params:
    WINIDEA_ID: main
    variables:
      app_state: 1
      error_count: 0
```

## `winidea_get_cpu_status`

```yaml
cpu_status:
  type: winidea_get_cpu_status
  params:
    WINIDEA_ID: main
```

## `winidea_reset` / `winidea_close`

```yaml
winidea_reset_target:
  type: winidea_reset
  params:
    WINIDEA_ID: main
```

`winidea_close` removes the session from the resource pool (same single `WINIDEA_ID` field).

## Category index

| Step type | Description |
|---|---|
| `winidea_setup` | Connect to WinIDEA |
| `winidea_configure_session` | Configure session (program/symbols/watch/PC preset) |
| `winidea_flash_pflash` | Flash PFLASH |
| `winidea_flash_dflash` | Flash DFLASH (FEE) |
| `winidea_flash_ucb` | Flash UCB |
| `winidea_flash_pflash_dflash` | Flash PFLASH + DFLASH (UCB skipped) |
| `winidea_flash_all` | Flash a merged PFLASH+DFLASH+UCB hex |
| `winidea_load_symbols` | Load ELF symbols on all cores |
| `winidea_read_variables` | Evaluate C-syntax expressions on target |
| `winidea_check_counters` | Poll numeric counters over several cycles |
| `winidea_verify_variables` | Assert variable/expression values |
| `winidea_get_cpu_status` | Query CPU status |
| `winidea_reset` | Reset target |
| `winidea_close` | Disconnect WinIDEA |
