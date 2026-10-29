# 1. Introduction and Goals

## 1.1 Purpose

`xc_ce_utils.core_engine` is a **configuration-driven, multi-variant execution orchestrator**.
It turns declarative YAML configuration (`config/actions/actions_conf.yml`,
`config/project/project_conf.yml`, `config/main_conf.yml`) into:

- A dynamically generated CLI (one command per configured *action*, context-sensitive options).
- A phase/step execution pipeline per *variant* (a point in an N-dimensional build matrix —
  hardware × customer × feature × ...).
- Unified build reporting (log-finding classification, JUnit/HTML/JSON reports).
- Repeatable environment bootstrap (Conan, Bazel, git hooks, VS Code/Copilot tooling, credentials).

No code changes are required to add a new build action or step type — everything is wired
through configuration and a step registry.

```{note}
`config/` above is the common **default** location, not a hardcoded requirement — the actual
config root is configurable per project. See [main_conf.yml's Discovery
Order](../guides/config_files/main_conf.md#discovery-order) for the resolution algorithm.
```

## 1.2 Requirements Overview

| Requirement | Description |
|---|---|
| Configuration-driven | Actions, phases, steps, and variants are defined entirely in YAML. |
| Multi-variant | A single invocation can target one, several, or all configured variants, in parallel. |
| Extensible step catalog | 100+ step types (CMake/Bazel/Make/Conan builds, static analysis, HIL hardware, deployment, ...); new types register via a decorator, no core changes needed. |
| Resilient execution | Per-step recovery strategies (abort / continue / retry-once / skip) declared at registration time. |
| Reusable core, replaceable front-end | The execution engine must be usable by more than one driving adapter (today: a CLI; potentially: a GUI or other automation surface) without changes to the engine itself. |
| Distributable | Ships as a PyInstaller-frozen executable; must start fast for `--help`/`--version` and work without a pre-installed Python environment on target machines. |

## 1.3 Quality Goals (top 5, see also [ch. 10](10_quality_requirements.md))

1. **Maintainability** — no single file should carry more than one clearly-scoped responsibility;
   large orchestration logic is decomposed into small, independently testable collaborators.
2. **Testability** — architecture boundaries (domain/application/adapters/cli) are enforced by
   automated tests (`tests/unit/test_architecture_boundaries.py`), not just convention.
3. **Extensibility** — adding a build action, step type, or variant dimension never requires
   touching orchestration code.
4. **Portability** — the engine runs on Windows and Linux; platform differences are isolated to
   dedicated adapters (e.g. `application/orchestration/tool_requires_installer.py`).
5. **Startup performance** — `--help`/`--version` invocations must avoid importing the full step
   registry or heavy optional dependencies.

## 1.4 Stakeholders

| Role | Concern |
|---|---|
| Embedded project maintainers (XC-CE consumer repos) | Configure builds/actions via YAML; consume the CLI; rarely touch core_engine source. |
| XC-CE Utils maintainers | Own core_engine; add step types, fix orchestration bugs, keep the CLI fast and reliable. |
| CI pipelines | Invoke the frozen executable non-interactively; depend on stable exit codes and unified reports. |
| Future driving-adapter authors | May build a GUI or other automation surface against the `core_engine.application` public API. |
