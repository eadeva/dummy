# Vendor / Code Generation & Toolbase

Vector DaVinci, EB tresos, IBM DNG export, and Toolbase tool installation.

## `vector_davinci_configure`

- **Source:** [`vendor_steps.py`](../../../../xc_ce_utils/core_engine/steps/vendor_steps.py)

```yaml
davinci_configure:
  type: vector_davinci_configure
  project_file: SW/cfg/davinci/project.dpa
  command: validate
```

## `vector_davinci_generate`

```yaml
davinci_generate:
  type: vector_davinci_generate
  project_file: SW/cfg/davinci/project.dpa
```

## `tresos_configure`

- **Notes:** Inherits config from `variant.get_tresos_conf()` — `workspace`, `projects`, `executable_path` / `tresos_cmd` must be available.

```yaml
tresos_cfg:
  type: tresos_configure
```

## `tresos_generate`

- **Behavior:** File-locks via `executable_path`. Hash-based change detection skips regeneration when inputs are unchanged unless `context.force_gen`.

```yaml
tresos_gen:
  type: tresos_generate
  projects: "BSW,RTE"
```

## `dng_export`

- **Behavior:** Uses `alm_utils.alm_exporter.DNGExporter`. `config_path` is resolved against `repo_root` when relative.

```yaml
dng_pull:
  type: dng_export
  config_path: SW/cfg/dng_export.yml
```

## `tb_installation`

- **Source:** [`tb_steps.py`](../../../../xc_ce_utils/core_engine/steps/tb_steps.py)
- **Behavior:** Calls `add_tool_for_installation(...)` for each entry, then `run_toolbase_update()`. Exports `TB_HOMEDIR/tool/version[/subfolder]` into named env variables.

```yaml
tools:
  type: tb_installation
  env: GW_2WP
  tools:
    tasking-tricore:
      version: 6.3r1
      env_variable:
        TASKING_HOME: ""
    trace32:
      version: 2023.09
      env_variable:
        T32_HOME: ""
        T32_SYS: ""
```

## Category index

| Step type | Description |
|---|---|
| `vector_davinci_configure` | Vector DaVinci Configurator |
| `vector_davinci_generate` | Vector DaVinci code generation |
| `tresos_configure` | EB tresos configuration |
| `tresos_generate` | EB tresos code generation |
| `dng_export` | DOORS Next Generation export |
| `tb_installation` | Install/activate Toolbase tools (Windows) |
