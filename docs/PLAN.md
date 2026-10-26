# ptk — Implementation Plan

> **ptk** (*project tool kit*): a generic, configuration-driven project CLI.
> Configuration files use `.ptk.yml` (with `artifactory_structure.ptk.yaml` as a conventional exception): entry point `.main.ptk.yml` (ptk version + main fields),
> fragments `*.ptk.yml`, layers `cx.ptk.yml` and `local.ptk.yml`, and `maintainers.ptk.yml`.
> Workspace folders: `_builds/`, `_bin/`, `_logs/`, `_reports/` (structured by variant / job / step).

One CLI that every project can use: declarative jobs made of steps and step
sets, built-in variant handling, credentials, tool setup, shared base configs,
unified logging and reporting.

---

## 0. Goals and principles

| Goal | Meaning |
|------|---------|
| **Generic** | No project-specific code in the core. Projects describe *what* to run in YAML; domain specifics come as plugins. |
| **User-friendly configuration** | Short forms, good defaults, strict validation with "did you mean …", `file:line` in every error, JSON Schema for editor autocompletion. |
| **Reproducible** | Every command runs with an explicit environment; the CLI process is never mutated; reports record what ran, with which values and from where. |
| **Safe by default** | Credential references never on command lines; supported secret inputs masked in logs; unknown names are errors; no silent fallbacks. |
| **Testable** | Clean Architecture; every use case runs against in-memory fakes. |

**Targets:** Python **3.12+**, **Windows and Linux** (Linux also headless),
**uv** as Python manager (installed by `ptk setup self` if missing).
No frozen executable.

---

## 1. Architecture (Clean Architecture)

```
src/ptk/
├── domain/                     pure model + rules — no I/O, no frameworks except pydantic
│   ├── config/                 meta-model: Project, Job, Step, StepSet, Param, Tool, ...
│   ├── variants/               components, features, variants, expressions, resolver
│   ├── execution/              run model: RunPlan, StepResult, Status, Event
│   ├── credentials/            SecretRef, CredentialSpec (never secret values)
│   ├── tools/                  ToolSpec, version ranges
│   └── shared_configs/         merge rules for base + overlay
├── application/
│   ├── ports.py                ConfigSource, ProcessRunner, PythonEnvManager, SecretProvider,
│   │                           ToolInstaller, LogSink, ReportExporter, ReportContributor,
│   │                           FileSystem, Clock, Prompt
│   └── use_cases/              LoadConfig, ValidateConfig, PlanJob, RunJob,
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
| `project` | name, description, default job, default variant |
| `include` | further files / globs merged into the configuration |
| `vars` | reusable values (`${vars.build_dir}`) |
| `environment` | isolation rules: variables and PATH entries kept, added, removed |
| `tools` | tools with version range, check command, install sources per OS |
| `credentials` | named credentials with provider chain |
| `variants` | product line: components, features, variants (inline or file reference) |
| `jobs` | CLI commands: params, required tools, steps |
| `configs` | shared base configs and project overlays (pre-commit, ruff, clang-*) |
| `logging` | console style, run directory, retention |
| `reporting` | formats, output dir, contributors |
| `plugins` | extra plugin packages to load / options |

### 2.2 Loading pipeline

```
.main.ptk.yml               ptk_version, project, include, main settings
  → include: [...]            merged in order (files or globs)
  → cx.ptk.yml              applied automatically in CI
  → local.ptk.yml           personal overrides (git-ignored)
  → --set key=value           command line
  → validate (pydantic, extra=forbid, suggestions)
  → run preparation          substitute all selected steps before execution
```

- **Merge rules:** mappings merge deeply, lists replace.
  Tags: `!replace` (replace whole mapping), `!append` (append to list),
  `!include file.yaml` (insert a file at this point).
- **Provenance:** every value knows file and line → `ptk setup config show --sources`,
  errors as `.main.ptk.yml:42: jobs.build.params.jobs: expected int`.
- **Substitution** (one syntax, unknown names are errors):

  ```
  ${env:NAME}  ${env:NAME:-default}  ${vars.x}  ${params.x}
  ${vh.variant}  ${vh.features.X}  ${secret:name.field}  ${project.root}  ${run.build_dir}
  ```

  `$${...}` escapes. Values are typed; secrets are masked wherever printed.

### 2.3 User-friendliness

- Short forms: `run: "cmake --build ."` instead of a full mapping.
- Defaults everywhere (working dir = project root, `continue_on_error: false`, ...).
- `ptk setup init` (`ptk init` alias) scaffolds a project; `ptk dry-run <job>` shows the expanded step
  tree with evaluated conditions, final commands and parameter sources before
  running anything.
- `ptk help` opens the full help as an offline HTML page in the default browser
  (see 10a).
- `ptk setup config schema` exports JSON Schema (VS Code YAML autocompletion).
- `ptk setup config validate` for CI; `ptk setup config show [--sources] [path]`.

### 2.4 Example

```yaml
schema_version: 1
project: {name: demo, default_job: build}
include: [ptk/jobs/*.yaml]
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

jobs:
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
  - small product lines inline in `.main.ptk.yml`, larger ones in separate files
  - matrix levels become enum features (`PLATFORM: [tc397, tc399]`)
  - free-form `data:` merged through inheritance (e.g. toolchain, flash layout)
- **Integration:**
  - `when:` on steps (replaces `execute_if`, `only_variants`, `omit_variants`)
  - `${vh.*}` substitution; `VH_*` (and optionally legacy `BO_*`) env vars per command
  - `--variant <name|alias>[,...]`, `--all-variants`
- **Commands:** `ptk variant list | show | explain | check`.
- **Generators** (header, CMake, Bazel, Make, Yocto, Robot, Sphinx) bundled with an extension interface;
  step `uses: variant.generate` (seven bundled generators; external extensions use `ptk.generators`).

---

## 4. Main point 3 — Credential handler

### 4.1 Provider chain

Default order `env -> keyring -> gopass -> vault -> prompt`; a credential can
restrict or reorder it with `providers: [...]`. The first provider with a value
wins; the value is cached for the rest of the ptk run.

| Provider | Where | Notes |
|---

## 5. Main point 4 — Jobs, step sets, steps

### 5.1 Concepts

- **Job** — a CLI command: `help`, `params`, `requires_tools`, `steps`.
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
`PTK_*`, `PTK_PARAM_*`, `VH_*` → job `env` → step `env` (+ `PTK_STEP`,
`PTK_BUILD_DIR`) → secrets of that step. ptk's own `os.environ` is never changed,
so parallel step sets are safe.

Working directory: the project root (relative `cwd:` is resolved against it).
Each step also gets its own build folder `${run.build_dir}` / `PTK_BUILD_DIR`
and reports folder `${run.reports_dir}`.

### 5.5 Parameters

- Declared per job → real rich_click options (shown in `--help`, typed, validated).
- `--set key=value` for scripts; `--params file.yaml`; `-- ...` passed to steps with
  `passthrough: true` (if several in range: `--args-for <step>="..."`).
- Precedence: CLI > params file > declared env var (`env:`) > `default:`.
  Final values and their sources go into the report and `ptk dry-run`.
- **Defaults** are typed and checked against `choices` when the config loads, and can
  be changed per layer: `local.ptk.yml` (per developer), `cx.ptk.yml` (CI), `--set`.
- A default may be a template using `${env:...}`, `${vars.x}`, `${vh.*}` or
  `${project.*}` - e.g. a **per-variant default** `default: "${vh.data.toolchain}"`.
  Templates are resolved and type-checked when the job runs; a default cannot
  refer to other parameters.

### 5.5a Default job

`project.default_job` names the job run by plain `ptk` (and by `ptk run` /
`ptk dry-run` without a job). It must exist and must not be maintainer-only;
both are checked when the configuration loads. The HTML help marks it.

### 5.6 Built-in steps (`uses:`)

`variant.generate` · `configs.sync` · `tools.ensure` · `report.import` (JUnit, SARIF,
Cobertura, ...) · `files.copy` / `files.clean` · `wait` · `echo`.

---

## 5a. Workspace layout

```
_builds/<variant>/<job>/<set>/<step>/    working directory per step  ${run.build_dir}
_bin/<variant>/                             binaries per variant        ${run.bin_dir}
_logs/<variant>/<job>/run.log            whole run; <set>/<step>.log per step
_reports/<variant>/<job>/<set>/<step>/   reports per step            ${run.reports_dir}
```

Without variants the variant level is `default`. Root and folder names are
configurable (`layout:`). Previous runs are archived per variant/job
(`logging.keep_history`).

## 6. Main point 5 — Unified logging

- One stream of events from the run engine (port `RunObserver`): run/step
  started/finished, command output, and ptk's own levelled messages. The console
  and the log files are two observers of the same stream; reports (M7) are another.
- **Logs** follow the workspace layout (5a); the latest run is always directly
  in the job folder:
  - `_logs/<variant>/<job>/run.log` — everything, each line tagged with its step
  - `_logs/<variant>/<job>/<set>/<step>.log` — one file per step (command line,
    debug details, output, result)
  - `_logs/<variant>/<job>/events.jsonl` — one JSON object per event (timestamps,
    step, status, exit code, attempts, messages) for tools and reports
  - `_logs/<variant>/<job>/run.json` — summary: status, params with sources, step tree
  - `_logs/<variant>/<job>/_history/<run id>/` — previous runs, pruned to
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
- **Report model** (domain): job, variant, params with sources, step tree with
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
- Written to `_reports/<variant>/<job>/report.*` after every run
  (`reporting.dir` moves them); a reporting problem never changes the run's result.
- Commands: `ptk [-V v] report export [JOB] [--run ID] [-f FORMAT]... [-o DIR]` ·
  `ptk [-V v] report open [JOB] [--run ID]`.

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
|Base configs are versioned with ptk; upgrading ptk shows a diff of the
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

- Jobs declare `requires_tools`. Before a run ptk checks them (version from
  the `check` command against the range); missing or wrong tools stop the run
  with what to do. `ptk <job> --setup` installs them first. Dry runs never block.
- `ptk setup install [--job A]... [--dry-run] [--allow-system] [--bootstrap-choco]`.
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
  configs, installs enabled pre-commit hooks through a persistent uv environment,
  reports missing credentials, installs tools with `--tools`.
- `ptk setup doctor`: ptk/Python, uv, git (+ user.email), configuration, role, tools,
  credentials (never prompting), shared configs, pre-commit hook; exit 1 on problems.
- Local jobs and workflows automatically ensure enabled pre-commit hooks before
  execution; every developer is allowed this installation. VMR workflows check
  participating repositories once before parallel execution. Git queries support
  symlinks, gitfiles and worktrees; usable hooks are kept and broken runtimes repaired.
  The engine lives in `<git-common-dir>/ptk/pre-commit`; concurrent installers use
  a shared Git-directory lock. Generated configs remain maintainer-owned and must
  already exist. Help/dry runs/CI and disabled entries do not install hooks.
  Ordinary existing hooks are preserved; custom hook paths/symlink hooks/backup
  collisions stop with an actionable conflict. Local bypass remains possible;
  CI required checks provide enforcement. See `docs/configuration.rst`.

---

## 9a. VS Code tasks

- `ptk setup vscode tasks` creates or updates `.vscode/tasks.json` with one task per
  visible job (label `ptk: <job>`), a `pickString` input for the variant,
  and the default job as default build task.
- Existing user tasks are kept: ptk only manages entries whose label starts with
  `ptk: ` and its `ptkVariant` input, so re-running is safe; `--check` reports
  drift (CI). Parameters keep their defaults (no prompts per parameter).
- Maintainer-only jobs appear only for maintainers (see 9b); `--users-only`
  for a committed file.

## 9b. Maintainer-only commands

- `maintainers.ptk.yml` in the configured folder contains `maintainers: [login-id, ...]`.
  Local OS login IDs and triggering GitHub actor IDs are matched case-insensitively;
  Git author names/emails and `PTK_ROLE=maintainer` do not grant privileges.
  `PTK_ROLE=user` can reduce privileges for testing. Init seeds its creator's ID.
- Default restricted built-ins: `setup configs sync`, `setup self`, `setup vscode`
  and its children; `--ci/--no-ci` is a maintainer-only root option. Additional `command_audience` policies
  may restrict commands but cannot relax this baseline.
- Restricted commands are absent from normal/HTML help and completion; direct calls,
  aliases and legacy setup dispatch enforce permissions before writes.
- Tool installation, personal credentials, inspection/validation, diagnostics,
  version/report generation and ordinary job execution remain developer operations.
  Init only creates missing configurations and preserves existing ones.
- Jobs/workflows still support `audience: maintainer`; shared editor tasks use
  `--users-only`. VMR root and repository identity lists are independent. Combined
  editor setup preflights all member roles; no partial writes on permission failure.
- These are CLI guardrails, not a security boundary against editing the checkout
  or process environment. Configuration and plugins remain trusted executable code.

## 10. CLI surface

```
ptk [--config FILE] [--set k=v]... [--ci/--no-ci] [-V VARIANT] [-v|-vv]
ptk <job> [--<param> VALUE]... [--from STEP] [--to STEP]
             [--params FILE] [-q] [--args-for STEP="ARGS"] [--setup] [-- args]
ptk                                     run project.default_job

ptk dry-run [<job> [same options]]  what would run - nothing is executed
ptk run [<job>] [...]                generic form (scripts, CI); -p NAME=VALUE
ptk help [--no-open] [-o FILE]          full help as HTML, opened in the browser
ptk setup init [DIRECTORY] [--name NAME] [--dry-run]  scaffold a project
ptk setup config  show [--sources] | validate | schema
ptk variant list | show | explain | check
ptk setup creds   setup | set | list | test | remove
ptk setup configs sync [--diff] | check
ptk setup install [--job A] [--dry-run]
ptk setup self | doctor
ptk setup vscode  tasks [--check] [--command CMD] [--users-only]
ptk report  open | export
```

`ptk dry-run <job>` (no separate `plan` command, no `--dry-run` flag on
jobs) prints the step tree with conditions evaluated, the final command of
every step, Python runtimes, step env (secrets masked), every parameter value
with its source and, with `--env`, the generated `PTK_*`/`VH_*` variables.
Without `<job>`, `ptk`, `ptk run` and `ptk dry-run` use `project.default_job`.

### Generated job commands

- Each job is a command; each parameter a typed option (`int`, `float`,
  `choice`, `bool` → `--x/--no-x`, `list` → `a,b`). Only given options are passed
  on, so configured defaults (incl. per-variant templates) and their sources
  stay authoritative. `ptk dry-run <job>` has exactly the same options.
- `ptk --help` shows the jobs in their own panel; unknown commands get
  "did you mean"; shell completion covers jobs and their options.
- Maintainer-only jobs are hidden (help, completion, VS Code tasks) and refused
  for users - also through `ptk run`.

### VS Code tasks (`ptk setup vscode tasks`)

- One task per visible job (`ptk: <job>`), a variant picker input
  (`${input:ptkVariant}`) when the project has variants, and the default job
  as the default build task.
- Merges into `.vscode/tasks.json` (JSON with comments accepted): ptk's tasks and
  input are replaced, the user's tasks and inputs are kept; comments cannot be kept
  and a note says so. `--check` exits 1 if the file is out of date (CI);
  `--users-only` leaves out maintainer jobs for a committed file;
  `--command "uv run ptk"` if ptk is not on PATH.

## 10a. Advanced help (`ptk help`)

- Writes one self-contained HTML page (`.ptk/help.html`, no external resources,
  works offline / behind a VPN) and opens it in the default browser; on machines
  without a desktop it prints the path.
- Content: project overview and configuration layers; every job with usage,
  parameters (type, choices, default, env variable) and its **step pipeline**
  (sequential steps on a rail, parallel sets as lanes, `when` conditions, Python
  runtime, timeouts, retries, secrets by variable name); variants; credentials
  (names, fields and env variables - never values); tools; configuration files;
  every CLI command with its options.
- Search box (`/`), copy buttons, light/dark theme, print-friendly.
- Maintainer-only jobs only appear for maintainers.

Jobs and their parameters are generated from the configuration (rich_click),
so `ptk build --help` documents the project's real options.

---

## 11. Mapping from the current tool

| Current | ptk |
|---------|------|
| `JOBS.<a>.PHASES` / `SETS` / `steps` | `jobs.<a>.steps` (top-level = phases) |
| `parallel: true` | `parallel: true` |
| `execute_if` | Dropped from required legacy migration scope by user decision |
| `only_variants` / `omit_variants` | `when: "variant in [...]"` / `not in` |
| `variant_overrides` / `*_cx` | `when` blocks, `cx.ptk.yml` overlay |
| `game_stopper: false` | `continue_on_error: true` |
| `non_blocking` | `background: true` (scoped finite processes) |
| `DEFAULT_PARAMETERS(_CX)` | `params` defaults, `cx.ptk.yml` |
| `-bo name=value` | variant feature override `--feature FEATURE=value` / `--set vh.FEATURE=value` (alias `-bo` kept) |
| `-mp name=value` | declared `params` / `--set` (alias `-mp` kept) |
| `shell_run_command`, `custom_script` | `run:` |
| `ENV_ISOLATION` | Deferred from required legacy migration scope by user decision |
| `$VAR{...}` / env replacement | `${vars.x}` / `${env:X}` |
| `variant_matrix` + `variants` | product line with enum features + aliases |

Legacy conversion is not supported; configurations must use the current schema.

---

## 12. Skills (Claude, shipped in `.claude/skills/`)

| Skill | Use when | Content |
|-------|----------|---------|
| `ptk-config-authoring` | creating or changing `*.ptk.yml`, includes, overlays, vars | meta-model, merge rules and tags, substitution, `config validate/show --sources`, common mistakes |
| `ptk-job-authoring` | adding/changing jobs, steps, step sets, params | step kinds, controls, parallel rules, params + defaults + precedence, `ptk dry-run` before running, `--from/--to`, `audience: maintainer`, regenerating VS Code tasks |
| `ptk-python-steps` | running Python tools/scripts | uvx vs venv vs project vs cli interpreter, pinning versions, cache, Windows/Linux differences |
| `ptk-variant-model` | adding features, variants, conditions | variant model, `when:`, explain/check, renaming features across configs |
| `ptk-credentials` | adding a credential or fixing auth | provider chain, gopass+age setup, vault, CI env vars, masking rules, never on command lines |
| `ptk-shared-configs` | adjusting ruff, pre-commit, clang-format/tidy/clangd for a project | overlay principle, per-tool strategy, `configs sync --diff/check`, upgrading base configs |
| `ptk-tools-setup` | declaring tools, Chocolatey/download sources, onboarding | tool model, version ranges, `setup`/`self-setup`/`doctor`, admin vs user installs |
| `ptk-reporting` | adding report output or importing tool results | run model, exporters, contributors (JUnit/SARIF/Cobertura), writing a contributor plugin |
| `ptk-troubleshooting` | any failing ptk run or config | error categories → fixes, reading `run.log`/`events.jsonl`, `doctor`, `ptk dry-run`, variant `explain` |
| `ptk-development` | changing ptk itself or writing plugins | architecture rules, where changes go, plugin entry points, definition of done (tests, docs, skills) |
| `ptk-docs-writing` | documenting ptk features or project jobs (docs-as-code) | doc structure, reference tables generated from the schema, examples tested in CI |

Each skill contains: exact commands, rules, a verification checklist and the
most common pitfalls — kept in sync with the implementation (definition of done).

---

## 13. Testing strategy

- **Domain / use cases:** unit tests with in-memory fakes (no files, no processes).
- **Adapters:** real subprocesses, real uv (skipped if absent), temp directories;
  gopass/Chocolatey adapters with fake binaries + optional real-tool tests.
- **End-to-end:** example project (`examples/quickstart`) run for several variants.
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
| M3 ✅ | Execution engine: steps, sets, parallel, script types, uv Python modes, env per command; `ptk run`, `ptk dry-run`, default job, parameter defaults (incl. per variant); `ptk help` (HTML) with maintainer visibility | demo job runs on Linux; parallel set without shared state |
| M4 ✅ | Unified logging | `run.log`, step logs, `events.jsonl`, `run.json`, history; levels; masking |
| M5 ✅ | CLI: generated jobs/params, `--from/--to`, `config`, `variant`, maintainer visibility (`maintainers.ptk.yml`), `vscode tasks` | `ptk build --help` shows declared params; maintainer jobs hidden for others; tasks.json merge keeps user tasks |
| M6 ✅ | Credential handler: env, keyring, gopass, vault, prompt | `creds` commands; secrets only via step env; masking tested |
| M7 ✅ | Unified reporting | JSON, JUnit, HTML, Markdown, GitHub summary; contributors API |
| M8 ✅ | Shared configs: pre-commit, ruff, clang-format, clang-tidy, clangd | `configs sync/check/--diff` |
| M9 ✅ | Tools: model, Chocolatey, uv-tool, download, `setup`, `self-setup`, `doctor`, installers | missing tools detected and installed (Windows run by user) |
| M10 ✅ | Runnable quickstart, schema-generated reference, thirteen authoring skills, native process tests and CI matrix | Sphinx `-W`, lint and tests passed on Linux/Windows with Python 3.12/3.13 (run 40195082145) |
| M11 ✅ | Scoped background steps and plugin discovery | done |

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

## Post-M10 completion: project initialization

- Implemented `ptk setup init [DIRECTORY] [--name NAME] [--dry-run]` and the hidden
  `ptk init` alias, closing the scaffold feature described in section 2.3.
- Generates a portable `hello` job and a new `.gitignore` when absent.
- Refuses existing configuration, preserves existing ignore rules, and previews
  without writing files. Does not install tools or access credentials.
- M11 background processes are implemented with documented limits. The desktop
  editor was subsequently removed; variants now have read-only CLI inspection.

## M11 implementation

- Background `run` steps overlap subsequent work, join at their sequence boundary,
  preserve result ordering, and use existing timeout/retry/cancellation handling.
- Regression coverage includes real process overlap/cancellation, failure reporting,
  variant constraints and plugin dispatch.

## Detail-plan completion after M11

- Fixed `path`/`secret` CLI parameters. Secret options request hidden input; values
  are masked in run metadata and only substituted into step environments.
- `report: false` hides complete step subtrees from exported reports/contributions,
  while audit logs and overall failure status remain intact.
- Groups and built-ins support retries and deadlines. Built-in Python handlers
  cooperate with cancellation; they are not forcibly killed like subprocesses.
- Added `--all-variants`, comma selections, feature overrides and `-bo`/`-mp`
  compatibility spellings. Persistent variant editors were subsequently removed.
- Implemented all six extension entry-point groups from section 1, selected by
  installed distribution names in `plugins`. Contracts are in `docs/plugins.rst`.
- Added the remaining setup/file/generator built-ins and seven bundled generators.
- Added configurable maintainer visibility for built-in command groups and aliases.
- Native Linux/Windows behavior, extension integration and generator outputs are
  covered in tests.

### Explicit release / acceptance boundaries

- Real machine-wide Chocolatey/gopass setup remains a user-environment acceptance
  check; CI does not claim those installations occurred.
- Generator format restrictions and cooperative Python timeouts are documented.
- Package name/index availability and publishing a release remain delivery decisions.
  Code is delivered on `ChatGPT_version`; it has not been merged into the base branch.

## Confirmed scope and shared defaults

- CX means GitHub Actions/workflows. `cx.ptk.yml` is the automatic workflow
  overlay; maintainers can force mode with `--ci` / `--no-ci`. No legacy filename is required.
- Legacy migration is not a completion requirement. `execute_if`, legacy
  `ENV_ISOLATION`, `*_cx`, `variant_overrides` and `DEFAULT_PARAMETERS_CX` do not
  create further legacy obligations. The legacy converter and both CLI spellings have been removed.
- Drop `variant_matrix` as a separate deliverable. Named variants, inheritance,
  feature overrides and multi-variant execution cover the accepted requirement.
- Shared `param_defaults` applies only to explicitly declared job parameters.
  Explicit job defaults override shared values; required parameters remain
  required. Inherited defaults retain provenance and undergo normal type checks.
- Automatically load configuration-directory `tools.ptk.yml` and `<job>.tools.ptk.yml`.
  Explicit includes are not applied a second time. Main/includes override auto
  files; CX, local and CLI layers follow. See `docs/configuration.rst` for ordering.
- **Tool requirements override per tool.** Unmentioned global requirements stay;
  job maps can add a tool, override its settings, or disable a named tool with
  `false`. An empty list does not disable global requirements. Per-job tool
  settings do not mutate the global definition or other jobs.
- `setup install --job NAME` and execution checks use effective per-job
  settings; incompatible settings across a combined install selection are errors.
- Explicit job/step `only_variants` and `omit_variants` fields discussed earlier
  remain a separate follow-up; current runtime filtering uses `when` on steps.
  Maintainer job visibility uses `audience: maintainer`.

## Repository discovery and VMR (implemented)

- Root `.main.ptk.yml` declares `repository.alias` and `repository.config_path`.
  No automatic discovery of the old filename. Configuration and execution roots
  are separate; includes/automatic files use the configuration directory while
  commands and outputs use the repository root.
- Upward standalone discovery stops at Git boundaries. Explicit `--config`
  selects one project, bypassing VMR grouping.
- `.repo` in the invocation directory activates VMR mode. Inside a repository,
  only its root `.git` symlink/junction or `gitdir:` file resolving inside `.repo`
  establishes automatic membership; proximity to a parent `.repo` is insufficient.
- Git-repo members come from `.repo/project.list`; a missing index reports an
  error with `repo sync` guidance. There is no recursive discovery fallback.
- Manual workspaces use `.main.ptk.yml` with `virtual_monorepo: true` at the
  workspace root. Inspect direct child directories by default, or use an explicit
  `members` list for nested paths. A project's explicit `virtual_monorepo: false`
  opts out; omission enables automatic discovery. These fields are entry-only.
- Entry metadata and member indexes are cached per invocation and reused by
  routing, credentials and version dependencies. Unselected project includes
  remain unloaded. Manual members receive workspace context through root routing;
  direct invocation inside an ordinary manual member is standalone.
- Every participating member needs its own root entry file and unique alias.
  CLI: `ptk <alias> <original command>`, including setup, variants and jobs.
  Global options precede the alias; bare VMR invocation lists repositories.
- Regression coverage checks path separation, includes/overlays, root boundaries,
  aliases, member containment, Git indirection, manual markers, explicit opt-out,
  bounded discovery, cache refresh, per-repository execution and access.

## Review corrections and shared VMR operations

- Fixed process-group escalation, vault lost updates, repository-scoped identity
  and credential tests, stale/historical report inputs and cross-layer true tool
  requirements. Editor schema and generated reference describe authored inputs.
- Isolated child environments default on, with explicit host-variable/PATH opt-ins.
  Managed tool versions coexist by definition identity; jobs select paths and
  verify tools in their actual subprocess environment. System/custom installers
  remain shared host operations, not isolated package managers.
- VMR shares credential coordination, config views/validation, host/per-repo
  diagnostics, variant views/checks and report summaries. Tool installation and
  mutable project operations remain repository-qualified.
- Added `ptk-vmr` and `ptk-plugin-development` skills with tested starter artifacts;
  synchronized existing skills; project-facing skills now ship with offline references.

## Version discovery and organized initialization (implemented)

- Per-run Git/file/env/command/literal discovery with explicit fallback, component
  inheritance, variant-specific sources and explicit recursive VMR dependencies.
- Qualified PTK_VERSION_ALIAS / PTK_VERSION_ALIAS_COMPONENT_NAME variables and
  version.projects substitutions share one immutable-by-convention run snapshot.
- Unique ignored .gen.version.ptk.yml snapshots; no version bump/tag mutations.
- C header, CMake, MSBuild, Python and JSON generation preserves unchanged mtimes.
- Init asks for a config directory, emits minimal root metadata and complete
  runnable fragments, preflights existing files and adds missing ignore rules.
- The config folder is required user input with no implicit default: prompt on
  a terminal or require `--config-dir PATH` for scripts/`--yes`. Interpret it
  relative to each repository root and apply one choice across new VMR members.
- In a VMR, `setup init` without DIRECTORY uses the full member list to initialize
  checked-out repositories without a root `.main.ptk.yml`. Existing entries and
  missing checkouts are skipped; the workspace root stays untouched. Prompt once,
  preflight all new members, avoid alias collisions, and report per-member results.
  Dry runs write nothing and repeat runs skip configured members. Explicit DIRECTORY
  keeps single-project behavior; manual automatic selection requires a direct
  child Git repository or PTK entry, so build folders are not scaffolded.
- Snapshots are manually retained/cleaned; Git uses reachable tags and rejects
  shallow history by default. Discovery commands must be authored read-only.

## Init starter organization

- Separate hello/build job files under jobs/, discovered by a glob.
- Topic folders for variants (model plus debug/release files), tools, versioning,
  environment, credentials and shared formatter/linter settings.
- Commented optional field examples; starter jobs remain runnable offline.
- Conventional CX/maintainer entries remain at config root; other files use includes.

## PTK self-hosted development commands

- Replaced repository starter jobs with test/check/docs/package, one default variant,
  and no components; preserved topic-based configuration under config/ptk.
- Python project runtimes accept explicit dependency groups, using pyproject.toml
  as the source for pytest/Ruff/Sphinx dependencies.
- CI exercises the same PTK jobs, with JUnit results and strict Sphinx builds.
- Fixed the repository Git tag match and added a configured development fallback for
  untagged, shallow and source-only checkouts.

## Package preparation and portable editor resources

- `ptk package` builds an sdist and a wheel from that sdist, validates metadata,
  smoke-tests the installed wheel in a consumer project and produces HTML docs,
  checksums and a manifest. Output stays local; no upload, tag or version bump.
- The wheel ships fourteen project-facing skills and allowlisted lightweight docs
  and examples. Sphinx and release tooling remain development dependencies.
  Full rendered HTML is a separate artifact. Dynamic package metadata consumes the
  Git-managed PTK project version; sdists preserve it for rebuilds without Git.
- `ptk setup vscode` generates tasks and installs offline skills under .github/skills
  plus version-matched docs, examples and schema under .github/ptk. Tasks and skills
  can be updated separately; `skills --check` performs a read-only drift check.
- Generated resource hashes protect local edits and unrelated GitHub files during
  upgrades. Maintainer skills for PTK development/docs stay in its source checkout.
- CI prepares packages and tests the installed wheel on both Linux and Windows.


## Local workflows and current authoring coverage

Implemented local `workflow.ptk.yml` composition of existing jobs, including
VMR repository-qualified calls, nested sequential/parallel groups, bounded job
concurrency, preflight, cancellation, per-job isolation and retained child reports.
The CLI exposes `workflow list/show/dry-run/run`; execution is rejected on CX/CI.
VS Code tasks include workflows, and regular setup init scaffolds a local starter.

Current project-facing skills now include `ptk-workflow-authoring`, `ptk-versioning`
and `ptk-package-preparation`; existing tools/reporting/job/VMR skills cover the
new installers, default Docker install policy, report cards, filtering and opening.
The offline authoring bundle contains fourteen project-facing skills; two additional
skills remain checkout-only. See docs/workflows.rst and docs/skills.rst.

Deferred explicitly: `ptk setup init --workflows` will generate GitHub templates.
Job calls become jobs invoking a generic PTK run-job GitHub Action. Sequential
and nested parallel structure determines job `needs`: each branch inherits incoming
needs, and its terminal jobs join before subsequent steps. Template generation,
checkout/artifact policy and the reusable GitHub Action are not implemented yet.

## Job terminology and report navigation

PTK executable units are now jobs throughout configuration, CLI options, Python
interfaces, runtime variables, JSON reports, examples and bundled skills. This is a
breaking rename without legacy field aliases; docs/configuration.rst lists the
required updates. Setup init scaffolds jobs/ and editor setup installs the renamed
ptk-job-authoring skill. GitHub Actions terminology retains its platform meaning.

Local workflow shortcuts appear beside jobs in CLI help. Name collisions prompt
locally, select the job on CX, and require explicit commands for non-interactive
callers. Editor tasks always select jobs/workflows explicitly. Report titles use
Job - or Workflow -. Workflow tables link only HTML child reports, retaining JSON
artifacts. A selected workflow summary suppresses child auto-opening; otherwise
child policies apply after completion. Interactive VS Code terminals print scoped
loopback HTTP links, with default-browser settings documented in docs/editor.rst.

## Date templates and destination-only Artifactory structure

Implemented invocation-scoped local/UTC date templates with component fields,
parameter/default/step/environment substitution, workflow/VMR propagation and
report context metadata. Date resolution does not depend on per-step wall clocks.

Implemented automatic artifactory_structure.ptk.yaml discovery, global/event/job
path composition, push branch/tag routes, preserved branch slashes, repository
overrides and read-only JSON/GitHub-output/URL resolution. PTK jobs/variants and
repository versions retain their own context. CLI --at can reuse an explicit
instant across destination commands. Added current-repository version shortcuts
and four-digit numeric sort keys; arbitrary/prerelease semantic ordering and
numeric components above 9999 are not provided by that key. Uploads, credentials,
file selection and GitHub workflow generation remain outside this resolver.
Docs and existing config/package skills include the portable destination example.


## Maintainer defaults and identity schema review

Replaced name/email/user records with a strict list of login IDs. Removed Git
subprocesses from role lookup and the unconditional environment-role elevation.
New scaffolds identify their creator; doctor reports the ID, role and list path.
Added mandatory built-in configuration-editor restrictions, consistent alias/help/
completion handling, and a guard on legacy setup installation dispatch. VMR root
maintainer lists now govern workspace operations independently of member lists.
Tests cover normal and maintainer paths, invalid/missing identity files, attempted
role elevation, no-write denials, VMR isolation and combined-operation preflight.


## Startup performance and reproducible benchmarks

Profiled fresh-process help in the PTK checkout, missing/broken projects, and
20/100-member VMR fixtures. Removed repeated YAML diagnostic path calculations,
prefer the C safe parser with tested fallback, cache CLI project failures/successes
and roles for one invocation, and defer runtime service imports/construction.
No persistent config or permission cache was added; all workflow shortcuts remain.

The reproducible scripts/benchmark_cli.py records wall-time samples and metadata;
source baseline/optimized samples are kept in docs/benchmarks. CI logs benchmark
results on Linux/Windows Python 3.12 without flaky time thresholds. Deterministic
regression tests bound repeated work and ensure help avoids runtime imports.
See docs/performance.rst for measurements and remaining VMR scaling costs.


## CLI simplification and editor inventory

- CI mode switches are hidden and refused for non-maintainers; automatic detection
  remains unchanged. VMR repository commands use member identity; workspace commands
  use the root list, and member preflight retains member permissions.
- `-V` / `--variant` is global and propagated to repository jobs, variant display,
  version commands, report commands and artifact destinations. Workflows keep their
  authored per-job selections. Setup and other read-only inventories ignore it.
- Removed persistent variant mutation commands, the GUI and editor plugin interface,
  unused overlay writer, desktop tests and GUI CI job. Retained list/show/explain/check.
- `ptk describe --json` exposes a versioned, read-only editor inventory with role-aware
  jobs/workflows/capabilities and no resolved credentials, versions or tool installs.

## Project Toolkit VS Code extension

- Added `extensions/project-toolkit`, with sidebar discovery through the versioned
  PTK inventory, explicit job/workflow process tasks, previews, non-secret parameter
  prompts, variant selection in workspace state, config navigation and job reports.
- Supports multi-root folders and VMRs; workspace trust and CLI permissions govern
  execution. Saved task definitions retain preview mode, parameters and variants.
- Node tests cover argument construction, controller dispatch, trust, stale commands,
  task restoration and multi-root state. Real Python CLI integration tests exercise
  repository/VMR discovery, read-only previews and parameterized job execution.
- CI tests and packages VSIX artifacts on Linux and Windows. Installation instructions
  are in the extension README and docs/editor.rst. Marketplace publication and a
  graphical extension-host acceptance run remain separate from this implementation.
