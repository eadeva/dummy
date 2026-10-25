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
**uv** as Python manager (installed by `ptk setup self` if missing).
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
- **Provenance:** every value knows file and line → `ptk setup config show --sources`,
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
- `ptk init` scaffolds a project; `ptk dry-run <action>` shows the expanded step
  tree with evaluated conditions, final commands and parameter sources before
  running anything.
- `ptk help` opens the full help as an offline HTML page in the default browser
  (see 10a).
- `ptk setup config schema` exports JSON Schema (VS Code YAML autocompletion).
- `ptk setup config validate` for CI; `ptk setup config show [--sources] [path]`.

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
      jobs:       {type: int, default: 8, env: PTK_JOBS, help: Parallel jobs}
      toolchain:  {default: "${vh.data.toolchain}", help: Compiler toolchain (per variant)}
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
  - free-form `data:` merged through inheritance (e.g. toolchain, flash layout)
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

Default order `env -> keyring -> gopass -> vault -> prompt`; a credential can
restrict or reorder it with `providers: [...]`. The first provider with a value
wins; the value is cached for the rest of the ptk run.

| Provider | Where | Notes |
|----------|-------|-------|
| `env` | CI | `credentials.<name>.env.<field>`, else `PTK_CRED_<NAME>_<FIELD>`; read-only |
| `keyring` | Windows, macOS, Linux desktops | optional extra `ptk[keyring]`; skipped when not installed or no real backend (headless Linux); service `ptk`, user `<name>.<field>` |
| `gopass` | Windows, headless Linux, teams | `gopass show --password` / `insert --force` via stdin; path `gopass.path/<field>` (default `ptk/<name>/<field>`); recommend the **age** backend (no gpg-agent/pinentry); team sharing via git |
| `vault` | everywhere, no external tool | one file per user (`%APPDATA%\\ptk\\vault.json`, `~/.config/ptk/vault.json`, `PTK_VAULT_FILE`); AES-256-GCM, key from the master password via scrypt; names and values encrypted; tampering detected; written atomically, mode 600; password asked once per run or `PTK_VAULT_PASSWORD` |
| `prompt` | interactive only | never in CI or without a terminal; not stored |

Keys are shared by all projects of a user (`artifactory.token` is the same
everywhere). More providers (HashiCorp Vault, ...) can be added behind the same
port.

### 4.2 Commands

`ptk setup creds setup [--vault]` (which providers work here and how to set them up;
`--vault` creates the vault) · `ptk setup creds set <name> [field] [--store keyring|gopass|vault]`
(value typed hidden or piped in, never an argument) · `ptk setup creds list [name]`
(which provider supplies what - never values, never prompts) ·
`ptk setup creds test <name>` (runs the credential's `test` command with its values as
environment variables) · `ptk setup creds remove <name> [field] [--store ...]`.

### 4.3 Rules

- Secrets reach commands only as environment variables of that single step -
  never as arguments (visible in process lists), never written unencrypted.
- All secrets the selected steps need are resolved **before the first step
  starts**: a missing credential stops the run with a list of what was tried,
  and no prompt appears in the middle of parallel steps. Skipped steps need none.
- Masked in console, log files, events, reports and `ptk dry-run` output
  (dry runs never look secrets up).
- Access tokens preferred over passwords.

----------|-------|-------|
| `env` | CI | names configured per credential |
| `gopass` | Windows, headless Linux | `gopass show -o <path>` / `gopass insert`; recommend **age** backend (no gpg-agent/pinentry); team sharing via git |
| `vault` | everywhere, no external tool | AES-GCM file in the user's config dir, key from master password (scrypt); unlocked once per session |
| `prompt` | interactive only | never in CI |

First provider returning a value wins. More providers (e.g. Windows Credential
Manager, HashiCorp Vault) as plugins.

### 4.2 Commands

`ptk setup creds setup` (detect gopass, guide `gopass setup --crypto age`, or create vault) ·
`ptk setup creds set <name>` · `ptk setup creds list` (which provider supplies what — never values) ·
`ptk setup creds test <name>` (optional check command per credential) · `ptk setup creds remove <name>`.

### 4.3 Rules

- Secrets reach commands only as environment variables of that single step —
  never as arguments (visible in process lists), never written unencrypted.
- Masked in console, log files, events, reports and `ptk dry-run` output.
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

Built per command, later layers win: host environment (or only OS essentials +
`keep` with `isolate: true`) → `environment.set/unset/path_*` → generated
`PTK_*`, `PTK_PARAM_*`, `VH_*` → action `env` → step `env` (+ `PTK_STEP`,
`PTK_BUILD_DIR`) → secrets of that step. ptk's own `os.environ` is never changed,
so parallel step sets are safe.

Working directory: the project root (relative `cwd:` is resolved against it).
Each step also gets its own build folder `${run.build_dir}` / `PTK_BUILD_DIR`
and reports folder `${run.reports_dir}`.

### 5.5 Parameters

- Declared per action → real rich_click options (shown in `--help`, typed, validated).
- `--set key=value` for scripts; `--params file.yaml`; `-- ...` passed to steps with
  `passthrough: true` (if several in range: `--args-for <step>="..."`).
- Precedence: CLI > params file > declared env var (`env:`) > `default:`.
  Final values and their sources go into the report and `ptk dry-run`.
- **Defaults** are typed and checked against `choices` when the config loads, and can
  be changed per layer: `local.ptk.yml` (per developer), `ci.ptk.yml` (CI), `--set`.
- A default may be a template using `${env:...}`, `${vars.x}`, `${vh.*}` or
  `${project.*}` - e.g. a **per-variant default** `default: "${vh.data.toolchain}"`.
  Templates are resolved and type-checked when the action runs; a default cannot
  refer to other parameters.

### 5.5a Default action

`project.default_action` names the action run by plain `ptk` (and by `ptk run` /
`ptk dry-run` without an action). It must exist and must not be maintainer-only;
both are checked when the configuration loads. The HTML help marks it.

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

- One stream of events from the run engine (port `RunObserver`): run/step
  started/finished, command output, and ptk's own levelled messages. The console
  and the log files are two observers of the same stream; reports (M7) are another.
- **Logs** follow the workspace layout (5a); the latest run is always directly
  in the action folder:
  - `_logs/<variant>/<action>/run.log` — everything, each line tagged with its step
  - `_logs/<variant>/<action>/<set>/<step>.log` — one file per step (command line,
    debug details, output, result)
  - `_logs/<variant>/<action>/events.jsonl` — one JSON object per event (timestamps,
    step, status, exit code, attempts, messages) for tools and reports
  - `_logs/<variant>/<action>/run.json` — summary: status, params with sources, step tree
  - `_logs/<variant>/<action>/_history/<run id>/` — previous runs, pruned to
    `logging.keep_history` (0 = keep only the latest)
- **Levels** for ptk's messages: trace (full masked environment per step), debug
  (cwd, Python runtime, env and secret names), info, warning (retries, allowed
  failures), error. Console: `logging.level`, `-v` debug, `-vv` trace, `run -q`
  warnings only. Files always keep debug and above (trace when configured).
- Secrets are masked before anything reaches an observer; values shorter than 4
  characters cannot be masked safely and trigger a warning instead.

---

## 7. Main point 6 — Unified reporting

- **Source:** the canonical run summary (`run.json`, written from the same event
  stream as the logs) plus the tool results the steps left in their reports
  folders - so any report can be regenerated later (`ptk report export --run ID`).
- **Report model** (domain): action, variant, params with sources, step tree with
  status, start offset, duration, exit code, attempts, log links; imported test
  suites, findings and coverage.
- **Contributions:** a step writes results into `$PTK_STEP_REPORTS_DIR`
  (`${run.reports_dir}`); JUnit XML, SARIF and Cobertura are recognised by content
  and imported automatically. `uses: report.import` with `files: [globs]` copies
  results produced elsewhere into the step's folder (`optional: true` allows none).
  More formats (QAC, CANoe, SBOM, ...) can be added as importers.
- **Exporters** (`reporting.formats`, default json + html): JSON (canonical, with
  totals) · JUnit XML (steps as test cases - allowed failures are not failures -
  plus imported suites) · single-file HTML (offline; "what failed", a **timeline**
  of all steps at their real start times so parallel sets and slow steps are
  visible, parameters, tests, findings, coverage; relative links to the logs) ·
  Markdown · GitHub step summary (appended to `$GITHUB_STEP_SUMMARY`).
- Written to `_reports/<variant>/<action>/report.*` after every run
  (`reporting.dir` moves them); a reporting problem never changes the run's result.
- Commands: `ptk report export [ACTION] [-V v] [--run ID] [-f FORMAT]... [-o DIR]` ·
  `ptk report open [ACTION] [-V v] [--run ID]`.

---

## 8. Main point 7 — Shared base configs (projects can override)

### 8.1 Principle

ptk ships **versioned base configs** (`src/ptk/resources/configs/`). Only configs
listed under `configs:` are managed. A project adds an **overlay**; `ptk setup configs sync`
writes the effective file, which is **committed** (tools and CI use it directly).
Generated files carry a header ("generated by ptk from base X v1 + overlay Y - do not
edit"). `ptk setup configs check` fails in CI when an effective file is missing or stale;
`ptk setup configs sync --diff` previews changes (e.g. after upgrading ptk).

```yaml
configs:
  pre-commit:   {overlay: ptk/configs/pre-commit.overlay.yaml}
  ruff:         {}                       # your ruff.toml is the overlay
  clang-format: {overlay: ptk/configs/clang-format.overlay.yaml}
  clang-tidy:   {overlay: ptk/configs/clang-tidy.overlay.yaml}
  clangd:       {}                       # base only; `output:` changes the file name
```

### 8.2 Per tool

| Config | Strategy | Output |
|--------|----------|--------|
| **a) pre-commit** | base hooks (pre-commit-hooks, ruff, clang-format) + overlay merged by repo URL and hook id; overlay changes `rev`/`args`/`files`/..., adds repos and hooks (also `local`), `disable: true` removes a hook or a repo; `ptk setup self` installs the hooks | `.pre-commit-config.yaml` |
| **b) ruff** | base = ruff's default rules + `I`, `B`, `UP`, `SIM` (as ptk's own code) written to `ruff-base.toml` (committed - not `.ptk/`, which is git-ignored); the project's `ruff.toml` contains `extend = "ruff-base.toml"` plus its own settings (created if missing; an existing one is never edited, ptk says what to add) | `ruff-base.toml` |
| **c) clang-format** | base YAML + overlay, deep merge (maps merge, lists replace, `null` deletes) | `.clang-format` |
| **c) clang-tidy** | `Checks`/`WarningsAsErrors` combined (overlay `-x` drops `x`, `x` drops `-x`), `CheckOptions` merged by key (list or mapping form, `null` deletes), base key order kept | `.clang-tidy` |
| **c) clangd** | base + overlay, deep merge | `.clangd` |

--------|----------|--------|
| **a) pre-commit** | generated: base hooks + overlay merged by repo URL + hook id; overlay can add, change (`args`, `files`, `exclude`) or disable hooks; `ptk setup self` installs the hooks | `.pre-commit-config.yaml` |
| **b) ruff** | base = ruff's default rules (default rule set and line length) plus `I`, `B`, `UP`, `SIM`, same as ptk's own code; native `extend`: base shipped to `.ptk/configs/ruff-base.toml`, project `ruff.toml` contains `extend = ".ptk/configs/ruff-base.toml"` plus overrides | `ruff.toml` (project-owned) |
| **c) clang-format** | generated: base YAML + overlay, same merge rules as the config loader | `.clang-format` |
| **c) clang-tidy** | generated: `Checks` combined (base + overlay, `-check` removes), `CheckOptions` merged by key | `.clang-tidy` |
| **c) clangd** | generated: base + overlay | `.clangd` |

Base configs are versioned with ptk; upgrading ptk shows a diff of the
effective files (`ptk setup configs sync --diff`).

---

## 9. Main point 8 — Tool installation, Chocolatey, self-setup

### 9.1 Tool model

```yaml
tools:
  cmake:
    version: ">=3.28,<4"
    check: cmake --version            # version parsed from the output (version_regex)
    choco: {package: cmake, version: "3.30.2"}     # Windows
    uv_tool: cmake==3.30.2                         # Windows + Linux
  clang-format:
    version: "==18.*"
    choco: {package: llvm, version: "18.1.8"}
    download: {linux: {url: "https://.../clang-format-18.tar.xz", sha256: "...", bin: bin}}
    apt: clang-format-18                           # only with --allow-system
```

### 9.2 Behaviour

- Actions declare `requires_tools`. Before a run ptk checks them (version from
  the `check` command against the range); missing or wrong tools stop the run
  with what to do. `ptk <action> --setup` installs them first. Dry runs never block.
- `ptk setup [--action A]... [--dry-run] [--allow-system] [--bootstrap-choco]`.
- Install order: Windows `choco -> uv tool -> download`; Linux/macOS
  `uv tool -> download -> apt/dnf` (apt/dnf only with `--allow-system`, via
  `sudo -n`). After installing, the tool is checked again.
- **Chocolatey:** `choco install <pkg> --version <v> --allow-downgrade -y`; needs an
  administrator terminal - without one ptk says so and the next method is tried.
  `--bootstrap-choco` installs Chocolatey itself (official script, admin only).
- **Downloads:** sha256 verified (a warning if none is configured), unpacked
  safely into `%LOCALAPPDATA%\\ptk\\tools\\<name>` or `~/.local/share/ptk/tools/<name>`
  (`PTK_TOOLS_DIR`); their `bin` folders and uv's tool folder go first on PATH for
  every command ptk runs.

### 9.3 Self-setup and installers

- `install/install.ps1` / `install/install.sh`: install uv if missing, then
  `uv tool install ptk` (`PTK_SOURCE` for a git URL or another name, `PTK_EXTRAS`
  e.g. `keyring`; package indexes via the standard `UV_INDEX_URL`).
- `ptk setup self [--tools] [--allow-system]`: checks uv and git, syncs shared
  configs, installs the pre-commit hooks (`uv tool run pre-commit install`),
  reports missing credentials, installs tools with `--tools`.
- `ptk setup doctor`: ptk/Python, uv, git (+ user.email), configuration, role, tools,
  credentials (never prompting), shared configs, pre-commit hook; exit 1 on problems.

---

## 9a. VS Code tasks

- `ptk setup vscode tasks` creates or updates `.vscode/tasks.json` with one task per
  visible action (label `ptk: <action>`), a `pickString` input for the variant,
  and the default action as default build task.
- Existing user tasks are kept: ptk only manages entries whose label starts with
  `ptk: ` and its `ptkVariant` input, so re-running is safe; `--check` reports
  drift (CI). Parameters keep their defaults (no prompts per parameter).
- Maintainer-only actions appear only for maintainers (see 9b); `--users-only`
  for a committed file.

## 9b. Maintainer-only commands

- Actions (and built-in command groups such as tool/config maintenance) can be
  marked `audience: maintainer`.
- `maintainers.ptk.yml` (committed, next to `main.ptk.yml`) lists maintainers by git
  e-mail and/or OS user name. ptk compares it with `git config user.email` and the
  OS user; `PTK_ROLE=maintainer` forces the role (e.g. in CI).
- For everyone else these commands are hidden from `--help`, the HTML help (`ptk help`), VS Code
  tasks and shell completion, and refuse to run with a clear message.
- This is a usability feature, not access control: anyone can edit the file.
  Real protection belongs in CI permissions and credentials.

## 10. CLI surface

```
ptk [--config FILE] [--set k=v]... [--ci/--no-ci] [-v|-vv]
ptk <action> [--<param> VALUE]... [-V VARIANT] [--from STEP] [--to STEP]
             [--params FILE] [-q] [--args-for STEP="ARGS"] [--setup] [-- args]
ptk                                     run project.default_action

ptk dry-run [<action> [same options]]  what would run - nothing is executed
ptk run [<action>] [...]                generic form (scripts, CI); -p NAME=VALUE
ptk help [--no-open] [-o FILE]          full help as HTML, opened in the browser
ptk init                                scaffold a project
ptk setup config  show [--sources] | validate | schema
ptk variant list | show | explain | check | set | new | gui
ptk setup creds   setup | set | list | test | remove
ptk setup configs sync [--diff] | check
ptk setup   [--action A] [--dry-run]
ptk setup self | doctor
ptk setup vscode  tasks [--check] [--command CMD] [--users-only]
ptk report  open | export
```

`ptk dry-run <action>` (no separate `plan` command, no `--dry-run` flag on
actions) prints the step tree with conditions evaluated, the final command of
every step, Python runtimes, step env (secrets masked), every parameter value
with its source and, with `--env`, the generated `PTK_*`/`VH_*` variables.
Without `<action>`, `ptk`, `ptk run` and `ptk dry-run` use `project.default_action`.

### Generated action commands

- Each action is a command; each parameter a typed option (`int`, `float`,
  `choice`, `bool` → `--x/--no-x`, `list` → `a,b`). Only given options are passed
  on, so configured defaults (incl. per-variant templates) and their sources
  stay authoritative. `ptk dry-run <action>` has exactly the same options.
- `ptk --help` shows the actions in their own panel; unknown commands get
  "did you mean"; shell completion covers actions and their options.
- Maintainer-only actions are hidden (help, completion, VS Code tasks) and refused
  for users - also through `ptk run`.

### VS Code tasks (`ptk setup vscode tasks`)

- One task per visible action (`ptk: <action>`), a variant picker input
  (`${input:ptkVariant}`) when the project has variants, and the default action
  as the default build task.
- Merges into `.vscode/tasks.json` (JSON with comments accepted): ptk's tasks and
  input are replaced, the user's tasks and inputs are kept; comments cannot be kept
  and a note says so. `--check` exits 1 if the file is out of date (CI);
  `--users-only` leaves out maintainer actions for a committed file;
  `--command "uv run ptk"` if ptk is not on PATH.

## 10a. Advanced help (`ptk help`)

- Writes one self-contained HTML page (`.ptk/help.html`, no external resources,
  works offline / behind a VPN) and opens it in the default browser; on machines
  without a desktop it prints the path.
- Content: project overview and configuration layers; every action with usage,
  parameters (type, choices, default, env variable) and its **step pipeline**
  (sequential steps on a rail, parallel sets as lanes, `when` conditions, Python
  runtime, timeouts, retries, secrets by variable name); variants; credentials
  (names, fields and env variables - never values); tools; configuration files;
  every CLI command with its options.
- Search box (`/`), copy buttons, light/dark theme, print-friendly.
- Maintainer-only actions only appear for maintainers.

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
| `ptk-action-authoring` | adding/changing actions, steps, step sets, params | step kinds, controls, parallel rules, params + defaults + precedence, `ptk dry-run` before running, `--from/--to`, `audience: maintainer`, regenerating VS Code tasks |
| `ptk-python-steps` | running Python tools/scripts | uvx vs venv vs project vs cli interpreter, pinning versions, cache, Windows/Linux differences |
| `ptk-variant-model` | adding features, variants, conditions | variant model, `when:`, explain/check, renaming features across configs |
| `ptk-credentials` | adding a credential or fixing auth | provider chain, gopass+age setup, vault, CI env vars, masking rules, never on command lines |
| `ptk-shared-configs` | adjusting ruff, pre-commit, clang-format/tidy/clangd for a project | overlay principle, per-tool strategy, `configs sync --diff/check`, upgrading base configs |
| `ptk-tools-setup` | declaring tools, Chocolatey/download sources, onboarding | tool model, version ranges, `setup`/`self-setup`/`doctor`, admin vs user installs |
| `ptk-reporting` | adding report output or importing tool results | run model, exporters, contributors (JUnit/SARIF/Cobertura), writing a contributor plugin |
| `ptk-troubleshooting` | any failing ptk run or config | error categories → fixes, reading `run.log`/`events.jsonl`, `doctor`, `ptk dry-run`, variant `explain` |
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

## 13a. Code style

All Python code (ptk itself, tests, shipped helper scripts and generated
Python) follows ruff's default rules, plus `I`, `B`, `UP` and `SIM`, and is
formatted with `ruff format`. CI runs `ruff check` and `ruff format --check`.

## 14. Milestones

| # | Deliverable | Done when |
|---|-------------|-----------|
| M1 ✅ | Meta-model, loader (include, overlays, tags, provenance), substitution, validation, JSON Schema | invalid configs fail with `file:line` + suggestion; `config show --sources` works |
| M2 ✅ | Variant core integrated | `when:`, `${vh.*}`, `variant` commands, explain/check |
| M3 ✅ | Execution engine: steps, sets, parallel, script types, uv Python modes, env per command; `ptk run`, `ptk dry-run`, default action, parameter defaults (incl. per variant); `ptk help` (HTML) with maintainer visibility | demo action runs on Linux; parallel set without shared state |
| M4 ✅ | Unified logging | `run.log`, step logs, `events.jsonl`, `run.json`, history; levels; masking |
| M5 ✅ | CLI: generated actions/params, `--from/--to`, `config`, `variant`, maintainer visibility (`maintainers.ptk.yml`), `vscode tasks` | `ptk build --help` shows declared params; maintainer actions hidden for others; tasks.json merge keeps user tasks |
| M6 ✅ | Credential handler: env, keyring, gopass, vault, prompt | `creds` commands; secrets only via step env; masking tested |
| M7 ✅ | Unified reporting | JSON, JUnit, HTML, Markdown, GitHub summary; contributors API |
| M8 ✅ | Shared configs: pre-commit, ruff, clang-format, clang-tidy, clangd | `configs sync/check/--diff` |
| M9 ✅ | Tools: model, Chocolatey, uv-tool, download, `setup`, `self-setup`, `doctor`, installers | missing tools detected and installed (Windows run by user) |
| M10 ✅ | Runnable quickstart, schema-generated reference, eleven authoring skills, native process tests and CI matrix | Sphinx `-W`, lint and tests passed on Linux/Windows with Python 3.12/3.13 (run 40195082145) |
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
| Credentials | env → optional keyring → gopass (age) → vault → prompt |
| Frozen executable | not supported |
| Platforms | Windows, Linux (incl. headless) |
| Delivery | git bundle, or branch push once GitHub write access is connected |

## CLI organization update

Configuration, shared configs, credentials, tool installation, self-setup, doctor
and VS Code task generation are grouped under `ptk setup`. See `docs/cli.rst`.
Bare `ptk setup` displays help; `ptk setup install` installs configured tools.
Former top-level commands remain hidden compatibility aliases.
