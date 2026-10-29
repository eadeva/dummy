# CANoe

**Package:** `xc_ce_utils.canoe`

Python wrapper for Vector CANoe automation via Windows COM, with test execution and JUnit XML reporting.

---

## Architecture

```text
CanoeApi        (lifecycle, measurement, system variables, diagnostics)
└── CanoeTestApi   (test configurations, environments, modules, XCP)
```

The generic base class handles CANoe application lifecycle (open/close), measurement control, system variable access, and configuration info. The test subclass adds vTESTstudio test configuration execution, CAPL/XML test environment management, individual test module execution, and XCP device configuration.

CANoe installation selection is managed manually through Vector Tool Manager. `CanoeApi` launches
the registered `CANoe.Application` COM server and does not scan or select installed versions.

A standalone `junit_reporter` module generates JUnit XML from structured test results.

---

## CanoeApi Class

Base class wrapping CANoe COM automation for programmatic control.

```python
from xc_ce_utils.canoe.canoe_api import CanoeApi

canoe = CanoeApi()
canoe.open(config_path=r"C:\canoe\project.cfg")
canoe.start_measurement()

# Read/write system variables
value = canoe.get_sysvar_value("MyNamespace", "MyVariable")
canoe.set_sysvar_value("MyNamespace", "MyVariable", 42)

canoe.stop_measurement()
canoe.quit()
```

### Key Methods

| Method | Description |
|---|---|
| `open(config_path="")` | Launch CANoe and optionally load a `.cfg` file |
| `load_configuration(config_path)` | Load a CANoe configuration by path |
| `start_measurement()` | Start CANoe measurement with timeout polling |
| `stop_measurement()` | Stop CANoe measurement with timeout polling |
| `get_sysvar_value(namespace, variable)` | Read a system variable value |
| `set_sysvar_value(namespace, variable, value)` | Write a system variable value |
| `enable_disable_block(block_name, active)` | Toggle a measurement setup block |
| `get_simulation_setup_info()` | Get bus/node/database info |
| `get_write_window_log(lines)` | Read diagnostic write window log |
| `get_configuration_info()` | Get loaded configuration name and path |
| `quit(save_cfg=False)` | Stop measurement, quit CANoe, force-kill fallback |
| `is_connected` (property) | Whether CANoe COM object is active |

### Static Methods

| Method | Description |
|---|---|
| `is_canoe_running()` | Check if CANoe64.exe is in the process list |

---

## CanoeTestApi Class

Test execution capabilities extending `CanoeApi`.

```python
from xc_ce_utils.canoe.canoe_test_api import CanoeTestApi

canoe = CanoeTestApi()
canoe.open(config_path=r"C:\canoe\test_project.cfg")
canoe.start_measurement()

# Execute vTESTstudio test configuration
results = canoe.execute_test_configuration("SmokeTests", sw_variant="Variant_A")

# Execute CAPL/XML test environment
results = canoe.execute_test_environment("IntegrationTests")

# Execute specific test modules
results = canoe.execute_test_modules("Module1,Module2")

canoe.stop_measurement()
canoe.quit()
```

### XCP Configuration

| Method | Description |
|---|---|
| `add_xcp_configuration(xcp_config_path)` | Add an XCP ECU configuration file |
| `remove_all_xcp_devices()` | Remove all XCP devices from the configuration |

### Test Configurations (vTESTstudio)

| Method | Description |
|---|---|
| `get_test_configurations_info()` | Get all test configuration details |
| `create_test_configuration(name)` | Create a new test configuration |
| `add_test_unit(test_unit_path, test_config_id)` | Add `.vtuexe` test unit(s) |
| `execute_test_configuration(test_suite, sw_variant)` | Execute and collect results |
| `discover_yaml_test_units(test_folders)` | Recursively discover `.vtestunit.yaml` files |
| `execute_yaml_tests(test_folders, test_config_name="CT", mode=1)` | Execute YAML test units in mode 1 or 2 |

### Test Environments (CAPL/XML)

| Method | Description |
|---|---|
| `get_test_environments_info()` | Get all test environment details |
| `add_test_environment(test_env_path)` | Add a `.tse` test environment file |
| `create_test_environment(name)` | Create a new test environment |
| `add_xml_test_module(module_path, env_name, components)` | Add XML test module |
| `add_capl_test_module(module_path, env_name)` | Add CAPL test module |
| `execute_test_environment(test_environments)` | Execute and collect results |
| `execute_test_modules(test_module_names)` | Execute specific modules by name |

### Result Dictionary Format

All `execute_*` methods return a dictionary:

```python
{
    "suite_name": "TestSuite",
    "total": 10,
    "passed": 8,
    "failed": 2,
    "other": 0,
    "failed_tests": ["env/module1", "env/module2"],
    "report_path": "C:\\reports\\test.xml",  # or "report_paths": [...]
}
```

---

## JUnit XML Reporter

Generates standard JUnit XML from CANoe test results.

```python
from xc_ce_utils.canoe.junit_reporter import generate_junit_xml

report_path = generate_junit_xml(
    results=results,
    suite_name="CANoe_Integration_Tests",
    output_path="_reports/canoe_tests.xml",
    properties={"variant": "Variant_A", "canoe_id": "CANOE1"},
)
```

The generated XML follows the JUnit schema compatible with CI systems (Jenkins, GitHub Actions), pytest, and the existing GTest JUnit XML parser in xc_ce_utils.

---

## Core Engine Step Types

11 registered step types under the **Testing** category:

| Step Type | Description |
|---|---|
| `canoe_open` | Launch CANoe and optionally load configuration (game stopper) |
| `canoe_start_measurement` | Start CANoe measurement |
| `canoe_stop_measurement` | Stop CANoe measurement |
| `canoe_load_xcp_config` | Load XCP configuration file |
| `canoe_set_sysvar` | Set a system variable value |
| `canoe_execute_test_config` | Execute vTESTstudio test config(s) + JUnit XML |
| `canoe_execute_test_env` | Execute CAPL/XML test environment(s) + JUnit XML |
| `canoe_execute_test_modules` | Execute specific test module(s) + JUnit XML |
| `canoe_execute_yaml_tests` | Execute YAML vTESTstudio test units |
| `canoe_ini_file` | Generate an INI file from section mappings |
| `canoe_close` | Quit CANoe and remove from resource pool |

### Example YAML Configuration

```yaml
open_canoe:
  type: canoe_open
  params:
    CANOE_ID: CANOE1
    config_path: "C:\\canoe\\test_project.cfg"

start_measurement:
  type: canoe_start_measurement
  params:
    CANOE_ID: CANOE1

run_tests:
  type: canoe_execute_test_config
  params:
    CANOE_ID: CANOE1
    test_suite: "SmokeTests,RegressionTests"
    sw_variant: "Variant_A"
    vtest_report: true

run_yaml_tests:
  type: canoe_execute_yaml_tests
  params:
    CANOE_ID: CANOE1
    tests:
      - "Automation/CANOE/tests"
    test_config: CT
    mode: 1

write_ini:
  type: canoe_ini_file
  params:
    target_path: "_builds/canoe/runtime.ini"
    sections:
      General:
        Project: GW_2WP

stop_measurement:
  type: canoe_stop_measurement
  params:
    CANOE_ID: CANOE1

close_canoe:
  type: canoe_close
  parameters:
    CANOE_ID: CANOE1
```

---

## CANoe TBE Reference

Detailed reference documentation for the CANoe Test Bench Edition and COM interface extracted from the Vector CANoe Family 18 help system:

| Document | Description |
|---|---|
| [canoe_tbe/overview.md](../external_refs/canoe_tbe/overview.md) | Product editions, installation paths, registry, feature matrix |
| [canoe_tbe/com_interface.md](../external_refs/canoe_tbe/com_interface.md) | COM object reference — Application, Measurement, Configuration, System |
| [canoe_tbe/com_programming.md](../external_refs/canoe_tbe/com_programming.md) | COM programming guide — scripts, events, tips & tricks |
| [canoe_tbe/command_line.md](../external_refs/canoe_tbe/command_line.md) | Command-line parameters for CANoe64.exe and CANoeTBE.exe |
| [canoe_tbe/automation.md](../external_refs/canoe_tbe/automation.md) | Vector Tool Manager and COM launch contract |
| [canoe_tbe/licensing.md](../external_refs/canoe_tbe/licensing.md) | Licensing technology, TBE-only machines, View Only mode |

---

## Dependencies

- **pywin32** (`win32com.client`, `pythoncom`) — COM automation, lazy-imported
- **Windows only** — CANoe is a Windows application

Install via extras:

```bash
pip install xc-ce-utils[canoe]
```

---

## See Also

- [WinIDEA](winidea.md) — iSYSTEM winIDEA debugging and flashing
- [Power Supply](powersupply.md) — ECU power cycling before flash
- [COM I/O Handler](com_io_handler.md) — Serial communication
