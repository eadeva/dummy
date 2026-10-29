# 9. Architecture Decisions

Lightweight ADR log for the 2026-07 clean-architecture migration of `core_engine`.

## ADR-1: Layered clean/hexagonal architecture (domain → application → adapters, cli as driving adapter)

**Status:** Accepted.

**Context:** `core_engine` had already partially migrated toward `domain/`, `application/`,
`adapters/`, `reporting/` packages, but three monolithic legacy files remained
(`execution_engine.py` ~2950 lines, `dynamic_cli.py` ~950 lines, `adapters/execution/infra.py`
~800 lines), plus 8 root-level "compatibility shim" files re-exporting `domain/*` symbols under
their old flat paths, and 3 further one-purpose indirection shims.

**Decision:** Complete the migration: split every remaining monolith into single-responsibility
collaborators, remove every legacy shim (no dual import paths for any symbol), and make `cli/`
a pure driving adapter.

**Consequences:** Every symbol has exactly one canonical import path. Toyota Sphinx `conf.py`
(external consumer) and ~20 internal test files required import-path updates as part of the same
change.

## ADR-2: Driving-port boundary for CLI/GUI plug-and-play

**Status:** Accepted.

**Context:** The user requirement was to separate core execution from the CLI enough that
additional driving adapters (e.g. a future GUI) could be added without touching the execution
engine.

**Decision:** `core_engine/application/__init__.py` becomes the one sanctioned import surface for
driving adapters. `cli/` may only import from it and from `core_engine.domain`. Enforced by an
AST-based test rule.

**Consequences:** Two gaps were found and closed during implementation: `cli/vscode_commands.py`
and the dev-tooling-provider-override logic reached into `adapters.dev_tooling.adapter` directly
(fixed by re-exporting those factory functions through `application/__init__.py`), and
`application/facades/execution.py` had a type-only dependency on the concrete
`cli.generator.DynamicCLIGenerator` class (fixed with a locally-defined `GeneratorPort` Protocol).

## ADR-3: Split `execution_engine.py` into `application/orchestration/*` + move reporting into `reporting/`

**Status:** Accepted.

**Context:** `ExecutionAction` was a ~2950-line god-class covering lifecycle orchestration, step
creation/execution/retry, tool-requires installation, debug-artifact upload, and ~1500 lines of
log-parsing/classification/reporting-pipeline logic.

**Decision:** Split into `action_orchestrator.py` (thin facade), `step_executor.py`,
`error_recovery.py`, `tool_requires_installer.py`, `debug_artifact_uploader.py`; move the
reporting-pipeline logic into `reporting/adapters/execution_log_reporter.py` since the `reporting/`
subsystem already had its own clean domain/application/adapters layering suited to it.

**Consequences:** Two pre-existing latent bugs were discovered during extraction and deliberately
**preserved** (not silently fixed) to keep the split behavior-identical — see
[ch. 11](11_risks_and_technical_debt.md). Genuinely dead/unreachable code (a broken, never-called
tool-download helper and an unused dataclass) was dropped rather than moved.

## ADR-4: Split `adapters/execution/infra.py` into three focused adapters

**Status:** Accepted.

**Decision:** `resource_manager.py` (resource pool init/release), `tool_installer_adapter.py`
(tool-requires installation dependency boundary + filtering), `debug_upload_adapter.py`
(debug-upload plan assembly + deploy-alias resolution).

## ADR-5: Fold `dynamic_cli.py` into `cli/`

**Status:** Accepted.

**Decision:** Split into `cli/generator.py` (the `DynamicCLIGenerator` class),
`cli/entrypoint.py` (`create_dynamic_cli`/`main`), `cli/platform_setup.py` (console/PATH/env
fixes, rich-click config, dev-tooling provider override), `cli/environment_setup_orchestrator.py`
(Conan/toolchain bootstrap), `cli/startup_tracing.py` (timing checkpoints); `build_python_command`
moved into the existing `cli/variant_executor.py`.

## ADR-6: Remove all legacy compatibility shims; move `deployer.py` and `Deployer`

**Status:** Accepted.

**Decision:** Deleted the 8 root-level `domain/*` re-export shims, the unused
`application/runtime_facade.py`, `application/execution_facade.py`,
`application/execution_use_cases.py`, `adapters/dev_tooling_adapter.py`,
`adapters/dev_tooling_ports.py`, and `adapters/execution_infra_adapter.py` indirection shims.
Moved `core_engine/deployer.py` → `adapters/deployment/artifactory_deployer.py` (a `git mv`,
content unchanged). Removed the silent `try/except ImportError: pass` around the package-level
`Deployer` re-export in `core_engine/__init__.py` (no consumer used the shortcut).

**Consequences:** A regression guard
(`test_legacy_compatibility_wrappers_are_removed`) asserts these paths never reappear.
