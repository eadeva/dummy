# 4. Solution Strategy

## 4.1 Layered (hexagonal) architecture

`core_engine` is organized into four layers with a strict, test-enforced dependency direction:

```text
   cli/  (driving adapter)              ─┐
                                          │  may only import
                                          ▼
   application/  (public API + use cases) ── depends on ──▶  domain/  (pure vocabulary)
        │                                                         ▲
        │  depends on (ports/adapters)                            │  no upward deps
        ▼                                                          │
   adapters/  (infrastructure: execution, deployment, dev_tooling) ┘
```

- **`domain/`** — pure data/vocabulary: `VariantMatrix`/`Variant`, exceptions, `StepRegistry`,
  `WrapperRegistry`, `EnvManager`, `RuntimeContext`, comparison/layered-config helpers. Zero
  dependencies on any other core_engine layer.
- **`application/`** — the orchestration brain (`application/orchestration/*`), execution facades
  (`application/facades/*`), and use-case boundaries (`application/use_cases/*`). Its package
  `__init__.py` is the **one public API** driving adapters may import from.
- **`adapters/`** — infrastructure implementations: `adapters/execution/*` (resource pooling, tool
  install, debug upload), `adapters/deployment/*` (Artifactory upload), `adapters/dev_tooling/*`
  (VS Code/Copilot/git-hooks configuration).
- **`cli/`** — the (currently sole) driving adapter: a rich-click CLI generator that translates
  YAML-defined actions into commands and calls `core_engine.application` to execute them.

## 4.2 The driving-port pattern (CLI/GUI plug-and-play)

`core_engine/application/__init__.py` is a curated, explicit re-export surface (`ExecutionAction`,
`BuildType`, `execute_action`, `load_runtime_config`, dev-tooling configuration functions, ...).
`cli/` is only allowed to import from this module and from `core_engine.domain` — never from
`adapters` or from `application.{orchestration,facades,use_cases}` submodules directly. This rule
is mechanically enforced by
`tests/unit/test_architecture_boundaries.py::test_cli_layer_only_uses_application_public_api_and_domain`.

Consequence: a future `core_engine/gui/` package (or a second CLI) can be built against the exact
same `core_engine.application` surface, with **zero changes** required below that boundary. Where
the CLI previously reached directly into an adapter (e.g. dev-tooling provider configuration), the
symbol was re-exported through `application/__init__.py` instead of leaving the shortcut in place.

## 4.3 Configuration-driven extensibility

- **Step registry**: concrete step classes self-register via `@StepRegistry.register(type_name,
  recovery=...)`; `application/orchestration/step_executor.py` looks them up purely by the
  `type`/`step_type` string from YAML. Adding a step type never touches orchestration code.
- **Variant matrix**: an N-dimensional tree (`domain/variant_matrix.py`) resolved once at CLI
  startup; every phase/step config is merged against the active variant's settings.
- **Actions/phases**: declared in `config/actions/actions_conf.yml`; `cli/generator.py` builds one
  `click.Command` per action, with context-sensitive options derived by introspecting the
  action's step types (`cli/action_introspection.py`).

## 4.4 Decomposition of large orchestration logic

The former `execution_engine.py` (~2950 lines, one god-class) and `adapters/execution/infra.py`
(~800 lines) were split into small, single-responsibility collaborators (see
[ch. 5](05_building_block_view.md) and [ADR-3/ADR-4](09_architecture_decisions.md)), each
independently unit-testable. The same applied to the former `dynamic_cli.py` (~950 lines, folded
into `cli/`, see [ADR-5](09_architecture_decisions.md)).

## 4.5 Resilience strategy

Each step type declares an `ErrorRecoveryStrategy` (`ABORT` / `CONTINUE_WITH_ERRORS` / `RETRY_ONCE`
/ `SKIP`) at registration time. `application/orchestration/step_executor.py` and
`error_recovery.py` dispatch failures accordingly, preserving legacy `AbortError` /
`ContinueWithErrorsError` semantics for steps that raise them explicitly regardless of the
registry-declared strategy.
