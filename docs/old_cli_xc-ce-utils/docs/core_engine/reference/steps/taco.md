# TACO (Test Selections)

- **Source:** [`taco_steps.py`](../../../../xc_ce_utils/core_engine/steps/taco_steps.py)
- **Category:** Testing

[TACO](https://project-documentation.bosch.com/XC-CE_Methods_and_Tools_documentation/tools/taco.html)
selects test cases from the documentation (`needs.json`) with test selections (`*.tl.yaml`) and
test suites (`*.ts.yaml`), runs them through a test runner and writes one result JSON per run.
XC-CE Utils runs TACO through the project's **TACO adapter**: a small project-owned Python
package that provides the `taco` CLI with the commands `filter`, `unit-tests` and `robotfw` and
holds the project specifics (runners, variants, selection rules).

```text
taco (core)  ->  xcce_taco_helpers (runner base classes)  ->  project adapter (taco CLI)
```

## Setup

- The TACO packages (`taco`, `xcce_taco_helpers`, `elefanto`, `das-metamodel`, `robotframework`)
  are dependencies of XC-CE Utils and installed with it.
- The adapter is installed by the setup phase `taco_adapter` when `main_conf.yml` points to it:

  ```yaml
  TACO:
    adapter_path: tools/taco_project   # folder with the adapter's pyproject.toml
  ```

  It is reinstalled only when its version changes.

## Steps

Each step runs one adapter command from the repository root:

| Step | Adapter command | Purpose |
|---|---|---|
| `taco_filter` | `taco filter` | Resolve a test selection to its test case IDs |
| `taco_ctest` | `taco unit-tests` | Run the selected GoogleTest cases through CTest (`ctest -N` discovery check, then `ctest -R`) |
| `taco_robotfw` | `taco robotfw` | Run the selected Robot Framework test cases |

| Field | Required | Default | Type | Notes |
|---|---|---|---|---|
| `test_list` | **Yes** | — | str | Test selection `.tl.yaml`, relative to the repo root. Wrap it in `$LITERAL{...}`, otherwise the config loader resolves `.yaml` values relative to the action file. `<name>.<variant alias>.tl.yaml` next to it replaces it for that variant |
| `variant` | No | variant alias | str | TACO variant |
| `needs_file` | No | see below | str | `needs.json` with the test cases (repo-relative; wrap in `$LITERAL{...}`). Default: `<action build folder>/needs/needs.json` if a `docascode` step with `builder: needs` created it in the same action, otherwise the adapter's default |
| `output` | No | see below | str | `taco_filter`: result YAML (default `<step reports>/<selection>.yaml`); `taco_ctest` / `taco_robotfw`: output folder (default step reports folder) |
| `build_dir` | No (`taco_ctest`) | action build folder | str | CTest build directory |
| `ecu_artifacts` | No (`taco_robotfw`) | — | str \| list[str] | Glob patterns (repo-relative) of the ECU artifacts; compiled into `ecu_artifacts.json` in the output folder and passed with `--ecu-artifacts` (Robot variable `${ECU_ARTIFACTS}`) |
| `taco_results_dir` | No (`taco_ctest`, `taco_robotfw`) | `_reports/<variant>/taco_results` | str | Collects the result JSONs for the docs (`docascode` `taco_results_dir`) |

**Results.** `taco_ctest` and `taco_robotfw` accept the adapter return codes `0` (all passed)
and `1` (test cases did not pass). Failed or not executed test cases are reported as
`N of M selected test case(s) did not pass: {...}`; set `game_stopper: false` to continue the
action anyway. Both steps write `taco_summary.json` (verdict counts and test case verdicts) into
their output folder, which `test_report_collect` shows as the *Test Selections (TACO)* section.
The result JSONs are collected into `taco_results_dir` even when the run fails.

## Verdicts in the documentation

The `docascode` step parameter `taco_results_dir` points the docs build at the collected result
JSONs; the `verdict_overlay` extension writes each verdict onto its test case need
(`latest_test_verdict`, `latest_report_path`). See
[Docs as Code](../../../modules/docascode.md#taco-integration).

## Example

A needs-only docs build provides the test cases, then a test selection runs:

```yaml
PHASES:
  needs:
    step_type: docascode
    builder: needs              # needs.json only: no Doxygen, no HTML
    docascode_config_folder: build_environment/xc-ce-utils/docascode
  unit_tests:
    step_type: taco_ctest
    test_list: $LITERAL{test/management/test_selections/unit_test_selection.tl.yaml}
    game_stopper: false
  robot:
    step_type: taco_robotfw
    test_list: $LITERAL{test/management/test_selections/taco_hello_world.tl.yaml}
    ecu_artifacts:
      - _builds/$ENV{XC_CE_UTILS_VARIANT_ALIAS}/build/swb/hexmerge/*.hex
```

Run the `doc` action afterwards (with `taco_results_dir`) to see the verdicts.
