# CANoe

11 step types share an explicit `config_fields` schema. Resource pool key `canoes` is keyed by `CANOE_ID`. CI forces `headless=True`. CANoe test reports are copied to each step's `_reports` folder.

```{note}
**Shape: PARAMS-DICT.** All fields below are nested under a `params:` mapping, not flat siblings
of `type`.
```

## `canoe_open`  *(game_stopper)*

- **Source:** [`canoe_steps.py`](../../../../xc_ce_utils/core_engine/steps/canoe_steps.py)
- **Fields:** `CANOE_ID` (required), `config_path`, `headless`, `keep_open`
  (all optional besides `CANOE_ID`). Does **not** take `xcp_config_path` or `save_config` —
  those belong to `canoe_load_xcp_config` and `canoe_close` respectively (see below).
- **Version selection:** Configure the desired installation manually with Vector Tool Manager.
  The step launches the registered `CANoe.Application` COM server.

```yaml
canoe_launch:
  type: canoe_open
  params:
    CANOE_ID: main
    config_path: Automation/CANOE/main.cfg
    headless: false
    keep_open: true
```

## `canoe_start_measurement` / `canoe_stop_measurement`

```yaml
canoe_start:
  type: canoe_start_measurement
  params:
    CANOE_ID: main
canoe_stop:
  type: canoe_stop_measurement
  params:
    CANOE_ID: main
```

## `canoe_load_xcp_config`

```yaml
canoe_xcp:
  type: canoe_load_xcp_config
  params:
    CANOE_ID: main
    xcp_config_path: Automation/CANOE/xcp.xml
```

## `canoe_set_sysvar`

```yaml
canoe_set_var:
  type: canoe_set_sysvar
  params:
    CANOE_ID: main
    namespace: Diag
    variable: TesterPresent
    value: 1
```

## `canoe_execute_test_config`

- **Behavior:** Runs vTESTstudio test configurations and copies CANoe report files for unified reporting.

```yaml
canoe_vt:
  type: canoe_execute_test_config
  params:
    CANOE_ID: main
    test_suite: "smoke,regression"
    sw_variant: pl9
    vtest_report: true
```

## `canoe_execute_test_env`

```yaml
canoe_env:
  type: canoe_execute_test_env
  params:
    CANOE_ID: main
    test_environments: "EnvA,EnvB"
    vtest_report: false
```

## `canoe_execute_test_modules`

- **Fields:** `CANOE_ID`, `test_modules` (required), `vtest_report` (optional). Does **not** take
  `test_environments`.

```yaml
canoe_modules:
  type: canoe_execute_test_modules
  params:
    CANOE_ID: main
    test_modules: "Mod1,Mod2"
    vtest_report: false
```

## `canoe_execute_yaml_tests`

- **Required:** `CANOE_ID`, `tests` (non-empty list of folders).
- **Optional:** `test_config` (default `CT`), `mode` (`1` per unit, `2` together; default `1`),
  `vtest_report` (default `false`). Mode `3` is not supported.
- **Behavior:** Recursively discovers `*.vtestunit.yaml`, runs them through the named CANoe test
  configuration, and copies CANoe report files to the step `_reports` folder. XC-CE does not
  generate synthetic canonical or JUnit test cases from CANoe's aggregate COM verdicts.

```yaml
canoe_yaml:
  type: canoe_execute_yaml_tests
  params:
    CANOE_ID: main
    tests:
      - Automation/CANOE/tests/diagnostics
      - Automation/CANOE/tests/routing
    test_config: CT
    mode: 1
    vtest_report: true
```

When `vtest_report` is enabled, the step calls
`%ARTIFACT_CANOE_REPORT_VIEWER%/ReportViewerCli.exe -d <step-reports-folder> -xu`.
Missing tools and conversion failures are warnings; they do not change test verdicts.
When it is disabled, unified reporting imports JUnit-compatible XML produced directly by CANoe.

## `canoe_ini_file`

```yaml
create_canoe_ini:
  type: canoe_ini_file
  params:
    target_path: _builds/canoe/runtime.ini
    sections:
      General:
        Project: GW_2WP
        Coverage: 100%
      Runtime:
        Retries: 3
```

The step creates parent folders and atomically replaces the target. Section and key order and key
case are preserved; entries use `parameter=value` without spaces.

## `canoe_close`

```yaml
canoe_quit:
  type: canoe_close
  params:
    CANOE_ID: main
    save_config: false
```

## Category index

| Step type | Description |
|---|---|
| `canoe_open` *(game_stopper)* | Launch CANoe |
| `canoe_start_measurement` | Start measurement |
| `canoe_stop_measurement` | Stop measurement |
| `canoe_load_xcp_config` | Load XCP config |
| `canoe_set_sysvar` | Set a system variable |
| `canoe_execute_test_config` | Run vTESTstudio configurations |
| `canoe_execute_test_env` | Run CAPL/XML environments |
| `canoe_execute_test_modules` | Run specific test modules |
| `canoe_execute_yaml_tests` | Run YAML vTESTstudio test units |
| `canoe_ini_file` | Generate a CANoe INI file |
| `canoe_close` | Quit CANoe |
