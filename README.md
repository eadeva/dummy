# ptk — project tool kit

A configuration-driven project CLI: actions made of steps and step sets,
built-in variant handling, credentials, tool setup, shared base configs,
unified logging and reporting. See [`docs/PLAN.md`](docs/PLAN.md) for the full plan.

**Status:** M1 (configuration meta-model and loader), M2 (variant core), M3
(execution engine, dry run, HTML help), M4 (unified logging), M5 (generated
CLI, maintainer visibility, VS Code tasks), M6 (credentials), M7 (reporting), M8 (shared configs) and M9 (tools,
setup, doctor, installers) are done. M10 adds a runnable offline quickstart, Sphinx documentation with a generated
configuration reference, eleven authoring skills and Linux/Windows CI.
See the plan for remaining features outside this milestone.

```bash
uv sync                     # install with dev dependencies
uv run ptk --help
uv run pytest
uv run ruff check && uv run ruff format --check   # ruff default rules
```

## Create a project

```bash
ptk setup init my-project --dry-run
ptk setup init my-project
cd my-project
ptk hello
```

Existing configuration and `.gitignore` files are preserved.

## Runnable quickstart

From the repository root:

```bash
uv sync
uv run ptk -c examples/quickstart/main.ptk.yml dry-run build
uv run ptk -c examples/quickstart/main.ptk.yml build -V debug
uv run ptk -c examples/quickstart/main.ptk.yml build -V release
```

This example runs without compilers or credentials and writes logs and reports
inside `examples/quickstart`. The existing firmware demo contains placeholders
and is intended for configuration exploration and dry runs.

Build the [documentation](docs/index.rst):

```bash
uv sync --group docs
uv run sphinx-build -W --keep-going -b html docs docs/_build/html
```

## Tools

```yaml
tools:
  cmake: {version: ">=3.28,<4", check: cmake --version,
          choco: {package: cmake, version: "3.30.2"}, uv_tool: "cmake==3.30.2"}
actions:
  build: {requires_tools: [cmake], steps: [...]}
```

Runs check `requires_tools` first; `ptk setup install` (or `ptk build --setup`) installs what is
missing - Chocolatey on Windows, `uv tool`, sha256-verified downloads, apt/dnf only with
`--allow-system`. `ptk setup doctor` diagnoses a machine; `ptk setup self` gets it ready.
Install ptk itself with `install/install.sh` or `install/install.ps1`.

## Shared configs

```yaml
configs:
  pre-commit:   {overlay: ptk/configs/pre-commit.overlay.yaml}
  ruff:         {}
  clang-format: {overlay: ptk/configs/clang-format.overlay.yaml}
  clang-tidy:   {overlay: ptk/configs/clang-tidy.overlay.yaml}
  clangd:       {}
```

`ptk setup configs sync` merges ptk's base configs with your overlays into `.pre-commit-config.yaml`,
`.clang-format`, `.clang-tidy`, `.clangd` and `ruff-base.toml` (your `ruff.toml` extends it).
Commit them; `ptk setup configs check` in CI catches stale files.

## Reports

After every run ptk writes `_reports/<variant>/<action>/report.*` (`reporting.formats`:
json, junit, html, markdown, github). Steps contribute tool results by writing them to
`$PTK_STEP_REPORTS_DIR` - JUnit, SARIF and Cobertura are picked up automatically - or
with `uses: report.import`. The HTML report shows what failed and a timeline of all
steps; `ptk report open` opens it, `ptk report export --run ID` rebuilds older ones.

## Credentials

```yaml
credentials:
  artifactory:
    fields: [user, token]
    env: {token: ARTIFACTORY_TOKEN}          # CI
    gopass: {path: team/artifactory}         # optional
    # Optional test: use a helper that reads secrets from its environment.
```

Looked up in order `env -> keyring -> gopass -> vault -> prompt` (configurable per
credential). `ptk setup creds set artifactory token` stores a value (typed hidden); the
built-in vault is an AES-GCM file protected by a master password - no external tool
needed. Steps get secrets only as environment variables (`secrets: {TOKEN: artifactory.token}`),
and ptk masks them in its execution output. Child programs must not expand them
into command-line arguments or write them to report input files. keyring support: `uv tool install "ptk[keyring]"`.

## Configuration files

All ptk files end in `.ptk.yml`:

| File | Purpose |
|------|---------|
| `main.ptk.yml` | entry point: `ptk_version`, project, includes, main settings |
| `*.ptk.yml` | fragments pulled in with `include:` (e.g. `ptk/actions/*.ptk.yml`) |
| `cx.ptk.yml` | applied automatically in CI |
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

Loading order: `main.ptk.yml` (+ includes) → `cx.ptk.yml` (in CI) →
`local.ptk.yml` → `--set PATH=VALUE`.

* mappings merge deeply, lists are replaced; `!replace`, `!append` and
  `!include file-or-glob` give explicit control
* every value remembers its file and line: `ptk setup config show --sources`
* unknown keys, unknown names in conditions and `${...}` references are errors
  with `file:line` and "did you mean ..."
* `ptk setup config schema -o .ptk/schema.json` for editor autocompletion

## Commands available now

```
ptk [-c main.ptk.yml] [--set PATH=VALUE]... [--ci/--no-ci] [-v|-vv]
ptk                                  run the default action (project.default_action)
ptk ACTION [--PARAM VALUE]... [-V VARIANT] [--from STEP] [--to STEP] [--params FILE]
           [-q] [--args-for STEP="ARGS"]... [-- ARGS]
ptk dry-run [ACTION [same options]] [--env]   what would run - nothing is executed
ptk run [ACTION] [-p NAME=VALUE]... [same options]   generic form for scripts and CI
ptk setup config validate | show [PATH] [--sources] [--format yaml|json] | schema [-o FILE]
ptk variant list [--names] | show [NAME] [--json] [--all] | explain NAME FEATURE | check [NAMES] [--strict]
ptk setup vscode tasks [--check] [--command "uv run ptk"] [--users-only]
ptk setup creds setup [--vault] | set NAME [FIELD] [--store S] | list | test NAME | remove NAME
ptk setup configs sync [NAMES] [--diff] | check [NAMES]
ptk setup [--action A]... [--dry-run] [--allow-system] | ptk setup doctor | ptk setup self [--tools]
ptk report export [ACTION] [-V v] [--run ID] [-f FORMAT]... | open [ACTION] [--run ID]
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
  be changed per layer (`local.ptk.yml`, `cx.ptk.yml`, `--set`) and may use `${env:..}`,
  `${vars.x}`, `${vh.*}` (per-variant defaults) or `${project.*}`
* `project.default_action` is what plain `ptk` runs

## Workspace layout

```
_builds/<variant>/<action>/<set>/<step>/    build folder per step (${run.build_dir})
_bin/<variant>/                             binaries per variant
_logs/<variant>/<action>/run.log            + <set>/<step>.log, events.jsonl, run.json, _history/
_reports/<variant>/<action>/report.{json,xml,html,md} + <set>/<step>/ (tool results)
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

### Migration, background jobs and variant editing

- `ptk setup migrate old-config.yaml --dry-run` previews supported legacy conversion.
- `background: true` lets a finite `run` step overlap subsequent steps; PTK waits at
  the containing group's end and includes failures in the report.
- `ptk variant gui` opens an optional Tk YAML editor with validation and export to
  a new standalone project file. A graphical desktop and Python Tk support are needed.

See [M11 features and limitations](docs/m11.rst) for migration coverage, process
lifecycle and the `ptk.variant_gui` editor plugin interface.
