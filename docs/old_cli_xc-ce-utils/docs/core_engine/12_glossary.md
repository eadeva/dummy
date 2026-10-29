# 12. Glossary

| Term | Definition |
|---|---|
| **Action** | A named, YAML-configured unit of work (e.g. `build`, `unit-tests`, `doc`) composed of phases and/or sets, executed via `ExecutionAction`. |
| **Variant** | One point in the N-dimensional build matrix (e.g. a specific hardware × customer × feature combination), resolved via `VariantMatrix`. |
| **Phase** | A named step (or set) within an action's `PHASES` mapping, executed in declaration order within an optional `from_phase`/`to_phase` window. |
| **Set** | A group of steps (`SETS` in YAML) supporting sequential or parallel execution and nesting, implemented by `ExecutionSet`. |
| **Step** | A leaf unit of work (`ExecutionStep` subclass) registered under a `type`/`step_type` string via `StepRegistry`. |
| **Step Registry** | `domain/step_registry.py::StepRegistry` — decorator-based registration/lookup of step classes and their declared `ErrorRecoveryStrategy`. |
| **Wrapper** | A build-tool abstraction (Conan/CMake/Bazel/Make/script runner) providing standardized invocation, logging, and error handling; registered via `WrapperRegistry`. |
| **Game-stopper** | Legacy terminology for a step whose failure halts the entire action (`AbortError`); the opposite is a non-game-stopper step, which raises `ContinueWithErrorsError`. |
| **Driving adapter** | A component that *calls into* the application layer to trigger use cases (the CLI today; potentially a GUI in the future). Contrasted with a "driven" adapter (called *by* the application layer, e.g. Artifactory upload). |
| **Driving port** | The stable interface (`core_engine.application`'s public API) that all driving adapters must depend on exclusively. |
| **ExecutionAction** | The thin orchestrator facade (`application/orchestration/action_orchestrator.py`) managing an action's lifecycle for one variant. |
| **Resource pool** | The per-run `resources: dict` holding long-lived hardware/connection handles, released in bulk at the end of a run. |
| **Unified reporting** | The end-of-action pipeline that classifies per-step log findings and emits canonical JSON/HTML/JUnit reports, run unconditionally (success or failure). |
| **Compatibility shim** | A now-fully-removed pattern: a thin module re-exporting symbols under a legacy import path. None remain in `core_engine` as of the 2026-07 migration. |
