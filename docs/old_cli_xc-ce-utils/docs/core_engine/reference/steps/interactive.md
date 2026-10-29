# Interactive Steps

Steps that prompt the user. In CI these steps use their `cx_default_*` fallback automatically (no prompt).

## `choice`

- **Source:** [`interactive_steps.py`](../../../../xc_ce_utils/core_engine/steps/interactive_steps.py)
- **Behavior:** Presents the keys of `choice_steps` to the user; on CI uses `cx_default_choice` (or `default_choice`). The selected entry is materialised as a nested step via `ExecutionSet` / `StepRegistry`.

```yaml
pick_target:
  type: choice
  description: "Select flashing target"
  default_choice: t32
  cx_default_choice: t32
  choice_steps:
    t32:
      type: t32_flash_hex
      params:
        T32_ID: main
        hex_file: "${APP_HEX}"
    winidea:
      type: winidea_flash_pflash
      params:
        WINIDEA_ID: main
        hex_file: "${APP_HEX}"
```

## `user_input`

- **Behavior:** Prompts for a string; on CI uses `cx_default_value` / `default_value`. Stores the value in an env variable and/or a global variable.
- **Shape:** hybrid — `description`/`default_value`/`cx_default_value` are flat; the store target
  is nested under `params:` (the source docstring says `parameters:`, but the code reads `params`).

```yaml
ask_branch:
  type: user_input
  description: "Branch to deploy"
  default_value: "development"
  cx_default_value: "development"
  params:
    target_env_variable: DEPLOY_BRANCH
    target_global_variable: DEPLOY_BRANCH
```

## Category index

| Step type | Description |
|---|---|
| `choice` | Pick one nested step from a labelled menu |
| `user_input` | Prompt for a string (env / global var) |
