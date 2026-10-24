# ptk — project tool kit

A configuration-driven project CLI: actions made of steps and step sets,
built-in variant handling, credentials, tool setup, shared base configs,
unified logging and reporting. See [`docs/PLAN.md`](docs/PLAN.md) for the full plan.

**Status:** M1 (configuration meta-model and loader), M2 (variant core), M3
(execution engine, dry run, HTML help), M4 (unified logging) and M5 (generated
CLI, maintainer visibility, VS Code tasks) are done.

```bash
uv sync                     # install with dev dependencies
uv run ptk --help
uv run pytest
uv run ruff check && uv run ruff format --check   # ruff default rules
```

## Configuration files

All ptk files end in `.ptk.yml`:

| File | Purpose |
|------|---------|
| `main.ptk.yml` | entry point: `ptk_version`, project, includes, main settings |
| `*.ptk.yml` | fragments pulled in with `include:` (e.g. `ptk/actions/*.ptk.yml`) |
| `ci.ptk.yml` | applied automatically in CI |
| `local.ptk.yml` | personal overrides (git-ignore it) |
| `maintainers.ptk.yml` | who sees maintainer-only actions |

```yaml
# main.ptk.yml
schema_version: 1
ptk_version: ">=0.1,<0.2"          # ptk refuses to run with another version
project: {name: demo, default_action: build}
include: [ptk/actions/*.ptk.yml]
variants: ptk/variants.ptk.yml       # plain string = include this file here
vars: {preset: "${vh.variant}"}
```

Loading order: `main.ptk.yml` (+ includes) → `ci.ptk.yml` (in CI) →
`local.ptk.yml` → `--set PATH=VALUE`.

* mappings merge deeply, lists are replaced; `!replace`, `!append` and
  `!include file-or-glob` give explicit control
* every value remembers its file and line: `ptk config show --sources`
* unknown keys, unknown names in conditions and `${...}` references are errors
  with `file:line` and "did you mean ..."
* `ptk config schema -o .ptk/schema.json` for editor autocompletion

## Commands available now

```
ptk [-c main.ptk.yml] [--set PATH=VALUE]... [--ci/--no-ci] [-v|-vv]
ptk                                  run the default action (project.default_action)
ptk ACTION [--PARAM VALUE]... [-V VARIANT] [--from STEP] [--to STEP] [--params FILE]
           [-q] [--args-for STEP="ARGS"]... [-- ARGS]
ptk dry-run [ACTION [same options]] [--env]   what would run - nothing is executed
ptk run [ACTION] [-p NAME=VALUE]... [same options]   generic form for scripts and CI
ptk config validate | show [PATH] [--sources] [--format yaml|json] | schema [-o FILE]
ptk variant list [--names] | show [NAME] [--json] [--all] | explain NAME FEATURE | check [NAMES] [--strict]
ptk vscode tasks [--check] [--command "uv run ptk"] [--users-only]
ptk help [--no-open] [-o FILE]       full help as an HTML page, opened in your browser
```

Every action is a command with typed options for its parameters (`ptk build --help`
lists them; `int`, `float`, `choice`, `bool` as `--x/--no-x`, `list` as `a,b`).
Maintainer-only actions are hidden from users and refused if invoked.
Shell completion comes from click: e.g. `eval "$(_PTK_COMPLETE=bash_source ptk)"`.

Exit codes: 0 passed, 1 failed, 2 usage/configuration error, 130 cancelled (Ctrl+C).

## Running actions

```yaml
actions:
  build:
    params:
      jobs: {type: int, default: 8, env: PTK_JOBS}                 # typed default
      toolchain: {default: "${vh.data.toolchain}"}                # per-variant default
    steps:
      - configure: [cmake, --preset, "${vars.preset}"]        # list: no shell
      - compile: "cmake --build --preset ${vars.preset} -j ${params.jobs}"   # string: shell
      - checks:
          parallel: true
          steps:
            - lint: {run: tools/lint.py, python: {uvx: "ruff==0.6.9"}}
            - unit: {run: [pytest, -q], python: {venv: {requirements: tools/req.txt}}, passthrough: true}
            - qac:  {run: tools/qac.bat, when: "COMPONENT_CAMERA", continue_on_error: true}
      - upload: {run: tools/upload.sh, secrets: {TOKEN: artifactory.token}, retries: 2, timeout: 600}
```

* `.bat/.cmd` → `cmd /c`, `.ps1` → `pwsh -File`, `.sh` → `bash`, `.py` → Python via uv
* `python:` `uvx` (tool from PyPI), `venv` (cached in `.ptk/venvs/<hash>`), `project`
  (`uv run --project`), `interpreter: cli` (ptk's own) - nothing is ever activated
* every command gets its own environment: `PTK_*`, `PTK_PARAM_*`, `VH_*`, action/step
  `env`, then secrets; secrets are masked in console, logs and `ptk dry-run`
* working directory: project root; per-step folders `${run.build_dir}`, `${run.reports_dir}`
* `ptk dry-run ACTION` shows the expanded steps, conditions, final commands and where every
  parameter value comes from
* parameter precedence: `-p` > `--params FILE` > `env:` variable > `default:`; defaults can
  be changed per layer (`local.ptk.yml`, `ci.ptk.yml`, `--set`) and may use `${env:..}`,
  `${vars.x}`, `${vh.*}` (per-variant defaults) or `${project.*}`
* `project.default_action` is what plain `ptk` runs

## Workspace layout

```
_builds/<variant>/<action>/<set>/<step>/    build folder per step (${run.build_dir})
_bin/<variant>/                             binaries per variant
_logs/<variant>/<action>/run.log            + <set>/<step>.log, events.jsonl, run.json, _history/
_reports/<variant>/<action>/<set>/<step>/
```

## Architecture

```
src/ptk/
  domain/        config meta-model, tree + merge rules, substitution, expressions,
                 variants (model, rules, conventions), layout
  domain/execution  params, planning, per-command environment, command building
  application/   ports, use cases (LoadProject, ShowConfig, ExportSchema, VariantService,
                 PrepareRun, RunAction, BuildHelp, role)
  adapters/      YAML loader, file source, host environment, subprocess runner,
                 uv Python environments, env secrets, log files, HTML help
  drivers/cli/   rich_click CLI
  bootstrap.py   composition root
```

Dependencies point inwards only; the domain has no I/O.
