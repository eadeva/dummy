# XC-CE Utils

**XC-CE Utils** is a configuration-driven automation engine for the development lifecycle of multi-variant embedded software. It orchestrates everything from build and code generation through static analysis, testing possibilities, documentation, and release — replacing dozens of disconnected scripts with a single engine.

At its core it is a **generic automation engine**: it does not require an embedded project and
works just as well for smaller, simpler tasks. For example, the MPCI project uses it for
SW container generation.

```{note}
XC-CE Utils is or was used in the following projects: 2 Wheeler Project, Toyota CGW, VCU-P,
MPCI, HCP5Gen1 and HCP5Gen1Plus.
```

```{tip}
New here? Start with [Getting Started](guides/getting_started.md) for a 5-minute walkthrough,
or open the overview presentation: {download}`XC-CE Utils overview (PowerPoint) <presentations/xc-ce-utils-overview.pptx>`.
```

## The Problem

Every embedded project needs the same things: **build, code generation, static analysis,
documentation, unit and tests, deployment**. Historically, every project
built its own scripts for each of them:

- fragile, undocumented automation that is hard to maintain and duplicated across teams;
- a new variant, target or tool often meant **forking the scripts**;
- knowledge did not transfer — every team solved the same problem again, and a good pattern
  found in one project rarely reached the next one.

## The Idea

XC-CE Utils is **one configuration-driven engine** that replaces those project-specific scripts.
The execution logic lives once, in XC-CE Utils, and is reused by every project; what makes a
project's automation "its own" is a set of **declarative YAML files**. A new capability for a
project is a YAML file — no code change, no new script to maintain. An improvement made for one
project reaches every project, instead of each project maintaining its own version of the same fix.

**Flexibility: shared base + project overrides.** The same rule applies throughout: XC-CE Utils
ships a **base configuration**, and a project only describes where it **deviates**. Examples are
the [pre-commit and ruff setup](guides/code_quality_config.md) (shared XC-CE base, optional
project overrides), the Docs-as-Code configuration (PMT meta model plus project
[meta model deviations](modules/docascode.md#project-deviations-from-the-meta-model) and a
project `needs_config.yml`), and the project configuration itself, which reuses shared parts via
`!include`. Projects get the common defaults and updates for free, and their differences stay
small, explicit and reviewable.

**Use central tools as dependencies, not copies.** Some functionality in XC-CE Utils is
currently a slightly modified copy of PMT scripts that are not reachable centrally, for example
the SBOM generation, the open source (OSS) scan scripts, and the Docs-as-Code `conf_standard`
with its extensions. These copies are only synchronized from time to time and drift from their
source. The goal is to remove the copied code: the central tools are published as packages,
added as dependencies of XC-CE Utils and used as they are, so fixes and improvements reach every
project without a manual sync.

```{note}
The Docs-as-Code part (`conf_standard`, meta model, extensions and related additions) is kept in
sync with Kirsch Christoph (XC-CE/EBE1). It will be removed from XC-CE Utils and added as a
dependency as soon as a PMT python package for that is available.
```

## Independent, Flexible and Scalable

| Ad-hoc project scripts | XC-CE Utils |
|---|---|
| Tied to one build system and tool set | Independent of the project's tooling; use only what you need |
| Hard-coded per project, per variant | Declarative YAML — variants are data, available in every step |
| New action = new script to write and maintain | New action = a YAML file; existing scripts run as steps |
| Different commands and options in every project | One generated CLI in every project, plus Advanced Help (HTML) |
| Copy-pasted logic across projects | Reusable step types, shared by all projects |
| Manual, ad-hoc error handling | Unified error-recovery strategy per step |
| Custom log parsing per project | Unified, classified reporting (JSON / HTML) |
| Custom CI/CD glue per project | Possibility for reusable CI/CD workflows with automatic variant dispatch usage |
| Manual setup guides for every new developer | Self-installing and self-setting-up from configuration |

**Independent of the project's tooling — use only what you need.** XC-CE Utils orchestrates the
tools a project already uses; it does not replace them, and nothing is mandatory. A project
picks the parts that help it and keeps its own solutions for the rest: dependency management via
Conan or not, the test, analysis, documentation or deployment features or not. The build system
is a step like any other: CMake (`cmake_set-up`, `cmake_build`, `ctest`), Make and Bazel are
supported side by side (see [Build Wrappers](core_engine/reference/steps/build_wrappers.md)),
and anything else is driven through command or script steps. Whatever the project chooses, it is
run, logged and reported the same way.

**Variant handling through the whole run.** The selected {term}`variant` is not only a build
option: its settings, dependencies and variables are available to every step of every action (included project specific scripts over environment variables) —
configuration, build, code generation, analysis, tests, documentation and deployment. One
variant, a list of variants, or all of them run with the same action definition.

**Project-specific scripts welcome.** Existing project scripts do not have to be rewritten.
They run as steps (`custom_script` for `.py`, `.ps1` and `.sh`, `shell_run_command` for any
command; see [Shell, Files & Variables](core_engine/reference/steps/shell_files_vars.md)) and
get the same variant context, logging, error handling and reporting as the built-in steps.

**One CLI in every project.** The command line is generated dynamically from the project's
configuration: every action, action group and variant defined in YAML appears as a command or
option, with help text, without writing any CLI code. Developers get the same interface
(`build.ps1` / `build.sh`, the same flags, the same `--help`) in every project that uses
XC-CE Utils, so moving between projects does not mean learning a new set of scripts.

**Advanced Help for the project's own CLI.** `build.ps1 --adv-help` (`-ah`) generates and opens an
interactive HTML report built from the current project configuration (written to `_reports/`):
the actions with their descriptions and groups, the variant matrix, which actions are available
for which variant, and the build, tool and test requirements per variant. Because it is generated
from the configuration, it always matches the project's CLI as it is right now.

**Self-installing and self-setting-up.** The project wrapper installs the XC-CE Utils version
pinned in `main_conf.yml`, and the first run sets up the workstation from configuration: git hooks
(pre-commit), credentials (validated, stored in the system keyring, with renewal reminders and
`creds` commands), Conan and Bazel caches, the tools required per action (toolbase, Chocolatey,
Linux packages, Artifactory artifacts). VS Code extensions are installed on demand with
`config vs-code refresh-extensions`. The AI integrations (Copilot
instructions, skills and agents, MCP server configurations) and VS Code tasks are generated from
the same configuration by the maintainers and shipped with the project. Each part is re-applied
only when its configuration changes. In CI,
interactive parts (credential prompts, DevMate PAT) are skipped; in Docker,
tool installation is skipped and preinstalled tools on `PATH` are used (Artifactory artifacts only
with `on-docker: true`). See [Environment Setup Flow](core_engine/reference/environment_setup_flow.md)
and [Setup & CLI Command Classes](guides/setup_classes.md).

**Scales from one project to many.** The same engine and step catalog serve small single-variant
projects and large variant matrices; a new project, variant or tool is added in configuration,
not in code.

## How It Works

**Config → CLI → variant/s → steps → reports**

1. A project ships a thin wrapper (`build.ps1` / `build.sh`) and a configuration folder.
2. The CLI is **generated dynamically** from that configuration — the actions you see are the
   actions defined in YAML.
3. The selected {term}`variant` is resolved from the variant matrix.
4. The action runs as a sequence of {term}`steps <step>` from a shared step catalog.
5. Every run writes artifacts, logs and reports to the same predictable folders
   (`_builds/`, `_logs/`, `_reports/`), on every project.

**Many product variants.** Real projects are a matrix of hardware × customer × feature x calibration
combinations. XC-CE Utils models this as an **N-dimensional variant matrix** defined once in
configuration: each variant carries its own settings, dependencies and build options without code
forks, and you build one variant, a list, or all of them in parallel.

**Portable and modular.** Each project stays independent: it pins a **versioned** XC-CE Utils
release, which is cached locally per project and major version (no global install conflicts).
Project-specific decisions (build system, variants, actions) live only in the project's
configuration folder, not in the engine, so one project's changes cannot break another. Different
major versions can coexist across projects and upgrades are opt-in.

In short: **portability** (one versioned engine reused everywhere), **modularity** (capabilities
composed from reusable steps), **scalability** (one variant matrix instead of per-variant scripts)
and **configurability** (project behavior in YAML, not in the engine).

## Documentation map

| Section | What's inside |
|---|---|
| [User Guides](guides/getting_started.md) | CLI usage, config files, extending steps |
| [Core Engine](core_engine/index.md) | Internal architecture (arc42): layered domain/application/adapters/cli, driving-port pattern, execution orchestration, step registry, variant matrix, wrappers |
| [Module Reference](modules/global_modules.md) | Per-module Python API docs (logger, TRACE32, WinIDEA, CANoe, Helix QAC, MCP, …) |
| [CI/CD Workflows](workflows/index.md) | Reusable GitHub Actions workflows and composite actions |
| [WinIDEA SDK Reference](external_refs/winidea_sdk/winidea_sdk_configuration.md) | WinIDEA SDK |
| [CANoe TBE Reference](external_refs/canoe_tbe/overview.md) | CANoe vendor references |
| [Helix QAC Reference](external_refs/helix_qac/index.md) | Vendor manuals for MISRA/CERT C, SCA, SFA, message reference |
| [Glossary](glossary.md) · [What's New](changelog.md) | Terminology and recent changes |

---

## What It Can Do

::::{grid} 2
:gutter: 3

:::{grid-item-card} **Build & Compile**
:columns: 6
Multi-variant builds through CMake, Bazel, and Make (Conan 2.x package management supported through uvx), ccache for incremental compilation.

:::

:::{grid-item-card} **Code Generation**
:columns: 6
AUTOSAR code generation via Vector DaVinci Configurator and EB tresos — with hash-based change detection to skip unchanged configurations and file locking for concurrent builds.
:::

:::{grid-item-card} **Quality & Compliance**
:columns: 6
Static code analysis (Helix QAC), static flow analysis, baseline-differential reporting, and open-source license scanning (FossID). Run the same analysis locally and in CI. Layered [pre-commit & ruff configuration](guides/code_quality_config.md) ships the XC-CE Python style as a shared base, with optional per-project overrides.
:::

:::{grid-item-card} **Documentation**
:columns: 6
Docs-as-Code pipeline — Sphinx + MyST Markdown + reStructuredText + Doxygen + PlantUML + sphinx-needs 8. The sphinx-needs configuration is generated from the PMT meta model, with project [deviations](modules/docascode.md#project-deviations-from-the-meta-model) applied; architecture needs come from `*.arch.yml` models (Arch2Needs), test cases and verdicts from TACO. Generates HTML and PDF with C/C++ API docs, architecture diagrams, and requirements traceability.
:::

:::{grid-item-card} **Hardware-in-the-Loop & Test**
:columns: 6
**TACO** test management is supported: [TACO](core_engine/reference/steps/taco.md) test selections (unit tests via CTest, Robot Framework) are filtered and run per variant, and their verdicts appear on the test cases in the documentation. Independently of TACO, the test and hardware steps flash, debug, and test on physical targets — TRACE32 (CMM scripts), iSYSTEM **WinIDEA** (PFLASH/DFLASH/UCB flashing, session control, SoC core control), Vector **CANoe** (XCP measurement, system variables, test modules), serial COM I/O with thread-safe queuing, and programmable power supplies.
:::

:::{grid-item-card} **Developer Experience**
:columns: 6
One command generates VS Code tasks, C/C++ IntelliSense settings, and MCP server configurations. Git hooks enforce commit message conventions. Six MCP servers (RTC, DNG, Jira, Artifactory, Docupedia, DIA Brain) expose enterprise systems to AI assistants.
:::

:::{grid-item-card} **CI/CD & Release**
:columns: 6
Reusable GitHub Actions workflows for parallel multi-variant dispatch, automated versioning, artifact deployment to Artifactory, documentation publishing, and PR review checklists. Release steps generate the SBOM and run the OSS scan.
:::

:::{grid-item-card} **Clang Tooling Stack**
:columns: 6
Formatting, linting, IDE language server, and a parallel clangd CMake toolchain that gives every project a clean `compile_commands.json` even when the real compiler is Green Hills / TASKING / IAR. See the [Clang Tooling Stack](guides/clang_stack.md) for the full picture (install, layered configs, compat shims, MemMap VFS overlay, per-variant defines).
:::

::::

---

## Architecture at a Glance

```{uml} _diagrams/core_engine_architecture.puml
:caption: XC-CE Utils core_engine — hexagonal/clean-architecture package layout (domain, application, adapters, cli, reporting, steps, setup, wrappers, config) and the driving-port pattern.
```

The same layering, drawn as the classic Uncle Bob concentric-circle view:

```{image} _diagrams/clean_architecture_circular.svg
:alt: core_engine clean architecture — concentric rings (domain, application, interface adapters, frameworks & drivers) with the Dependency Rule pointing inward.
:width: 640px
:align: center
```

For the full walkthrough see [Core Engine](core_engine/index.md).

---

## Who Is It For?

| Role | How They Use XC-CE Utils |
|---|---|
| **Developer** | `.\build.ps1 -var <alias> <action>` — run an action locally with the same config as CI. |
| **CI/CD Pipeline** | Variant-dispatcher workflow generates a build matrix and runs actions in parallel across all variants. |
| **Test Lab Engineer** | TRACE32/WinIDEA + COM I/O + power supply steps automate flash-debug-test cycles on physical hardware. |
| **Test Engineer** | `winidea_*` and `canoe_*` steps assemble HIL test actions — flash via WinIDEA, measure with CANoe, aggregate JUnit reports per variant. |
| **Quality Engineer** | SCA/SFA steps run Helix QAC with baseline comparison; sphinx-needs tracks requirement coverage. |
| **Release Engineer** | Version bumps, Artifactory uploads, and release validation — all through the same CLI and config. |

---

## Quick Start

```powershell
# Show available commands and variants
.\build.ps1 --help

# Build a specific variant (if the action is called build)
.\build.ps1 -var <alias> build

# Clean rebuild
.\build.ps1 -var <alias> -rb build

# Validate the configuration
.\build.ps1 config validate

# Run a custom action
.\build.ps1 -var <alias> <action>

```

---

## At a Glance

| | |
|---|---|
| **Step types** | 100+ — build, package, analyze, generate, flash, `winidea_*`, `canoe_*`, deploy, and more |
| **Build systems** | CMake, Bazel, Make — with presets, remote cache, and ccache |
| **Package management** | Conan 2.x via uvx (`uvx --from <spec> conan ...`) with lock files, approval-based uploads, and cache cleanup |
| **Variant dimensions** | N-dimensional matrix — hardware × customer × feature × ... |
| **AUTOSAR toolchains** | Vector DaVinci Configurator, EB tresos |
| **Static analysis** | Helix QAC (MISRA-C:2012, CERT C, SCA, SFA) |
| **HIL & test** | TRACE32, iSYSTEM WinIDEA SDK, Vector CANoe (COM API), serial I/O, programmable power supplies — JUnit aggregation per variant |
| **Test management** | TACO test selections (`taco_filter`, `taco_ctest`, `taco_robotfw`) with verdicts in the docs |
| **Docs as Code** | Sphinx + sphinx-needs 8, configuration generated from the PMT meta model plus project deviations |
| **Release & compliance** | SBOM generation (`sbom`), OSS scanning (`oss`), Artifactory deployment |
| **CI/CD** | 8 reusable GitHub Actions workflows + 6 composite actions |
| **MCP servers** | 6 — RTC, DNG, Jira, Artifactory, Docupedia, DIA Brain |
| **Platform** | Windows + Linux, Python 3.10+ |
| **Output formats** | HTML and PDF docs (Sphinx + LaTeX), JUnit XML reports, JSON Lines logs |

```{toctree}
:maxdepth: 2
:caption: User Guides

guides/getting_started
guides/config_guide
guides/config_files/index
guides/code_quality_config
guides/clang_stack
guides/clangd_toolchain
guides/integration
guides/setup_classes
guides/extending_steps
guides/contributing_tests
```

```{toctree}
:maxdepth: 2
:caption: Core Engine

core_engine/index
core_engine/01_introduction_and_goals
core_engine/02_architecture_constraints
core_engine/03_system_scope_and_context
core_engine/04_solution_strategy
core_engine/05_building_block_view
core_engine/06_runtime_view
core_engine/07_deployment_view
core_engine/08_crosscutting_concepts
core_engine/09_architecture_decisions
core_engine/10_quality_requirements
core_engine/11_risks_and_technical_debt
core_engine/12_glossary
core_engine/reference/step_reference
core_engine/reference/steps/index
core_engine/reference/variant_matrix
core_engine/reference/wrappers
core_engine/reference/environment_setup
core_engine/reference/environment_setup_flow
core_engine/reference/config_schema_reference
```

```{toctree}
:maxdepth: 2
:caption: Module Reference
:glob:

modules/*
```

```{toctree}
:maxdepth: 2
:caption: CI/CD Workflows

workflows/index
```

```{toctree}
:maxdepth: 2
:caption: External References

external_refs/index
```

```{toctree}
:maxdepth: 1
:caption: Reference

glossary
changelog
```
