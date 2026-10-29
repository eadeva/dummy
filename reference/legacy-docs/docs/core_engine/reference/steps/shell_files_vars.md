# Shell, Files & Variables

General-purpose steps for running commands, scanning files, and manipulating global variables shared between steps.

```{note}
`shell_run_command` is FLAT. `custom_script` is FLAT too but its own `params` field holds a raw
dict/list passthrough (not named sub-fields). `file_find`, `dir_find`, `file_text_log_scan`,
`variable_add`, `variable_set` are all PARAMS-DICT — nest their fields under `params:`, not
`parameters:` (an inconsistency in some of these steps' own docstrings).
```

## `shell_run_command`

- **Source:** [`shell_steps.py`](../../../../xc_ce_utils/core_engine/steps/shell_steps.py)
- **Base:** `ExecutionStep`

```yaml
print_status:
  type: shell_run_command
  cmd: "git status --short"
  working_dir: "."
  check_output:
    expected_strs: ["nothing to commit"]
    order_relevant: false
```

## `custom_script`

- **Source:** [`shell_steps.py`](../../../../xc_ce_utils/core_engine/steps/shell_steps.py)
- **Base / wrapper:** `WrappedStep` / `script` (`RBScriptRunner`)
- **Behavior:** Dispatches by extension to `.py`, `.ps1`, or `.sh`. `params` (dict or list) is
  flattened into the script's CLI arguments.

```yaml
run_codegen:
  type: custom_script
  path: SW/tools/codegen.py
  params:
    input: SW/specs/api.yaml
    output: SW/generated/
  return_success_codes: [0]
```

## `file_find`

- **Source:** [`file_steps.py`](../../../../xc_ce_utils/core_engine/steps/file_steps.py)
- **Base:** `ExecutionStep`
- **Behavior:** Stores the absolute path of the first match in `global_variables[output_variable]`.

```yaml
find_elf:
  type: file_find
  params:
    regex: ".*\\.elf$"
    path: _bin
    output_variable: APP_ELF
```

## `dir_find`

```yaml
find_reports_dir:
  type: dir_find
  params:
    regex: "^reports$"
    path: _build
    output_variable: REPORTS_DIR
```

## `file_text_log_scan`

```yaml
scan_build_log:
  type: file_text_log_scan
  params:
    file_path: _log/build.log
    expected_strs: ["Build succeeded"]
    order_relevant: false
```

## `variable_add`

- **Source:** [`variable_steps.py`](../../../../xc_ce_utils/core_engine/steps/variable_steps.py)
- **Behavior:** Adds or overwrites entries in `global_variables`.

```yaml
set_vars:
  type: variable_add
  params:
    variables:
      BUILD_ID: "RC1"
      DEPLOY_BRANCH: "main"
```

## `variable_set`

- **Behavior:** Same as `variable_add` but **errors** if the key is missing.

```yaml
update_var:
  type: variable_set
  params:
    variables:
      BUILD_ID: "RC2"   # BUILD_ID must already exist
```

## Category index

| Step type | Description |
|---|---|
| `shell_run_command` | Run a shell command |
| `custom_script` | Run a `.py`/`.ps1`/`.sh` script |
| `file_find` | Find files (regex) — stores first match |
| `dir_find` | Find directories (regex) — stores first match |
| `file_text_log_scan` | Scan text/log files for expected/forbidden strings |
| `variable_add` | Add/overwrite a global variable |
| `variable_set` | Overwrite an existing global variable |
