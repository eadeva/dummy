# Conan / Package Management

Conan command execution is exposed through a single generic step type: `conan_command`.

The step forwards CLI arguments directly to Conan through the uvx runtime:

`uvx --from <spec> conan <args>`

Runtime execution uses uvx with Conan 2.x only, using the command shape `uvx --from <spec> conan <args>` (default spec: `conan==2.12.0`, configurable via `XC_CE_UTILS_CONAN_UVX_SPEC`).

```{note}
These steps run only when `CONAN_ENABLED` (in `main_conf.yml`) is `true` — its default. Projects that do not use Conan can skip this entire category.
```

```{note}
Conan is invoked via uvx rather than an embedded Conan runtime. Ensure `uvx` is available in `PATH` when running Conan-enabled actions.
```

## `conan_command`

- **Source:** [`conan_steps.py`](../../../../xc_ce_utils/core_engine/steps/conan_steps.py)
- **Base:** `ExecutionStep` — a plain leaf step. There is **no** `WrapperRegistry`/`WrappedStep`
  integration for Conan; the step invokes `uvx` directly.
- **Required config:** `params`

```yaml
conan_list:
  type: conan_command
  params:
    - list
    - "pkg/*"
```

`params` accepts three forms:

1. **List** (recommended) — passed through as-is:

   ```yaml
   conan_list:
     type: conan_command
     params: [list, "pkg/*"]
   ```

2. **String** — split with `shlex.split(..., posix=False)`:

   ```yaml
   conan_graph:
     type: conan_command
     params: graph info conanfile.py
   ```

3. **Dict** — must contain either `command` or `cmd` (value is itself a list or string,
   normalized the same way):

   ```yaml
   conan_install:
     type: conan_command
     params:
       command: install conanfile.py -of conan_install
   ```

Optional fields:

- `operation`: Log operation label used for log file naming (defaults to step name).

### Validation and error handling

`validate()` raises `ConfigurationError` (before execution) for:

- `params` missing entirely — `"Conan command step requires 'params' configuration"`
- `params` empty (empty list, blank string, or dict without a usable command) —
  `"Conan command step requires non-empty 'params'"`
- `params` dict missing both `command` and `cmd` keys —
  `"Conan command step 'params' dict must contain one of: command, cmd"`
- `params` a type other than `list[str]`, `str`, or `dict` —
  `"Conan command step 'params' must be a list[str], string, or dict"`
- List entries that are not non-empty strings —
  `"Conan command step 'params' entries must be non-empty strings"`

At execution time, `ExecutionStepError` is raised with `'uvx executable not found'` if `uvx` is
not resolvable on `PATH` (see `find_uvx()`). A non-zero Conan process exit propagates as a normal
`run_command()` failure (step marked `FAILED`, message captured in the step log/report).

## Category index

- `conan_command`: Execute a generic Conan CLI command via uvx.
