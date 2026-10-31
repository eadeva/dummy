# ptk — project tool kit

A configuration-driven project CLI: jobs made of named steps with explicit dependencies,
built-in variant handling, credentials, tool setup, shared base configs,
unified logging and reporting. See [`reference/development-plan.md`](reference/development-plan.md) for the full plan.

**Status:** Configuration, execution, variants, credentials, reporting, tool setup,
reusable Python tools, VMR discovery and local workflows are implemented. The current scope and acceptance
boundaries are recorded in `reference/development-plan.md`. Sixteen repository-local skills
include tested authoring and Python tool examples.

```bash
uv sync                     # install with dev dependencies
uv run ptk --help
uv run pytest
uv run ruff check && uv run ruff format --check   # ruff default rules
```

## Create a project

```bash
ptk init my-project --config-dir config/ptk --dry-run
ptk init my-project --config-dir config/ptk
cd my-project
ptk hello
```

Existing configuration and `.gitignore` files are preserved.

## Runnable quickstart

With PTK installed, copy `examples/quickstart` to a directory outside this Git
checkout, then open a terminal in that copy:

```bash
ptk build --dry-run
ptk -V debug build
ptk -V release build
```

PTK discovers `.main.ptk.yml` from the current directory. This example runs
without compilers or credentials and writes logs and reports inside the copy. The existing firmware demo contains placeholders
and is intended for configuration exploration and dry runs.

The [documentation](docs/index.rst) contains user guides, CLI requirements,
twelve arc42 architecture chapters, reference material and CI/CD guidance.
Requirements follow the supplied convention in authored RST, without loading
the reference meta-model. Historical inputs remain outside the published site
and packages under `reference/`.

Build the documentation:

```bash
uv sync --group docs
uv run sphinx-build -W --keep-going -b html docs docs/_build/html
```

## VS Code extension

The [Project Toolkit extension](extensions/project-toolkit/README.md) adds a
sidebar for jobs, local workflows, built-in commands, variants and reports. Job
rows have Run, Dry Run, Parameters and Help icons with tooltips. Expand built-in
commands to access setup, credentials and help, or select a variant for your jobs.
It supports single repositories, VMRs and multiple workspace folders.

Install the VSIX through **Extensions: Install from VSIX...**. Build it from the
repository root with `ptk extension` (or `uv run ptk extension`), or download
the VSIX artifact from the branch's CI run. The job requires Node.js 22+ and npm,
installs the build dependencies, runs the checks and writes
`extensions/project-toolkit/project-toolkit-0.4.0.vsix`.
PTK must be installed on the workspace host. See
[editor documentation](docs/guides/editor.rst) for setup and permissions.

## Tools

```yaml
# config/ptk/tools.ptk.yml
cmake:
  version: '>=3.28,<4'
  check: cmake --version
  choco:
    package: cmake
    version: 3.30.2
  uv_tool: cmake==3.30.2

# config/ptk/jobs/build.ptk.yml
requires_tools:
- cmake
steps:
- '...'
```

Runs check `requires_tools` first; `ptk self-service tools` (or `ptk build --setup`) installs what is
missing - Chocolatey on Windows, `uv tool`, sha256-verified downloads, apt/dnf only with
`--allow-system`. `ptk self-service doctor` diagnoses a machine; `ptk self-service tools` installs required tools.
Install or refresh ptk itself with `sh install/install.sh` or
`powershell -ExecutionPolicy Bypass -File install/install.ps1`.
When run from a checkout, both scripts install that checkout (relative to the
script, regardless of your current directory). Rerunning reinstalls even the same
package version and updates compatible dependencies. Pull the desired branch
first: installing a checkout does not run `git pull`. `PTK_SOURCE` overrides the
source; a standalone downloaded script defaults to the `ptk` package index entry.
Explicit version pins remain respected. Open a new terminal after installation.
Both installers persist Tab completion for your account in Bash/Git Bash and
detected PowerShell editions. No project venv needs to be active. Windows
PowerShell and PowerShell 7 get their own current-user/all-hosts registrations;
Bash login and non-login terminals load the same generated script. Profiles
preserve other settings, retain backups and do not start Python at shell startup.
Running `.\install\install.ps1` also enables completion in that session.
Use `-NoCompletion` or `--no-completion` to opt out. To repair an existing setup,
run `ptk self-service completion install` and open a new terminal. PowerShell's double-Tab
binding applies to all commands in that shell. Zsh/Fish registration is explicit;
see `ptk self-service completion --help` and the CLI documentation.
Installation reads only the marker, versioning and optional default-variant
settings to determine the package version. Errors in other project files remain
visible through `ptk validate` and do not block installation.

## Shared configs

```yaml
# config/ptk/configs.ptk.yml
pre-commit:
  overlay: ptk/configs/pre-commit.overlay.yaml
ruff: {}
clang-format:
  overlay: ptk/configs/clang-format.overlay.yaml
clang-tidy:
  overlay: ptk/configs/clang-tidy.overlay.yaml
clangd: {}
```

`ptk maintainer sync configs` merges ptk's base configs with your overlays into `.pre-commit-config.yaml`,
`.clang-format`, `.clang-tidy`, `.clangd` and `ruff-base.toml` (your `ruff.toml` extends it).
Commit them; `ptk validate --generated` in CI catches stale files.

When pre-commit is enabled, local jobs automatically install or repair its Git
hooks for every developer. Workflows check each participating VMR repository
before starting jobs. Help, dry runs and CI skip installation; missing generated
configuration blocks execution. See [hook setup and conflicts](docs/guides/configuration.rst#local-git-hooks).

## Reports

After every run ptk writes `_reports/<variant>/<job>/report.*` (`report_formats`:
json, junit, html, markdown, github). Steps contribute tool results by writing them to
`$PTK_STEP_REPORTS_DIR` - JUnit, SARIF and Cobertura are picked up automatically - or
with `uses: report.import`. The HTML report shows what failed and a timeline of all
steps; `ptk report open` opens it, `ptk report export --run ID` rebuilds older ones.

## Credentials

```yaml
# config/ptk/credentials.ptk.yml
artifactory:
  fields:
  - user
  - token
  env:
    token: ARTIFACTORY_TOKEN
  gopass:
    path: team/artifactory
```

Looked up in order `env -> keyring -> gopass -> vault -> prompt` (configurable per
credential). `ptk self-service creds set artifactory token` stores a value (typed hidden); the
built-in vault is an AES-GCM file protected by a master password - no external tool
needed. Steps get secrets only as environment variables (`secrets: {TOKEN: artifactory.token}`),
and ptk masks them in its execution output. Child programs must not expand them
into command-line arguments or write them to report input files. keyring support: `uv tool install "ptk[keyring]"`.

## Configuration files

`.main.ptk.yml` identifies the project and its configuration directory:

```yaml
repository: {alias: demo, config_path: config/ptk}
schema_version: 1
```

| Location | Contents |
|---|---|
| `config/ptk/project.ptk.yml` | Project name, component directories, variables and shared defaults |
| `config/ptk/folder_structure.ptk.yml` | Output layout |
| `config/ptk/artifactory_paths.ptk.yml` | Artifact destinations |
| `config/ptk/credentials.ptk.yml` | Credential declarations |
| `config/ptk/tools.ptk.yml` | Tool declarations |
| `config/ptk/versioning.ptk.yml` | Version sources |
| `config/ptk/configs.ptk.yml` | Formatter/linter settings |
| `config/ptk/maintainers.ptk.yml` | Maintainer login IDs |
| `config/ptk/project.variants.ptk.yml` | Default variant, constraints and variant environment |
| `config/ptk/variants/<name>.ptk.yml` | One project variant |
| `config/ptk/jobs/<name>.ptk.yml` | One job |
| `config/ptk/workflows/<name>.ptk.yml` | One workflow |
| `<component directory>/component.variants.ptk.yml` | Component features, dependencies and constraints |

Each file contains its section body; entity names come from filenames. Register
component directories in `project.ptk.yml` and keep their definitions beside their
`CMakeLists.txt` or Bazel module. All files except the marker and project document
are optional. PTK loads known locations only, with no includes or implicit file
overrides. It validates each document and then references across the model.

Use `ptk maintainer config show --sources` for provenance and `ptk validate`
for errors with source locations. Explicit `--set` overrides, shared defaults and
variant inheritance remain available. The extension uses PTK's loading mechanism
and document schemas. See [configuration authoring](docs/guides/configuration.rst).

## Commands available now

```
ptk [-c .main.ptk.yml] [--set PATH=VALUE]... [--ci/--no-ci] [-V VARIANT] [-v|-vv]
ptk                                  run the default job (project.default_job)
ptk JOB [--PARAM VALUE]... [--only-step STEP] [--to STEP] [--params FILE]
           [-q] [--args-for STEP="ARGS"]... [-- ARGS]
ptk JOB [--dry-run] [--env]       # run a job or preview its expanded plan
ptk WORKFLOW [--dry-run]         # workflows are direct commands too
ptk workflow list | show NAME | run NAME [--dry-run]
ptk variant list | show [NAME] | explain NAME FEATURE
ptk validate [--variants] [--versions] [--generated]
ptk report open [JOB] | open --workflow NAME | export [JOB]
ptk pre-commit run [--all-files] | validate
ptk init [DIRECTORY] --config-dir config/ptk
ptk self-service tools [--job JOB] [--dry-run]
ptk self-service creds setup | set | list | test | remove
ptk self-service completion install | powershell | bash | zsh | fish
ptk self-service extension | doctor
ptk self-service hooks install | uninstall | status
ptk maintainer config show [PATH] [--sources] | schema
ptk maintainer sync configs | tasks | agent [--check]
ptk maintainer version show | generate
ptk maintainer artifacts destination --job JOB
ptk maintainer JOB_OR_WORKFLOW [--dry-run]
ptk help                        # full offline help in the browser
```

Every job is a command with typed options for its parameters (`ptk build --help`
lists them; `int`, `float`, `choice`, `bool` as `--x/--no-x`, `list` as `a,b`).
Maintainer-only jobs are hidden from users and refused if invoked.
Shell completion comes from click: e.g. `eval "$(_PTK_COMPLETE=bash_source ptk)"`.

Exit codes: 0 passed, 1 failed, 2 usage/configuration error, 130 cancelled (Ctrl+C).

## Running jobs

```yaml
params:
  jobs:
    type: int
    default: 8
    env: PTK_JOBS
  toolchain:
    default: ${vh.data.toolchain}
steps:
  configure:
    run:
    - cmake
    - --preset
    - ${vars.preset}
  compile:
    run: cmake --build --preset ${vars.preset} -j ${params.jobs}
    needs:
    - configure
  lint:
    run: tools/lint.py
    python:
      uvx: ruff==0.6.9
    needs:
    - compile
  unit:
    run:
    - pytest
    - -q
    python:
      venv:
        requirements: tools/req.txt
    passthrough: true
    needs:
    - compile
  qac:
    run: tools/qac.bat
    when: COMPONENT_CAMERA
    continue_on_error: true
    needs:
    - compile
  upload:
    run: tools/upload.sh
    secrets:
      TOKEN: artifactory.token
    retries: 2
    timeout: 600
    needs:
    - lint
    - unit
    - qac
```

* `.bat/.cmd` → `cmd /c`, `.ps1` → `pwsh -File`, `.sh` → `bash`, `.py` → Python via uv
* `python:` `uvx` (tool from PyPI), `venv` (cached in `.ptk/venvs/<hash>`), `project`
  (`uv run --project`), `interpreter: cli` (ptk's own) - nothing is ever activated
* every command gets its own environment: `PTK_*`, `PTK_PARAM_*`, `VARIANT_*`, job/step
  `env`, then secrets; secrets are masked in console, logs and `ptk JOB --dry-run`
* working directory: project root; per-step folders `${run.build_dir}`, `${run.reports_dir}`
* `ptk JOB --dry-run` shows the expanded steps, conditions, final commands and where every
  parameter value comes from
* parameter precedence: `-p` > `--params FILE` > `env:` variable > `default:`; defaults can
  be changed explicitly with `--set` and may use `${env:..}`,
  `${vars.x}`, `${vh.*}` (per-variant defaults) or `${project.*}`
* `project.default_job` is what plain `ptk` runs
* `outputs: [file, folder]` declares project-owned artifacts, primarily for workflow
  uploads/downloads. Transfers remain the workflow's responsibility. PTK's optional
  built-in `cache: true` can reuse existing outputs of successful dependent work;
  roots always run, and there is no inferred build directory or artifact restoration.
  Cache correctness belongs to the project. `--no-cache-ptk` disables PTK reuse for
  the whole job/workflow invocation. See the [complete output/cache guide](docs/guides/output-reuse.rst).

## Workspace layout

```
_builds/<variant>/<job>/<step>/    build folder per step (${run.build_dir})
_bin/<variant>/                             binaries per variant
_logs/<variant>/<job>/run.log            + steps/<step>.log, events.jsonl, run.json, _history/
_reports/<variant>/<job>/report.{json,xml,html,md} + <step>/ (tool results)
```

## Architecture

```
src/ptk/
  domain/        config meta-model, tree + merge rules, substitution, expressions,
                 variants (model, rules, conventions), layout
  domain/execution  params, planning, per-command environment, command building
  application/   ports, use cases (LoadProject, ShowConfig, ExportSchema, VariantService,
                 PrepareRun, RunJob, BuildHelp, role)
  adapters/      YAML loader, file source, host environment, subprocess runner,
                 uv Python environments, env secrets, log files, HTML help
  drivers/cli/   rich_click CLI
  bootstrap.py   composition root
```

Dependencies point inwards only; the domain has no I/O.

### Dependency execution and variant inspection

- Steps without `needs` may run concurrently. Dependencies define joins, and
  `max_workers` bounds active steps. `--to` selects a prerequisite closure;
  `--only-step` deliberately bypasses prerequisites. Both job and workflow dry-runs
  show their graphs automatically; `--graph` inspects them without preparing commands.
- `ptk variant list|show|explain` inspects variants without editing configuration.
  Select a variant before the command: `ptk -V debug build`.
- `--ci/--no-ci` is maintainer-only. Automatic CI detection remains the default.

See [dependency execution and output responsibility](docs/reference/execution.rst) and the [CLI reference](docs/reference/cli.rst).

## Local workflows

Put `workflows/verify.ptk.yml` in the configuration folder to compose existing jobs:

```yaml
# config/ptk/workflows/verify.ptk.yml
max_workers: 2
jobs:
  build:
    job: build
  tests:
    job: test
    needs: build
  lint:
    job: lint
    needs: build
```

Run `ptk workflow run --dry-run verify`, then `ptk verify` (or `ptk workflow run verify`). Each call keeps
its repository's tools, environment, credentials and reports. Use `job: REPO:JOB` for VMR calls, `params` for job parameters and owner
`repo_variants` mappings for variant selection. `needs` names invocation IDs;
independent jobs can run concurrently, regardless of YAML order. PTK preflights every call before execution
and rejects conflicting parallel outputs or shared uv project environments.
Generated VS Code tasks include workflows. These workflows run locally;
execution on CX/CI is refused.

Workflow `open_report` defaults to `always`. Use `on-errors` to open the summary
only for execution or imported report errors, or `null` to disable it.
CX and dry runs never open workflow reports.
When the workflow summary opens, child job reports stay closed. The summary
links to HTML reports; JSON files remain available for automation.

If a job and workflow share a name, local interactive calls ask which to run;
CX selects the job. Use `ptk run NAME` or `ptk workflow run NAME` to select
explicitly. Reports print their file paths; use `ptk report open JOB` to open
a job report explicitly, or `ptk report open --workflow NAME` for the latest aggregate
workflow report. Add `--if-exists` to get an informational message when there
is no saved run/report. No local browser-link server is started.

See [workflows](docs/guides/workflows.rst) and `examples/workflows` for dependency graphs,
VMR ownership, failure handling and reports. A future generator could map invocation IDs and `needs` directly to GitHub jobs;
GitHub template generation and the generic PTK GitHub Action are not implemented yet.

## VMR workspaces and isolated environments

VMR mode activates at a git-repo workspace root containing `.repo`, or inside a
member whose root `.git` pointer resolves into `.repo`. A parent `.repo` alone
does not establish membership. PTK reads `.repo/project.list` without recursively
scanning the workspace. For manual workspaces, put `virtual_monorepo: true` in a
workspace-root `.main.ptk.yml`; it checks direct children, or exact paths from an
optional `members: [nested/repository, other]` list. Each participating repository
still needs its own `.main.ptk.yml` with an alias and configuration path.

In a `.repo` workspace, use `ptk repos`, shared `ptk self-service creds list`,
`ptk validate`, `ptk self-service doctor`, `ptk variant list`, `ptk validate --variants`,
and `ptk report list/summary`. Jobs and installation stay repository-specific:
`ptk firmware build` and `ptk firmware self-service tools --job build`.

Commands receive a fresh isolated environment by default. Declare variables to
keep explicitly; caller PATH is not inherited unless `environment.inherit_path`
is enabled. Only selected managed tool versions are prepended. Managed download
and Python-tool versions coexist; system installers remain
shared host operations. See `docs/guides/configuration.rst` and `docs/reference/cli.rst`.

For a complete tested starter, copy `examples/authoring`. For a reusable Python CLI starter,
use `examples/python-tool`. The authoring skill catalog is in `docs/guides/skills.rst`;
the wheel bundles the PTK expert agent, fourteen project-facing skills and lightweight offline references.
Run `ptk maintainer sync tasks` to create tasks. Run `ptk maintainer sync agent` to install
`.github/agents/ptk-expert.agent.md`, copy skills to `.github/skills`, and install version-matched docs, examples and a configuration
schema under `.github/ptk`. Relative links work without a PTK checkout or network
access. `ptk maintainer sync agent --check` checks drift; updates preserve custom
skills and refuse to overwrite local edits. See [editor setup](docs/guides/editor.rst).

The extension consumes PTK's versioned CLI/JSON interface: schemas, loaded values,
file ownership, diagnostics and available commands. Compatible fields, jobs,
workflows and parameters appear after refresh without an extension rebuild.
New UI behavior or breaking interface changes require an extension update;
package and extension release numbers do not need to match. See the
[compatibility contract](docs/guides/editor.rst#ptk-and-extension-compatibility).

## Version discovery and initialization

`ptk init` requires a configuration folder, supplied at the terminal prompt
or with `--config-dir config/ptk`. The path is relative to the repository root;
there is no implicit default. Scripts must supply `--config-dir`. It creates a minimal root entry and
two runnable jobs in `jobs/hello.ptk.yml` and `jobs/build.ptk.yml`.
Variants, tools, versioning, environment, credentials and shared settings have
separate folders with commented configuration examples. `project.ptk.yml` defines the project; PTK discovers
them; the conventional CX and maintainer entry files remain at the config root.
A local `workflows/verify.ptk.yml` starter sequences the two generated jobs.
Run `ptk hello` for messages and `ptk build` for generated version files. Existing files are protected; missing ignore rules are appended.

In a VMR, `ptk init` initializes every checked-out member without a root
`.main.ptk.yml`, skips configured repositories, and leaves the workspace root alone.
The config folder is chosen once and applied relative to each new member's root.
Preview with `ptk init --config-dir config/ptk --dry-run`; repeat the command safely as more repositories arrive.
Use `ptk init DIRECTORY` to initialize just one project.

Versions can come from Git tags, manifests/text files, environment variables,
commands or explicit values. Components inherit unless given a source. Every
configured job gets one ignored `.gen.version.ptk.yml` snapshot and qualified
variables such as `PTK_VERSION_ENGINE` and `PTK_VERSION_ENGINE_COMPONENT_SDK`.
`version.generate` produces C headers, CMake, MSBuild, Python or JSON files without
rewriting unchanged content. See [versioning](docs/guides/versioning.rst) for variant
release lines, explicit VMR dependencies and `ptk maintainer version show/generate` and `ptk validate --versions`.

## Develop PTK using PTK

To prepare release artifacts without publishing, run `uv run ptk package`.
It builds a wheel and source archive, checks metadata, smoke-tests the installed
wheel in a consumer repository, and creates a separate HTML documentation ZIP
and checksums under `_bin/default/package`. Only `dist/` contains Python upload
artifacts; nothing is uploaded. See [package preparation](docs/guides/packaging.rst).

The repository configuration in `config/ptk` has one `default` variant and no
components. From the repository root:

```sh
uv run ptk test                          # pytest + JUnit/PTK reports
uv run ptk test -- tests/test_init.py -q  # selected tests and pytest options
uv run ptk check                         # Ruff lint and format checks
uv run ptk docs                          # _builds/default/docs/sphinx/html/index.html
uv run ptk workflow run verify           # check -> test -> package, alongside docs
```

An installed `ptk` can run these directly. Jobs use this checkout's Python
project and its `dev`/`docs` dependency groups, rather than the global tool's
Python environment. Package metadata uses the same Git-managed PTK versioning
configuration as jobs. Untagged/shallow checkouts use the development fallback
in `versioning.ptk.yml`; source distributions retain their resolved version. The default job is `test`.

Dedicated uv environments for `test`, `check`, `docs` and `package` under `.ptk/venvs/<job>`
let docs run alongside the sequential check/test/package branch without modifying
the environment running PTK. Packaging also builds a separate documentation archive.

The `dev` group includes pinned CMake for generator integration tests. uv selects
the project environment's CMake ahead of host PATH entries, so the test job
does not require a separate machine-wide CMake installation.

## Dates and upload destinations

Runtime templates can use `${date.timestamp}` (for example `2026_10_26_1507`),
`${date.utc.timestamp}`, or separate date/time components. One timestamp is shared
across a CLI invocation, including parallel workflow children.

`artifactory_paths.ptk.yml` defines a global base path, GitHub event paths,
and optional job suffixes. PTK resolves the destination; GitHub workflows choose
files, authenticate and upload:

```bash
ptk maintainer artifacts destination --job package --format github
```

For a GitHub workflow's first job, `ptk maintainer matrix --format github`
exports eligible variant/job pairs, execution arguments, version/source commit
and the shared upload base. GitHub `needs` identifies artifact producers; output
paths and optional `artifact_type` properties belong to completed jobs.
Completed executions list declared output paths and write `upload.json` beside
`run.json`, containing available artifacts and producer properties for workflow
uploaders. Outputs accept strings or `{path, artifact_type}` entries. The hidden built-in command works
for local maintainers and in CX without granting maintenance rights.
See [CX setup, uploads and downloads](docs/guides/cx-matrix.rst).

See [destination configuration and examples](docs/guides/artifacts.rst) and
[date substitutions](docs/guides/configuration.rst#date-and-time-substitutions).

Log analysis is enabled by default; HTML shows active diagnostics and retains ignored/justified findings with source-log links. See [logging and reporting](docs/guides/log-analysis.rst) for `report_formats`, `logging_history_backups` and rule examples. `ptk maintainer sync agent` also installs the log-analyzer skill and PTK expert agent.
