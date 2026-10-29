# Glossary

```{glossary}

action
   A named, top-level CLI verb (e.g. `build`, `doc`, `sca`, `test`). Each action is a YAML-declared sequence of {term}`phases <phase>` and {term}`steps <step>` that run per {term}`variant`.

alias
   Short identifier for a {term}`variant` (e.g. `pl7`, `pl9eol`). Used on the CLI as `-var <alias>`.

artifact
   Any file produced by a build, code generation, analysis, or test step. Conventionally lives under `_bin/`, `_build/`, `_reports/`, or `_log/`.

ccache
   Compiler cache used to skip re-compilation of unchanged translation units. Configured per {term}`wrapper`.

conan
   Conan 2.x package manager. XC-CE Utils invokes Conan through uvx (default command shape: `uvx --from conan==2.12.0 conan ...`) with lock files for reproducibility and approval-based uploads.

generator
   The runtime object that executes an {term}`action` for a single {term}`variant`. Holds the resolved variant context, paths, and step registry.

JUnit
   XML test-report format. HIL test actions aggregate results to `_reports/<variant>/<action>/junit.xml`.

MCP server
   Model Context Protocol server. XC-CE Utils ships 6 built-in servers (rtc, dng, jira, artifactory, docupedia, diabrain) configurable via `config-devops vs-code regen-mcp-json`.

meta model
   The PMT docs-as-code meta model (`meta_model_spec.yaml`): need classes with their attributes, allowed values, relations, cardinalities and lifecycle. The sphinx-needs configuration is generated from it on every docs build.

meta model deviation
   A project-specific change to the {term}`meta model`, recorded with ID and rationale in `meta_model_deviations.yaml` instead of editing the spec. Deviated objects are tagged `deviation` in the documentation.

phase
   A named group of {term}`steps <step>` within an {term}`action`. Phases run sequentially; steps within a phase run in declared order.

step
   The atomic unit of execution. Subclass of `ExecutionStep`. Examples: `cmake_build`, `conan_command`, `winidea_flash_pflash`, `canoe_start_measurement`. See the {term}`step registry`.

step registry
   The runtime catalog of all available step types. Built dynamically from `xc_ce_utils.core_engine.steps.*`. Run `StepRegistry.available_types()` for a live list.

TACO
   Test case selection and execution tool of the PMT docs-as-code ecosystem. Selects test cases from `needs.json` with test selections (`*.tl.yaml`), runs them through a project adapter and writes result JSONs whose verdicts are shown in the documentation. See the [TACO steps](core_engine/reference/steps/taco.md).

trace id
   Short string injected into log records via `trace_context()`. Used to correlate output across nested actions and threads.

variant
   One point in the N-dimensional {term}`variant matrix` — a unique combination of hardware × customer × feature × ... Identified by its {term}`alias`.

variant matrix
   The Cartesian product of all configured dimensions (hardware, customer, feature, ...). Each cell is a {term}`variant`.

wrapper
   A build-system adapter (CMake, Bazel, Make, Conan). Wrappers translate the YAML config into invocations of the underlying tool (Conan calls are routed through uvx).
```
