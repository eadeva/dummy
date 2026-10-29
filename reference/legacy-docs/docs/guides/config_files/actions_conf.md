# `actions_conf.yml` â€” Action Registry

The action registry maps **action names** to action files. Each entry can be a file reference or an inline action definition. `actions_conf.yml` itself is intentionally tiny â€” the heavy lifting lives in the per-action files.

## Schema

```yaml
# === Defaults applied to every action invocation ===
DEFAULT_PARAMETERS:
  action: build                       # Default action when none is specified on the CLI
  build_type: Release                 # Default build_type (CMake/Make actions)

# === CI-only defaults (deep-merged on top of DEFAULT_PARAMETERS in CI) ===
DEFAULT_PARAMETERS_CX:
  ccache: false

# === Action registry (action name â†’ file reference OR inline dict) ===
ACTIONS:
  build: build.yml                              # Top-level actions live in actions/
  doc: doc.yml
  sca: sca.yml
  sfa: sfa.yml
  oss: oss.yml
  smoke_test: smoke_test.yml

  # Grouped actions â€” paths can be anywhere under config/
  davinci: tools/davinci.yml
  helix:   tools/helix.yml
  tresos:  tools/tresos.yml

  test: tests/test.yml
  debug: debug/debug.yml

  # Maintenance actions
  conan-cache-cleanup: cleanup/conan_cache_cleanup.yml
  remotes-cleanup:     cleanup/remotes_cleanup.yml

  # Inline action (no file reference) â€” fine for very simple ones
  hello:
    description: "Print a banner"
    steps:
      banner:
        type: shell
        command: "echo Hello from {{ PROJECT }}"
```

## Top-Level Keys

| Key | Type | Description |
|---|---|---|
| `ACTIONS` | dict | **Required.** Map of action name â†’ file reference or inline action. |
| `DEFAULT_PARAMETERS` | dict | Defaults applied to every action invocation (merged into the action's own `DEFAULT_PARAMETERS`). |
| `DEFAULT_PARAMETERS_CX` | dict | CI override of `DEFAULT_PARAMETERS`; deep-merged when CI detection succeeds. |

## CLI Surface

Each entry in `ACTIONS` becomes a positional CLI argument:

```powershell
.\build.ps1 -var pl9 build           # action: build
.\build.ps1 -var pl9 doc             # action: doc
.\build.ps1 -var pl9 davinci         # action: davinci (grouped tool action)
```

`DEFAULT_PARAMETERS.action` controls the action used when **no** action is given:

```powershell
.\build.ps1 -var pl9                 # runs the default action (build above)
```

## Discovery & Hot Reload

`ConfigLoader` walks every file reference once at startup. To add a new action:

1. Create the YAML file (`actions/my_action.yml`).
2. Add one line: `my_action: my_action.yml`.

To remove an action: delete or comment out the line. The action disappears from `--help` immediately on next invocation.

## Grouped Actions

Actions can be organised into subdirectories purely for readability â€” there is no hard "group" concept at the registry level:

```yaml
ACTIONS:
  davinci:    tools/davinci.yml
  tresos:     tools/tresos.yml
  helix:      tools/helix.yml
  conan-cache-cleanup: cleanup/conan_cache_cleanup.yml
```

Optionally, action files can declare `action_group: <name>`, which is propagated to CI metadata and to VS Code task labels.

## Minimal Example

```yaml
ACTIONS:
  build:
    steps:
      compile:
        type: cmake_build
```

## See Also

- [Action file anatomy](action_file.md) â€” what goes inside `build.yml`, `doc.yml`, â€¦
- [Step Reference](../../core_engine/reference/step_reference.md)
- [Configuration Guide](../config_guide.md)
