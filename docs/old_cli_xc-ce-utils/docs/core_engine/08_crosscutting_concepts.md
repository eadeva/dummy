# 8. Crosscutting Concepts

## 8.1 The driving-port boundary

See [ch. 4](04_solution_strategy.md#42-the-driving-port-pattern-cligui-plug-and-play) for the
rationale. Mechanically:

- `core_engine/application/__init__.py` is the single curated export surface.
- `tests/unit/test_architecture_boundaries.py` enforces, via AST inspection (not just naming
  convention), that:
  - `domain/` never imports `application`, `adapters`, or `cli`.
  - `application/` never imports `cli` or `rich.console`, and never calls `sys.exit` (process
    control belongs to the driving adapter, not the application layer).
  - `cli/` never imports `adapters.*` or `application.{orchestration,facades,use_cases}.*`
    directly — only the top-level `application` package and `domain.*`.
  - The 9 legacy compatibility shim paths deleted during the migration never reappear.

Where the application layer needs a type describing "the CLI generator object" (for the
execution facade's function signatures), it defines its own local `typing.Protocol`
(`GeneratorPort` in `application/facades/execution.py`) instead of importing the concrete
`cli.generator.DynamicCLIGenerator` class — even a `TYPE_CHECKING`-guarded import would violate
the boundary (the AST-based check does not distinguish typing-only imports).

## 8.2 Error recovery strategy

Every step type registers with `StepRegistry.register(type_name, recovery=<ErrorRecoveryStrategy>)`.
`application/orchestration/step_executor.py` and `error_recovery.py` dispatch failures uniformly
regardless of step family:

| Strategy | Behavior |
|---|---|
| `ABORT` (default) | Re-raise as `ExecutionStepError`; halts the action. |
| `CONTINUE_WITH_ERRORS` | Log, mark the action as having errors, continue. |
| `RETRY_ONCE` | Re-run the step once; fall back to `ABORT` if the retry also fails. |
| `SKIP` | Swallow the exception at debug-log level. |

Legacy `AbortError` / `ContinueWithErrorsError` exceptions raised explicitly by a step (the
`game_stopper` mechanism predating the registry) always take precedence over the
registry-declared strategy.

## 8.3 Shared resource pooling

Long-lived hardware/connection objects (Trace32 sessions, CANoe applications, COM ports, SSH
clients, TFTP servers, Voltcraft power supplies, background threads) are pooled in a per-run
`resources: dict[str, dict]` initialized by `adapters/execution/resource_manager.py`. Steps
register/look up entries by a well-known key (`'lauterbachs'`, `'ssh_connections'`, `'threads'`,
...); `ExecutionAction._release_resources()` releases every group in a `finally` block, tolerating
individual release failures (logged, not raised).

## 8.4 Unified reporting

Regardless of success or failure, every action run ends with `ExecutionLogReporter` (see
[ch. 5](05_building_block_view.md#53-whitebox-reporting)):

1. Scans every `**/execution-step.json` descriptor + its paired `.jsonl` log under
   `_reports/<variant>/<action>/`.
2. Classifies each log line into an issue family (Compiler/Linker/CMake/Bazel/QAC/XC-CE
   Utils/Custom Script/...) and severity (error/warning/exception).
3. Writes a canonical `log-findings.canonical.json` artifact.
4. Runs the format-agnostic reporting pipeline (`reporting/factory.py`) to emit
   `<action>-report.canonical.json` and `<action>-report.html` (and any other configured
   `REPORTING.formats`).

Set `REPORTING.needs: true` to generate `needs.json` through DocAsCode when test reports are
present and no needs artifact was discovered. The setting defaults to `false` when omitted.

## 8.5 Logging conventions

- `logger.log_phase_header(...)` brackets major phases (`SETUP`, `EXECUTING ACTION ...`,
  `UNIFIED REPORTING`, ...) for readable console/CI output.
- `logger.file_scope()` captures a step's full stdout/stderr into a per-step log file.
- `logger.trace(...)` startup checkpoints (`cli/startup_tracing.py`) are only emitted at
  `-vv`/`TRACE` verbosity and are cumulative-from-process-start, so they stay monotonic across
  modules loaded in the same process.

## 8.6 Ruff / code-quality enforcement

`config/ruff/base.toml` is the single source of truth for style, regenerated into every consumer
repo. It is deliberately strict (preview-mode pylint-refactor rules, complexity checks, copyright
header checks). Pre-existing code that predates a given refactor pass may still carry known,
accepted findings (documented per-file, e.g. in `docs/core_engine/11_risks_and_technical_debt.md`)
— new code introduced by a refactor should be clean.
