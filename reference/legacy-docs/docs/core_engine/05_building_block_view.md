# 5. Building Block View

## 5.1 Whitebox: `core_engine` top-level packages

| Package | Responsibility |
|---|---|
| `domain/` | Pure vocabulary: `VariantMatrix`/`Variant`, `StepRegistry`, `WrapperRegistry`, exceptions, `EnvManager`, `RuntimeContext`, comparison + layered-config helpers. No dependencies on other layers. |
| `application/` | Public API (`__init__.py`) + orchestration (`orchestration/`), execution/runtime facades (`facades/`), use-case boundaries (`use_cases/`). |
| `adapters/` | Infrastructure implementations: `execution/` (resource pool, tool install, debug upload), `deployment/` (Artifactory upload), `dev_tooling/` (VS Code/Copilot/git-hooks). |
| `cli/` | The driving adapter: dynamic CLI generation, variant dispatch, command/option construction. |
| `reporting/` | Independent clean sub-architecture: `domain/` (canonical report model), `application/` (use cases/ports), `adapters/{importers,exporters}/` (format-specific parsers/writers), plus `factory.py` and `adapters/execution_log_reporter.py` for the execution-log classification pipeline. |
| `steps/` | 100+ concrete `ExecutionStep` implementations, grouped by tool family (`*_steps.py`). See [Step Reference](reference/step_reference.md). |
| `setup/` | Environment bootstrap: `EnvironmentSetup` + phase chain (`setup/phases/*`) for Conan, Bazel, clang, git hooks, VS Code, DevMate, credentials. See [Environment Setup Flow](reference/environment_setup_flow.md). |
| `wrappers/` | Build tool wrappers (Conan, CMake, Bazel, Make, script runner, ccache). See [Wrappers](reference/wrappers.md). |
| `config/` | `ActionConfiguration` facade + Pydantic v2 config models. See [Configuration Schema Reference](reference/config_schema_reference.md). |
| `generators/` | CMake/Bazel build-definition file generation. |

## 5.2 Whitebox: `application/orchestration/` (the former `execution_engine.py`)

| Module | Responsibility |
|---|---|
| `action_orchestrator.py` | `ExecutionAction` — thin facade: lifecycle (`setup()`/`execute_action()`/`run()`), phase-window selection, clean operations, version environment variables, ccache stats. Composes the four collaborators below. |
| `step_executor.py` | `StepExecutor` — step/execution-set creation (`create_step`, `create_execution_set`) and execution dispatch (`execute()` → recovery routing). |
| `error_recovery.py` | Pure functions: `get_recovery_strategy`, `log_step_failure`, `retry_step_once`, `raise_phase_failure`. |
| `tool_requires_installer.py` | `ToolRequiresInstaller` — platform tool-requires installation (toolbase/choco on Windows, packages on Linux, artifact downloads on both). |
| `debug_artifact_uploader.py` | `DebugArtifactUploader` — CI debug-artifact (`_log`/`_reports`) upload on action failure. |

Unified end-of-action reporting (log-finding classification, report-pipeline invocation — formerly
~1500 lines inside `execution_engine.py`) now lives in
[`reporting/adapters/execution_log_reporter.py`](#53-whitebox-reporting) as `ExecutionLogReporter`;
`action_orchestrator.py` keeps only a thin try/except/log-phase-header wrapper around it.

## 5.3 Whitebox: `reporting/`

| Module | Responsibility |
|---|---|
| `domain/models.py`, `domain/classification.py` | Canonical report data model and finding classification. |
| `application/use_cases.py`, `application/ports.py` | Reporting pipeline orchestration and port definitions. |
| `adapters/importers/*` | Format-specific parsers (JUnit XML, gcovr, QAC CSV, SonarQube, needs analysis, CycloneDX, ...). |
| `adapters/exporters/*` | JSON, JUnit, HTML exporters (with per-section HTML generators). |
| `adapters/execution_log_reporter.py` | `ExecutionLogReporter` — parses per-step JSONL logs, classifies findings (compiler/linker/CMake/Bazel/QAC/...), and drives the reporting pipeline at the end of every action run. |
| `factory.py` | `build_default_reporting_pipeline()` — assembles the default importer/exporter pipeline. |

## 5.4 Whitebox: `adapters/execution/` (the former `infra.py`)

| Module | Responsibility |
|---|---|
| `resource_manager.py` | Shared resource pool init/release (threads, Trace32, SSH, COM, Voltcraft, TFTP, WinIDEA, CANoe). |
| `tool_installer_adapter.py` | `ToolRequiresInstallationAdapter` dependency boundary + `tool_requires` type filtering, consumed by `application/orchestration/tool_requires_installer.py`. |
| `debug_upload_adapter.py` | Debug-upload plan assembly + deploy-Artifactory-alias resolution, consumed by `application/orchestration/debug_artifact_uploader.py`. |

## 5.5 Whitebox: `cli/` (the former `dynamic_cli.py`)

| Module | Responsibility |
|---|---|
| `generator.py` | `DynamicCLIGenerator` — loads runtime config (via `core_engine.application.load_runtime_config`), builds the `VariantMatrix`, wires action commands. |
| `entrypoint.py` | `create_dynamic_cli()`, standalone `main()` (`python -m xc_ce_utils.core_engine.cli.entrypoint`). |
| `platform_setup.py` | Windows console UTF-8 fix, PyInstaller PATH setup, rich-click defaults, cross-platform env vars, dev-tooling provider override (resolved through `core_engine.application`). |
| `environment_setup_orchestrator.py` | One-time Conan/toolchain environment bootstrap before CLI construction. |
| `startup_tracing.py` | Process-scoped startup timing checkpoints (`--verbose -vv` trace output). |
| `command_factory.py` | Builds each per-action `click.Command`, including context-sensitive options. |
| `variant_executor.py` | Variant resolution + multi-variant parallel subprocess dispatch (`build_python_command`, `execute_action_with_arguments`). |
| `root_group.py` | Top-level `click.Group`, global flags, version banner. |
| `action_introspection.py` | Help-text rendering, phase enumeration, variant-constraint validation. |
| `option_parser.py` | Pure-function parsing of repeatable `-bo`/`-mp`/`-art` flags. |
| `execution_tracker.py` | Per-run warnings/errors/timing summary. |
| `role_gating.py` | `requires_role: maintainer` action visibility gating. |
| `vs_code_setup.py`, `vscode_commands.py` | `config vs-code` / `config-devops vs-code` commands (via `core_engine.application` dev-tooling re-exports). |

## 5.6 Exception Hierarchy (`domain/exceptions.py`)

```text
ExecutionError                    (aliased as BuildError)
├── ConfigurationError
│   └── RuntimeConfigError
├── DependencyError
├── ExecutionStepError
├── SetupError
├── AbortError               ← game_stopper step failures (always ABORT)
├── ContinueWithErrorsError  ← non-critical step failures (never aborts)
├── BlockingTestError
└── NonBlockingTestError
```
