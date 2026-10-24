# ptk — Implementation Plan

> **ptk** (*project tool kit*): a generic, configuration-driven project CLI.
> All configuration files end in `.ptk.yml`: entry point `main.ptk.yml` (ptk version + main fields),
> fragments `*.ptk.yml`, layers `ci.ptk.yml` and `local.ptk.yml`, and `maintainers.ptk.yml`.
> Workspace folders: `_builds/`, `_bin/`, `_logs/`, `_reports/` (structured by variant / action / step).

One CLI that every project can use: declarative actions made of steps and step
sets, built-in variant handling, credentials, tool setup, shared base configs,
unified logging and reporting.

---

## 0. Goals and principles

| Goal | Meaning |
|------|---------|
| **Generic** | No project-specific code in the core. Projects describe *what* to run in YAML; domain specifics come as plugins. |
| **User-friendly configuration** | Short forms, good defaults, strict validation with "did you mean …", `file:line` in every error, JSON Schema for editor autocompletion. |
| **Reproducible** | Every command runs with an explicit environment; the CLI process is never mutated; reports record what ran, with which values and from where. |
| **Safe by default** | Secrets never on command lines or in logs; unknown names are errors; no silent fallbacks. |
| **Testable** | Clean Architecture; every use case runs against in-memory fakes. |

**Targets:** Python **3.12+**, **Windows and Linux** (Linux also headless),
**uv** as Python manager (installed by `ptk self-setup` if missing).
No frozen executable.

---

## 1. Architecture (Clean Architecture)

```
src/ptk/
├── domain/                     pure model + rules — no I/O, no frameworks except pydantic
│   ├── config/                 meta-model: Project, Action, Step, StepSet, Param, Tool, ...
│   ├── variants/               components, features, variants, expressions, resolver
│   ├── execution/              run model: RunPlan, StepResult, Status, Event
│   ├── credentials/            SecretRef, CredentialSpec (never secret values)
│   ├── tools/                  ToolSpec, version ranges
│   └── shared_configs/         merge rules for base + overlay
├── application/
│   ├── ports.py                ConfigSource, ProcessRunner, PythonEnvManager, SecretProvider,
│   │                           ToolInstaller, LogSink, ReportExporter, ReportContributor,
│   │                           FileSystem, Clock, Prompt
│   └── use_cases/              LoadConfig, ValidateConfig, PlanAction, RunAction,
│                               ResolveVariant, ExplainFeature, CheckVariants,
│                               ResolveSecret, StoreSecret, TestCredential,
│                               CheckTools, EnsureTools, SelfSetup,
│                               SyncSharedConfigs, CheckSharedConfigs, BuildReport
├── adapters/
│   ├── config/                 YAML loader: include, overlays, tags, provenance, substitution
│   ├── process/                subprocess runner (streaming, timeouts, process groups)
│   ├── python_env/             uv: uvx, cached venvs, uv run, python install
│   ├── credentials/            env, gopass, vault (AES-GCM), prompt
│   ├── tools/                  chocolatey, uv-tool, download, apt/dnf (opt-in)
│   ├── logging/                rich console, per-step files, events.jsonl
│   ├── reporting/              json, junit, html, markdown, github-summary + contributors
│   └── shared_configs/         renderers: pre-commit, ruff, clang-format, clang-tidy, clangd
├── drivers/
│   ├── cli/                    rich_click; commands generated from the configuration
│   └── gui/                    optional variant editor (plugin)
├── resources/                  base configs, JSON Schema, `ptk init` templates, installers
└── bootstrap.py                composition root — the only place that wires adapters
```

**Rules**

- Dependencies point inwards only (`drivers → application → domain`; adapters implement ports).
- Drivers translate input/output and call use cases — nothing else.
- Plugins register via entry points: `ptk.steps`, `ptk.reporters`,
  `ptk.report_contributors`, `ptk.installers`, `ptk.secret_providers`,
  `ptk.generators`.

---

## 2. Main point 1 — Meta-model of the CLI configuration

### 2.1 Elements

| Element | Purpose |
|---------|---------|
| `project` | name, description, default action, default variant |
| `include` | further files / globs merged into the configuration |
| `vars` | reusable values (`${vars.build_dir}`) |
| `environment` | isolation rules: variables and PATH entries kept, added, removed |
| `tools` | tools with version range, check command, install sources per OS |
| `credentials` | named credentials with provider chain |
| `variants` | product line: components, features, variants (inline or file reference) |
| `actions` | CLI commands: params, required tools, steps |
| `configs` | shared base configs and project overlays (pre-commit, ruff, clang-*) |
| `logging` | console style, run directory, retention |
| `reporting` | formats, output dir, contributors |
| `plugins` | extra plugin packages to load / options |

### 2.2 Loading pipeline

```
main.ptk.yml               ptk_version, project, include, main settings
  → include: [...]            merged in order (files or globs)
  → ci.ptk.yml              applied automatically in CI
  → local.ptk.yml           personal overrides (git-ignored)
  → --set key=value           command line
  → validate (pydantic, extra=forbid, suggestions)
  → late substitution         just before a step runs
```

- **Merge rules:** mappings merge deeply, lists replace.
  Tags: `!replace` (replace whole mapping), `!append` (append to list),
  `!include file.yaml` (insert a file at this point).
- **Provenance:** every value knows file and line → `ptk config show --sources`,
  errors as `main.ptk.yml:42: actions.build.params.jobs: expected int`.
- **Substitution** (one syntax, unknown names are errors):

  ```
  ${env:NAME}  ${env:NAME:-default}  ${vars.x}  ${params.x}
  ${vh.variant}  ${vh.features.X}  ${secret:name.field}  ${project.root}  ${run.dir}
  ```

  `$${...}` escapes. Values are typed; secrets are masked wherever printed.

### 2.3 User-friendliness

- Short forms: `run: "cmake --build ."` instead of a full mapping.
- Defaults everywhere (working dir = project root, `continue_on_error: false`, ...).
- `ptk init` scaffolds a project; `ptk plan <action>` shows the expanded step
  tree with evaluated conditions before running anything.
- `ptk config schema` exports JSON Schema (VS Code YAML autocompletion).
- `ptk config validate` for CI; `ptk config show [--sources] [path]`.

### 2.4 Example

```yaml
schema_version: 1
project: {name: demo, default_action: build}
include: [ptk/actions/*.yaml]
variants: ptk/variants.yaml

vars:
  build_dir: build/${vh.variant}

environment:
  keep: [JAVA_HOME]
  path_prepend: [C:/Tools/bin]

tools:
  cmake: {version: ">=3.28", check: "cmake --version", choco: cmake}
  ninja: {version: ">=1.11", check: "ninja --version", choco: ninja, uv_tool: ninja}

credentials:
  artifactory:
    providers: [env, gopass, vault, prompt]
    env: {user: ARTIFACTORY_USER, token: ARTIFACTORY_TOKEN}
    gopass: {path: work/artifactory}

actions:
  build:
    help: Build the firmware
    requires_tools: [cmake, ninja]
    params:
      build_type: {type: choice, choices: [Debug, Release], default: Release, help: Build type}
      jobs:       {type: int, default: 8, help: Parallel jobs}
    steps:
      - configure:
          run: [cmake, --preset, "${vh.variant}", "-DCMAKE_BUILD_TYPE=${params.build_type}"]
      - compile:
          run: [cmake, --build, --preset, "${vh.variant}", -j, "${params.jobs}"]
      - checks:
          parallel: true
          steps:
            - lint: {run: tools/lint.py, python: {uvx: "ruff==0.6.9"}}
            - qac:  {run: tools/qac.bat, when: "COMPONENT_CAMERA"}
            - gen:  {uses: variant.generate, with: {generators: [cmake]}}
```

---

## 3. Main point 2 — Variant handler

Reuse the core of `variant_handler` (already built and tested), trimmed for the CLI:

- **Model:** components, features (`bool`, `int`, `string`, `enum`), variants with
  inheritance (`extends`), abstract variants, aliases.
- **Rules:** `depends_on`, `requires`, `conflicts`, project constraints — same safe
  expression language everywhere.
- **Resolution with sources:** every value knows whether it is a default, set by
  which variant layer, forced off by a dependency, or inactive.
- **Simplifications for users:**
  - small product lines inline in `main.ptk.yml`, larger ones in separate files
  - matrix levels become enum features (`PLATFORM: [tc397, tc399]`)
  - free-form `data:` merged through inheritance (e.g. Conan requirements)
- **Integration:**
  - `when:` on steps (replaces `execute_if`, `only_variants`, `omit_variants`)
  - `${vh.*}` substitution; `VH_*` (and optionally legacy `BO_*`) env vars per command
  - `--variant <name|alias>[,...]`, `--all-variants`
- **Commands:** `ptk variant list | show | explain | check | set | new | gui`.
- **Generators** (header, CMake, Bazel, Make, Yocto, Robot, Sphinx) as plugin package;
  step `uses: variant.generate`.

---

## 4. Main point 3 — Credential handler

### 4.1 Provider chain

| Provider | Where | Notes |
|----------|-------|-------|
| `env` | CI | names configured per credential |
| `gopass` | Windows, headless Linux | `gopass show -o <path>` / `gopass insert`; recommend **age** backend (no gpg-agent/pinentry); team sharing via git |
| `vault` | everywhere, no external tool | AES-GCM file in the user's config dir, key from master password (scrypt); unlocked once per session |
| `prompt` | interactive only | never in CI |

First provider returning a value wins. More providers (e.g. Windows Credential
Manager, HashiCorp Vault) as plugins.

### 4.2 Commands

`ptk creds setup` (detect gopass, guide `gopass setup --crypto age`, or create vault) ·
`ptk creds set <name>` · `ptk creds list` (which provider supplies what — never values) ·
`ptk creds test <name>` (optional check command per credential) · `ptk creds remove <name>`.

### 4.3 Rules

- Secrets reach commands only as environment variables of that single step —
  never as arguments (visible in process lists), never written unencrypted.
- Masked in console, log files, events, reports and `ptk plan`.
- Access tokens preferred over passwords; expiry warnings when known.

---

## 5. Main point 4 — Actions, step sets, steps

### 5.1 Concepts

- **Action** — a CLI command: `help`, `params`, `requires_tools`, `steps`.
  Top-level steps are the phases for `--from` / `--to`.
- **Step** — exactly one of:
  - `run:` a command or script
  - `uses:` + `with:` a built-in or plugin step
  - `steps:` a **step set** (nestable) with `parallel: true|false`
- **Controls on every step:** `when`, `continue_on_error`, `timeout`, `retries`,
  `cwd`, `env`, `passthrough`, `title`, `report: false`.

### 5.2 Running commands and scripts

| Input | Executed as |
|-------|-------------|
| list `[cmd, arg, ...]` | directly, no shell (recommended) |
| string | through the shell (`cmd.exe` / `/bin/sh`), values quoted |
| `*.bat`, `*.cmd` | `cmd /c` |
| `*.ps1` | `pwsh`/`powershell -NoProfile -ExecutionPolicy Bypass -File` |
| `*.sh` | `bash` |
| `*.py` | Python via uv (below) |

Output is streamed live (prefixed with the step name in parallel sets) and
written to the step's log file. Ctrl+C terminates the whole process tree.

### 5.3 Python via uv (uv is the Python manager)

```yaml
python: {uvx: "ruff==0.6.9"}                                    # tool from PyPI
python: {venv: {requirements: tools/requirements.txt, python: "3.12"}}
python: {project: tools/myproj}                                 # uv run --project
python: {interpreter: cli}                                      # ptk's own environment
```

- `venv` environments are cached under `.ptk/venvs/<hash of python + requirements>`,
  created with `uv venv` + `uv pip install`; uv installs the Python version if needed.
- No activation, no "switching back": each command gets the interpreter and
  environment it needs; ptk's own process is untouched.

### 5.4 Environment per command

Built from: isolation rules → action/step `env` → params (`PTK_PARAM_*`) →
variant (`VH_*`) → secrets of that step. Parallel step sets are therefore safe.

### 5.5 Parameters

- Declared per action → real rich_click options (shown in `--help`, typed, validated).
- `--set key=value` for scripts; `--params file.yaml`; `-- ...` passed to steps with
  `passthrough: true` (if several in range: `--args-for <step>="..."`).
- Precedence: CLI > params file > declared env var > default.
  Final values and their sources go into the report.

### 5.6 Built-in steps (`uses:`)

`variant.generate` · `configs.sync` · `tools.ensure` · `report.import` (JUnit, SARIF,
Cobertura, ...) · `files.copy` / `files.clean` · `wait` · `echo`.

---

## 5a. Workspace layout

```
_builds/<variant>/<action>/<set>/<step>/    working directory per step  ${run.build_dir}
_bin/<variant>/                             binaries per variant        ${run.bin_dir}
_logs/<variant>/<action>/run.log            whole run; <set>/<step>.log per step
_reports/<variant>/<action>/<set>/<step>/   reports per step            ${run.reports_dir}
```

Without variants the variant level is `default`. Root and folder names are
configurable (`layout:`). Previous runs are archived per variant/action
(`logging.keep_history`).

## 6. Main point 5 — Unified logging

- One logging facade (stdlib `logging` + rich), configured once by the CLI.
- **Logs** follow the workspace layout (5a):
  - `_logs/<variant>/<action>/run.log` — everything
  - `_logs/<variant>/<action>/<set>/<step>.log` — one file per step (command line, env diff, output, exit code)
  - `_logs/<variant>/<action>/events.jsonl` — structured events (run/step started/finished, warning, output)
- Console: compact live view; `-v` debug, `-vv` trace; `--quiet` for CI.
- Secrets masked everywhere; previous runs archived (`logging.keep_history`).

---

## 7. Main point 6 — Unified reporting

- **Run model** (domain): action, variant snapshot, params with sources, tool
  versions, sanitised environment summary, step tree with status, duration,
  exit code, log links, attachments.
- Built from `events.jsonl` → the report can be regenerated after the fact.
- **Exporters:** console summary · JSON (canonical) · JUnit XML · single-file HTML ·
  Markdown · GitHub step summary.
- **Contributors (plugins):** import tool results into the report — JUnit, SARIF,
  Cobertura; later project-specific formats (QAC, CANoe, SBOM, ...).
- Commands: `ptk report open [run]` · `ptk report export --format html`.

---

## 8. Main point 7 — Shared base configs (projects can override)

### 8.1 Principle

ptk ships **versioned base configs** in `resources/configs/`. A project adds an
**overlay**; `ptk configs sync` produces the effective file. Generated files carry
a header ("generated by ptk — edit the overlay"). `ptk configs check` fails in CI
when the effective file is out of date.

```yaml
configs:
  pre-commit:   {overlay: ptk/configs/pre-commit.overlay.yaml}
  ruff:         {overlay: ptk/configs/ruff.toml}
  clang-format: {overlay: ptk/configs/clang-format.overlay.yaml}
  clang-tidy:   {overlay: ptk/configs/clang-tidy.overlay.yaml}
  clangd:       {}
```

### 8.2 Per tool

| Config | Strategy | Output |
|--------|----------|--------|
| **a) pre-commit** | generated: base hooks + overlay merged by repo URL + hook id; overlay can add, change (`args`, `files`, `exclude`) or disable hooks; `ptk self-setup` installs the hooks | `.pre-commit-config.yaml` |
| **b) ruff** | native `extend`: base shipped to `.ptk/configs/ruff-base.toml`, project `ruff.toml` contains `extend = ".ptk/configs/ruff-base.toml"` plus overrides | `ruff.toml` (project-owned) |
| **c) clang-format** | generated: base YAML + overlay, same merge rules as the config loader | `.clang-format` |
| **c) clang-tidy** | generated: `Checks` combined (base + overlay, `-check` removes), `CheckOptions` merged by key | `.clang-tidy` |
| **c) clangd** | generated: base + overlay | `.clangd` |

Base configs are versioned with ptk; upgrading ptk shows a diff of the
effective files (`ptk configs sync --diff`).

---

## 9. Main point 8 — Tool installation, Chocolatey, self-setup

### 9.1 Tool model

```yaml
tools:
  cmake:
    version: ">=3.28,<4"
    check: "cmake --version"          # version parsed from output (regex configurable)
    choco: {package: cmake, version: "3.30.2"}
    linux: {uv_tool: cmake}           # or download / apt / dnf (opt-in)
  clang-format:
    version: "==18.*"
    check: "clang-format --version"
    choco: {package: llvm, version: "18.1.8"}
    linux: {download: {url: "...", sha256: "..."}}
```

### 9.2 Behaviour

- Actions declare `requires_tools`. Before a run ptk checks versions and reports
  missing / wrong ones; `--setup` installs them automatically.
- `ptk setup [--action build] [--dry-run]` — install tools for all or one action.
- Installers: **Chocolatey** (Windows), uv tool, download (sha256 verified,
  into the user's tool dir), apt/dnf only when explicitly allowed.
- **Chocolatey provider:** bootstraps Chocolatey if missing (official script,
  needs admin), pins versions, logs into the report; without admin rights it
  explains and suggests user-level alternatives.

### 9.3 Self-setup and installers

- `install.ps1` / `install.sh`: install uv if missing, then `uv tool install ptk`.
- `ptk self-setup`: verifies uv, Python, git; installs project tools
  (optional), syncs shared configs, installs pre-commit hooks, checks credentials.
- `ptk doctor`: diagnoses the environment (versions, PATH, credentials, configs).

---

## 9a. VS Code tasks

- `ptk vscode tasks` creates or updates `.vscode/tasks.json` with one task per
  visible action (label `ptk: <action>`), a `pickString` input for the variant and
  inputs for declared choice parameters.
- Existing user tasks are kept: ptk only manages entries it created (marked in
  `detail`), so re-running the command is safe; `--check` reports drift (CI).
- Maintainer-only actions appear only for maintainers (see 9b).

## 9b. Maintainer-only commands

- Actions (and built-in command groups such as tool/config maintenance) can be
  marked `audience: maintainer`.
- `maintainers.ptk.yml` (committed, next to `main.ptk.yml`) lists maintainers by git
  e-mail and/or OS user name. ptk compares it with `git config user.email` and the
  OS user; `PTK_ROLE=maintainer` forces the role (e.g. in CI).
- For everyone else these commands are hidden from `--help`, `ptk plan`, VS Code
  tasks and shell completion, and refuse to run with a clear message.
- This is a usability feature, not access control: anyone can edit the file.
  Real protection belongs in CI permissions and credentials.

## 10. CLI surface

```
ptk [--variant V[,V...] | --all-variants] [--rebuild] [-v|-vv|--quiet]
     [--config FILE] [--set k=v]... [--params FILE]
     <action> [declared params] [--from STEP] [--to STEP] [--dry-run] [--setup] [-- args]

ptk plan <action> [...]                 expanded step tree, conditions evaluated
ptk init                                scaffold a project
ptk config  show [--sources] | validate | schema
ptk variant list | show | explain | check | set | new | gui
ptk creds   setup | set | list | test | remove
ptk configs sync [--diff] | check
ptk setup   [--action A] [--dry-run]
ptk self-setup | doctor
ptk vscode  tasks [--check]
ptk report  open | export
```

Actions and their parameters are generated from the configuration (rich_click),
so `ptk build --help` documents the project's real options.

---

## 11. Mapping from the current tool

| Current | ptk |
|---------|------|
| `ACTIONS.<a>.PHASES` / `SETS` / `steps` | `actions.<a>.steps` (top-level = phases) |
| `parallel: true` | `parallel: true` |
| `execute_if: {VAR: value}` | `when: "VAR == 'value'"` |
| `only_variants` / `omit_variants` | `when: "variant in [...]"` / `not in` |
| `variant_overrides` / `*_cx` | `when` blocks, `ci.ptk.yml` overlay |
| `game_stopper: false` | `continue_on_error: true` |
| `non_blocking` | `background: true` (later milestone) |
| `DEFAULT_PARAMETERS(_CX)` | `params` defaults, `ci.ptk.yml` |
| `-bo name=value` | variant feature override `--set vh.FEATURE=value` (alias `-bo` kept) |
| `-mp name=value` | declared `params` / `--set` (alias `-mp` kept) |
| `shell_run_command`, `custom_script` | `run:` |
| `ENV_ISOLATION` | `environment:` |
| `$VAR{...}` / env replacement | `${vars.x}` / `${env:X}` |
| `variant_matrix` + `variants` | product line with enum features + aliases |

A one-off converter (`ptk migrate old-config.yaml`) is optional (milestone M11).

---

## 12. Skills (Claude, shipped in `.claude/skills/`)

| Skill | Use when | Content |
|-------|----------|---------|
| `ptk-config-authoring` | creating or changing `*.ptk.yml`, includes, overlays, vars | meta-model, merge rules and tags, substitution, `config validate/show --sources`, common mistakes |
| `ptk-action-authoring` | adding/changing actions, steps, step sets, params | step kinds, controls, parallel rules, params + precedence, `ptk plan` before running, `--from/--to`, `audience: maintainer`, regenerating VS Code tasks |
| `ptk-python-steps` | running Python tools/scripts | uvx vs venv vs project vs cli interpreter, pinning versions, cache, Windows/Linux differences |
| `ptk-variant-model` | adding features, variants, conditions | variant model, `when:`, explain/check, renaming features across configs |
| `ptk-credentials` | adding a credential or fixing auth | provider chain, gopass+age setup, vault, CI env vars, masking rules, never on command lines |
| `ptk-shared-configs` | adjusting ruff, pre-commit, clang-format/tidy/clangd for a project | overlay principle, per-tool strategy, `configs sync --diff/check`, upgrading base configs |
| `ptk-tools-setup` | declaring tools, Chocolatey/download sources, onboarding | tool model, version ranges, `setup`/`self-setup`/`doctor`, admin vs user installs |
| `ptk-reporting` | adding report output or importing tool results | run model, exporters, contributors (JUnit/SARIF/Cobertura), writing a contributor plugin |
| `ptk-troubleshooting` | any failing ptk run or config | error categories → fixes, reading `run.log`/`events.jsonl`, `doctor`, `plan`, variant `explain` |
| `ptk-development` | changing ptk itself or writing plugins | architecture rules, where changes go, plugin entry points, definition of done (tests, docs, skills) |
| `ptk-docs-writing` | documenting ptk features or project actions (docs-as-code) | doc structure, reference tables generated from the schema, examples tested in CI |

Each skill contains: exact commands, rules, a verification checklist and the
most common pitfalls — kept in sync with the implementation (definition of done).

---

## 13. Testing strategy

- **Domain / use cases:** unit tests with in-memory fakes (no files, no processes).
- **Adapters:** real subprocesses, real uv (skipped if absent), temp directories;
  gopass/Chocolatey adapters with fake binaries + optional real-tool tests.
- **End-to-end:** example project (`examples/demo`) run for several variants.
- **CI:** Linux + Windows matrix (Windows covers `.bat`, PowerShell, Chocolatey).
- **Docs:** Sphinx docs-as-code built with `-W`; examples executed in tests.

---

## 14. Milestones

| # | Deliverable | Done when |
|---|-------------|-----------|
| M1 | Meta-model, loader (include, overlays, tags, provenance), substitution, validation, JSON Schema | invalid configs fail with `file:line` + suggestion; `config show --sources` works |
| M2 | Variant core integrated | `when:`, `${vh.*}`, `variant` commands, explain/check |
| M3 | Execution engine: steps, sets, parallel, script types, uv Python modes, env per command | demo action runs on Linux; parallel set without shared state |
| M4 | Unified logging | run dir with `run.log`, step logs, `events.jsonl`; masking |
| M5 | CLI: generated actions/params, `--from/--to`, `plan`, `config`, `variant`, maintainer visibility (`maintainers.ptk.yml`), `vscode tasks` | `ptk build --help` shows declared params; maintainer actions hidden for others; tasks.json merge keeps user tasks |
| M6 | Credential handler: env, gopass, vault, prompt | `creds` commands; secrets only via step env; masking tested |
| M7 | Unified reporting | JSON, JUnit, HTML, Markdown, GitHub summary; contributors API |
| M8 | Shared configs: pre-commit, ruff, clang-format, clang-tidy, clangd | `configs sync/check/--diff` |
| M9 | Tools: model, Chocolatey, uv-tool, download, `setup`, `self-setup`, `doctor`, installers | missing tools detected and installed (Windows run by user) |
| M10 | Example project, docs-as-code, skills, CI Linux + Windows | docs build with `-W`; all skills present |
| M11 | Optional: `ptk migrate`, background steps, variant GUI plugin | — |

---

## 15. Decisions

| Topic | Decision |
|-------|----------|
| Name | **ptk** (project tool kit); confirm availability on PyPI / internal index |
| Python | 3.12+ |
| Python manager | uv (required) |
| Steps format | ordered list |
| Variant matrix | levels become enum features; aliases supported |
| Credentials | env → gopass (age) → vault → prompt; no `keyring` |
| Frozen executable | not supported |
| Platforms | Windows, Linux (incl. headless) |
| Delivery | git bundle, or branch push once GitHub write access is connected |
