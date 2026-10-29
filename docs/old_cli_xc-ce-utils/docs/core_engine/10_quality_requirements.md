# 10. Quality Requirements

## 10.1 Quality Tree

```text
Quality
├── Maintainability
│   ├── No single orchestration file with mixed, unbounded responsibilities
│   ├── Each collaborator independently unit-testable
│   └── Ruff-enforced style (complexity, refactor-suggestion rules)
├── Testability
│   ├── Layer boundaries enforced by automated AST-based tests, not convention
│   └── Collaborators accept plain data / callables (dependency-injection-friendly dataclasses)
├── Extensibility
│   ├── New step type: one decorator-registered class, zero orchestration changes
│   ├── New variant dimension: YAML only
│   └── New driving adapter (GUI, etc.): implement against `core_engine.application` only
├── Portability
│   ├── Windows/Linux tool-requires installation isolated per platform
│   └── Docker-context detection gates host tool installation
└── Performance (startup)
    ├── `--help`/`--version` avoid importing the step registry and reporting toolchain
    └── Lazy `import_module()` calls gate heavy optional dependencies
```

## 10.2 Quality Scenarios

| # | Scenario | Expected outcome |
|---|---|---|
| 1 | A new step type is added under `steps/` with `@StepRegistry.register(...)`. | No changes needed in `application/orchestration/*` or `cli/*`; the step becomes available immediately. |
| 2 | A future GUI driving adapter is implemented against `core_engine.application`. | Zero changes required in `domain/`, `application/` internals, or `adapters/`. |
| 3 | A step type's recovery strategy is changed from `ABORT` to `RETRY_ONCE`. | Only the `@StepRegistry.register(..., recovery=...)` declaration changes. |
| 4 | `cli/` code attempts to import `core_engine.adapters.dev_tooling.adapter` directly. | `test_cli_layer_only_uses_application_public_api_and_domain` fails the build. |
| 5 | `xc-ce-utils --help` is invoked. | Full step registry, reporting toolchain, and environment-setup phase chain are never imported; response is near-instant. |
| 6 | The PyInstaller build (`build.ps1 xc-ce-utils`) is run after any core_engine restructuring. | Build completes with `SUCCESS: 'xc-ce-utils' built successfully` and no missing-hidden-import errors for any core_engine module. |
